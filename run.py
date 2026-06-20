from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.audit_report import HoneypotAuditWriter, audit_existing_fingerprints
from src.baseline_ranker import RankingResult, rank_fingerprints
from src.candidate_loader import CandidateLoader
from src.candidate_profiler import CandidateProfiler, CandidateProfilerConfig
from src.feature_store import IncrementalFeatureStore
from src.honeypot_firewall import HoneypotFirewall
from src.jd_parser import parse_jd_file
from src.ranking_output import write_ranking_outputs
from src.schema_inspector import inspect_schema
from src.submission_validator import validate_ranked_candidates
from src.utils import Timer, log


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip().strip("\"'")
    lowered = cleaned.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        try:
            return float(cleaned)
        except ValueError:
            return cleaned


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            indentation = len(raw_line) - len(raw_line.lstrip(" "))
            stripped = raw_line.strip()
            if ":" not in stripped:
                continue
            key, raw_value = stripped.split(":", 1)
            while stack[-1][0] >= indentation:
                stack.pop()
            parent = stack[-1][1]
            if raw_value.strip():
                parent[key.strip()] = _parse_scalar(raw_value)
            else:
                nested: dict[str, Any] = {}
                parent[key.strip()] = nested
                stack.append((indentation, nested))
    return root


def load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        return _load_simple_yaml(path)


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile and rank candidates with the offline EvidenceRank pipeline."
    )
    parser.add_argument("--input", dest="input_path", help="CSV, JSON, JSONL, or Parquet input.")
    parser.add_argument("--jd", dest="jd_path", help="Plain-text job description path.")
    parser.add_argument("--limit", type=int, default=None, help="Profile at most N valid records.")
    parser.add_argument("--batch-size", type=int, default=None, help="Bounded Parquet batch size.")
    parser.add_argument("--top-k", type=int, default=None, help="Number of candidates to rank.")
    parser.add_argument(
        "--enable-honeypot-firewall",
        action="store_true",
        help="Enable deterministic honeypot risk detection and risk-aware reranking.",
    )
    parser.add_argument(
        "--strict-top-n",
        type=int,
        default=None,
        help="Number of leading ranks protected by stricter risk rules.",
    )
    parser.add_argument(
        "--risk-rerank-pool-size",
        type=int,
        default=None,
        help="Bounded shortlist size for deep honeypot analysis.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml.")
    parser.add_argument("--output-dir", default=None, help="Override configured output directory.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--profile-only", action="store_true", help="Build fingerprints only.")
    modes.add_argument("--rank", action="store_true", help="Rank existing fingerprints.")
    modes.add_argument(
        "--profile-and-rank",
        action="store_true",
        help="Build fingerprints, then rank them.",
    )
    modes.add_argument(
        "--audit-honeypots",
        action="store_true",
        help="Audit existing fingerprints without producing a new ranking.",
    )
    return parser


def run_profiling(
    input_path: Path,
    output_dir: Path,
    config: dict[str, Any],
    limit: int | None,
    batch_size: int,
) -> dict[str, Any]:
    progress_every = int(config.get("progress_every", 10000))
    max_text_length = int(config.get("max_text_length_per_candidate", 12000))
    run_config = {
        **config,
        "batch_size": batch_size,
        "input_path": str(input_path),
        "output_dir": str(output_dir),
    }

    log(f"Inspecting schema for {input_path}")
    schema_report = inspect_schema(input_path)
    loader = CandidateLoader(
        input_path,
        batch_size=batch_size,
        progress_every=progress_every,
        limit=limit,
    )
    profiler = CandidateProfiler(
        CandidateProfilerConfig(max_text_length_per_candidate=max_text_length),
        schema_report=schema_report,
    )

    with IncrementalFeatureStore(output_dir) as store:
        store.save_schema_report(schema_report)
        for row_number, candidate in enumerate(loader, start=1):
            try:
                fingerprint = profiler.profile(candidate, row_number)
                store.write_fingerprint(fingerprint)
            except Exception as exc:
                store.record_profiler_error()
                log(f"Skipping candidate row {row_number} after profiler error: {exc}", "ERROR")
        return store.finalize(loader.stats.errors, schema_report, run_config)


def print_profile_summary(summary: dict[str, Any]) -> None:
    print("\nEvidenceRank profiler complete")
    print("-" * 32)
    print(f"Candidates processed: {summary['total_candidates_processed']:,}")
    print(f"Total errors: {summary['total_errors']:,}")
    print(f"Detected schema fields: {', '.join(summary['detected_schema_fields'])}")
    print(
        "Average profile completeness: "
        f"{summary['average_profile_completeness_score']:.4f}"
    )
    print(
        "Average skill evidence hint: "
        f"{summary['average_skill_evidence_hint_score']:.4f}"
    )
    print(f"Approximate runtime: {summary['runtime_seconds']:.2f} seconds")
    print(f"Memory-safe mode enabled: {summary['memory_safe_mode']}")
    print(f"Fingerprints: {summary['output_files']['candidate_fingerprints']}")


def run_ranking(
    fingerprints_path: Path,
    jd_path: Path,
    output_dir: Path,
    config: dict[str, Any],
    top_k_override: int | None,
    enable_honeypot_firewall: bool = False,
    strict_top_n_override: int | None = None,
    risk_pool_override: int | None = None,
) -> tuple[
    RankingResult,
    dict[str, Path],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
]:
    ranking_config = config.get("ranking", {})
    top_k = int(top_k_override or ranking_config.get("top_k", 100))
    strict_pool = int(ranking_config.get("strict_rerank_pool_size", 300))
    max_snippets = int(ranking_config.get("max_evidence_snippets", 5))
    firewall_config = config.get("honeypot_firewall", {})
    strict_top_n = int(
        strict_top_n_override or firewall_config.get("strict_top_n", 10)
    )
    risk_pool = int(
        risk_pool_override or firewall_config.get("risk_rerank_pool_size", 500)
    )
    firewall = HoneypotFirewall.from_dict(firewall_config)
    jd_profile = parse_jd_file(jd_path)
    audit_summary: dict[str, Any] | None = None
    audit_paths: dict[str, Path] = {}
    if enable_honeypot_firewall:
        with HoneypotAuditWriter(output_dir) as audit_writer:
            result = rank_fingerprints(
                fingerprints_path,
                jd_profile,
                top_k=top_k,
                strict_rerank_pool_size=strict_pool,
                max_evidence_snippets=max_snippets,
                score_weights=ranking_config.get("score_weights"),
                penalties=ranking_config.get("penalties"),
                progress_every=int(config.get("progress_every", 10000)),
                enable_honeypot_firewall=True,
                firewall=firewall,
                audit_writer=audit_writer,
                strict_top_n=strict_top_n,
                risk_rerank_pool_size=risk_pool,
            )
            audit_summary = audit_writer.finalize(result.ranked_candidates)
            audit_paths = audit_writer.output_paths
    else:
        result = rank_fingerprints(
            fingerprints_path,
            jd_profile,
            top_k=top_k,
            strict_rerank_pool_size=strict_pool,
            max_evidence_snippets=max_snippets,
            score_weights=ranking_config.get("score_weights"),
            penalties=ranking_config.get("penalties"),
            progress_every=int(config.get("progress_every", 10000)),
        )
    output_paths = write_ranking_outputs(result.ranked_candidates, output_dir)
    output_paths.update(audit_paths)
    validation = validate_ranked_candidates(
        output_paths["ranked_candidates"],
        expected_rows=min(top_k, result.total_candidates_scored),
        score_breakdown_path=output_paths["score_breakdown"],
        firewall_enabled=enable_honeypot_firewall,
    )
    return result, output_paths, validation, jd_profile, audit_summary


def print_ranking_summary(
    result: RankingResult,
    output_paths: dict[str, Path],
    validation: dict[str, Any],
    jd_profile: dict[str, Any],
    top_k: int,
    memory_safe_mode: bool,
    total_runtime: float,
    audit_summary: dict[str, Any] | None = None,
) -> None:
    parsed_skills = jd_profile["required_skills"] + jd_profile["preferred_skills"]
    print("\nEvidenceRank ranking complete")
    print("-" * 32)
    print(f"JD parsed skills: {', '.join(parsed_skills) or '(none detected)'}")
    print(f"Total candidates scored: {result.total_candidates_scored:,}")
    print(f"Top K requested: {top_k}")
    print(f"Output CSV: {output_paths['ranked_candidates'].resolve()}")
    print(f"Score breakdown: {output_paths['score_breakdown'].resolve()}")
    print(f"Proof output: {output_paths['top_candidate_proofs'].resolve()}")
    if audit_summary is not None:
        print(f"Total candidates flagged: {audit_summary['total_candidates_flagged']:,}")
        print(f"High risk count: {audit_summary['high_risk_count']:,}")
        print(f"Severe risk count: {audit_summary['severe_risk_count']:,}")
        print(f"Disqualified count: {audit_summary['disqualified_count']:,}")
        print(
            "Top 10 average risk: "
            f"{audit_summary['top_10_risk_summary']['average_risk_score']:.4f}"
        )
        print(f"Honeypot audit: {output_paths['honeypot_audit'].resolve()}")
        print(f"Honeypot flags: {output_paths['honeypot_flags'].resolve()}")
        print(f"Rerank audit: {output_paths['rerank_audit_top100'].resolve()}")
    print(f"Validation result: {'PASS' if validation['valid'] else 'FAIL'}")
    if validation["errors"]:
        for error in validation["errors"]:
            print(f"  - {error}")
    print(f"Runtime: {total_runtime:.2f} seconds")
    print(f"Memory-safe mode: {memory_safe_mode}")
    if result.peak_memory_mb is not None:
        print(f"Peak observed RSS during ranking: {result.peak_memory_mb:.2f} MB")


def main(argv: list[str] | None = None) -> int:
    timer = Timer()
    args = build_parser().parse_args(argv)
    config_path = resolve_project_path(args.config)
    config = load_config(config_path)
    output_dir = resolve_project_path(args.output_dir or config["output_dir"])
    batch_size = int(args.batch_size or config.get("batch_size", 1000))
    ranking_config = config.get("ranking", {})
    top_k = int(args.top_k or ranking_config.get("top_k", 100))
    firewall_config = config.get("honeypot_firewall", {})
    firewall_enabled = bool(
        args.enable_honeypot_firewall or firewall_config.get("enabled", False)
    )

    profile_requested = (
        args.profile_only
        or args.profile_and_rank
        or (not args.rank and not args.audit_honeypots)
    )
    rank_requested = args.rank or args.profile_and_rank

    if profile_requested:
        input_path = resolve_project_path(args.input_path or config["input_path"])
        profile_summary = run_profiling(
            input_path,
            output_dir,
            config,
            args.limit,
            batch_size,
        )
        print_profile_summary(profile_summary)

    if rank_requested:
        if not args.jd_path:
            print("Ranking requires --jd PATH_TO_JOB_DESCRIPTION.txt", file=sys.stderr)
            return 2
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if not fingerprints_path.exists():
            print(
                "Candidate fingerprints are missing. Run --profile-only first or use "
                "--profile-and-rank.",
                file=sys.stderr,
            )
            return 2
        result, output_paths, validation, jd_profile, audit_summary = run_ranking(
            fingerprints_path,
            resolve_project_path(args.jd_path),
            output_dir,
            config,
            args.top_k,
            enable_honeypot_firewall=firewall_enabled,
            strict_top_n_override=args.strict_top_n,
            risk_pool_override=args.risk_rerank_pool_size,
        )
        print_ranking_summary(
            result,
            output_paths,
            validation,
            jd_profile,
            top_k,
            bool(config.get("memory_safe_mode", True)),
            timer.elapsed_seconds,
            audit_summary,
        )
        return 0 if validation["valid"] else 1

    if args.audit_honeypots:
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if not fingerprints_path.exists():
            print(
                "Candidate fingerprints are missing. Run --profile-only first.",
                file=sys.stderr,
            )
            return 2
        jd_profile = (
            parse_jd_file(resolve_project_path(args.jd_path)) if args.jd_path else None
        )
        summary, paths = audit_existing_fingerprints(
            fingerprints_path,
            output_dir,
            HoneypotFirewall.from_dict(firewall_config),
            jd_profile=jd_profile,
            progress_every=int(config.get("progress_every", 10000)),
            max_evidence_snippets=int(
                ranking_config.get("max_evidence_snippets", 5)
            ),
        )
        print("\nEvidenceRank honeypot audit complete")
        print("-" * 38)
        print(f"Candidates audited: {summary['total_candidates_scored']:,}")
        print(f"Candidates flagged: {summary['total_candidates_flagged']:,}")
        print(f"High risk: {summary['high_risk_count']:,}")
        print(f"Severe risk: {summary['severe_risk_count']:,}")
        print(f"Disqualified: {summary['disqualified_count']:,}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        print(f"Runtime: {timer.elapsed_seconds:.2f} seconds")
        print(f"Memory-safe mode: {bool(config.get('memory_safe_mode', True))}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
