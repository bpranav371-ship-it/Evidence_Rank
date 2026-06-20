# EvidenceRank - Candidate Proof Engine

**Hackathon:** INDIA RUNS Track 1 - Intelligent Candidate Discovery

EvidenceRank is a CPU-only, offline candidate ranking system designed for roughly 100,000 professional profiles. It separates skill claims from profile evidence, streams candidates in low-memory mode, and keeps only bounded reranking pools in memory.

## Feature status

Completed:

- **Feature 1 - Streaming Candidate Profiler**
  - Schema discovery for CSV, JSON, JSONL, and Parquet
  - Low-memory candidate loading
  - Deterministic candidate fingerprints
  - Incremental JSONL feature storage
- **Feature 2 - Baseline JD Ranker + Candidate Proof Graph**
  - Rule-based JD parsing
  - Evidence-supported skill matching
  - Explainable weighted scoring
  - Strict shortlist reranking
  - Ranked CSV, score breakdown, proof output, and validation
- **Feature 3 - Honeypot Firewall + Risk-Aware Reranking**
  - Explainable anomaly and contradiction rules
  - Bounded risk scores and penalties
  - Lightweight streaming checks plus deep shortlist analysis
  - Strict top-10 risk protection
  - Honeypot and reranking audit outputs
- **Feature 4 - Evidence-Calibrated Hiring Intelligence + Ablation Safety Suite**
  - Structured career evidence and timeline extraction
  - JD-specific positive and negative constraints
  - Calibrated behavioral hireability signals
  - Bounded evidence calibration for the top candidate pool
  - Four-variant proxy ablation reports
  - Final submission safety validation
- **Feature 5 - Submission-Grade Evaluation, Reproducibility, and Packaging Suite**
  - Eight deterministic offline benchmark cases
  - Controlled weight-sensitivity analysis
  - Runtime, memory, and 100,000-candidate projections
  - Git/config/environment reproducibility metadata
  - Clean submission ZIP generation and one-command final checks
- **Feature 6 - Judge Demo Polish + Approach Deck Material Generator**
  - Evidence-grounded top-10 explanation cards
  - Twelve-slide approach deck content and a timed demo script
  - Judge walkthrough, FAQ, and final submission checklist
  - Mermaid architecture, scoring, and evidence-flow diagrams
  - Safe judge demo packet ZIP and automated demo readiness check
- **Feature 7 - Final Deck Export + Submission Freeze**
  - Offline 12-slide PPTX and optional PDF export
  - Final one-page summary and submission guide
  - SHA-256 hashes for important submission artifacts
  - Allowlisted final submission bundle
  - Submission freeze manifest and blocking readiness report

Not implemented:

- Dashboard or frontend
- External APIs or LLM-generated explanations

## Why EvidenceRank is not keyword matching

EvidenceRank keeps three ideas separate:

1. What the candidate claims
2. What their title and career history support
3. Whether behavioral, availability, and profile-risk signals make the ranking trustworthy

The Candidate Proof Graph classifies skills as supported, weakly supported, or unsupported. The Honeypot Firewall then detects suspicious combinations such as dense buzzwords with weak evidence, unsupported senior AI positioning, experience contradictions, or retrieval/evaluation claims without proof.

## System constraints

- CPU-only and offline
- No API or network calls during profiling or ranking
- JSONL and CSV streamed one record at a time
- Parquet read in configurable batches
- Default batch size: 1,000
- Fingerprints written immediately to JSONL
- Ranking keeps only bounded top pools in a heap
- Full candidate DataFrames are never created
- Full evidence snippets and deep firewall checks run only on the shortlist

## Setup

```powershell
cd Evidence_Rank
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Place candidate data and the job description in `data/input/`. Raw input and generated output files are ignored by Git.

## Commands

Profile only:

```powershell
python run.py --input data/input/candidates.jsonl --profile-only
python run.py --input data/input/candidates.jsonl --profile-only --limit 5000 --batch-size 500
```

Rank existing fingerprints without the firewall:

```powershell
python run.py --jd data/input/job_description.txt --rank --top-k 100
```

Rank with the firewall:

```powershell
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall
```

Rank with firewall and evidence calibration:

```powershell
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration
```

Profile and rank with the firewall:

```powershell
python run.py --input data/input/candidates.jsonl --jd data/input/job_description.txt --profile-and-rank --top-k 100 --limit 5000 --batch-size 500 --enable-honeypot-firewall
```

Audit existing fingerprints without reranking:

```powershell
python run.py --audit-honeypots
```

Run the proxy ablation suite:

```powershell
python run.py --jd data/input/job_description.txt --run-ablation --top-k 100
```

Validate final submission artifacts:

```powershell
python run.py --validate-final-submission --top-k 100
```

Run Feature 5 evaluation and packaging tools:

```powershell
python run.py --jd data/input/job_description.txt --run-benchmark
python run.py --jd data/input/job_description.txt --run-weight-sensitivity --top-k 100
python run.py --jd data/input/job_description.txt --profile-runtime --top-k 100
python run.py --build-reproducibility-manifest
python run.py --build-submission-package --top-k 100
python run.py --final-submit-check --top-k 100
```

Build Feature 6 judge materials:

```powershell
python run.py --build-deck-materials
python run.py --explain-top-candidates --top-n 10
python run.py --build-demo-pack --top-k 100
python run.py --judge-demo-check
python run.py --build-all-submission-artifacts --top-k 100
```

Export and freeze the final submission:

```powershell
python run.py --export-deck --format pptx
python run.py --export-deck --format pdf
python run.py --build-final-submission-bundle --top-k 100
python run.py --freeze-submission --top-k 100
```

Recommended final workflow:

```powershell
# 1. Build fingerprints once
python run.py --input data/input/candidates.jsonl --profile-only --batch-size 500

# 2. Generate the final ranked CSV
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration

# 3-6. Validate and collect optional evidence
python run.py --validate-final-submission --top-k 100
python run.py --jd data/input/job_description.txt --run-ablation --top-k 100
python run.py --jd data/input/job_description.txt --run-benchmark
python run.py --jd data/input/job_description.txt --run-weight-sensitivity --top-k 100

# 7. Build the final internal package
python run.py --final-submit-check --top-k 100
```

Optional risk controls:

```powershell
python run.py --jd data/input/job_description.txt --rank --enable-honeypot-firewall --strict-top-n 10 --risk-rerank-pool-size 500
```

Run tests:

```powershell
python -m pytest
python -m unittest discover -s tests
```

## Outputs

Feature 1:

- `data/output/candidate_fingerprints.jsonl` - one normalized fingerprint per candidate
- `data/output/schema_report.json` - source format, record count, fields, and likely mappings
- `data/output/profiler_summary.json` - profiling errors, averages, runtime, and memory observations

Feature 2:

- `data/output/ranked_candidates.csv` - candidate ID, rank, final score, and concise reasoning
- `data/output/score_breakdown.csv` - component scores, penalties, risk scores, and rerank status
- `data/output/top_candidate_proofs.jsonl` - proof graphs and evidence snippets

Feature 3:

- `data/output/honeypot_audit.json` - aggregate risk and top-rank summaries
- `data/output/honeypot_flags.csv` - candidate-level flags and reasons
- `data/output/rerank_audit_top100.csv` - original versus risk-adjusted ranks

Feature 4:

- `data/output/evidence_calibration_report.json` - bounded-pool evidence and readiness summary
- `data/output/jd_constraints_report.json` - role archetype, priorities, and negative constraints
- `data/output/hireability_audit.csv` - calibrated behavior and availability components
- `data/output/ablation_report.json` - proxy metrics across four ranking variants
- `data/output/ablation_summary.csv` - compact ablation comparison
- `data/output/sanity_checks_report.json` - deterministic behavioral sanity checks
- `data/output/final_submission_safety_report.json` - blocking errors and upload warnings

Feature 5:

- `data/output/benchmark_report.json` and `benchmark_summary.csv` - synthetic sanity cases
- `data/output/weight_sensitivity_report.json` and `weight_sensitivity_summary.csv` - controlled variant stability
- `data/output/runtime_profile_report.json` - measured runtime, RSS, and scale projection
- `data/output/reproducibility_manifest.json` - Git, Python, config, and dependency hashes
- `data/output/final_submission_manifest.json` - package contents and readiness state
- `data/output/approach_summary.md` - concise judge-facing architecture summary
- `data/output/final_reproduction_command.txt` - exact regeneration commands
- `data/output/submission_package.zip` - clean internal submission bundle without raw data

Feature 6:

- `docs/approach_deck.md` - twelve-slide judge-facing deck content
- `docs/demo_script.md` - concise 2–3 minute presentation script
- `docs/judge_walkthrough.md` - recommended artifact review order
- `docs/submission_checklist.md` - final hackathon checklist
- `docs/faq_for_judges.md` - concise technical answers to likely questions
- `docs/*_diagram.mmd` - Mermaid architecture, scoring, and evidence-flow sources
- `data/output/top10_explanation_cards.md` and `.json` - evidence-grounded cards
- `data/output/judge_demo_packet.md` - consolidated judge handout
- `data/output/demo_packet_manifest.json` - packet allowlist and missing files
- `data/output/demo_packet.zip` - safe demo bundle without raw candidate data
- `data/output/judge_demo_check_report.json` - demo readiness result

Feature 7:

- `data/output/EvidenceRank_Approach_Deck.pptx` - final 12-slide approach deck
- `data/output/EvidenceRank_Approach_Deck.pdf` - offline PDF deck when ReportLab is installed
- `data/output/pdf_export_instructions.txt` - graceful PDF fallback instructions
- `data/output/EvidenceRank_One_Page_Summary.md` - concise project summary
- `data/output/EvidenceRank_Final_Submission_Guide.md` - upload and regeneration guide
- `data/output/final_artifact_hashes.json` - SHA-256 hashes and file sizes
- `data/output/submission_freeze_manifest.json` - locked bundle and hash snapshot
- `data/output/final_submission_bundle.zip` - allowlisted final backup bundle
- `data/output/final_submission_freeze_report.json` - final readiness result

## Scoring

The Feature 2 baseline score is:

```text
0.25 * JD relevance
+ 0.20 * must-have skill coverage
+ 0.25 * proof alignment
+ 0.10 * retrieval/ranking/evaluation depth
+ 0.10 * production readiness
+ 0.10 * hireability
- configured basic anomaly penalties
```

When the firewall is enabled:

```text
risk_adjusted_score = max(0, base_final_score - honeypot_penalty)
```

When evidence calibration is enabled:

```text
calibrated_final_score =
    risk_adjusted_score
    + calibration_bonus
    - calibration_penalty
```

The bonus is capped at 0.08 and the penalty at 0.15. Calibration runs only on
the configurable top pool (700 by default), so the full 100,000-candidate
ranking remains streaming and bounded-memory.

Penalty bands are bounded by risk level:

- low: 0.00-0.03
- medium: 0.04-0.10
- high: 0.11-0.25
- severe: 0.30-0.50

Missing behavior or availability data is neutral to mildly risky, not automatically disqualifying. Severe disqualification requires a strong or compound anomaly.

## Risks detected

- Explicit zero-duration expert claims when structured or textual evidence exists
- Excessive keyword density and buzzword stuffing
- Many claimed skills with weak career proof
- Negative, impossible, or suspicious experience values
- Seniority and title-career contradictions
- Research-only profiles without production evidence
- Service-only profiles without relevant AI/retrieval depth
- Unsupported required, retrieval, evaluation, or production claims
- Low response, stale activity, and unclear availability signals

## Limitations

- Skill aliases are deterministic and intentionally finite.
- Structured zero-duration checks work only when duration/proficiency data exists in the fingerprint or is explicitly stated in text.
- Feature 1 fingerprints do not preserve every original role-date field, so timeline checks are conservative and best-effort.
- Term overlap is lexical; no embedding model is used.
- Reasoning is templated from real scores and evidence, not generated by an LLM.
- Career and timeline extraction is lexical and best-effort because older fingerprints
  do not preserve every original structured role field.
- Ablation metrics are proxy sanity metrics because the challenge does not provide
  public ground-truth relevance labels.
- Offline benchmark and weight-sensitivity results are also sanity checks, not
  official leaderboard or ground-truth metrics.

## Safety note

**Risk flags are heuristic ranking signals, not accusations against real people.** They reduce ranking confidence and identify records for human review.

## Fairness note

Hireability and risk signals are ranking-confidence signals, not final hiring
decisions. Human review is required.

## What to upload

- The GitHub repository
- The approach deck PDF
- `ranked_candidates.csv`
- Optionally keep `submission_package.zip` as an internal backup bundle

The ZIP intentionally excludes raw candidates, input files, fingerprints,
secrets, Git metadata, caches, and virtual environments.

## Final project workflow

```powershell
# 1. Profile
python run.py --input data/input/candidates.jsonl --profile-only --batch-size 500

# 2. Rank
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration

# 3. Final safety and submission package
python run.py --final-submit-check --top-k 100

# 4. Demo and deck materials
python run.py --build-demo-pack --top-k 100

# 5. Judge readiness check
python run.py --judge-demo-check

# 6. Rebuild every final artifact in one command
python run.py --build-all-submission-artifacts --top-k 100

# 7. Export and freeze
python run.py --export-deck --format pptx
python run.py --freeze-submission --top-k 100
```

Judges should inspect `ranked_candidates.csv`, `score_breakdown.csv`,
`top10_explanation_cards.md`, `final_submission_safety_report.json`, and
`reproducibility_manifest.json` first.

The final deck PDF should be created manually from `docs/approach_deck.md`.
Copy the twelve slide sections into PowerPoint, Google Slides, Marp, or another
presentation tool, render the Mermaid diagrams where useful, and export to PDF.

Feature 7 can also create the deck directly:

```powershell
python run.py --export-deck --format pptx
python run.py --export-deck --format pdf
```

The recommended hackathon uploads are:

- GitHub repository link
- `data/output/ranked_candidates.csv`
- `data/output/EvidenceRank_Approach_Deck.pdf` or `.pptx`
- Optionally `data/output/final_submission_bundle.zip` as a private backup

See [docs/methodology.md](docs/methodology.md) for implementation details.
