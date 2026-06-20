from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .anomaly_rules import RuleFinding, evaluate_anomaly_rules
from .utils import clamp


DEFAULT_RULE_PENALTIES = {
    "zero_duration_expert_claim": 0.25,
    "expert_claim_without_tenure": 0.20,
    "excessive_keyword_density": 0.15,
    "buzzword_stuffing": 0.15,
    "many_claimed_skills_weak_evidence": 0.18,
    "unsupported_required_skill": 0.20,
    "weak_proof_alignment": 0.15,
    "seniority_evidence_mismatch": 0.15,
    "title_skill_mismatch": 0.12,
    "research_only_for_production_jd": 0.08,
    "missing_availability_signals": 0.03,
    "empty_profile_text": 0.50,
}


@dataclass(frozen=True)
class HoneypotFirewallConfig:
    disqualify_severe: bool = True
    max_risk_penalty: float = 0.50
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "low": 0.24,
            "medium": 0.49,
            "high": 0.74,
            "severe": 1.00,
        }
    )
    penalties: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RULE_PENALTIES))


class HoneypotFirewall:
    def __init__(self, config: HoneypotFirewallConfig | None = None) -> None:
        self.config = config or HoneypotFirewallConfig()

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "HoneypotFirewall":
        config = config or {}
        return cls(
            HoneypotFirewallConfig(
                disqualify_severe=bool(config.get("disqualify_severe", True)),
                max_risk_penalty=float(config.get("max_risk_penalty", 0.50)),
                thresholds={
                    **HoneypotFirewallConfig().thresholds,
                    **(config.get("risk_thresholds") or {}),
                },
                penalties={
                    **DEFAULT_RULE_PENALTIES,
                    **(config.get("penalties") or {}),
                },
            )
        )

    def _risk_level(self, score: float) -> str:
        thresholds = self.config.thresholds
        if score <= float(thresholds["low"]):
            return "low"
        if score <= float(thresholds["medium"]):
            return "medium"
        if score <= float(thresholds["high"]):
            return "high"
        return "severe"

    def _penalty(self, risk_score: float, findings: list[RuleFinding]) -> float:
        configured_sum = sum(
            self.config.penalties.get(finding.flag, finding.weight)
            for finding in findings
        )
        if risk_score < 0.25:
            penalty = min(0.03, max(risk_score * 0.10, configured_sum * 0.15))
        elif risk_score < 0.50:
            penalty = min(
                0.10,
                max(0.04, 0.04 + (risk_score - 0.25) * 0.24, configured_sum * 0.30),
            )
        elif risk_score < 0.75:
            penalty = min(
                0.25,
                max(0.11, 0.11 + (risk_score - 0.50) * 0.56, configured_sum * 0.45),
            )
        else:
            penalty = max(
                0.30,
                0.30 + (risk_score - 0.75) * 0.80,
                configured_sum * 0.60,
            )
        return clamp(penalty, 0.0, self.config.max_risk_penalty)

    def assess(
        self,
        fingerprint: dict[str, Any],
        proof_graph: dict[str, Any] | None = None,
        jd_profile: dict[str, Any] | None = None,
        component_scores: dict[str, Any] | None = None,
        deep: bool = True,
    ) -> dict[str, Any]:
        del jd_profile  # Rules use the JD-derived component scores, not external context.
        findings = evaluate_anomaly_rules(
            fingerprint,
            proof_graph=proof_graph,
            component_scores=component_scores,
            deep=deep,
        )
        raw_weight = sum(
            self.config.penalties.get(finding.flag, finding.weight)
            for finding in findings
        )
        severe_count = sum(finding.severity == "severe" for finding in findings)
        high_count = sum(finding.severity == "high" for finding in findings)
        risk_score = clamp(raw_weight + 0.05 * max(0, high_count - 1))
        risk_level = self._risk_level(risk_score)
        flags = [finding.flag for finding in findings]
        severe_flags = [
            finding.flag for finding in findings if finding.severity == "severe"
        ]
        warning_flags = [
            finding.flag for finding in findings if finding.severity != "severe"
        ]

        compound_zero_stuffing = (
            "zero_duration_expert_claim" in flags
            and any(
                flag in flags
                for flag in (
                    "buzzword_stuffing",
                    "many_claimed_skills_weak_evidence",
                    "weak_proof_alignment",
                )
            )
        )
        compound_impossible = any(
            flag in flags for flag in ("negative_experience", "impossible_years_of_experience")
        )
        compound_empty = "empty_profile_text" in flags
        compound_unsupported = (
            "unsupported_required_skill" in flags
            and "buzzword_stuffing" in flags
            and (proof_graph or {}).get("proof_alignment_score", 0.0) < 0.10
        )
        disqualified = bool(
            self.config.disqualify_severe
            and risk_level == "severe"
            and (
                severe_count >= 2
                or compound_empty
                or compound_zero_stuffing
                or compound_impossible
                or compound_unsupported
            )
        )
        penalty = self._penalty(risk_score, findings)
        notes = [finding.note for finding in findings]
        top_findings = sorted(
            findings,
            key=lambda finding: (
                {"severe": 3, "high": 2, "medium": 1, "low": 0}[finding.severity],
                self.config.penalties.get(finding.flag, finding.weight),
            ),
            reverse=True,
        )
        return {
            "candidate_id": str(fingerprint.get("candidate_id") or ""),
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "disqualified": disqualified,
            "risk_flags": flags,
            "severe_flags": severe_flags,
            "warning_flags": warning_flags,
            "evidence_notes": notes,
            "penalty_recommendation": round(penalty, 4),
            "top_reasons": [finding.note for finding in top_findings[:5]],
        }
