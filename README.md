# EvidenceRank — Candidate Proof Engine

An offline, evidence-grounded candidate ranking system for INDIA RUNS Track 1.

**Python:** 3.11–3.12
**License:** MIT License placeholder
**Build/Test:** 75 tests passing

## What This Is

- Ranks candidates beyond résumé keyword overlap by checking whether claimed skills have career evidence.
- Combines semantic-lite TF-IDF matching, a Candidate Proof Graph, a Honeypot Firewall, and evidence calibration.
- Runs locally on CPU with streaming input, incremental output, deterministic rules, and bounded reranking pools.
- Designed to process 100,000+ candidate profiles without loading the full dataset into memory.
- Implemented milestones: Feature 1 profiler, Feature 2 proof ranker, Feature 3 firewall, Feature 4 calibration, Feature 5 submission suite, Feature 6 judge materials, and Feature 7 submission freeze.

## System Requirements

- Python `>=3.11,<3.13`
- Windows, Linux, or macOS
- CPU-only; no GPU or external API required
- 4 GB RAM minimum; 8 GB recommended for comfortable operation
- Approximately 1 GB free disk space for the environment and generated artifacts, excluding the private dataset

## Installation

```bash
git clone https://github.com/bpranav371-ship-it/Evidence_Rank.git
cd Evidence_Rank
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py --help
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py --help
```

For an exact documented dependency snapshot, use `requirements-freeze.txt`.

## 30-Second Quick Start

Run the complete profiler and ranker on tracked synthetic data:

```bash
python run.py --quick-demo --top-k 5
```

Validate the demo output:

```bash
python run.py --validate-final-submission --top-k 5 --output-dir data/output/demo
```

Expected outputs are written to `data/output/demo/ranked_candidates.csv`, `data/output/demo/score_breakdown.csv`, and `data/output/demo/top_candidate_proofs.jsonl`.

## Architecture Overview

EvidenceRank streams candidate records into compact fingerprints, parses the job description once, scores candidates incrementally, and retains only bounded shortlists for deeper checks. Ranking remains CPU-only, offline, and deterministic.

Major stages:

1. **Profile** — discover schema and create candidate fingerprints incrementally.
2. **Rank** — combine lexical and semantic-lite JD relevance with required-skill and proof scores.
3. **Firewall** — identify explainable profile-risk patterns and protect top ranks.
4. **Calibrate** — assess career depth, JD constraints, hireability signals, and top-10 readiness.
5. **Package / Freeze** — validate, hash, document, and bundle submission artifacts.

See `docs/architecture_diagram.mmd` for the Mermaid architecture source.

## CLI Usage

Profile candidates:

```bash
python run.py --input data/input/candidates.jsonl --profile-only --batch-size 500
```

Rank existing fingerprints with the full safeguards:

```bash
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration
```

Run the synthetic demo:

```bash
python run.py --quick-demo --top-k 5
```

Run offline benchmark cases:

```bash
python run.py --jd data/input/job_description.txt --run-benchmark
```

Run the four-variant ablation:

```bash
python run.py --jd data/input/job_description.txt --run-ablation --top-k 100
```

Export the approach deck:

```bash
python run.py --export-deck --format all
```

Freeze the final submission:

```bash
python run.py --freeze-submission --top-k 100
```

## API Usage

API server is not part of the default submission build; the project is submitted as an offline CLI ranking system.

## Configuration

Runtime settings are in `config.yaml`. The most important controls are:

- `semantic_matching.enabled` — enables local word and character TF-IDF relevance.
- `honeypot_firewall.enabled` — sets the default risk-aware reranking behavior.
- `evidence_calibration.enabled` — sets the default bounded calibration behavior.
- `batch_size` — controls bounded candidate-loading batches.
- `reproducibility.reference_year` — fixes time-sensitive ranking logic to a deterministic reference.

CLI flags can enable firewall and calibration without changing the configuration file.

## Output Files

| File | Description | When Generated | Judge Relevance |
|---|---|---|---|
| `ranked_candidates.csv` | Final `candidate_id,rank,score,reasoning` submission | Ranking | Primary answer |
| `score_breakdown.csv` | Component, risk, and calibration scores | Ranking | Scoring transparency |
| `top_candidate_proofs.jsonl` | Evidence links and proof graphs for top candidates | Ranking | Evidence verification |
| `honeypot_audit.json` | Aggregate deterministic risk audit | Firewall-enabled ranking | Top-rank safety |
| `evidence_calibration_report.json` | Calibration and readiness summary | Calibration-enabled ranking | Evidence quality |
| `final_submission_safety_report.json` | Format and ranking safety checks | Validation/freeze | Submission readiness |
| `EvidenceRank_Approach_Deck.pptx` | Generated 12-slide project deck | Deck export/freeze | Judge presentation |
| `EvidenceRank_Approach_Deck.pdf` | Generated PDF deck | PDF/all deck export | Submission deck |

Generated files are written under `data/output/` and are intentionally ignored by Git.

## Key Features

- Semantic-lite JD matching with offline word and character TF-IDF plus lexical fallback.
- Candidate Proof Graph separating supported, weakly supported, and unsupported skills.
- Honeypot Firewall applying explainable risk flags and bounded penalties.
- Evidence Calibration rewarding career-backed retrieval, evaluation, and production depth.
- Hireability Calibration treating missing behavioral signals neutrally rather than as automatic failure.
- Deterministic Hinglish normalization for common Indian profile-language variants.
- Streaming schema discovery and incremental JSONL output for memory-safe profiling.
- Benchmarks, ablation, sensitivity checks, reproducibility manifests, and submission freezing.

## Performance

- Candidate profiling and baseline scoring stream records instead of retaining full profiles.
- Deep firewall and calibration logic operates only on bounded shortlist pools.
- Memory and runtime can be measured on the local machine with:

```bash
python run.py --jd data/input/job_description.txt --profile-runtime --top-k 100
```

The generated `data/output/runtime_profile_report.json` records candidate count, runtime, peak RSS, file sizes, and a 100,000-candidate projection. Results vary with profile length, storage speed, and enabled safeguards.

## Troubleshooting

1. **Python version mismatch:** install Python 3.11 or 3.12, then recreate the environment with `python -m venv .venv`.
2. **Dependency import error:** activate the virtual environment and rerun `python -m pip install -r requirements.txt`.
3. **Parquet input fails:** install optional support with `python -m pip install ".[parquet]"`.

## Submission Checklist

- GitHub repository: `https://github.com/bpranav371-ship-it/Evidence_Rank`
- Final `data/output/ranked_candidates.csv`
- `data/output/EvidenceRank_Approach_Deck.pdf` or PPTX fallback
- Optional score breakdown, proof, risk, calibration, and reproducibility audit outputs
- Confirm `python run.py --freeze-submission --top-k 100` passes before upload

## License

MIT License placeholder.
