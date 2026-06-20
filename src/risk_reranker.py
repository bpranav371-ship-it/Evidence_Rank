from __future__ import annotations

from typing import Any

from .honeypot_firewall import HoneypotFirewall
from .scoring_engine import apply_honeypot_risk


def apply_risk_adjusted_reranking(
    candidates: list[dict[str, Any]],
    top_k: int,
    strict_top_n: int = 10,
    firewall: HoneypotFirewall | None = None,
    jd_profile: dict[str, Any] | None = None,
    disqualify_severe: bool = True,
) -> list[dict[str, Any]]:
    firewall = firewall or HoneypotFirewall()
    original_order = sorted(
        candidates,
        key=lambda item: (
            -float(item["score"].get("final_score", 0.0)),
            str(item["candidate_id"]),
        ),
    )
    original_ranks = {
        str(item["candidate_id"]): rank
        for rank, item in enumerate(original_order, start=1)
    }

    adjusted: list[dict[str, Any]] = []
    for item in candidates:
        report = firewall.assess(
            item["fingerprint"],
            proof_graph=item.get("proof_graph"),
            jd_profile=jd_profile,
            component_scores=item.get("score"),
            deep=True,
        )
        item["risk_report"] = report
        item["original_rank"] = original_ranks[str(item["candidate_id"])]
        item["score"] = apply_honeypot_risk(item["score"], report)
        if report["risk_level"] == "high" and float(
            item["score"].get("proof_alignment_score", 0.0)
        ) < 0.85:
            item["score"]["risk_adjusted_score"] = round(
                max(0.0, float(item["score"]["risk_adjusted_score"]) - 0.08),
                6,
            )
            item["score"]["top10_risk_guard_penalty"] = 0.08
        else:
            item["score"]["top10_risk_guard_penalty"] = 0.0
        if disqualify_severe and report["disqualified"]:
            continue
        adjusted.append(item)

    adjusted.sort(
        key=lambda item: (
            -float(item["score"].get("risk_adjusted_score", 0.0)),
            str(item["candidate_id"]),
        )
    )

    # Severe profiles never enter top 10. High-risk profiles require exceptional proof.
    safe_front = [
        item
        for item in adjusted
        if item["risk_report"]["risk_level"] not in {"severe"}
        and (
            item["risk_report"]["risk_level"] != "high"
            or float(item["score"].get("proof_alignment_score", 0.0)) >= 0.85
        )
    ]
    safe_head = safe_front[:strict_top_n]
    safe_ids = {str(item["candidate_id"]) for item in safe_head}
    ordered = safe_head + [
        item for item in adjusted if str(item["candidate_id"]) not in safe_ids
    ]
    final = ordered[: min(top_k, len(ordered))]
    for rank, item in enumerate(final, start=1):
        item["rank"] = rank
        item["adjusted_rank"] = rank
    return final
