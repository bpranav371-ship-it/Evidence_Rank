from __future__ import annotations

from pathlib import Path
from typing import Any

from .diagram_generator import generate_diagrams


SLIDES = [
    (
        "EvidenceRank — Candidate Proof Engine",
        [
            "INDIA RUNS Track 1",
            "CPU-only, offline candidate ranking for approximately 100,000 profiles",
            "Built for evidence-backed, explainable, and reproducible selection",
        ],
        "Open with the one-line idea: do not just match skills—prove them.",
    ),
    (
        "The problem",
        [
            "Traditional résumé matching trusts self-reported keywords",
            "High keyword overlap can hide weak or missing career proof",
            "Recruiters need reliable top-10 candidates, not merely a large shortlist",
        ],
        "Frame the task as ranking confidence, not only text similarity.",
    ),
    (
        "Why keyword matching fails",
        [
            "Keyword stuffing can outrank genuine experience",
            "Hidden gems may describe strong work in plain language",
            "Skill claims are not connected to projects, deployment, or evaluation",
            "No protection exists against contradictory or suspicious profiles",
        ],
        "Use the keyword-stuffer versus hidden-gem benchmark example.",
    ),
    (
        "Core idea: prove the match",
        [
            "Create a compact fingerprint for every candidate",
            "Separate claimed skills from career evidence",
            "Rank with proof, production depth, evaluation, risk, and constraints",
            "Explain every top result using fields already present in the profile",
        ],
        "Emphasize deterministic and auditable logic.",
    ),
    (
        "System architecture",
        [
            "Streaming profiler keeps full-dataset memory use bounded",
            "JD parsing and proof graphs remain fully local",
            "Deep risk and calibration work runs only on bounded top pools",
            "See `architecture_diagram.mmd` for the end-to-end flow",
        ],
        "Walk left-to-right from dataset to final CSV and audits.",
    ),
    (
        "Candidate Proof Graph",
        [
            "Supported: direct title, project, achievement, or career evidence",
            "Weakly supported: broad profile or education mention",
            "Unsupported: claim exists without matching evidence",
            "Short snippets show exactly what the system found",
        ],
        "This is the clearest differentiator from a keyword matcher.",
    ),
    (
        "Honeypot Firewall",
        [
            "Detects keyword stuffing, zero-duration expertise, and contradictions",
            "Assigns explainable low, medium, high, or severe risk",
            "Applies bounded penalties instead of aggressive blanket deletion",
            "Protects the top 10 with stricter deterministic checks",
        ],
        "Risk flags are confidence signals, not accusations.",
    ),
    (
        "Evidence Calibration",
        [
            "Rewards retrieval, ranking, evaluation, and production proof",
            "Checks JD-specific positive and negative constraints",
            "Uses hireability signals modestly; missing behavior stays neutral",
            "Calibration cannot replace weak technical evidence",
        ],
        "Explain that the adjustment is bounded and top-pool-only.",
    ),
    (
        "Evaluation and safety",
        [
            "Four-variant ablation compares keyword, baseline, risk, and calibration",
            "Eight synthetic benchmark cases test intended ranking behavior",
            "Weight sensitivity checks that results are not tied to one fragile setup",
            "Final validation checks rank continuity, scores, risks, and files",
        ],
        "Be explicit that these are proxy sanity checks without public labels.",
    ),
    (
        "Submission outputs",
        [
            "`ranked_candidates.csv` is the final answer",
            "`score_breakdown.csv` exposes component scores and penalties",
            "Proof, honeypot, calibration, runtime, and reproducibility audits are included",
            "Submission and demo ZIPs use explicit safe allowlists",
        ],
        "Show the top candidate card and score breakdown side by side.",
    ),
    (
        "Performance and reproducibility",
        [
            "Runs locally on CPU with no API, network, GPU, or LLM dependency",
            "Measured peak RSS is tens of MB on the verification run",
            "Projected calibrated ranking for 100,000 fingerprints is about 3–4 minutes",
            "A manifest records Git commit, config hashes, environment, and exact command",
        ],
        "Quote the latest runtime report rather than promising a universal time.",
    ),
    (
        "Impact",
        [
            "Recruiters receive evidence-backed rankings instead of keyword counts",
            "Top candidates come with concise proof and transparent concerns",
            "Risk-aware reranking improves confidence in the most visible positions",
            "Human review remains the final hiring decision",
        ],
        "Close with trustworthy ranking, reproducibility, and practical CPU deployment.",
    ),
]


def _deck(project_title: str, hackathon_track: str, include_notes: bool) -> str:
    lines = [
        f"# {project_title}",
        "",
        f"Approach deck material for **{hackathon_track}**.",
        "",
        "> Convert this Markdown into PPT/PDF using any presentation tool. Mermaid source "
        "files in this directory can be rendered by GitHub or Mermaid-compatible tools.",
        "",
    ]
    for index, (title, bullets, notes) in enumerate(SLIDES, 1):
        lines.extend(
            [
                "---",
                "",
                f"## Slide {index} — {title}",
                "",
                *[f"- {bullet}" for bullet in bullets],
                "",
            ]
        )
        if include_notes:
            lines.extend([f"**Speaker notes:** {notes}", ""])
    return "\n".join(lines)


def _demo_script() -> str:
    return """# EvidenceRank 2–3 Minute Demo Script

## 0:00–0:20 — Problem

Traditional résumé matching rewards repeated keywords. A candidate can list RAG,
ranking, or Python without showing where those skills were used. EvidenceRank asks
a stricter question: what can the profile actually prove?

## 0:20–0:50 — What EvidenceRank does

The pipeline streams candidate records into compact fingerprints, parses the job
description, and ranks candidates locally. It is CPU-only, offline, deterministic,
and designed for roughly 100,000 profiles without loading the dataset into memory.

## 0:50–1:30 — Architecture

The Candidate Proof Graph connects skill claims to titles, projects, achievements,
and career text. Baseline scoring combines JD relevance, required skills, proof,
retrieval and evaluation depth, production readiness, and modest hireability
signals. Only a bounded shortlist receives deeper analysis.

## 1:30–2:10 — Proof Graph and Firewall

Skills become supported, weakly supported, or unsupported. The Honeypot Firewall
then looks for combinations such as keyword stuffing with weak evidence,
zero-duration expertise, or title-career contradictions. It assigns explainable
risk and protects the top 10 without accusing candidates or replacing human review.

## 2:10–2:40 — Outputs and reproducibility

The final CSV contains candidate ID, rank, score, and reasoning. A score breakdown,
proof JSONL, risk audits, runtime report, and reproducibility manifest show how each
result was produced. The final submit command validates and packages these files.

## 2:40–3:00 — Impact

EvidenceRank turns résumé matching into candidate proof: safer top ranks, visible
evidence, low memory use, and a result judges or recruiters can reproduce locally.
"""


def _walkthrough() -> str:
    return """# Judge Walkthrough

## Start here

1. `README.md`
2. `data/output/ranked_candidates.csv`
3. `data/output/score_breakdown.csv`
4. `data/output/top10_explanation_cards.md`
5. `data/output/final_submission_safety_report.json`
6. `data/output/reproducibility_manifest.json`

## How to run

```powershell
python -m pip install -r requirements.txt
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration
python run.py --final-submit-check --top-k 100
```

## What each artifact proves

- `ranked_candidates.csv`: final ranked answer in submission format
- `score_breakdown.csv`: transparent component scores and penalties
- `top_candidate_proofs.jsonl`: supported, weak, and unsupported skill evidence
- `honeypot_audit.json`: deterministic risk controls
- `ablation_report.json`: unlabeled proxy sanity comparison
- `runtime_profile_report.json`: measured CPU runtime and memory
- `reproducibility_manifest.json`: commit, hashes, environment, and exact command
"""


def _checklist() -> str:
    return """# INDIA RUNS Submission Checklist

## Required by the hackathon

- [ ] GitHub repository is clean and shared as required
- [ ] Approach deck PDF is ready
- [ ] `ranked_candidates.csv` is generated
- [ ] Final reproduction command has been tested

## Before submission

- [ ] `pytest` passes
- [ ] `python run.py --final-submit-check --top-k 100` passes
- [ ] Output CSV validates with exactly the required columns
- [ ] No raw dataset is committed
- [ ] No generated output is staged accidentally
- [ ] README and methodology are current
- [ ] Deck Markdown has been exported to PPT/PDF
- [ ] Repository link is confirmed
- [ ] Top candidate explanations were reviewed for factual grounding
"""


def _faq() -> str:
    return """# FAQ for Judges

## 1. Is this just keyword matching?

No. Keywords contribute to relevance, but claimed skills are connected to career
evidence and classified as supported, weakly supported, or unsupported.

## 2. Why not use an LLM?

The challenge benefits from reproducibility and offline execution. Deterministic
rules avoid API cost, network dependency, prompt drift, and hallucinated evidence.

## 3. How does Candidate Proof Graph work?

It searches titles, projects, achievements, and career text for each claimed skill
and known aliases, then records real snippets and proof-alignment scores.

## 4. How are fake or suspicious profiles handled?

The Honeypot Firewall detects risk patterns such as stuffing, contradictory
experience, and unsupported senior claims. Flags reduce ranking confidence; they
are not accusations.

## 5. How do you avoid over-penalizing missing behavior signals?

Missing behavior and availability data receive a neutral score near 0.50. They do
not erase strong technical evidence.

## 6. How do you validate without labels?

We use transparent proxy checks: ablation, synthetic benchmarks, weight sensitivity,
proof alignment, risk rates, production evidence, and top-10 sanity constraints.
These are not official accuracy metrics.

## 7. Can the output be reproduced?

Yes. The manifest records the commit, config and dependency hashes, environment,
and exact ranking command.

## 8. Does it run under CPU-only constraints?

Yes. It uses streaming JSONL/CSV processing and bounded top pools, with no GPU,
network call, embedding service, or external API.

## 9. What are the limitations?

Matching remains lexical, aliases are finite, timeline extraction is best-effort,
and no public relevance labels are available. Human review remains necessary.

## 10. What would you improve with more time?

With labeled judgments, we would tune weights against NDCG, expand schema-aware
timeline evidence, add fairness analysis, and test more role archetypes.
"""


def build_deck_materials(
    docs_dir: Path | str,
    config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    settings = config or {}
    target = Path(docs_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = generate_diagrams(target)
    documents = {
        "approach_deck": _deck(
            str(settings.get("project_title", "EvidenceRank — Candidate Proof Engine")),
            str(settings.get("hackathon_track", "INDIA RUNS Track 1")),
            bool(settings.get("include_speaker_notes", True)),
        ),
        "demo_script": _demo_script(),
        "judge_walkthrough": _walkthrough(),
        "submission_checklist": _checklist(),
        "faq_for_judges": _faq(),
    }
    for name, content in documents.items():
        path = target / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        paths[name] = path
    return paths
