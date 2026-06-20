from __future__ import annotations

import csv
import heapq
import json
from pathlib import Path
from typing import Any

from .baseline_ranker import rank_fingerprints
from .honeypot_firewall import HoneypotFirewall
from .text_normalizer import clean_text
from .utils import write_json


VARIANTS = (
    "keyword_only",
    "baseline_feature2",
    "baseline_plus_firewall",
    "baseline_plus_firewall_plus_calibration",
)


def _keyword_only(
    fingerprints_path: Path,
    jd_profile: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    terms = set(clean_text(jd_profile.get("normalized_jd_text", "")).split())
    heap: list[tuple[float, str, dict[str, Any]]] = []
    with fingerprints_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            fingerprint = json.loads(line)
            candidate_terms = set(clean_text(fingerprint.get("raw_text_compact", "")).split())
            score = len(terms & candidate_terms) / max(1, len(terms))
            item = {
                "candidate_id": str(fingerprint.get("candidate_id") or ""),
                "fingerprint": fingerprint,
                "proof_graph": {
                    "proof_alignment_score": fingerprint.get("skill_evidence_hint_score", 0.0),
                    "retrieval_ranking_evidence_score": 0.0,
                    "evaluation_evidence_score": 0.0,
                    "production_evidence_score": 0.0,
                },
                "score": {
                    "final_score": score,
                    "risk_adjusted_score": score,
                    "calibrated_final_score": score,
                    "unsupported_required_skills": [],
                },
            }
            key = (score, item["candidate_id"])
            if len(heap) < top_k:
                heapq.heappush(heap, (key[0], key[1], item))
            elif key > (heap[0][0], heap[0][1]):
                heapq.heapreplace(heap, (key[0], key[1], item))
    ranked = [entry[2] for entry in heap]
    ranked.sort(key=lambda item: (-float(item["score"]["final_score"]), item["candidate_id"]))
    return ranked


def _metrics(items: list[dict[str, Any]], keyword_ids: set[str]) -> dict[str, Any]:
    top100 = items[:100]
    top10 = items[:10]
    denominator = max(1, len(top100))
    proof_avg = sum(float(item.get("proof_graph", {}).get("proof_alignment_score", 0.0)) for item in top100) / denominator
    risk_avg = sum(float((item.get("risk_report") or {}).get("risk_score", 0.0)) for item in top100) / denominator
    confidence_avg = sum(float(item.get("calibration_profile", {}).get("evidence_confidence_score", 0.0)) for item in top100) / denominator
    unsupported_rate = sum(bool(item.get("score", {}).get("unsupported_required_skills")) for item in top100) / denominator
    stuffing_rate = sum("buzzword_stuffing" in (item.get("risk_report") or {}).get("risk_flags", []) for item in top100) / denominator
    production_rate = sum(float(item.get("proof_graph", {}).get("production_evidence_score", 0.0)) > 0 for item in top100) / denominator
    retrieval_rate = sum(
        float(item.get("proof_graph", {}).get("retrieval_ranking_evidence_score", 0.0)) > 0
        or float(item.get("proof_graph", {}).get("evaluation_evidence_score", 0.0)) > 0
        for item in top100
    ) / denominator
    return {
        "top100_average_proof_alignment": round(proof_avg, 4),
        "top100_average_honeypot_risk": round(risk_avg, 4),
        "top100_average_evidence_confidence": round(confidence_avg, 4),
        "top10_average_top10_readiness": round(
            sum(float(item.get("calibration_profile", {}).get("top10_readiness_score", 0.0)) for item in top10)
            / max(1, len(top10)),
            4,
        ),
        "top100_unsupported_required_skill_rate": round(unsupported_rate, 4),
        "top100_keyword_stuffing_flag_rate": round(stuffing_rate, 4),
        "top100_production_evidence_rate": round(production_rate, 4),
        "top100_retrieval_evaluation_evidence_rate": round(retrieval_rate, 4),
        "overlap_with_keyword_only_top100": round(
            len({item["candidate_id"] for item in top100} & keyword_ids) / denominator,
            4,
        ),
        "severe_risk_in_top10_count": sum(
            (item.get("risk_report") or {}).get("risk_level") == "severe" for item in top10
        ),
    }


def run_ablation(
    fingerprints_path: Path | str,
    jd_profile: dict[str, Any],
    output_dir: Path | str,
    top_k: int,
    ranking_config: dict[str, Any],
    firewall_config: dict[str, Any],
    calibration_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Path]]:
    source = Path(fingerprints_path)
    keyword_items = _keyword_only(source, jd_profile, top_k)
    keyword_ids = {item["candidate_id"] for item in keyword_items[:100]}
    results: dict[str, list[dict[str, Any]]] = {"keyword_only": keyword_items}
    common = dict(
        fingerprints_path=source,
        jd_profile=jd_profile,
        top_k=top_k,
        strict_rerank_pool_size=int(ranking_config.get("strict_rerank_pool_size", 300)),
        max_evidence_snippets=int(ranking_config.get("max_evidence_snippets", 5)),
        score_weights=ranking_config.get("score_weights"),
        penalties=ranking_config.get("penalties"),
        progress_every=0,
    )
    results["baseline_feature2"] = rank_fingerprints(**common).ranked_candidates
    firewall = HoneypotFirewall.from_dict(firewall_config)
    results["baseline_plus_firewall"] = rank_fingerprints(
        **common,
        enable_honeypot_firewall=True,
        firewall=firewall,
        risk_rerank_pool_size=int(firewall_config.get("risk_rerank_pool_size", 500)),
    ).ranked_candidates
    results["baseline_plus_firewall_plus_calibration"] = rank_fingerprints(
        **common,
        enable_honeypot_firewall=True,
        firewall=firewall,
        risk_rerank_pool_size=int(firewall_config.get("risk_rerank_pool_size", 500)),
        enable_evidence_calibration=True,
        calibration_config=calibration_config,
        calibration_pool_size=int(calibration_config.get("calibration_pool_size", 700)),
    ).ranked_candidates

    metrics = {variant: _metrics(items, keyword_ids) for variant, items in results.items()}
    report = {
        "variants": metrics,
        "proxy_metrics_only": True,
        "notes": (
            "These are proxy sanity metrics because the challenge provides no public "
            "ground-truth relevance labels."
        ),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "ablation_report.json"
    summary_path = output / "ablation_summary.csv"
    sanity_path = output / "sanity_checks_report.json"
    write_json(report_path, report)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ("variant", *next(iter(metrics.values())).keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for variant in VARIANTS:
            writer.writerow({"variant": variant, **metrics[variant]})
    calibrated = metrics["baseline_plus_firewall_plus_calibration"]
    sanity = {
        "checks": {
            "severe_risk_excluded_from_top10": calibrated["severe_risk_in_top10_count"] == 0,
            "proof_alignment_not_worse_than_keyword_only": calibrated["top100_average_proof_alignment"]
            >= metrics["keyword_only"]["top100_average_proof_alignment"],
            "keyword_stuffing_controlled": calibrated["top100_keyword_stuffing_flag_rate"] <= 0.10,
            "production_evidence_present": calibrated["top100_production_evidence_rate"] > 0,
            "retrieval_evaluation_evidence_present": calibrated[
                "top100_retrieval_evaluation_evidence_rate"
            ] > 0,
        },
        "notes": "Sanity checks are unlabeled behavioral checks, not accuracy estimates.",
    }
    write_json(sanity_path, sanity)
    return report, {
        "ablation_report": report_path,
        "ablation_summary": summary_path,
        "sanity_checks_report": sanity_path,
    }
