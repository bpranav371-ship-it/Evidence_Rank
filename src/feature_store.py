from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, TextIO

from .utils import Timer, memory_usage_mb, write_json, write_jsonl_record


class IncrementalFeatureStore:
    """Write fingerprints immediately and retain only aggregate counters."""

    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fingerprints_path = self.output_dir / "candidate_fingerprints.jsonl"
        self.schema_report_path = self.output_dir / "schema_report.json"
        self.summary_path = self.output_dir / "profiler_summary.json"
        self._handle: TextIO | None = None
        self.timer = Timer()
        self.total_candidates = 0
        self.loader_errors = 0
        self.profiler_errors = 0
        self.completeness_sum = 0.0
        self.keyword_density_sum = 0.0
        self.skill_evidence_sum = 0.0
        self.missing_fields: Counter[str] = Counter()
        self.anomaly_flags: Counter[str] = Counter()
        self.peak_observed_memory_mb: float | None = None

    def __enter__(self) -> "IncrementalFeatureStore":
        self._handle = self.fingerprints_path.open("w", encoding="utf-8", buffering=1024 * 1024)
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None

    def save_schema_report(self, report: dict[str, Any]) -> None:
        write_json(self.schema_report_path, report)

    def write_fingerprint(self, fingerprint: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("Feature store must be opened with a context manager.")
        write_jsonl_record(self._handle, fingerprint)
        self.total_candidates += 1
        self.completeness_sum += float(fingerprint["profile_completeness_score"])
        self.keyword_density_sum += float(fingerprint["keyword_density_score"])
        self.skill_evidence_sum += float(fingerprint["skill_evidence_hint_score"])
        self.missing_fields.update(fingerprint.get("missing_fields", []))
        self.anomaly_flags.update(fingerprint.get("anomaly_flags", []))
        current_memory = memory_usage_mb()
        if current_memory is not None:
            self.peak_observed_memory_mb = max(self.peak_observed_memory_mb or 0.0, current_memory)

    def record_profiler_error(self) -> None:
        self.profiler_errors += 1

    def finalize(
        self,
        loader_errors: int,
        schema_report: dict[str, Any],
        run_config: dict[str, Any],
    ) -> dict[str, Any]:
        self.loader_errors = loader_errors
        total = max(1, self.total_candidates)
        summary = {
            "total_candidates_processed": self.total_candidates,
            "total_loader_errors": self.loader_errors,
            "total_profiler_errors": self.profiler_errors,
            "total_errors": self.loader_errors + self.profiler_errors,
            "average_profile_completeness_score": round(self.completeness_sum / total, 4),
            "average_keyword_density_score": round(self.keyword_density_sum / total, 4),
            "average_skill_evidence_hint_score": round(self.skill_evidence_sum / total, 4),
            "top_missing_fields": dict(self.missing_fields.most_common(15)),
            "top_anomaly_flags": dict(self.anomaly_flags.most_common(15)),
            "runtime_seconds": round(self.timer.elapsed_seconds, 3),
            "peak_observed_memory_mb": (
                round(self.peak_observed_memory_mb, 2)
                if self.peak_observed_memory_mb is not None
                else None
            ),
            "memory_safe_mode": bool(run_config.get("memory_safe_mode", True)),
            "batch_size": int(run_config.get("batch_size", 1000)),
            "input_format": schema_report.get("detected_format"),
            "detected_schema_fields": schema_report.get("top_level_columns", []),
            "output_files": {
                "candidate_fingerprints": str(self.fingerprints_path.resolve()),
                "schema_report": str(self.schema_report_path.resolve()),
                "profiler_summary": str(self.summary_path.resolve()),
            },
        }
        write_json(self.summary_path, summary)
        return summary
