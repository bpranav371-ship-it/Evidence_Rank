from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

from .honeypot_firewall import HoneypotFirewall
from .proof_graph import build_proof_graph
from .utils import log, write_json


FLAG_COLUMNS = (
    "candidate_id",
    "risk_score",
    "risk_level",
    "disqualified",
    "risk_flags",
    "severe_flags",
    "warning_flags",
    "penalty_recommendation",
    "top_reasons",
)
RERANK_COLUMNS = (
    "candidate_id",
    "original_rank",
    "adjusted_rank",
    "original_score",
    "risk_adjusted_score",
    "rank_change",
    "risk_level",
    "risk_flags",
    "reason_for_change",
)


class HoneypotAuditWriter:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.output_dir / "honeypot_audit.json"
        self.flags_path = self.output_dir / "honeypot_flags.csv"
        self.rerank_path = self.output_dir / "rerank_audit_top100.csv"
        self._handle: TextIO | None = None
        self._writer: csv.DictWriter | None = None
        self.total = 0
        self.flagged = 0
        self.disqualified = 0
        self.risk_sum = 0.0
        self.penalty_sum = 0.0
        self.level_counts: Counter[str] = Counter()
        self.flag_counts: Counter[str] = Counter()
        self.deep_overrides: dict[str, dict[str, Any]] = {}

    def __enter__(self) -> "HoneypotAuditWriter":
        self._handle = self.flags_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=FLAG_COLUMNS)
        self._writer.writeheader()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self._handle is not None:
            self._handle.close()

    def record(self, report: dict[str, Any]) -> None:
        self.total += 1
        flags = report.get("risk_flags") or []
        if flags:
            self.flagged += 1
        if report.get("disqualified"):
            self.disqualified += 1
        self.risk_sum += float(report.get("risk_score", 0.0))
        self.penalty_sum += float(report.get("penalty_recommendation", 0.0))
        self.level_counts[str(report.get("risk_level", "low"))] += 1
        self.flag_counts.update(flags)
        if flags and self._writer is not None:
            self._writer.writerow(
                self._report_row(report)
            )

    def _report_row(self, report: dict[str, Any]) -> dict[str, Any]:
        return {
            "candidate_id": report.get("candidate_id", ""),
            "risk_score": report.get("risk_score", 0.0),
            "risk_level": report.get("risk_level", "low"),
            "disqualified": report.get("disqualified", False),
            "risk_flags": "|".join(report.get("risk_flags") or []),
            "severe_flags": "|".join(report.get("severe_flags") or []),
            "warning_flags": "|".join(report.get("warning_flags") or []),
            "penalty_recommendation": report.get("penalty_recommendation", 0.0),
            "top_reasons": " | ".join(report.get("top_reasons") or []),
        }

    def replace_with_deep_report(
        self,
        lightweight_report: dict[str, Any],
        deep_report: dict[str, Any],
    ) -> None:
        old_flags = lightweight_report.get("risk_flags") or []
        new_flags = deep_report.get("risk_flags") or []
        if old_flags:
            self.flagged -= 1
        if new_flags:
            self.flagged += 1
        if lightweight_report.get("disqualified"):
            self.disqualified -= 1
        if deep_report.get("disqualified"):
            self.disqualified += 1
        self.risk_sum += float(deep_report.get("risk_score", 0.0)) - float(
            lightweight_report.get("risk_score", 0.0)
        )
        self.penalty_sum += float(
            deep_report.get("penalty_recommendation", 0.0)
        ) - float(lightweight_report.get("penalty_recommendation", 0.0))
        self.level_counts[str(lightweight_report.get("risk_level", "low"))] -= 1
        self.level_counts[str(deep_report.get("risk_level", "low"))] += 1
        self.flag_counts.subtract(old_flags)
        self.flag_counts.update(new_flags)
        self.deep_overrides[str(deep_report.get("candidate_id") or "")] = deep_report

    def _rewrite_flags_with_deep_overrides(self) -> None:
        if not self.deep_overrides:
            return
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None
            self._writer = None
        temporary_path = self.flags_path.with_suffix(".tmp")
        seen: set[str] = set()
        with self.flags_path.open("r", encoding="utf-8", newline="") as source, temporary_path.open(
            "w", encoding="utf-8", newline=""
        ) as target:
            reader = csv.DictReader(source)
            writer = csv.DictWriter(target, fieldnames=FLAG_COLUMNS)
            writer.writeheader()
            for row in reader:
                candidate_id = str(row.get("candidate_id") or "")
                override = self.deep_overrides.get(candidate_id)
                if override is not None:
                    seen.add(candidate_id)
                    if override.get("risk_flags"):
                        writer.writerow(self._report_row(override))
                else:
                    writer.writerow(row)
            for candidate_id, override in self.deep_overrides.items():
                if candidate_id not in seen and override.get("risk_flags"):
                    writer.writerow(self._report_row(override))
        temporary_path.replace(self.flags_path)

    def _risk_summary(self, candidates: list[dict[str, Any]], top_n: int) -> dict[str, Any]:
        subset = candidates[:top_n]
        if not subset:
            return {"count": 0, "average_risk_score": 0.0, "risk_levels": {}}
        return {
            "count": len(subset),
            "average_risk_score": round(
                sum(float(item.get("risk_report", {}).get("risk_score", 0.0)) for item in subset)
                / len(subset),
                4,
            ),
            "risk_levels": dict(
                Counter(
                    str(item.get("risk_report", {}).get("risk_level", "low"))
                    for item in subset
                )
            ),
        }

    def write_rerank_audit(self, candidates: list[dict[str, Any]]) -> None:
        with self.rerank_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RERANK_COLUMNS)
            writer.writeheader()
            for item in candidates[:100]:
                original_rank = int(item.get("original_rank", item.get("rank", 0)))
                adjusted_rank = int(item.get("adjusted_rank", item.get("rank", 0)))
                report = item.get("risk_report") or {}
                score = item.get("score") or {}
                rank_change = original_rank - adjusted_rank
                reason = (
                    "Moved down after risk penalty."
                    if rank_change < 0
                    else "Moved up after lower-risk candidates were preferred."
                    if rank_change > 0
                    else "Rank unchanged after risk adjustment."
                )
                writer.writerow(
                    {
                        "candidate_id": item.get("candidate_id", ""),
                        "original_rank": original_rank,
                        "adjusted_rank": adjusted_rank,
                        "original_score": score.get("final_score", 0.0),
                        "risk_adjusted_score": score.get("risk_adjusted_score", 0.0),
                        "rank_change": rank_change,
                        "risk_level": report.get("risk_level", "low"),
                        "risk_flags": "|".join(report.get("risk_flags") or []),
                        "reason_for_change": reason,
                    }
                )

    def finalize(self, ranked_candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        ranked_candidates = ranked_candidates or []
        self._rewrite_flags_with_deep_overrides()
        self.write_rerank_audit(ranked_candidates)
        denominator = max(1, self.total)
        summary = {
            "total_candidates_scored": self.total,
            "total_candidates_flagged": self.flagged,
            "low_risk_count": self.level_counts["low"],
            "medium_risk_count": self.level_counts["medium"],
            "high_risk_count": self.level_counts["high"],
            "severe_risk_count": self.level_counts["severe"],
            "disqualified_count": self.disqualified,
            "top_flag_counts": {
                flag: count
                for flag, count in self.flag_counts.most_common(20)
                if count > 0
            },
            "average_risk_score": round(self.risk_sum / denominator, 4),
            "average_penalty": round(self.penalty_sum / denominator, 4),
            "top_10_risk_summary": self._risk_summary(ranked_candidates, 10),
            "top_100_risk_summary": self._risk_summary(ranked_candidates, 100),
            "notes": (
                "Risk flags are deterministic ranking heuristics, not accusations. "
                "Human review is required before any hiring decision."
            ),
        }
        write_json(self.audit_path, summary)
        return summary

    @property
    def output_paths(self) -> dict[str, Path]:
        return {
            "honeypot_audit": self.audit_path,
            "honeypot_flags": self.flags_path,
            "rerank_audit_top100": self.rerank_path,
        }


def audit_existing_fingerprints(
    fingerprints_path: Path | str,
    output_dir: Path | str,
    firewall: HoneypotFirewall,
    jd_profile: dict[str, Any] | None = None,
    progress_every: int = 10000,
    max_evidence_snippets: int = 5,
) -> tuple[dict[str, Any], dict[str, Path]]:
    source = Path(fingerprints_path)
    if not source.exists():
        raise FileNotFoundError(f"Candidate fingerprints not found: {source}")
    with HoneypotAuditWriter(output_dir) as audit:
        with source.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    fingerprint = json.loads(line)
                    proof = build_proof_graph(
                        fingerprint,
                        max_evidence_snippets,
                        include_evidence_snippets=False,
                    )
                    report = firewall.assess(
                        fingerprint,
                        proof_graph=proof,
                        jd_profile=jd_profile,
                        deep=True,
                    )
                    audit.record(report)
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    log(f"Skipping fingerprint row {line_number}: {exc}", "WARNING")
                if progress_every and line_number % progress_every == 0:
                    log(f"Audited {line_number:,} candidate fingerprints.")
        summary = audit.finalize([])
        paths = audit.output_paths
    return summary, paths
