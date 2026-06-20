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

Profile and rank with the firewall:

```powershell
python run.py --input data/input/candidates.jsonl --jd data/input/job_description.txt --profile-and-rank --top-k 100 --limit 5000 --batch-size 500 --enable-honeypot-firewall
```

Audit existing fingerprints without reranking:

```powershell
python run.py --audit-honeypots
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

## Safety note

**Risk flags are heuristic ranking signals, not accusations against real people.** They reduce ranking confidence and identify records for human review.

## Next feature

**Feature 4 - Evidence-Calibrated Hiring Intelligence**

The next feature should strengthen structured career evidence, temporal consistency, behavior calibration, JD-specific negative constraints, ablation testing, and final submission safety without adding external APIs or a UI.

See [docs/methodology.md](docs/methodology.md) for implementation details.
