from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.candidate_loader import CandidateLoader
from src.candidate_profiler import CandidateProfiler, CandidateProfilerConfig
from src.feature_store import IncrementalFeatureStore
from src.schema_inspector import inspect_schema
from src.utils import log


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


def load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        config: dict[str, Any] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or ":" not in stripped:
                    continue
                key, value = stripped.split(":", 1)
                config[key.strip()] = _parse_scalar(value)
        return config


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build memory-safe EvidenceRank candidate fingerprints."
    )
    parser.add_argument("--input", dest="input_path", help="CSV, JSON, JSONL, or Parquet input.")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N valid records.")
    parser.add_argument("--batch-size", type=int, default=None, help="Parquet batch size.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml.")
    parser.add_argument("--output-dir", default=None, help="Override configured output directory.")
    return parser


def print_summary(summary: dict[str, Any]) -> None:
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
    print(f"Top missing fields: {json.dumps(summary['top_missing_fields'])}")
    print(f"Top anomaly flags: {json.dumps(summary['top_anomaly_flags'])}")
    print(f"Approximate runtime: {summary['runtime_seconds']:.2f} seconds")
    print(f"Memory-safe mode enabled: {summary['memory_safe_mode']}")
    if summary["peak_observed_memory_mb"] is not None:
        print(f"Peak observed RSS: {summary['peak_observed_memory_mb']:.2f} MB")
    print("Output files:")
    for name, path in summary["output_files"].items():
        print(f"  {name}: {path}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = resolve_project_path(args.config)
    config = load_config(config_path)

    input_path = resolve_project_path(args.input_path or config["input_path"])
    output_dir = resolve_project_path(args.output_dir or config["output_dir"])
    batch_size = args.batch_size or int(config.get("batch_size", 1000))
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
        limit=args.limit,
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
        summary = store.finalize(loader.stats.errors, schema_report, run_config)

    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
