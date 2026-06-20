# EvidenceRank — Candidate Proof Engine

Approach deck material for **INDIA RUNS Track 1**.

> Convert this Markdown into PPT/PDF using any presentation tool. Mermaid source files in this directory can be rendered by GitHub or Mermaid-compatible tools.

---

## Slide 1 — EvidenceRank — Candidate Proof Engine

- INDIA RUNS Track 1
- CPU-only, offline candidate ranking for approximately 100,000 profiles
- Built for evidence-backed, explainable, and reproducible selection

**Speaker notes:** Open with the one-line idea: do not just match skills—prove them.

---

## Slide 2 — The problem

- Traditional résumé matching trusts self-reported keywords
- High keyword overlap can hide weak or missing career proof
- Recruiters need reliable top-10 candidates, not merely a large shortlist

**Speaker notes:** Frame the task as ranking confidence, not only text similarity.

---

## Slide 3 — Why keyword matching fails

- Keyword stuffing can outrank genuine experience
- Hidden gems may describe strong work in plain language
- Skill claims are not connected to projects, deployment, or evaluation
- No protection exists against contradictory or suspicious profiles

**Speaker notes:** Use the keyword-stuffer versus hidden-gem benchmark example.

---

## Slide 4 — Core idea: prove the match

- Create a compact fingerprint for every candidate
- Separate claimed skills from career evidence
- Rank with proof, production depth, evaluation, risk, and constraints
- Explain every top result using fields already present in the profile

**Speaker notes:** Emphasize deterministic and auditable logic.

---

## Slide 5 — System architecture

- Streaming profiler keeps full-dataset memory use bounded
- JD parsing and proof graphs remain fully local
- Deep risk and calibration work runs only on bounded top pools
- See `architecture_diagram.mmd` for the end-to-end flow

**Speaker notes:** Walk left-to-right from dataset to final CSV and audits.

---

## Slide 6 — Candidate Proof Graph

- Supported: direct title, project, achievement, or career evidence
- Weakly supported: broad profile or education mention
- Unsupported: claim exists without matching evidence
- Short snippets show exactly what the system found

**Speaker notes:** This is the clearest differentiator from a keyword matcher.

---

## Slide 7 — Honeypot Firewall

- Detects keyword stuffing, zero-duration expertise, and contradictions
- Assigns explainable low, medium, high, or severe risk
- Applies bounded penalties instead of aggressive blanket deletion
- Protects the top 10 with stricter deterministic checks

**Speaker notes:** Risk flags are confidence signals, not accusations.

---

## Slide 8 — Evidence Calibration

- Rewards retrieval, ranking, evaluation, and production proof
- Checks JD-specific positive and negative constraints
- Uses hireability signals modestly; missing behavior stays neutral
- Calibration cannot replace weak technical evidence

**Speaker notes:** Explain that the adjustment is bounded and top-pool-only.

---

## Slide 9 — Evaluation and safety

- Four-variant ablation compares keyword, baseline, risk, and calibration
- Eight synthetic benchmark cases test intended ranking behavior
- Weight sensitivity checks that results are not tied to one fragile setup
- Final validation checks rank continuity, scores, risks, and files

**Speaker notes:** Be explicit that these are proxy sanity checks without public labels.

---

## Slide 10 — Submission outputs

- `ranked_candidates.csv` is the final answer
- `score_breakdown.csv` exposes component scores and penalties
- Proof, honeypot, calibration, runtime, and reproducibility audits are included
- Submission and demo ZIPs use explicit safe allowlists

**Speaker notes:** Show the top candidate card and score breakdown side by side.

---

## Slide 11 — Performance and reproducibility

- Runs locally on CPU with no API, network, GPU, or LLM dependency
- Measured peak RSS is tens of MB on the verification run
- Projected calibrated ranking for 100,000 fingerprints is about 3–4 minutes
- A manifest records Git commit, config hashes, environment, and exact command

**Speaker notes:** Quote the latest runtime report rather than promising a universal time.

---

## Slide 12 — Impact

- Recruiters receive evidence-backed rankings instead of keyword counts
- Top candidates come with concise proof and transparent concerns
- Risk-aware reranking improves confidence in the most visible positions
- Human review remains the final hiring decision

**Speaker notes:** Close with trustworthy ranking, reproducibility, and practical CPU deployment.
