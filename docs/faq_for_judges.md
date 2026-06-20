# FAQ for Judges

## 1. Is this just keyword matching?

No. Keywords contribute to relevance, but claimed skills are connected to career
evidence and classified as supported, weakly supported, or unsupported.

## 2. Why not use an LLM?

The challenge benefits from reproducibility and offline execution. Deterministic
rules avoid API cost, network dependency, prompt drift, and hallucinated evidence.

## 3. How does Candidate Proof Graph work?

It searches titles, projects, achievements, and career text for each claimed skill
and known aliases, then records real snippets and proof-alignment scores.

## 4. How are fake or suspicious profiles handled?

The Honeypot Firewall detects risk patterns such as stuffing, contradictory
experience, and unsupported senior claims. Flags reduce ranking confidence; they
are not accusations.

## 5. How do you avoid over-penalizing missing behavior signals?

Missing behavior and availability data receive a neutral score near 0.50. They do
not erase strong technical evidence.

## 6. How do you validate without labels?

We use transparent proxy checks: ablation, synthetic benchmarks, weight sensitivity,
proof alignment, risk rates, production evidence, and top-10 sanity constraints.
These are not official accuracy metrics.

## 7. Can the output be reproduced?

Yes. The manifest records the commit, config and dependency hashes, environment,
and exact ranking command.

## 8. Does it run under CPU-only constraints?

Yes. It uses streaming JSONL/CSV processing and bounded top pools, with no GPU,
network call, embedding service, or external API.

## 9. What are the limitations?

Matching remains lexical, aliases are finite, timeline extraction is best-effort,
and no public relevance labels are available. Human review remains necessary.

## 10. What would you improve with more time?

With labeled judgments, we would tune weights against NDCG, expand schema-aware
timeline evidence, add fairness analysis, and test more role archetypes.
