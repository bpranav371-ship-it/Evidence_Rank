from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

from .text_normalizer import clean_text
from .utils import log, write_json


FORMAT_SUFFIXES = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".parquet": "parquet",
    ".pq": "parquet",
}

LIKELY_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "candidate_id": ("candidate_id", "candidateid", "id", "profile_id", "user_id"),
    "skills": ("skills", "skill_set", "technical_skills", "competencies"),
    "profile_summary": ("summary", "profile_summary", "about", "bio", "description"),
    "headline": ("headline", "profile_headline", "professional_headline"),
    "current_title": ("current_title", "job_title", "current_role", "designation", "title"),
    "career_history": (
        "career_history",
        "work_experience",
        "experience_history",
        "employment_history",
        "work_history",
    ),
    "projects": ("projects", "project_history", "portfolio", "achievements"),
    "education": ("education", "education_history", "qualifications"),
    "years_of_experience": (
        "years_of_experience",
        "total_experience",
        "experience_years",
        "years_experience",
    ),
    "location": ("location", "city", "current_location", "address"),
    "behavioral_signals": (
        "behavioral_signals",
        "redrob_signals",
        "engagement_signals",
        "activity_signals",
    ),
    "availability_signals": (
        "availability",
        "availability_signals",
        "job_preferences",
        "work_preferences",
    ),
    "timestamps": (
        "created_at",
        "updated_at",
        "signup_date",
        "last_active_date",
        "timestamp",
    ),
    "assessments": ("assessments", "assessment_scores", "skill_assessment_scores", "test_scores"),
    "endorsements": ("endorsements", "endorsements_received", "skill_endorsements"),
    "notice_period": ("notice_period", "notice_period_days", "notice_days"),
    "open_to_work": ("open_to_work", "open_to_work_flag", "available_for_work"),
}


def detect_format(path: Path | str) -> str:
    source = Path(path)
    detected = FORMAT_SUFFIXES.get(source.suffix.lower())
    if not detected:
        raise ValueError(
            f"Unsupported input format '{source.suffix}'. "
            "Expected CSV, JSON, JSONL/NDJSON, or Parquet."
        )
    return detected


def _walk_paths(value: Any, prefix: str = "", max_depth: int = 5) -> Iterator[str]:
    if max_depth < 0:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path
            yield from _walk_paths(child, path, max_depth - 1)
    elif isinstance(value, list):
        for child in value[:3]:
            yield from _walk_paths(child, prefix, max_depth - 1)


def _normalized_field_name(path: str) -> str:
    return "".join(character for character in clean_text(path) if character.isalnum())


def _match_likely_fields(paths: list[str]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        leaf = path.rsplit(".", 1)[-1]
        normalized_leaf = _normalized_field_name(leaf)
        normalized_path = _normalized_field_name(path)
        for category, aliases in LIKELY_FIELD_ALIASES.items():
            for alias in aliases:
                normalized_alias = _normalized_field_name(alias)
                if normalized_leaf == normalized_alias or normalized_path.endswith(normalized_alias):
                    if path not in matches[category]:
                        matches[category].append(path)
                    break
    return dict(matches)


def _inspect_jsonl(path: Path, sample_size: int) -> tuple[int, list[dict[str, Any]], int]:
    count = 0
    malformed = 0
    samples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            if len(samples) >= sample_size:
                continue
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    samples.append(record)
            except json.JSONDecodeError:
                malformed += 1
    return count, samples, malformed


def _inspect_csv(path: Path, sample_size: int) -> tuple[int, list[dict[str, Any]], int]:
    count = 0
    samples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            count += 1
            if len(samples) < sample_size:
                samples.append(dict(row))
    return count, samples, 0


def _inspect_json(path: Path, sample_size: int) -> tuple[int | None, list[dict[str, Any]], int, list[str]]:
    warnings: list[str] = []
    try:
        import ijson  # type: ignore

        count = 0
        samples: list[dict[str, Any]] = []
        with path.open("rb") as handle:
            for item in ijson.items(handle, "item"):
                count += 1
                if len(samples) < sample_size and isinstance(item, dict):
                    samples.append(item)
        return count, samples, 0, warnings
    except ImportError:
        if path.stat().st_size > 50 * 1024 * 1024:
            warnings.append(
                "Large JSON arrays require ijson for memory-safe counting. "
                "Record count was not calculated during schema inspection."
            )
            return None, [], 0, warnings
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        records = payload if isinstance(payload, list) else [payload]
        samples = [record for record in records[:sample_size] if isinstance(record, dict)]
        return len(records), samples, 0, warnings


def _inspect_parquet(path: Path, sample_size: int) -> tuple[int, list[dict[str, Any]], int]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Parquet inspection requires pyarrow.") from exc
    parquet_file = pq.ParquetFile(path)
    samples: list[dict[str, Any]] = []
    for batch in parquet_file.iter_batches(batch_size=max(1, sample_size)):
        samples.extend(batch.to_pylist()[:sample_size])
        break
    return parquet_file.metadata.num_rows, samples, 0


def inspect_schema(path: Path | str, sample_size: int = 25) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    detected_format = detect_format(source)
    warnings: list[str] = []
    if detected_format == "jsonl":
        record_count, samples, malformed = _inspect_jsonl(source, sample_size)
    elif detected_format == "csv":
        record_count, samples, malformed = _inspect_csv(source, sample_size)
    elif detected_format == "json":
        record_count, samples, malformed, warnings = _inspect_json(source, sample_size)
    else:
        record_count, samples, malformed = _inspect_parquet(source, sample_size)

    path_counts: Counter[str] = Counter()
    top_level_columns: set[str] = set()
    for record in samples:
        top_level_columns.update(str(key) for key in record)
        path_counts.update(_walk_paths(record))

    available_paths = sorted(path_counts)
    report = {
        "input_path": str(source.resolve()),
        "detected_format": detected_format,
        "file_size_bytes": source.stat().st_size,
        "record_count": record_count,
        "record_count_method": "streaming" if record_count is not None else "not_counted",
        "sample_records_inspected": len(samples),
        "malformed_sample_rows": malformed,
        "top_level_columns": sorted(top_level_columns),
        "available_field_paths": available_paths,
        "likely_fields": _match_likely_fields(available_paths),
        "warnings": warnings,
    }

    count_text = str(record_count) if record_count is not None else "unknown"
    log(f"Detected {detected_format.upper()} input with {count_text} records.")
    log(f"Top-level fields: {', '.join(report['top_level_columns']) or '(none found)'}")
    for warning in warnings:
        log(warning, "WARNING")
    return report


def save_schema_report(report: dict[str, Any], output_path: Path | str) -> None:
    write_json(output_path, report)
