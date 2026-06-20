from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .schema_inspector import detect_format
from .utils import log, memory_usage_mb


@dataclass
class LoaderStats:
    records_seen: int = 0
    records_yielded: int = 0
    errors: int = 0


class CandidateLoader:
    """Memory-safe candidate iterator for supported tabular and JSON formats."""

    def __init__(
        self,
        path: Path | str,
        batch_size: int = 1000,
        progress_every: int = 10000,
        limit: int | None = None,
    ) -> None:
        self.path = Path(path)
        self.batch_size = max(1, batch_size)
        self.progress_every = max(0, progress_every)
        self.limit = limit if limit is None else max(0, limit)
        self.detected_format = detect_format(self.path)
        self.stats = LoaderStats()

    def __iter__(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            raise FileNotFoundError(f"Input file not found: {self.path}")

        readers = {
            "jsonl": self._iter_jsonl,
            "csv": self._iter_csv,
            "json": self._iter_json,
            "parquet": self._iter_parquet,
        }
        for record in readers[self.detected_format]():
            if self.limit is not None and self.stats.records_yielded >= self.limit:
                break
            self.stats.records_yielded += 1
            self._log_progress()
            yield record

    def _log_progress(self) -> None:
        if not self.progress_every or self.stats.records_yielded % self.progress_every:
            return
        memory = memory_usage_mb()
        memory_text = f", RSS {memory:.1f} MB" if memory is not None else ""
        log(
            f"Streamed {self.stats.records_yielded:,} candidates "
            f"({self.stats.errors:,} loader errors{memory_text})."
        )

    def _iter_jsonl(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if self.limit is not None and self.stats.records_yielded >= self.limit:
                    return
                if not line.strip():
                    continue
                self.stats.records_seen += 1
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("JSONL row is not an object")
                    yield record
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    self.stats.errors += 1
                    log(f"Skipping malformed JSONL row {line_number}: {exc}", "WARNING")

    def _iter_csv(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                if self.limit is not None and self.stats.records_yielded >= self.limit:
                    return
                self.stats.records_seen += 1
                try:
                    if row is None:
                        raise ValueError("empty CSV row")
                    yield dict(row)
                except (ValueError, TypeError) as exc:
                    self.stats.errors += 1
                    log(f"Skipping malformed CSV row {row_number}: {exc}", "WARNING")

    def _iter_json(self) -> Iterator[dict[str, Any]]:
        try:
            import ijson  # type: ignore

            with self.path.open("rb") as handle:
                for item in ijson.items(handle, "item"):
                    if self.limit is not None and self.stats.records_yielded >= self.limit:
                        return
                    self.stats.records_seen += 1
                    if isinstance(item, dict):
                        yield item
                    else:
                        self.stats.errors += 1
            return
        except ImportError:
            log(
                "ijson is not installed. Falling back to json.load(), which loads the "
                "entire JSON array into memory. Install ijson for large JSON arrays.",
                "WARNING",
            )

        with self.path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        records = payload if isinstance(payload, list) else [payload]
        for item in records:
            if self.limit is not None and self.stats.records_yielded >= self.limit:
                return
            self.stats.records_seen += 1
            if isinstance(item, dict):
                yield item
            else:
                self.stats.errors += 1

    def _iter_parquet(self) -> Iterator[dict[str, Any]]:
        try:
            import pyarrow.parquet as pq  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Parquet streaming requires pyarrow. Install project requirements first."
            ) from exc

        parquet_file = pq.ParquetFile(self.path)
        for batch in parquet_file.iter_batches(batch_size=self.batch_size):
            for item in batch.to_pylist():
                if self.limit is not None and self.stats.records_yielded >= self.limit:
                    return
                self.stats.records_seen += 1
                if isinstance(item, dict):
                    yield item
                else:
                    self.stats.errors += 1
