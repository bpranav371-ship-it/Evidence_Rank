from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.ablation_evaluator import run_ablation
from src.artifact_hasher import build_artifact_hashes
from src.benchmark_cases import run_offline_benchmarks
from src.audit_report import (
    HoneypotAuditWriter,
    audit_existing_fingerprints,
    write_calibration_reports,
)
from src.baseline_ranker import RankingResult, rank_fingerprints
from src.candidate_loader import CandidateLoader
from src.candidate_profiler import CandidateProfiler, CandidateProfilerConfig
from src.deck_materials import build_deck_materials
from src.deck_exporter import export_deck
from src.demo_exporter import build_demo_pack, judge_demo_check
from src.explanation_cards import build_explanation_cards
from src.feature_store import IncrementalFeatureStore
from src.final_submission_freeze import (
    build_final_submission_bundle,
    build_freeze_report,
)
from src.honeypot_firewall import HoneypotFirewall
from src.jd_parser import parse_jd_file
from src.ranking_output import write_ranking_outputs
from src.reproducibility import build_reproducibility_manifest
from src.runtime_profiler import profile_ranking_runtime
from src.schema_inspector import inspect_schema
from src.submission_packager import build_submission_package
from src.submission_validator import validate_ranked_candidates
from src.submission_safety import validate_final_submission
from src.utils import Timer, log
from src.weight_sensitivity import run_weight_sensitivity


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


def expected_ranked_rows(output_dir: Path, top_k: int) -> int:
    summary_path = output_dir / "profiler_summary.json"
    if not summary_path.exists():
        return top_k
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return min(top_k, max(0, int(summary.get("total_candidates_processed", top_k))))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return top_k


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
        "--top-n",
        type=int,
        default=None,
        help="Number of leading candidates to include in explanation cards.",
    )
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
    parser.add_argument(
        "--enable-evidence-calibration",
        action="store_true",
        help="Enable bounded evidence, career, constraint, and hireability calibration.",
    )
    parser.add_argument(
        "--calibration-pool-size",
        type=int,
        default=None,
        help="Bounded shortlist size for deep evidence calibration.",
    )
    parser.add_argument(
        "--format",
        dest="export_format",
        choices=("pptx", "pdf", "all"),
        default="pptx",
        help="Deck export format. Used with --export-deck.",
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
    modes.add_argument(
        "--run-ablation",
        action="store_true",
        help="Compare keyword, baseline, firewall, and calibrated ranking variants.",
    )
    modes.add_argument(
        "--validate-final-submission",
        action="store_true",
        help="Run final output and ranking safety checks.",
    )
    modes.add_argument(
        "--run-benchmark",
        action="store_true",
        help="Run deterministic synthetic ranking sanity benchmarks.",
    )
    modes.add_argument(
        "--run-weight-sensitivity",
        action="store_true",
        help="Compare controlled in-memory scoring weight variants.",
    )
    modes.add_argument(
        "--profile-runtime",
        action="store_true",
        help="Profile ranking runtime and memory from existing fingerprints.",
    )
    modes.add_argument(
        "--build-reproducibility-manifest",
        action="store_true",
        help="Write deterministic environment, config, and Git metadata.",
    )
    modes.add_argument(
        "--build-submission-package",
        action="store_true",
        help="Build the clean final submission ZIP and manifests.",
    )
    modes.add_argument(
        "--final-submit-check",
        action="store_true",
        help="Run validation, safety, reproducibility, runtime, and packaging checks.",
    )
    modes.add_argument(
        "--build-demo-pack",
        action="store_true",
        help="Generate judge-facing docs, explanation cards, and the demo ZIP.",
    )
    modes.add_argument(
        "--build-deck-materials",
        action="store_true",
        help="Generate deck Markdown, demo docs, and Mermaid diagrams.",
    )
    modes.add_argument(
        "--explain-top-candidates",
        action="store_true",
        help="Generate evidence-grounded explanation cards for top candidates.",
    )
    modes.add_argument(
        "--judge-demo-check",
        action="store_true",
        help="Validate judge-facing documentation and demo artifacts.",
    )
    modes.add_argument(
        "--build-all-submission-artifacts",
        action="store_true",
        help="Build safety, reproducibility, submission, deck, and demo artifacts.",
    )
    modes.add_argument(
        "--export-deck",
        action="store_true",
        help="Export the final approach deck as PPTX, PDF, or both.",
    )
    modes.add_argument(
        "--build-final-submission-bundle",
        action="store_true",
        help="Build the final allowlisted hackathon submission bundle.",
    )
    modes.add_argument(
        "--freeze-submission",
        action="store_true",
        help="Validate, hash, bundle, and freeze the final submission state.",
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
    enable_evidence_calibration: bool = False,
    calibration_pool_override: int | None = None,
) -> tuple[
    RankingResult,
    dict[str, Path],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
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
    calibration_config = config.get("evidence_calibration", {})
    calibration_pool = int(
        calibration_pool_override
        or calibration_config.get("calibration_pool_size", 700)
    )
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
                enable_evidence_calibration=enable_evidence_calibration,
                calibration_config=calibration_config,
                calibration_pool_size=calibration_pool,
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
            enable_evidence_calibration=enable_evidence_calibration,
            calibration_config=calibration_config,
            calibration_pool_size=calibration_pool,
        )
    output_paths = write_ranking_outputs(result.ranked_candidates, output_dir)
    output_paths.update(audit_paths)
    calibration_summary: dict[str, Any] | None = None
    if enable_evidence_calibration and result.jd_constraints is not None:
        calibration_summary, calibration_paths = write_calibration_reports(
            result.calibration_candidates,
            result.jd_constraints,
            output_dir,
        )
        output_paths.update(calibration_paths)
    validation = validate_ranked_candidates(
        output_paths["ranked_candidates"],
        expected_rows=min(top_k, result.total_candidates_scored),
        score_breakdown_path=output_paths["score_breakdown"],
        firewall_enabled=enable_honeypot_firewall,
        calibration_enabled=enable_evidence_calibration,
    )
    return (
        result,
        output_paths,
        validation,
        jd_profile,
        audit_summary,
        calibration_summary,
    )


def print_ranking_summary(
    result: RankingResult,
    output_paths: dict[str, Path],
    validation: dict[str, Any],
    jd_profile: dict[str, Any],
    top_k: int,
    memory_safe_mode: bool,
    total_runtime: float,
    audit_summary: dict[str, Any] | None = None,
    calibration_summary: dict[str, Any] | None = None,
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
    if calibration_summary is not None:
        print(f"Calibration pool size: {calibration_summary['candidates_calibrated']:,}")
        print(
            "Top 10 average readiness: "
            f"{calibration_summary['top10_average_readiness']:.4f}"
        )
        print(
            "Average evidence confidence: "
            f"{calibration_summary['average_evidence_confidence']:.4f}"
        )
        print(
            "Average hireability: "
            f"{calibration_summary['average_hireability']:.4f}"
        )
        print(
            "Negative constraint counts: "
            f"{json.dumps(calibration_summary['negative_constraint_counts'])}"
        )
        print(
            "Calibration report: "
            f"{output_paths['evidence_calibration_report'].resolve()}"
        )
        print(f"JD constraints: {output_paths['jd_constraints_report'].resolve()}")
        print(f"Hireability audit: {output_paths['hireability_audit'].resolve()}")
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
    calibration_config = config.get("evidence_calibration", {})
    calibration_enabled = bool(
        args.enable_evidence_calibration or calibration_config.get("enabled", False)
    )

    profile_requested = (
        args.profile_only
        or args.profile_and_rank
        or (
            not args.rank
            and not args.audit_honeypots
            and not args.run_ablation
            and not args.validate_final_submission
            and not args.run_benchmark
            and not args.run_weight_sensitivity
            and not args.profile_runtime
            and not args.build_reproducibility_manifest
            and not args.build_submission_package
            and not args.final_submit_check
            and not args.build_demo_pack
            and not args.build_deck_materials
            and not args.explain_top_candidates
            and not args.judge_demo_check
            and not args.build_all_submission_artifacts
            and not args.export_deck
            and not args.build_final_submission_bundle
            and not args.freeze_submission
        )
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
        (
            result,
            output_paths,
            validation,
            jd_profile,
            audit_summary,
            calibration_summary,
        ) = run_ranking(
            fingerprints_path,
            resolve_project_path(args.jd_path),
            output_dir,
            config,
            args.top_k,
            enable_honeypot_firewall=firewall_enabled,
            strict_top_n_override=args.strict_top_n,
            risk_pool_override=args.risk_rerank_pool_size,
            enable_evidence_calibration=calibration_enabled,
            calibration_pool_override=args.calibration_pool_size,
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
            calibration_summary,
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

    if args.run_ablation:
        if not args.jd_path:
            print("Ablation requires --jd PATH_TO_JOB_DESCRIPTION.txt", file=sys.stderr)
            return 2
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if not fingerprints_path.exists():
            print("Candidate fingerprints are missing. Run --profile-only first.", file=sys.stderr)
            return 2
        report, paths = run_ablation(
            fingerprints_path,
            parse_jd_file(resolve_project_path(args.jd_path)),
            output_dir,
            top_k,
            ranking_config,
            firewall_config,
            calibration_config,
        )
        print("\nEvidenceRank ablation complete")
        print("-" * 32)
        print("Variants: " + ", ".join(report["variants"]))
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        print(f"Runtime: {timer.elapsed_seconds:.2f} seconds")
        return 0

    if args.validate_final_submission:
        report = validate_final_submission(
            output_dir,
            top_k=top_k,
            config=config.get("submission_safety", {}),
        )
        print("\nEvidenceRank final submission safety")
        print("-" * 38)
        print(f"Passed: {report['passed']}")
        for error in report["blocking_errors"]:
            print(f"BLOCKING: {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        print(
            "Report: "
            f"{(output_dir / 'final_submission_safety_report.json').resolve()}"
        )
        return 0 if report["passed"] else 1

    if args.run_benchmark:
        if not args.jd_path:
            print("Benchmarking requires --jd PATH_TO_JOB_DESCRIPTION.txt", file=sys.stderr)
            return 2
        report = run_offline_benchmarks(
            resolve_project_path(args.jd_path),
            output_dir,
            min_pass_rate=float(config.get("benchmark", {}).get("min_pass_rate", 0.75)),
        )
        print("\nEvidenceRank offline benchmark complete")
        print("-" * 40)
        print(f"Passed: {report['passed']}")
        print(f"Pass rate: {report['pass_rate']:.1%}")
        for name, path in report["output_paths"].items():
            print(f"{name}: {Path(path).resolve()}")
        return 0 if report["passed"] else 1

    if args.run_weight_sensitivity:
        if not args.jd_path:
            print("Weight sensitivity requires --jd PATH_TO_JOB_DESCRIPTION.txt", file=sys.stderr)
            return 2
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if not fingerprints_path.exists():
            print("Candidate fingerprints are missing. Run --profile-only first.", file=sys.stderr)
            return 2
        report, paths = run_weight_sensitivity(
            fingerprints_path,
            parse_jd_file(resolve_project_path(args.jd_path)),
            output_dir,
            top_k,
            ranking_config,
            firewall_config,
            calibration_config,
        )
        print("\nEvidenceRank weight sensitivity complete")
        print("-" * 43)
        print("Variants: " + ", ".join(report["variants"]))
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        print(f"Runtime: {timer.elapsed_seconds:.2f} seconds")
        return 0

    if args.profile_runtime:
        if not args.jd_path:
            print("Runtime profiling requires --jd PATH_TO_JOB_DESCRIPTION.txt", file=sys.stderr)
            return 2
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if not fingerprints_path.exists():
            print("Candidate fingerprints are missing. Run --profile-only first.", file=sys.stderr)
            return 2
        report = profile_ranking_runtime(
            fingerprints_path,
            parse_jd_file(resolve_project_path(args.jd_path)),
            output_dir,
            top_k,
            ranking_config,
            firewall_config,
            calibration_config,
            config.get("runtime_profile", {}),
        )
        print("\nEvidenceRank runtime profile complete")
        print("-" * 39)
        print(f"Candidates measured: {report['candidate_count']:,}")
        print(f"Ranking runtime: {report['ranking_runtime_seconds']:.2f} seconds")
        print(f"Peak RSS: {report['peak_rss_memory_mb']} MB")
        print(
            "Projected 100,000-candidate runtime: "
            f"{report['estimated_100000_candidate_ranking_seconds']} seconds"
        )
        print(f"Report: {Path(report['output_path']).resolve()}")
        return 0

    if args.build_reproducibility_manifest:
        manifest = build_reproducibility_manifest(
            PROJECT_ROOT,
            output_dir,
            config,
            top_k=top_k,
        )
        print("\nEvidenceRank reproducibility manifest created")
        print("-" * 46)
        print(f"Git commit: {manifest['current_git_commit_hash'] or '(unavailable)'}")
        print(f"Manifest: {Path(manifest['output_path']).resolve()}")
        return 0

    if args.build_submission_package:
        build_reproducibility_manifest(PROJECT_ROOT, output_dir, config, top_k=top_k)
        safety = validate_final_submission(
            output_dir,
            top_k=top_k,
            config=config.get("submission_safety", {}),
        )
        manifest, paths = build_submission_package(
            PROJECT_ROOT,
            output_dir,
            config,
            top_k=top_k,
        )
        print("\nEvidenceRank submission package created")
        print("-" * 42)
        print(f"Safety passed: {safety['passed']}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        return 0 if not manifest["missing_required_files"] and safety["passed"] else 1

    if args.final_submit_check:
        ranked_path = output_dir / "ranked_candidates.csv"
        breakdown_path = output_dir / "score_breakdown.csv"
        validation = validate_ranked_candidates(
            ranked_path,
            expected_rows=expected_ranked_rows(output_dir, top_k),
            score_breakdown_path=breakdown_path,
            firewall_enabled=True,
            calibration_enabled=True,
        )
        safety = validate_final_submission(
            output_dir,
            top_k=top_k,
            config=config.get("submission_safety", {}),
        )
        build_reproducibility_manifest(PROJECT_ROOT, output_dir, config, top_k=top_k)
        runtime_warning = None
        default_jd = resolve_project_path(
            args.jd_path or "data/input/job_description.txt"
        )
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        if default_jd.exists() and fingerprints_path.exists():
            profile_ranking_runtime(
                fingerprints_path,
                parse_jd_file(default_jd),
                output_dir,
                top_k,
                ranking_config,
                firewall_config,
                calibration_config,
                config.get("runtime_profile", {}),
            )
        else:
            runtime_warning = "Runtime profile skipped because JD or fingerprints are missing."
        manifest, paths = build_submission_package(
            PROJECT_ROOT,
            output_dir,
            config,
            top_k=top_k,
        )
        passed = (
            validation["valid"]
            and safety["passed"]
            and not manifest["missing_required_files"]
        )
        print(
            "\nFINAL SUBMISSION CHECK: "
            + ("PASSED" if passed else "FAILED")
        )
        for error in validation["errors"]:
            print(f"BLOCKING: {error}")
        for error in safety["blocking_errors"]:
            print(f"BLOCKING: {error}")
        for warning in safety["warnings"]:
            print(f"WARNING: {warning}")
        if runtime_warning:
            print(f"WARNING: {runtime_warning}")
        print(f"Package: {paths['submission_package'].resolve()}")
        return 0 if passed else 1

    if args.build_deck_materials:
        paths = build_deck_materials(
            PROJECT_ROOT / "docs",
            config.get("demo_materials", {}),
        )
        print("\nEvidenceRank deck materials created")
        print("-" * 37)
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        return 0

    if args.explain_top_candidates:
        top_n = int(
            args.top_n
            or config.get("demo_materials", {}).get("top_n_explanations", 10)
        )
        try:
            cards, paths = build_explanation_cards(output_dir, top_n=top_n)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("\nEvidenceRank explanation cards created")
        print("-" * 41)
        print(f"Candidates explained: {len(cards)}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        return 0

    if args.build_demo_pack:
        top_n = int(
            args.top_n
            or config.get("demo_materials", {}).get("top_n_explanations", 10)
        )
        try:
            manifest, paths = build_demo_pack(
                PROJECT_ROOT,
                output_dir,
                config,
                top_n=top_n,
            )
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("\nEvidenceRank judge demo pack created")
        print("-" * 39)
        print(f"Generated files: {len(manifest['generated_files'])}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        return 0

    if args.judge_demo_check:
        report = judge_demo_check(PROJECT_ROOT, output_dir)
        print(
            "\nJUDGE DEMO CHECK: "
            + ("PASSED" if report["passed"] else "FAILED")
        )
        for error in report["blocking_errors"]:
            print(f"BLOCKING: {error}")
        print(
            "Report: "
            f"{(output_dir / 'judge_demo_check_report.json').resolve()}"
        )
        return 0 if report["passed"] else 1

    if args.build_all_submission_artifacts:
        required = (output_dir / "ranked_candidates.csv", output_dir / "score_breakdown.csv")
        if not all(path.exists() for path in required):
            print(
                "Run the final ranking command first:\n"
                "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
                "--enable-honeypot-firewall --enable-evidence-calibration",
                file=sys.stderr,
            )
            return 2
        safety = validate_final_submission(
            output_dir,
            top_k=top_k,
            config=config.get("submission_safety", {}),
        )
        build_reproducibility_manifest(PROJECT_ROOT, output_dir, config, top_k=top_k)
        default_jd = resolve_project_path(args.jd_path or "data/input/job_description.txt")
        fingerprints_path = output_dir / "candidate_fingerprints.jsonl"
        runtime_built = False
        if default_jd.exists() and fingerprints_path.exists():
            profile_ranking_runtime(
                fingerprints_path,
                parse_jd_file(default_jd),
                output_dir,
                top_k,
                ranking_config,
                firewall_config,
                calibration_config,
                config.get("runtime_profile", {}),
            )
            runtime_built = True
        submission_manifest, submission_paths = build_submission_package(
            PROJECT_ROOT,
            output_dir,
            config,
            top_k=top_k,
        )
        demo_manifest, demo_paths = build_demo_pack(
            PROJECT_ROOT,
            output_dir,
            config,
            top_n=int(
                args.top_n
                or config.get("demo_materials", {}).get("top_n_explanations", 10)
            ),
        )
        demo_check = judge_demo_check(PROJECT_ROOT, output_dir)
        passed = (
            safety["passed"]
            and not submission_manifest["missing_required_files"]
            and demo_check["passed"]
        )
        print(
            "\nALL SUBMISSION ARTIFACTS: "
            + ("PASSED" if passed else "FAILED")
        )
        print(f"Runtime profile refreshed: {runtime_built}")
        for name, path in {**submission_paths, **demo_paths}.items():
            print(f"{name}: {path.resolve()}")
        print(f"Demo files generated: {len(demo_manifest['generated_files'])}")
        for error in safety["blocking_errors"] + demo_check["blocking_errors"]:
            print(f"BLOCKING: {error}")
        return 0 if passed else 1

    if args.export_deck:
        result = export_deck(
            PROJECT_ROOT / "docs",
            output_dir,
            config,
            output_format=args.export_format,
        )
        print("\nEvidenceRank final deck export complete")
        print("-" * 42)
        print(f"Slides: {result['slide_count']}")
        for name, path in result["created_files"].items():
            print(f"{name}: {Path(path).resolve()}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        return 0

    if args.build_final_submission_bundle:
        export_deck(PROJECT_ROOT / "docs", output_dir, config, output_format="pptx")
        build_artifact_hashes(output_dir)
        manifest, paths = build_final_submission_bundle(
            output_dir,
            config,
            top_k=top_k,
        )
        print("\nEvidenceRank final submission bundle created")
        print("-" * 47)
        print(f"Included files: {len(manifest['included_files'])}")
        for name, path in paths.items():
            print(f"{name}: {path.resolve()}")
        return 0

    if args.freeze_submission:
        ranked_path = output_dir / "ranked_candidates.csv"
        breakdown_path = output_dir / "score_breakdown.csv"
        if not ranked_path.exists() or not breakdown_path.exists():
            print(
                "Run the final ranking command first:\n"
                "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
                "--enable-honeypot-firewall --enable-evidence-calibration",
                file=sys.stderr,
            )
            return 2
        validation = validate_ranked_candidates(
            ranked_path,
            expected_rows=expected_ranked_rows(output_dir, top_k),
            score_breakdown_path=breakdown_path,
            firewall_enabled=True,
            calibration_enabled=True,
        )
        safety = validate_final_submission(
            output_dir,
            top_k=top_k,
            config=config.get("submission_safety", {}),
        )
        demo_check = judge_demo_check(PROJECT_ROOT, output_dir)
        export_result = export_deck(
            PROJECT_ROOT / "docs",
            output_dir,
            config,
            output_format="all",
        )
        build_reproducibility_manifest(PROJECT_ROOT, output_dir, config, top_k=top_k)
        hash_report = build_artifact_hashes(output_dir)
        bundle_manifest, paths = build_final_submission_bundle(
            output_dir,
            config,
            top_k=top_k,
        )
        # Refresh hashes after guide/manifest creation, then rebuild once so the
        # bundle contains the final hash report. The bundle itself is not hashed,
        # avoiding a circular integrity dependency.
        hash_report = build_artifact_hashes(output_dir)
        bundle_manifest, paths = build_final_submission_bundle(
            output_dir,
            config,
            top_k=top_k,
        )
        report = build_freeze_report(
            PROJECT_ROOT,
            output_dir,
            config,
            validation=validation,
            safety=safety,
            judge_check=demo_check,
            bundle_manifest=bundle_manifest,
        )
        print(
            "\nSUBMISSION FREEZE: "
            + ("PASSED" if report["passed"] else "FAILED")
        )
        for error in report["blocking_errors"]:
            print(f"BLOCKING: {error}")
        for warning in [*export_result["warnings"], *report["warnings"]]:
            print(f"WARNING: {warning}")
        print(f"Artifact hashes: {Path(hash_report['output_path']).resolve()}")
        print(f"Final bundle: {paths['final_submission_bundle'].resolve()}")
        print(
            "Freeze report: "
            f"{(output_dir / 'final_submission_freeze_report.json').resolve()}"
        )
        return 0 if report["passed"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
