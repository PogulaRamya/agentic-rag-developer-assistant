# Setup and deployment

## Local demo

The default is `APP_MODE=demo`. It uses the actual LangGraph graph but substitutes lexical fixture retrieval and extractive answers for cloud calls. No GCP, PostgreSQL or Anthropic credentials are needed. The API is synchronous so blocking client calls run in FastAPI's worker thread pool.

A shared API key is optional in demo mode. If `API_KEY` is set, send it as `X-API-Key`. The browser form holds it only in memory.

## PostgreSQL and pgvector

Compose provisions PostgreSQL 16 with pgvector, a persistent named volume and the schema initialization script. The development password is explicitly not for production; port 5432 is not exposed by Compose. Change the password through a secret-backed deployment configuration before any external hosting.

For a managed database, install the vector extension, run `app/sql/schema.sql` as the migration role, and give the ingestion role only the required table writes. The API role should have SELECT on documents/chunks. The schema has HNSW cosine and GIN text indexes. Set database connection limits and monitor index memory, query plans and p95 latency as the corpus grows.

An existing Docker volume does not rerun init scripts. Apply schema migrations explicitly when updating an existing database.

## Google BigQuery

Enable BigQuery billing on a project and authenticate using ADC. For local development, `gcloud auth application-default login` provides ADC; for hosted workloads prefer workload identity. Do not commit a service-account JSON key.

The caller needs job execution permission in the billing project and read access to the public dataset. Both extraction and trends query only `bigquery-public-data.stackoverflow`.

Each query first runs a dry-run estimate. The default `BQ_MAX_BYTES=1000000000` is deliberately small and may reject a full Stack Overflow scan. Inspect the estimate and set an appropriate budget before a real backfill. LIMIT limits result rows, not necessarily bytes scanned. Per-query caps are not a daily account budget; configure billing alerts and quotas too.

In containers, ADC must be provided through a read-only mount or workload identity. The Compose file does not mount credentials automatically. For a local ADC mount, add an override mapping your credential file to a read-only container path and set `GOOGLE_APPLICATION_CREDENTIALS` to that path. Keep that override out of git.

## Ingestion

Install `.[models]`. FastEmbed and the matching tokenizer download the BGE-small model on first use, so allow the relevant model-host download or prepopulate a cache. Pin/cache model assets for reproducible deployments. The code fixes the model and schema dimension at 384.

Start small:

```bash
python -m app.ingest --init-db --max-posts 1000 --overlap-hours 0
```

The first query starts in 2008. It reads both accepted and unaccepted changed questions so it can also delete stale accepted-answer documents. A 500,000-row query therefore does not imply 500,000 indexed accepted pairs.

Continue backfills with `--overlap-hours 0` until the reported `indexed_documents_total` reaches your target. Each committed (modification timestamp, question ID) cursor supports resume. Set a fixed dataset snapshot/export for reproducible benchmarking; the public source itself can change between runs.

The default 24-hour overlap is for steady-state weekly refresh. If more rows change in that overlap than the per-run cap, use zero-overlap catch-up runs, then return to the usual schedule; otherwise repeated overlap can prevent progress. Alert when `examined` reaches `--max-posts`.

Text is chunked with the model tokenizer. The tokenizer's truncation is disabled before chunking. Every document's complete chunk replacement and cursor advance share a transaction. Embedding failure occurs before the transaction and leaves the old document untouched.

Hard-deleted questions are not visible to this incremental query. Periodically compare indexed question IDs against a source snapshot and remove absent records in a reviewed reconciliation job. This repository does not implement that full reconciliation yet.

## Claude and API

Set `APP_MODE=production` and these secrets/configuration values:

- `API_KEY`: at least 24 characters; generate with a password manager.
- `ANTHROPIC_API_KEY`: supplied through a secret manager.
- `CLAUDE_MODEL`: an available Claude model supporting structured output through LangChain; the example uses `claude-sonnet-4-5` and can be changed.
- `DATABASE_URL` and `GCP_PROJECT`.
- `BQ_MAX_BYTES`: account-appropriate per-query cap.

The assistant uses LangChain's ChatAnthropic integration and LangGraph's StateGraph. Requests can make up to three model calls (route, rerank, answer), with bounded model retries. A caller can incur costs; keep the endpoint behind authentication and rate limiting.

The FastAPI HTTP handler returns backend failures as generic 503 responses. Logs are operational diagnostics; configure redaction and access controls before sending sensitive questions. The current concurrency guard is per process, not a distributed rate limiter.

## Airflow

Use a separate Airflow 2.10 environment with its official Python-version constraints. Install this project with `.[models]` into the task worker image and mount/configure ADC and PostgreSQL credentials through your deployment's secret backend.

Copy `airflow/stackoverflow_refresh.py` to the DAG directory. It runs Sundays at 03:00 UTC, with retries, a 12-hour timeout and `max_active_runs=1`. The database advisory lock also guards manual invocations. Start the scheduler only after a manual ingest succeeds.

## Evaluation

Copy `evaluation/candidates.jsonl` to `evaluation/golden.jsonl`. Review each question/reference against indexed accepted answers, add numeric `expected_answer_ids` and set `reviewed=true` only after review. The validator requires all 200 rows to pass.

Run the API in production mode, install `.[eval]` and run `python -m evaluation.run --dataset evaluation/golden.jsonl`. It calls the API, then uses Claude as the RAGAS judge. This costs model tokens and does not establish objective truth. The runner writes actual results to ignored `artifacts/evaluation/`; it stops on errors rather than silently dropping failed cases.

## Publishing this repository

Create an empty GitHub repository named `agentic-rag-developer-assistant`, select Public, then push this project. Public source code is separate from deploying a publicly reachable API. No hosted API is created by a git push.
