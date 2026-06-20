import unittest

from src.hireability_calibrator import build_hireability_profile


class HireabilityCalibratorTests(unittest.TestCase):
    def test_missing_signals_are_neutral(self) -> None:
        profile = build_hireability_profile({"candidate_id": "A"})
        self.assertAlmostEqual(profile["hireability_score"], 0.5, delta=0.08)

    def test_positive_signals_boost_score(self) -> None:
        profile = build_hireability_profile(
            {
                "behavioral_signal_summary": {
                    "recruiter_response_rate": 0.9,
                    "interview_completion_rate": 0.9,
                },
                "availability_signal_summary": {
                    "open_to_work_flag": True,
                    "willing_to_relocate": True,
                    "notice_period_days": 15,
                },
            }
        )
        self.assertGreater(profile["hireability_score"], 0.7)

    def test_negative_signals_lower_score_and_remain_bounded(self) -> None:
        profile = build_hireability_profile(
            {
                "behavioral_signal_summary": {"recruiter_response_rate": 0.02},
                "availability_signal_summary": {
                    "open_to_work_flag": False,
                    "willing_to_relocate": False,
                    "notice_period_days": 180,
                },
            }
        )
        self.assertLess(profile["hireability_score"], 0.5)
        self.assertGreaterEqual(profile["hireability_score"], 0)


if __name__ == "__main__":
    unittest.main()
