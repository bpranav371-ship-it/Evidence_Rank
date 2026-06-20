import unittest

from src.evidence_calibrator import calibrate_evidence


def _inputs(strong: bool) -> tuple[dict, dict, dict, dict, dict, dict]:
    fingerprint = {
        "candidate_id": "A",
        "career_evidence_text": "deployed retrieval ranking production systems" if strong else "",
        "keyword_density_score": 0.03 if strong else 0.3,
    }
    proof = {"proof_alignment_score": 0.9 if strong else 0.0}
    career = {
        "career_depth_score": 0.8 if strong else 0.1,
        "career_consistency_score": 0.9,
        "production_depth_score": 0.8 if strong else 0.0,
        "retrieval_depth_score": 0.8 if strong else 0.0,
        "evaluation_depth_score": 0.7 if strong else 0.0,
    }
    constraints = {
        "required_positive_skills": ["Python", "Retrieval"],
        "production_heavy": True,
        "retrieval_heavy": True,
        "evaluation_heavy": True,
    }
    hireability = {"hireability_score": 0.9}
    score = {"unsupported_required_skills": [] if strong else ["Python", "Retrieval"]}
    return fingerprint, proof, career, constraints, hireability, score


class EvidenceCalibratorTests(unittest.TestCase):
    def _calibrate(self, strong: bool, risk: float) -> dict:
        fingerprint, proof, career, constraints, hireability, score = _inputs(strong)
        return calibrate_evidence(
            fingerprint,
            proof,
            career,
            constraints,
            hireability,
            {"risk_score": risk},
            score,
        )

    def test_rewards_supported_production_evidence(self) -> None:
        profile = self._calibrate(True, 0.0)
        self.assertGreater(profile["calibration_bonus"], 0)
        self.assertGreater(profile["top10_readiness_score"], 0.5)

    def test_penalizes_keyword_only_and_missing_must_have(self) -> None:
        profile = self._calibrate(False, 0.2)
        self.assertGreater(profile["calibration_penalty"], 0)
        self.assertIn("missing_must_have_skill", profile["negative_constraints_triggered"])
        self.assertIn("keyword_only_without_evidence", profile["negative_constraints_triggered"])

    def test_scores_are_bounded_and_hireability_cannot_override_weak_technical_evidence(self) -> None:
        weak = self._calibrate(False, 0.0)
        strong = self._calibrate(True, 0.0)
        self.assertLess(weak["calibration_bonus"], strong["calibration_bonus"])
        self.assertGreaterEqual(weak["top10_readiness_score"], 0)
        self.assertLessEqual(strong["top10_readiness_score"], 1)


if __name__ == "__main__":
    unittest.main()
