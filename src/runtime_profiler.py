from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any

from .baseline_ranker import rank_fingerprints
from .honeypot_firewall import HoneypotFirewall
from .submission_validator import validate_ranked_candidates
from .utils import memory_usage_mb, write_json


def _count_jsonl(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _system_memory() -> dict[str, float | None]:
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        return {
            "total_ram_mb": round(memory.total / (1024 * 1024), 2),
            "available_ram_mb": round(memory.available / (1024 * 1024), 2),
        }
    except (ImportError, OSError):
        return {"total_ram_mb": None, "available_ram_mb": None}


def profile_ranking_runtime(
    fingerprints_path: Path | str,
    jd_profile: dict[str, Any],
    output_dir: Path | str,
    top_k: int,
    ranking_config: dict[str, Any],
    firewall_config: dict[str, Any],
    calibration_config: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = Path(fingerprints_path)
    if not source.exists():
        raise FileNotFoundError(f"Candidate fingerprints not found: {source}")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidate_count = _count_jsonl(source)
    start_rss = memory_usage_mb()
    started = time.perf_counter()
    result = rank_fingerprints(
        source,
        jd_profile,
        top_k=top_k,
        strict_rerank_pool_size=int(ranking_config.get("strict_rerank_pool_size", 300)),
        max_evidence_snippets=int(ranking_config.get("max_evidence_snippets", 5)),
        score_weights=ranking_config.get("score_weights"),
        penalties=ranking_config.get("penalties"),
        progress_every=0,
        enable_honeypot_firewall=True,
        firewall=HoneypotFirewall.from_dict(firewall_config),
        risk_rerank_pool_size=int(firewall_config.get("risk_rerank_pool_size", 500)),
        enable_evidence_calibration=True,
        calibration_config=calibration_config,
        calibration_pool_size=int(calibration_config.get("calibration_pool_size", 700)),
    )
    ranking_runtime = time.perf_counter() - started
    validation_started = time.perf_counter()
    ranked_path = output / "ranked_candidates.csv"
    validation = (
        validate_ranked_candidates(ranked_path, expected_rows=min(top_k, candidate_count))
        if ranked_path.exists()
        else {"valid": False, "errors": ["ranked_candidates.csv is not available."], "row_count": 0}
    )
    validation_runtime = time.perf_counter() - validation_started
    projected_seconds = (
        ranking_runtime * 100000 / candidate_count if candidate_count else None
    )
    threshold = float(
        (runtime_config or {}).get("warn_if_projected_ranking_seconds_above", 300)
    )
    warnings: list[str] = []
    if projected_seconds is not None and projected_seconds > threshold:
        warnings.append(
            f"Projected 100,000-candidate ranking time exceeds {threshold:.0f} seconds."
        )
    output_sizes = {
        path.name: path.stat().st_size
        for path in output.iterdir()
        if path.is_file() and path.name != "candidate_fingerprints.jsonl"
    }
    memory = _system_memory()
    report = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "operating_system": platform.system(),
        "cpu_count": os.cpu_count(),
        **memory,
        "input_fingerprint_file_size_bytes": source.stat().st_size,
        "candidate_count": candidate_count,
        "ranking_runtime_seconds": round(ranking_runtime, 4),
        "validation_runtime_seconds": round(validation_runtime, 4),
        "ablation_runtime_seconds": None,
        "peak_rss_memory_mb": result.peak_memory_mb,
        "starting_rss_memory_mb": start_rss,
        "output_file_sizes_bytes": output_sizes,
        "estimated_100000_candidate_ranking_seconds": (
            round(projected_seconds, 2) if projected_seconds is not None else None
        ),
        "validation_result": validation,
        "warnings": warnings,
        "notes": (
            "The profile measures ranking from existing fingerprints and keeps only bounded "
            "top pools in memory."
        ),
    }
    report_path = output / "runtime_profile_report.json"
    write_json(report_path, report)
    report["output_path"] = str(report_path)
    return report
