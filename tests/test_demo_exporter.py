import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.demo_exporter import build_demo_pack


class DemoExporterTests(unittest.TestCase):
    def _minimal_outputs(self, output: Path) -> None:
        output.mkdir(parents=True)
        with (output / "ranked_candidates.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=("candidate_id", "rank", "score", "reasoning")
            )
            writer.writeheader()
            writer.writerow(
                {"candidate_id": "A", "rank": 1, "score": 0.8, "reasoning": "Evidence match."}
            )
        with (output / "score_breakdown.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "candidate_id", "rank", "final_score", "risk_adjusted_score",
                    "calibrated_final_score", "risk_level",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "candidate_id": "A", "rank": 1, "final_score": 0.8,
                    "risk_adjusted_score": 0.8, "calibrated_final_score": 0.8,
                    "risk_level": "low",
                }
            )
        (output / "top_candidate_proofs.jsonl").write_text(
            json.dumps({"candidate_id": "A", "top_evidence_snippets": []}) + "\n",
            encoding="utf-8",
        )

    def test_build_demo_pack_and_missing_output_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "data" / "output"
            self._minimal_outputs(output)
            manifest, paths = build_demo_pack(root, output, {}, top_n=1)
            self.assertTrue(paths["demo_packet_zip"].exists())
            self.assertIn("approach_deck", manifest["generated_files"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "Run the final ranking"):
                build_demo_pack(root, root / "output", {})


if __name__ == "__main__":
    unittest.main()
