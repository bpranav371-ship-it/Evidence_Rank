from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .audit_report import HoneypotAuditWriter
from .career_evidence import build_career_evidence_profile
from .evidence_calibrator import calibrate_evidence
from .hireability_calibrator import build_hireability_profile
from .honeypot_firewall import HoneypotFirewall
from .jd_constraints import build_jd_constraint_profile
from .proof_graph import build_proof_graph
from .risk_reranker import apply_risk_adjusted_reranking
from .scoring_engine import (
    apply_evidence_calibration,
    apply_honeypot_risk,
    apply_strict_rerank,
    score_candidate,
)
from .utils import Timer, log, memory_usage_mb


@dataclass
class RankingResult:
    ranked_candidates: list[dict[str, Any]]
    total_candidates_scored: int
    errors: int
    runtime_seconds: float
    peak_memory_mb: float | None
    calibration_candidates: list[dict[str, Any]] = field(default_factory=list)
    jd_constraints: dict[str, Any] | None = None


def _reverse_text_key(value: str) -> tuple[int, ...]:
    return tuple(-ord(character) for character in value)


def _heap_key(item: dict[str, Any]) -> tuple[float, tuple[int, ...]]:
    ranking_score = item["score"].get(
        "calibrated_final_score",
        item["score"].get("risk_adjusted_score", item["score"]["final_score"]),
    )
    return (
        float(ranking_score),
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
    enable_honeypot_firewall: bool = False,
    firewall: HoneypotFirewall | None = None,
    audit_writer: HoneypotAuditWriter | None = None,
    strict_top_n: int = 10,
    risk_rerank_pool_size: int = 500,
    enable_evidence_calibration: bool = False,
    calibration_config: dict[str, Any] | None = None,
    calibration_pool_size: int = 700,
    semantic_config: dict[str, Any] | None = None,
) -> RankingResult:
    source = Path(fingerprints_path)
    if not source.exists():
        raise FileNotFoundError(f"Candidate fingerprints not found: {source}")

    timer = Timer()
    heap_size = max(
        1,
        top_k,
        strict_rerank_pool_size,
        risk_rerank_pool_size if enable_honeypot_firewall else 0,
        calibration_pool_size if enable_evidence_calibration else 0,
    )
    firewall = firewall or HoneypotFirewall()
    calibration_config = calibration_config or {}
    jd_constraints = (
        build_jd_constraint_profile(jd_profile)
        if enable_evidence_calibration
        else None
    )
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
                proof_graph = build_proof_graph(
                    fingerprint,
                    max_evidence_snippets,
                    include_evidence_snippets=False,
                )
                score = score_candidate(
                    jd_profile,
                    fingerprint,
                    proof_graph,
                    score_weights=score_weights,
                    penalties=penalties,
                    semantic_config=semantic_config,
                )
                risk_report = None
                if enable_honeypot_firewall:
                    risk_report = firewall.assess(
                        fingerprint,
                        proof_graph=proof_graph,
                        jd_profile=jd_profile,
                        component_scores=score,
                        deep=False,
                    )
                    score = apply_honeypot_risk(score, risk_report)
                    if audit_writer is not None:
                        audit_writer.record(risk_report)
                item = {
                    "candidate_id": str(fingerprint.get("candidate_id") or ""),
                    "fingerprint": fingerprint,
                    "proof_graph": proof_graph,
                    "score": score,
                    "risk_report": risk_report,
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
    deep_pool_size = max(
        top_k,
        strict_rerank_pool_size,
        risk_rerank_pool_size if enable_honeypot_firewall else 0,
        calibration_pool_size if enable_evidence_calibration else 0,
    )
    for index, item in enumerate(shortlist[:deep_pool_size]):
        item["proof_graph"] = build_proof_graph(
            item["fingerprint"],
            max_evidence_snippets,
            include_evidence_snippets=True,
        )
        item["score"] = score_candidate(
            jd_profile,
            item["fingerprint"],
            item["proof_graph"],
            score_weights=score_weights,
            penalties=penalties,
            semantic_config=semantic_config,
        )
        if index < strict_rerank_pool_size:
            item["score"] = apply_strict_rerank(item["score"], item["fingerprint"])

    if enable_honeypot_firewall:
        effective_risk_pool = max(
            risk_rerank_pool_size,
            calibration_pool_size if enable_evidence_calibration else 0,
        )
        risk_pool_items = shortlist[:effective_risk_pool]
        for item in risk_pool_items:
            item["lightweight_risk_report"] = item.get("risk_report") or {}
        shortlist = apply_risk_adjusted_reranking(
            risk_pool_items,
            top_k=max(top_k, effective_risk_pool),
            strict_top_n=strict_top_n,
            firewall=firewall,
            jd_profile=jd_profile,
            disqualify_severe=firewall.config.disqualify_severe,
        )
        if audit_writer is not None:
            for item in risk_pool_items:
                audit_writer.replace_with_deep_report(
                    item.get("lightweight_risk_report") or {},
                    item.get("risk_report") or {},
                )

    calibration_candidates: list[dict[str, Any]] = []
    if enable_evidence_calibration and jd_constraints is not None:
        calibration_candidates = shortlist[:calibration_pool_size]
        for item in calibration_candidates:
            career = item["fingerprint"].get("career_evidence_v2")
            if not isinstance(career, dict):
                career = build_career_evidence_profile(item["fingerprint"])
            hireability = build_hireability_profile(
                item["fingerprint"],
                neutral_score=float(calibration_config.get("neutral_hireability_score", 0.50)),
                reference_year=int(calibration_config.get("reference_year", 2026)),
            )
            calibration = calibrate_evidence(
                item["fingerprint"],
                item["proof_graph"],
                career,
                jd_constraints,
                hireability,
                item.get("risk_report"),
                item["score"],
                calibration_config,
            )
            calibration["career_depth_score"] = career["career_depth_score"]
            item["career_evidence_profile"] = career
            item["hireability_profile"] = hireability
            item["calibration_profile"] = calibration
            item["score"] = apply_evidence_calibration(item["score"], calibration)

    shortlist.sort(
        key=lambda item: (
            -float(
                item["score"].get(
                    "calibrated_final_score",
                    item["score"].get(
                        "risk_adjusted_score",
                        item["score"]["final_score"],
                    ),
                )
            ),
            str(item["candidate_id"]),
        )
    )
    if enable_evidence_calibration:
        calibration_candidates = shortlist[:calibration_pool_size]
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
        calibration_candidates=calibration_candidates,
        jd_constraints=jd_constraints,
    )
