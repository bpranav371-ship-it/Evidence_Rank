# Ranked Candidate Submission Format

The final CSV must contain exactly:

```text
candidate_id,rank,score,reasoning
```

Rules:

- `rank` starts at 1 and is continuous.
- `score` is numeric and between 0 and 1.
- Rows are sorted by score descending.
- `candidate_id` is non-empty and unique.
- `reasoning` is non-empty, specific, and grounded in profile evidence.

Validate with:

```powershell
python run.py --validate-final-submission --top-k 100
```
