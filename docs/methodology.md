# Feature 1 Methodology

## Why streaming is used

The released pool contains roughly 100,000 profiles and may expand later. Loading the complete source, normalized text, and derived features together would create unnecessary memory pressure on a 16 GB laptop. EvidenceRank reads one JSONL/CSV record at a time, or one bounded Parquet batch at a time, and writes every completed fingerprint immediately.

This makes normal memory use depend on the size of one candidate rather than the size of the full dataset. Only small counters, discovered schema paths, and summary totals survive between records.

## CandidateFingerprint

A `CandidateFingerprint` is a deterministic intermediate representation. It separates:

- compact profile text;
- claimed and lightly inferred technical skills;
- career and project evidence;
- education;
- behavioral and availability signals;
- basic missing-data and keyword-density indicators.

This representation is deliberately ranking-neutral. Future scoring modules can consume it without repeatedly parsing the original nested records.

## Why raw skill lists are noisy

Skill fields are self-reported and can contain irrelevant, outdated, or unsupported claims. The profiler therefore preserves the claims but also creates a separate career-evidence field and a preliminary evidence hint. It does not treat skill count as candidate quality.

## Profile completeness score

The score is the fraction of ten important evidence groups found:

1. candidate ID;
2. summary or headline;
3. current title;
4. skills;
5. career history;
6. education;
7. years of experience;
8. location;
9. behavioral signals;
10. availability signals.

The result is clamped to the range 0–1. It is a data-availability measure, not a hiring score.

## Skill evidence hint score

The profiler extracts explicit skill names and lightly inferred technical terms. For each claim, it checks whether the normalized phrase—or all meaningful tokens in that phrase—appears in career or project evidence. The score is:

`supported claimed skills / total claimed skills`

It is clamped to 0–1. This is intentionally simple and explainable. Synonym graphs, duration weighting, assessments, endorsements, recency, and negative evidence belong to later features.

## Keyword density score

The score counts occurrences of a fixed, transparent technical vocabulary and divides that count by the number of normalized profile tokens. It is clamped to 0–1. The basic anomaly flag activates only for sufficiently long profiles with unusually concentrated technical vocabulary.

## Intentionally excluded from Feature 1

- JD-specific relevance scoring or final ranking
- Full timeline and honeypot consistency checks
- Product-company or consulting-career judgments
- Behavioral hireability scoring
- Candidate-to-skill evidence graphs
- Learned embeddings or supervised models
- LLM calls and generated explanations
- Submission CSV generation or dashboard UI

These boundaries keep the foundation reusable and make later ranking changes independently testable.
