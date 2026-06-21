# EvidenceRank — Judge Quick Start

EvidenceRank is a CPU-only, offline candidate ranking engine that verifies skill
claims against career evidence before producing explainable, risk-aware rankings.

## 90-second quick demo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py --quick-demo
```

Linux/macOS activation:

```bash
source .venv/bin/activate
```

The demo uses 20 synthetic candidates and writes results to `data/output/demo/`.

## Final ranking command

```powershell
python run.py --jd data/input/job_description.txt --rank --top-k 100 --enable-honeypot-firewall --enable-evidence-calibration
```

## Inspect these three files

1. `data/output/ranked_candidates.csv`
2. `data/output/EvidenceRank_Approach_Deck.pdf`
3. `data/output/score_breakdown.csv` or `top10_explanation_cards.md`

## Key differentiators

- **Candidate Proof Graph:** separates supported, weakly supported, and unsupported claims.
- **Honeypot Firewall:** detects suspicious evidence patterns without accusing candidates.
- **Evidence Calibration:** rewards production, retrieval/ranking, and evaluation depth.
- **Semantic-lite JD matching:** combines lexical relevance with offline word/character TF-IDF.

EvidenceRank is deterministic, streaming, memory-safe, and requires no API, GPU,
model download, or internet connection at runtime.

**Real hackathon dataset is not committed. Synthetic sample data is included for demo.**
