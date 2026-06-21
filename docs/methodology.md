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
- Research-only production gaps and shallow-project evidence checks
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

Only the bounded rerank pool receives deeper checks for title-career mismatch, seniority and experience conflicts, research-only production gaps, shallow project evidence, unsupported JD requirements, and retrieval/evaluation/production contradictions.

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
- AI/ML claims contain relevant role, project, and production depth;
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

# Feature 4 Methodology

## Career evidence extraction

Feature 4 extracts titles, seniority, explicit experience mentions, calendar
years, companies, production terms, retrieval/ranking terms, evaluation terms,
leadership terms, and project language from existing fingerprints. The
extractor is deterministic and never invents missing career facts. New
fingerprints store a compact `career_evidence_v2`; older fingerprints are
parsed on demand inside the bounded calibration pool.

Career depth combines evidence length, title variety, duration evidence,
projects, and ownership language. Separate production, retrieval, evaluation,
leadership, and consistency scores remain visible for audit.

## JD constraints

The JD constraint layer identifies a role archetype and separates core hard
skills from preferred supporting terms. For a retrieval/ranking AI role, core
constraints emphasize Python, embeddings, vector infrastructure, retrieval,
ranking, and evaluation. Broader technologies and individual metrics remain
preferred or top-10 signals rather than becoming an unrealistic all-or-nothing
checklist.

Negative constraints include missing must-have evidence, keyword-only claims,
research without production, shallow project evidence behind AI claims, and absent
retrieval, evaluation, or production proof. One weak constraint does not
disqualify a candidate.

## Hireability calibration

Response rate, recent activity, open-to-work status, interview completion,
relocation flexibility, and notice period are converted into bounded component
scores. Missing behavior returns a neutral score near 0.50. Hireability has a
small weight and cannot compensate for weak technical proof.

## Evidence calibration

Calibration combines proof alignment, career depth and consistency, JD
constraint match, production/retrieval/evaluation depth, bounded hireability,
and honeypot risk. It produces an evidence confidence score and strict top-10
readiness score.

```text
calibrated_final_score =
    risk_adjusted_score + calibration_bonus - calibration_penalty
```

The bonus is capped at 0.08 and penalty at 0.15. Keyword-only profiles,
unsupported core requirements, and absent JD-critical evidence receive
penalties. Calibration is applied only to the top 700 candidates by default.

## Ablation testing

The suite compares:

1. keyword-only overlap;
2. Feature 2 baseline;
3. baseline plus firewall;
4. baseline plus firewall plus calibration.

It reports proof alignment, risk, evidence confidence, unsupported requirement
rate, stuffing rate, production/retrieval evidence rates, keyword-top-100
overlap, top-10 readiness, and severe top-10 count.

These are proxy sanity metrics because no public ground-truth relevance labels
are provided. They demonstrate behavioral coherence, not benchmark accuracy.

## Submission safety

The safety validator checks row count, rank continuity, score range and order,
duplicates, reasoning completeness, score flatness, disqualified candidates,
severe top-10 risk, empty-profile flags, proof artifacts, risk audits, and
calibration reports. Blocking errors fail the command; non-blocking concerns
are reported as warnings and recommended actions.

## Performance and fairness

The full dataset remains streamed. Only lightweight fingerprints and a bounded
top pool are retained. Deep career, proof, risk, and calibration work is
restricted to the configured shortlist.

**Hireability and risk signals are used only as ranking confidence signals.
They should not be treated as final hiring decisions. Human review is
required.**

# Feature 5 Methodology

## Offline benchmark cases

Feature 5 evaluates eight fixed synthetic profiles: a production retrieval
engineer, keyword stuffer, research-only candidate, service-only candidate,
general ML engineer, low-keyword hidden gem, severe honeypot, and candidate
with missing behavior signals. The cases run through the same proof, firewall,
and calibration code as normal ranking, but never require the private dataset.

The checks focus on relative behavior: evidence should beat claims, severe
risk should not win, production depth should matter for a production JD, and
missing behavior data should remain neutral rather than destructive.

## Proxy evaluation without labels

The benchmark, ablation, and sensitivity reports measure deterministic
behavior rather than relevance accuracy. They use proof alignment, risk,
unsupported requirements, production/retrieval evidence, top-10 readiness,
rank overlap, and score spread.

**The benchmark and ablation results are sanity checks, not official
leaderboard metrics, because the challenge does not provide public
ground-truth labels.**

## Weight sensitivity

Eight variants alter weights only in memory: default, proof-heavy,
production-heavy, retrieval/evaluation-heavy, light hireability,
strict firewall, light calibration, and a keyword-only reference. The source
configuration is deep-copied and never rewritten. Each variant records overlap
with the default result and ranking-quality proxy metrics. A failed variant is
reported as a warning rather than aborting the entire analysis.

## Runtime and memory profiling

Runtime profiling reads the existing fingerprint JSONL, counts records by
streaming, and executes the final risk-aware calibrated ranker. It records
platform, Python version, CPU count, available RAM when `psutil` exists,
fingerprint size, measured runtime, observed RSS, output sizes, and a linear
100,000-candidate projection. Missing `psutil` produces null memory fields
instead of failing.

Normal ranking does not run profiling, benchmarks, or sensitivity analysis.
Those commands remain opt-in, so Feature 5 adds no default ranking overhead.

## Reproducibility

The reproducibility manifest stores the Git commit and branch when available,
dirty status, Python/platform data, SHA-256 hashes of `requirements.txt` and
`config.yaml`, configured random seed, expected filenames, enabled ranking
mode, and the exact recommended command. It records no candidate content and
does not hash or package private input data.

## Submission packaging

The packager includes the ranked CSV, score breakdown, safety and
reproducibility reports, judge-facing approach summary, exact reproduction
commands, and any available optional evaluation reports. It uses an explicit
allowlist, so raw inputs, candidate fingerprints, `.git`, caches, virtual
environments, and secrets cannot enter the ZIP accidentally.

The final submit command runs structured CSV validation, submission safety,
manifest creation, runtime profiling when the expected local inputs exist,
and package generation. Blocking validation errors produce a failed final
status; optional missing reports remain warnings.

## Limitations

Runtime extrapolation is linear and depends on the measured machine and input
mix. Synthetic benchmarks cannot replace relevance judgments from recruiters
or leaderboard labels. Weight stability indicates robustness, not optimality.
All risk and hireability signals remain decision-support evidence for human
review, never automated hiring decisions.

## Employer-neutral evidence assessment

EvidenceRank does not penalize candidates for working at service companies. It
only lowers ranking confidence when the profile lacks role-relevant evidence.
The `shallow_project_evidence` signal depends on short/generic career text, low
supported-skill count, and absent production/retrieval/evaluation depth—not an
employer name.

## Semantic-lite and Indian-context normalization

JD relevance retains the deterministic lexical score and blends it with local
word and character TF-IDF similarity. Character n-grams add modest tolerance for
hyphenation, inflection, and small typos without requiring model downloads.

Common Hinglish career phrases and number words are normalized before the
existing English cleaning pipeline. This keeps profiles such as “RAG system
banaya” searchable as “RAG system built” while preserving technical terms.

# Feature 6 Methodology

## Why judge-facing explanations matter

The ranking engine produces detailed machine-readable audits, but judges have
only a few minutes to understand the core contribution. Feature 6 converts
existing outputs into concise, traceable explanations without adding new
ranking signals or changing candidate order.

## Top candidate explanation cards

The explanation-card generator reads only `ranked_candidates.csv`,
`score_breakdown.csv`, and `top_candidate_proofs.jsonl`. It first identifies
the requested top candidate IDs, then streams the proof JSONL until those IDs
are found. It does not read `candidate_fingerprints.jsonl`.

Every statement comes from an existing score, risk flag, supported skill, or
proof snippet. Missing evidence is explicitly labeled “No explicit snippet
available.” The cards expose base, risk-adjusted, and calibrated scores so the
reader can distinguish relevance from later safety adjustments.

## Mermaid diagrams

Three dependency-free Mermaid source files communicate complementary views:

- the architecture diagram follows data from streaming input to final package;
- the scoring diagram shows positive components, risk penalties, and calibration;
- the evidence-flow diagram shows how claims become supported, weak, or unsupported.

The files are plain text and render in GitHub or Mermaid-compatible tools.

## Approach deck and demo workflow

The generated twelve-slide Markdown deck maps directly to the implemented
system: problem, keyword-matching failure, proof graph, firewall, calibration,
evaluation, outputs, performance, and impact. Speaker notes and a timed
2–3 minute script keep the story aligned with verifiable repository artifacts.

The judge walkthrough prioritizes the final CSV, score breakdown, explanation
cards, safety report, and reproducibility manifest. The FAQ states limitations
and explains why the system remains deterministic and offline.

## Safe demo packet

The demo packet uses a fixed file allowlist. It includes only generated docs,
top-candidate explanations, runtime/safety/reproducibility reports, and the
consolidated judge handout. It never recursively archives directories, so raw
input data, fingerprints, Git history, caches, secrets, and environments cannot
enter accidentally.

## Limitations

Feature 6 summarizes existing lexical evidence and therefore inherits the
ranking system’s finite aliases and best-effort timeline extraction. Markdown
deck material still requires manual visual design and PDF export. Explanation
cards are communication aids, not new hiring judgments, and human review
remains required.

# Feature 7 Methodology

## Why final deck export exists

Feature 6 defines the judge-facing narrative in Markdown. Feature 7 converts
that narrative into portable presentation files so the project can be reviewed
without requiring a Markdown or Mermaid tool. The exporter remains offline and
does not read candidate inputs or fingerprints.

The twelve-slide structure mirrors the implemented system: problem, proof-based
idea, architecture, Candidate Proof Graph, Honeypot Firewall, calibration,
scoring, evaluation, outputs, performance, and impact. Runtime, benchmark, and
safety values are inserted only from existing reports.

## PPTX and PDF generation

The PPTX writer creates a standards-compliant Open XML presentation with a
complete theme, slide master, layout relationships, readable typography,
footers, and slide numbers. PDF export uses ReportLab when installed. If that
optional dependency is unavailable, the command writes explicit conversion
instructions and does not fail the rest of the workflow.

No raw candidate text, private input file, or fingerprint store is embedded in
the deck.

## Artifact hashes

SHA-256 hashes and byte sizes create a stable record of the final CSV, deck,
packages, safety report, reproducibility manifest, runtime report, and
reproduction command. The hasher uses an explicit filename allowlist and
refuses raw input paths or `candidate_fingerprints.jsonl`.

Hashes make accidental post-freeze changes visible. They are integrity
evidence, not encryption or access control.

## Submission freeze

The freeze command runs CSV validation, submission safety, judge-demo checks,
deck export, reproducibility metadata, artifact hashing, guide generation, and
final bundle creation. Its report records Git branch and commit, dirty state,
required and missing artifacts, recommended uploads, exact final commands, and
the bundle manifest.

The one-page summary gives judges a compact technical overview. The submission
guide lists mandatory uploads, regeneration commands, and common failure modes.

## Bundle safety

The final ZIP is constructed from a fixed file allowlist. It never walks
directories recursively and therefore excludes:

- raw candidate datasets and all `data/input` files;
- `candidate_fingerprints.jsonl`;
- Git history, virtual environments, caches, and secrets;
- unrelated or unexpectedly large generated files.

## Limitations

The exported deck intentionally uses concise deterministic content rather than
automated free-form narrative. PDF generation depends on ReportLab or manual
PPTX conversion. A freeze is a point-in-time snapshot: any later change to the
CSV, deck, configuration, or reports requires rebuilding the hashes and freeze.
