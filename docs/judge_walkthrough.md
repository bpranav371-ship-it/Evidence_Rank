# Judge Walkthrough

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
