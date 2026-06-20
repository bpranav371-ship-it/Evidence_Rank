# EvidenceRank — Candidate Proof Engine

**Hackathon:** INDIA RUNS Track 1 — Intelligent Candidate Discovery

EvidenceRank is a CPU-only, offline candidate intelligence system. Feature 1 builds a trustworthy, reusable fingerprint for every candidate while streaming the source dataset in low-memory mode. Later features will use these fingerprints for evidence-based ranking, consistency checks, hireability scoring, and auditable explanations.

## Why this is different from keyword matching

A raw skills list is only a claim. EvidenceRank keeps claimed skills separate from career evidence, profile context, behavioral signals, availability, and basic data-quality indicators. The current profiler calculates a lightweight `skill_evidence_hint_score` by checking whether claimed or inferred skills appear in career and project evidence. It does not yet make hiring or ranking decisions.

## System constraints

- CPU-only and offline; no APIs or network calls
- Streams JSONL and CSV one record at a time
- Streams Parquet in configurable batches
- Uses `ijson` for memory-safe large JSON arrays when installed
- Default batch size: 1,000
- Writes fingerprints immediately to JSONL
- Keeps counters rather than the full candidate collection in memory
- Logs progress every 10,000 candidates
- Supports `--limit` for safe test runs
- Caps compact candidate text at 12,000 characters by default

## Setup

```bash
cd EvidenceRank
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Place the dataset at `data/input/candidates.jsonl`, or pass any supported path with `--input`.

## Run commands

```bash
python run.py --input data/input/candidates.jsonl
python run.py --input data/input/candidates.jsonl --limit 5000
python run.py --input data/input/candidates.jsonl --batch-size 500
python run.py --input data/input/candidates.csv --limit 1000
```

Run tests:

```bash
python -m pytest
```

The tests are also compatible with the standard library test runner:

```bash
python -m unittest discover -s tests
```

## Output files

- `data/output/candidate_fingerprints.jsonl`: one deterministic candidate fingerprint per line
- `data/output/schema_report.json`: detected format, record count, columns, nested field paths, likely field mappings, and warnings
- `data/output/profiler_summary.json`: aggregate quality metrics, errors, common missing fields/anomalies, runtime, and observed memory

Each run replaces these three output files so results cannot accidentally mix across datasets.

## Configuration

Edit `config.yaml` to change the default input, output directory, batch size, progress frequency, memory-safe mode marker, or text cap. CLI `--input`, `--batch-size`, and `--output-dir` override configuration values.

For JSONL and CSV, batch size does not cause records to accumulate in memory; records are still yielded one at a time. It controls Parquet batch reads and is reserved for later bounded-batch transforms.

## Current feature status

Implemented:

- Format and schema discovery used by the profiler before alias fallbacks
- Streaming CSV, JSONL, JSON, and Parquet loaders
- Deterministic text normalization
- Candidate fingerprint generation
- Basic safe anomaly flags
- Incremental JSONL feature storage
- Counter-based run summaries
- CLI limits and configurable batches
- Unit and end-to-end tests

Not implemented yet:

- Candidate ranking
- Full honeypot detection
- Candidate Proof Graph
- Dashboard
- LLM-generated explanations

## Low-memory design

At steady state the pipeline holds one source record, one fingerprint, a small schema sample, and aggregate counters. It never constructs a DataFrame containing all candidates and never accumulates fingerprints in a list. JSONL/CSV memory usage is therefore approximately constant as the dataset grows. Large JSON arrays require `ijson`; without it, the loader emits a warning before using the standard-library fallback.

## Next planned features

1. Baseline JD-to-candidate ranker
2. Candidate Proof Graph
3. Honeypot Firewall
4. Two-Stage Evidence Ranker
5. Hireability Intelligence
6. Evidence-Cited Explanations
7. CSV submission validator
8. Optional Recruiter Audit Studio

See [docs/methodology.md](docs/methodology.md) for scoring definitions and Feature 1 boundaries.
