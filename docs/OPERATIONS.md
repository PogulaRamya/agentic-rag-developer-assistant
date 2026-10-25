# Checks before using real traffic

1. Ingest a small slice and verify accepted-answer joins, source URLs, tokenizer chunk counts and 384-dimensional vectors.
2. Replay the same rows. Confirm no duplicate chunks and no missing chunks after an accepted-answer change.
3. Fail a transaction after deleting old chunks. Confirm rollback restores the previous document and cursor.
4. Test exact technical terms and semantic paraphrases. Compare lexical-only, vector-only and fused retrieval before choosing top-k.
5. Ask an unrelated question and check abstention. Test malicious instructions embedded in retrieved text; prompts are a mitigation, not a security proof.
6. Verify the trend query uses bound tag/month parameters and the dry run blocks an over-budget scan. Check stale or zero-data windows explicitly.
7. Review and annotate the evaluation set, then run the real evaluator. Report failed requests as failures, not omitted samples.
8. Measure median/p95 latency, model tokens, retrieval recall, ingestion documents/second, corpus count, index size and costs before making scale claims.

Recovery:
- A failed embedding leaves the prior document intact.
- A failed document transaction does not advance its cursor.
- Retrying can re-embed completed overlap rows; that costs time but avoids duplicate chunks.
- Changing accepted answer IDs replaces the prior answer's chunks.
- A lost checkpoint can require a backfill; do not invent a cursor.
- A public dataset refresh can contain late source changes outside the overlap. Run reconciliation against a fixed snapshot for comprehensive coverage.

Current limits: single-process shared-key API; no managed cloud deployment, full deletion reconciliation, production load benchmark or independently reviewed golden set included.
