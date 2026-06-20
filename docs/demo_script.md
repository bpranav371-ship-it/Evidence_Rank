# EvidenceRank 2–3 Minute Demo Script

## 0:00–0:20 — Problem

Traditional résumé matching rewards repeated keywords. A candidate can list RAG,
ranking, or Python without showing where those skills were used. EvidenceRank asks
a stricter question: what can the profile actually prove?

## 0:20–0:50 — What EvidenceRank does

The pipeline streams candidate records into compact fingerprints, parses the job
description, and ranks candidates locally. It is CPU-only, offline, deterministic,
and designed for roughly 100,000 profiles without loading the dataset into memory.

## 0:50–1:30 — Architecture

The Candidate Proof Graph connects skill claims to titles, projects, achievements,
and career text. Baseline scoring combines JD relevance, required skills, proof,
retrieval and evaluation depth, production readiness, and modest hireability
signals. Only a bounded shortlist receives deeper analysis.

## 1:30–2:10 — Proof Graph and Firewall

Skills become supported, weakly supported, or unsupported. The Honeypot Firewall
then looks for combinations such as keyword stuffing with weak evidence,
zero-duration expertise, or title-career contradictions. It assigns explainable
risk and protects the top 10 without accusing candidates or replacing human review.

## 2:10–2:40 — Outputs and reproducibility

The final CSV contains candidate ID, rank, score, and reasoning. A score breakdown,
proof JSONL, risk audits, runtime report, and reproducibility manifest show how each
result was produced. The final submit command validates and packages these files.

## 2:40–3:00 — Impact

EvidenceRank turns résumé matching into candidate proof: safer top ranks, visible
evidence, low memory use, and a result judges or recruiters can reproduce locally.
