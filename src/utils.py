from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO


def json_default(value: Any) -> Any:
    """Convert common non-JSON values without failing the profiling run."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def sanitize_json_value(value: Any) -> Any:
    """Recursively replace non-finite numbers and unsupported values."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): sanitize_json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json_value(child) for child in value]
    if isinstance(value, set):
        return [sanitize_json_value(child) for child in sorted(value, key=str)]
    return value


def write_json(path: Path | str, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(
            sanitize_json_value(payload),
            handle,
            ensure_ascii=False,
            indent=2,
            default=json_default,
            allow_nan=False,
        )
        handle.write("\n")


def write_jsonl_record(handle: TextIO, payload: dict[str, Any]) -> None:
    handle.write(
        json.dumps(
            sanitize_json_value(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            default=json_default,
            allow_nan=False,
        )
    )
    handle.write("\n")


@dataclass
class Timer:
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at


def memory_usage_mb() -> float | None:
    try:
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except (ImportError, OSError):
        return None


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return default
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def safe_int(value: Any, default: int | None = None) -> int | None:
    number = safe_float(value)
    if number is None:
        return default
    return int(number)


def safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level.upper():<7} {message}", flush=True)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
