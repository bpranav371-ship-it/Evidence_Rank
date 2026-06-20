from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any

from .ablation_evaluator import _keyword_only
from .baseline_ranker import rank_fingerprints
from .honeypot_firewall import HoneypotFirewall
from .utils import write_json


VARIANTS = (
    "default",
    "proof_heavy",
    "production_heavy",
    "retrieval_eval_heavy",
    "hireability_light",
    "firewall_strict",
    "calibration_light",
    "keyword_baseline_reference",
)


def _selected_score(item: dict[str, Any]) -> float:
    score = item.get("score", {})
    return float(
        score.get(
            "calibrated_final_score",
            score.get("risk_adjusted_score", score.get("final_score", 0.0)),
        )
    )


def _metrics(
    items: list[dict[str, Any]],
    default_ids: set[str],
    default_top10_ids: set[str],
    top_k: int,
) -> dict[str, Any]:
    top100 = items[: min(100, top_k, len(items))]
    top10 = top100[:10]
    denominator = max(1, len(top100))
    top10_scores = [_selected_score(item) for item in top10]
    top100_scores = [_selected_score(item) for item in top100]
    return {
        "top10_overlap_with_default": round(
            len({item["candidate_id"] for item in top10} & default_top10_ids)
            / max(1, len(top10)),
            4,
        ),
        "top100_overlap_with_default": round(
            len({item["candidate_id"] for item in top100} & default_ids) / denominator, 4
        ),
        "average_proof_alignment_top100": round(
            sum(float(item.get("proof_graph", {}).get("proof_alignment_score", 0.0)) for item in top100)
            / denominator,
            4,
        ),
        "average_honeypot_risk_top100": round(
            sum(float((item.get("risk_report") or {}).get("risk_score", 0.0)) for item in top100)
            / denominator,
            4,
        ),
        "average_evidence_confidence_top100": round(
            sum(float(item.get("calibration_profile", {}).get("evidence_confidence_score", 0.0)) for item in top100)
            / denominator,
            4,
        ),
        "severe_risk_in_top10_count": sum(
            (item.get("risk_report") or {}).get("risk_level") == "severe" for item in top10
        ),
        "unsupported_required_skill_rate_top100": round(
            sum(bool(item.get("score", {}).get("unsupported_required_skills")) for item in top100)
            / denominator,
            4,
        ),
        "average_top10_readiness": round(
            sum(float(item.get("calibration_profile", {}).get("top10_readiness_score", 0.0)) for item in top10)
            / max(1, len(top10)),
            4,
        ),
        "score_spread_top10": round(max(top10_scores) - min(top10_scores), 6)
        if len(top10_scores) > 1 else 0.0,
        "score_spread_top100": round(max(top100_scores) - min(top100_scores), 6)
        if len(top100_scores) > 1 else 0.0,
    }


def _variant_configs(
    variant: str,
    ranking: dict[str, Any],
    firewall: dict[str, Any],
    calibration: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rank_config = deepcopy(ranking)
    firewall_config = deepcopy(firewall)
    calibration_config = deepcopy(calibration)
    weights = {
        "jd_relevance": 0.25,
        "must_have_skill": 0.20,
        "proof_alignment": 0.25,
        "retrieval_evaluation_depth": 0.10,
        "production_readiness": 0.10,
        "hireability": 0.10,
        **(rank_config.get("score_weights") or {}),
    }
    if variant == "proof_heavy":
        weights.update(proof_alignment=0.37, jd_relevance=0.18, hireability=0.05)
    elif variant == "production_heavy":
        weights.update(production_readiness=0.22, jd_relevance=0.20, hireability=0.05)
    elif variant == "retrieval_eval_heavy":
        weights.update(retrieval_evaluation_depth=0.24, jd_relevance=0.18, hireability=0.05)
    elif variant == "hireability_light":
        weights.update(hireability=0.03, proof_alignment=0.30)
    elif variant == "firewall_strict":
        firewall_config["max_risk_penalty"] = 0.65
        penalties = dict(firewall_config.get("penalties") or {})
        penalties["weak_proof_alignment"] = 0.22
        penalties["buzzword_stuffing"] = 0.22
        firewall_config["penalties"] = penalties
    elif variant == "calibration_light":
        calibration_config["max_calibration_bonus"] = 0.04
        calibration_config["max_calibration_penalty"] = 0.08
    total = sum(float(value) for value in weights.values())
    if total > 0:
        weights = {key: float(value) / total for key, value in weights.items()}
    rank_config["score_weights"] = weights
    return rank_config, firewall_config, calibration_config


def run_weight_sensitivity(
    fingerprints_path: Path | str,
    jd_profile: dict[str, Any],
    output_dir: Path | str,
    top_k: int,
    ranking_config: dict[str, Any],
    firewall_config: dict[str, Any],
    calibration_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Path]]:
    source = Path(fingerprints_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    ranked_by_variant: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for variant in VARIANTS:
        try:
            if variant == "keyword_baseline_reference":
                ranked_by_variant[variant] = _keyword_only(source, jd_profile, top_k)
                continue
            rank_config, risk_config, calibration = _variant_configs(
                variant, ranking_config, firewall_config, calibration_config
            )
            result = rank_fingerprints(
                source,
                jd_profile,
                top_k=top_k,
                strict_rerank_pool_size=int(rank_config.get("strict_rerank_pool_size", 300)),
                max_evidence_snippets=int(rank_config.get("max_evidence_snippets", 5)),
                score_weights=rank_config.get("score_weights"),
                penalties=rank_config.get("penalties"),
                progress_every=0,
                enable_honeypot_firewall=True,
                firewall=HoneypotFirewall.from_dict(risk_config),
                risk_rerank_pool_size=int(risk_config.get("risk_rerank_pool_size", 500)),
                enable_evidence_calibration=True,
                calibration_config=calibration,
                calibration_pool_size=int(calibration.get("calibration_pool_size", 700)),
            )
            ranked_by_variant[variant] = result.ranked_candidates
        except (OSError, ValueError, KeyError) as exc:
            warnings.append(f"{variant}: {exc}")
            ranked_by_variant[variant] = []

    default_items = ranked_by_variant.get("default", [])
    default_ids = {item["candidate_id"] for item in default_items[:100]}
    default_top10_ids = {item["candidate_id"] for item in default_items[:10]}
    metrics = {
        variant: {
            "status": "ok" if ranked_by_variant[variant] else "warning",
            **_metrics(ranked_by_variant[variant], default_ids, default_top10_ids, top_k),
        }
        for variant in VARIANTS
    }
    report = {
        "variants": metrics,
        "warnings": warnings,
        "config_mutated": False,
        "notes": (
            "Sensitivity metrics test ranking stability under controlled in-memory weight "
            "changes. They are proxy checks without relevance labels."
        ),
    }
    report_path = output / "weight_sensitivity_report.json"
    summary_path = output / "weight_sensitivity_summary.csv"
    write_json(report_path, report)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ("variant", *next(iter(metrics.values())).keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for variant in VARIANTS:
            writer.writerow({"variant": variant, **metrics[variant]})
    return report, {
        "weight_sensitivity_report": report_path,
        "weight_sensitivity_summary": summary_path,
    }
