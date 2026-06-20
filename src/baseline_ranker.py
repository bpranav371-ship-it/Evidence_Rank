from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .proof_graph import build_proof_graph
from .scoring_engine import apply_strict_rerank, score_candidate
from .utils import Timer, log, memory_usage_mb


@dataclass
class RankingResult:
    ranked_candidates: list[dict[str, Any]]
    total_candidates_scored: int
    errors: int
    runtime_seconds: float
    peak_memory_mb: float | None


def _reverse_text_key(value: str) -> tuple[int, ...]:
    return tuple(-ord(character) for character in value)


def _heap_key(item: dict[str, Any]) -> tuple[float, tuple[int, ...]]:
    return (
        float(item["score"]["final_score"]),
        _reverse_text_key(str(item["candidate_id"])),
    )


def rank_fingerprints(
    fingerprints_path: Path | str,
    jd_profile: dict[str, Any],
    top_k: int = 100,
    strict_rerank_pool_size: int = 300,
    max_evidence_snippets: int = 5,
    score_weights: dict[str, float] | None = None,
    penalties: dict[str, float] | None = None,
    progress_every: int = 10000,
) -> RankingResult:
    source = Path(fingerprints_path)
    if not source.exists():
        raise FileNotFoundError(f"Candidate fingerprints not found: {source}")

    timer = Timer()
    heap_size = max(1, top_k, strict_rerank_pool_size)
    heap: list[tuple[float, tuple[int, ...], int, dict[str, Any]]] = []
    total_scored = 0
    errors = 0
    peak_memory: float | None = None

    with source.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                fingerprint = json.loads(line)
                if not isinstance(fingerprint, dict):
                    raise ValueError("fingerprint row is not an object")
                proof_graph = build_proof_graph(fingerprint, max_evidence_snippets)
                score = score_candidate(
                    jd_profile,
                    fingerprint,
                    proof_graph,
                    score_weights=score_weights,
                    penalties=penalties,
                )
                item = {
                    "candidate_id": str(fingerprint.get("candidate_id") or ""),
                    "fingerprint": fingerprint,
                    "proof_graph": proof_graph,
                    "score": score,
                }
                key = _heap_key(item)
                if len(heap) < heap_size:
                    heapq.heappush(heap, (key[0], key[1], line_number, item))
                elif key > (heap[0][0], heap[0][1]):
                    heapq.heapreplace(heap, (key[0], key[1], line_number, item))
                total_scored += 1
            except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                errors += 1
                log(f"Skipping fingerprint row {line_number}: {exc}", "WARNING")

            if progress_every and total_scored and total_scored % progress_every == 0:
                current_memory = memory_usage_mb()
                if current_memory is not None:
                    peak_memory = max(peak_memory or 0.0, current_memory)
                memory_text = (
                    f", RSS {current_memory:.1f} MB" if current_memory is not None else ""
                )
                log(f"Scored {total_scored:,} candidates{memory_text}.")

    shortlist = [entry[3] for entry in heap]
    shortlist.sort(
        key=lambda item: (
            -float(item["score"]["final_score"]),
            str(item["candidate_id"]),
        )
    )
    for item in shortlist[:strict_rerank_pool_size]:
        item["score"] = apply_strict_rerank(item["score"], item["fingerprint"])

    shortlist.sort(
        key=lambda item: (
            -float(item["score"]["final_score"]),
            str(item["candidate_id"]),
        )
    )
    ranked = shortlist[: min(top_k, len(shortlist))]
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    current_memory = memory_usage_mb()
    if current_memory is not None:
        peak_memory = max(peak_memory or 0.0, current_memory)
    return RankingResult(
        ranked_candidates=ranked,
        total_candidates_scored=total_scored,
        errors=errors,
        runtime_seconds=timer.elapsed_seconds,
        peak_memory_mb=peak_memory,
    )
