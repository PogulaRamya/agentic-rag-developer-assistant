# Validation

Checked locally on 2026-10-25:

- 18 unit/API tests passed, including the LangGraph demo, mocked model route, source-ID validation, parameter validation, authentication, scan-budget controls and evaluation review gate.
- PostgreSQL integration test is included but was skipped locally because a pgvector server was unavailable.
- BGE-small model and tokenizer downloaded successfully. A long sample became nine chunks; document and query embeddings both had 384 dimensions.
- RAGAS evaluation CLI imports and argument parsing passed. No judge calls or benchmark scores were produced.
- Dependency consistency (`pip check`), Python compilation, YAML parsing and frontend JavaScript syntax checks passed.
- The 200-question candidate file validates structurally and correctly fails the reviewed-golden-set gate.

GitHub Actions [run 40230784381](https://github.com/PogulaRamya/agentic-rag-developer-assistant/actions/runs/40230784381) passed on 2026-10-25 at commit `5859553`:

- All 19 tests passed, including PostgreSQL/pgvector ingestion, replacement, rollback and hybrid retrieval.
- Candidate-set validation and Python compilation passed.
- Docker Compose configuration, image build and the demo health-endpoint smoke test passed.

Not run: production Claude answers, billable BigQuery scans, a 500K accepted-document backfill, Airflow scheduling, a human-reviewed 200-question RAGAS evaluation, or public API deployment. Those require credentials, infrastructure and review.
