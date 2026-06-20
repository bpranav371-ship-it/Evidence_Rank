import tempfile
import unittest
from pathlib import Path

from src.benchmark_cases import run_offline_benchmarks


class BenchmarkCasesTests(unittest.TestCase):
    def test_benchmark_reports_expected_rank_behaviors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jd = root / "jd.txt"
            jd.write_text(
                "Senior production AI engineer requiring Python, RAG, retrieval, ranking, "
                "NDCG, MRR, evaluation, Docker, AWS, APIs, and monitoring.",
                encoding="utf-8",
            )
            report = run_offline_benchmarks(jd, root)
            cases = {case["case_name"]: case for case in report["cases"]}

            self.assertTrue((root / "benchmark_report.json").exists())
            self.assertTrue((root / "benchmark_summary.csv").exists())
            self.assertTrue(cases["strong production retrieval candidate"]["passed"])
            self.assertTrue(cases["keyword stuffer"]["passed"])
            self.assertTrue(cases["severe-risk honeypot"]["passed"])
            self.assertTrue(cases["missing behavior signals"]["passed"])


if __name__ == "__main__":
    unittest.main()
