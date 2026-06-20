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

# Feature 2 Methodology

## Deterministic JD parsing

The JD parser reads a plain-text job description once. It normalizes whitespace and punctuation, then applies an explicit AI/data/software skill dictionary. It returns required and preferred skills, seniority terms, domain terms, evaluation concepts, production concepts, retrieval/ranking concepts, experience ranges, and locations.

No model or external service is involved. Preferred skills are identified from local sections containing phrases such as “nice to have,” “preferred,” or “bonus.” Short or empty JDs return a valid profile with empty collections.

## Candidate Proof Graph

The proof graph distinguishes a claim from its evidence:

- **Supported:** the skill or an alias appears in the current title or career/project evidence.
- **Weakly supported:** it appears only in education or broad profile text.
- **Unsupported:** no matching evidence is found.

Evidence snippets are extracted directly from candidate fields and capped in length. The graph never invents accomplishments. It also calculates bounded scores for retrieval/ranking evidence, evaluation evidence, production evidence, AI/ML depth, and overall claim-to-evidence alignment.

## Evidence-supported skill matching

Canonical aliases connect related expressions. For example:

- RAG connects to retrieval-augmented generation, semantic search, embeddings, and retrievers.
- Ranking connects to learning-to-rank, recommender systems, NDCG, MRR, and MAP.
- Production readiness connects to deployment, APIs, monitoring, cloud, Docker, Kubernetes, scale, latency, and users.
- Evaluation connects to offline evaluation, A/B testing, precision, recall, experiments, and ranking metrics.

The matching remains lexical and deterministic. Synonyms are visible in source code and can be audited or extended.

## Baseline scoring

The score is a weighted sum:

| Component | Weight |
|---|---:|
| JD lexical and canonical-term relevance | 0.25 |
| Required-skill coverage | 0.20 |
| Candidate Proof Graph alignment | 0.25 |
| Retrieval/ranking/evaluation depth | 0.10 |
| Production readiness | 0.10 |
| Hireability and availability | 0.10 |

Configured Feature 1 anomaly penalties are subtracted, then the result is clamped to 0–1. Missing behavioral data uses a neutral 0.5 value so absence is not mistaken for bad behavior.

## Strict top-candidate reranking

The ranker streams every fingerprint and stores only the best bounded pool in a min-heap. By default, the pool contains 300 candidates. It then reranks only that pool with:

- stronger proof-alignment rewards;
- retrieval, ranking, and evaluation rewards;
- production-evidence rewards;
- penalties for unsupported required skills;
- a keyword-density penalty.

This second stage focuses computation on the candidates who can affect top-10 and top-100 quality.

## Output generation and validation

The pipeline produces:

- a compact ranked submission CSV;
- a detailed score-breakdown CSV;
- a JSONL proof audit for ranked candidates.

The validator checks required columns, continuous ranks, score range, unique IDs, non-empty reasoning, readability, and expected row count. The ranking command reports validation status before returning.

## CPU and memory safety

The JD is held once in memory. Candidate fingerprints are read one JSONL line at a time, scored, and discarded unless they enter the bounded shortlist. Only the shortlist and its proof graphs survive until output generation. Consequently, ranking memory grows with the configured shortlist size rather than with the 100,000-candidate dataset.

Feature 2 uses standard-library text operations and no embeddings, GPU, internet, or external APIs.

## Feature 2 boundaries addressed by Feature 3

- Impossible career timelines
- Zero-duration expert skills
- Experience/profile contradictions
- Research-only and service-only career penalties
- Title-chasing patterns
- Full keyword-stuffer and honeypot filtering

# Feature 3 Methodology

## Honeypot Firewall

The firewall is a deterministic confidence layer applied after normal candidate scoring. It does not replace relevance scoring and does not assume every unusual profile is fraudulent. Each rule produces a named flag, severity, evidence note derived from candidate fields, and bounded risk contribution.

The final report contains a 0-1 risk score, low/medium/high/severe level, recommended penalty, warning and severe flags, and a disqualification decision for only the strongest compound anomalies.

## Lightweight and deep analysis

Every fingerprint receives inexpensive streaming checks for:

- keyword density versus evidence alignment;
- many claims with weak evidence;
- explicit zero-duration expert patterns when available;
- response, activity, and availability risks;
- empty-profile indicators.

Only the bounded rerank pool receives deeper checks for title-career mismatch, seniority and experience conflicts, research-only production gaps, service-only profiles without relevant depth, unsupported JD requirements, and retrieval/evaluation/production contradictions.

Full evidence snippets are also generated only for this shortlist. This keeps runtime and memory proportional to the configured pool rather than the full candidate population.

## Zero-duration expert detection

The strongest form uses structured skill details when present, looking for expert or advanced proficiency with zero or near-zero duration. If structured details are unavailable, the rule uses only explicit textual patterns such as "expert ... 0 months." It does not infer a zero duration from missing information.

## Keyword stuffing

Keyword rules combine Feature 1 keyword density, number of claimed and detected skills, career-evidence length, and Candidate Proof Graph alignment. Dense vocabulary alone is not severe. Risk increases when it is paired with weak career proof.

## Title, career, and proof contradictions

The firewall checks whether:

- AI/ML titles have corresponding AI/ML career evidence;
- non-technical titles are paired with unsupported deep-AI claims;
- senior positioning has realistic experience and proof;
- research-heavy profiles show production evidence for a production-focused JD;
- service-company evidence contains relevant AI/retrieval/ranking depth;
- required, retrieval, evaluation, and production claims have proof-graph support.

## Risk-adjusted scoring

Feature 2 computes the base final score. Feature 3 applies:

```text
risk_adjusted_score = max(0, base_final_score - honeypot_penalty)
```

Penalty bands:

- low risk: 0.00-0.03;
- medium risk: 0.04-0.10;
- high risk: 0.11-0.25;
- severe risk: 0.30-0.50.

Severe profiles are disqualified only when configured and supported by a strong or compound anomaly such as an empty profile, impossible experience, or zero-duration expertise combined with stuffing and weak proof.

## Strict top-10 reranking

The top risk pool is re-evaluated with full proof graphs. Severe profiles cannot enter the top 10. High-risk profiles require exceptionally strong proof alignment; otherwise a top-10 guard penalty pushes them lower. This targets the hackathon's top-rank-sensitive metrics without filtering the entire population aggressively.

## Audit outputs

The system writes:

- `honeypot_audit.json` for aggregate risk counts and top-rank summaries;
- `honeypot_flags.csv` for candidate-level flags and evidence reasons;
- `rerank_audit_top100.csv` for original and adjusted rank comparison.

Audit files are produced incrementally where possible. Only shortlist candidate objects remain in memory.

## Limitations and fairness

The fingerprint format does not preserve every original role date or structured skill-duration field. Timeline and zero-duration checks therefore use structured values when available and conservative text fallbacks otherwise.

**The firewall does not claim that a candidate is fake. It detects profile-risk patterns that may reduce ranking confidence. Human review is still required.**
