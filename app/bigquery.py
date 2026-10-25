from datetime import datetime, timezone
from pathlib import Path
from google.cloud import bigquery

SQL = Path(__file__).parent / "sql"

def bounded_query(client, sql, params, max_bytes):
    estimate = client.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=params, dry_run=True, use_query_cache=False, use_legacy_sql=False))
    if (estimate.total_bytes_processed or 0) > max_bytes:
        raise ValueError("Query exceeds BQ_MAX_BYTES; no billable query submitted")
    config = bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=max_bytes,
                                    use_legacy_sql=False, job_timeout_ms=120000)
    return client.query(sql, job_config=config)

class TrendTool:
    def __init__(self, settings):
        self.client = bigquery.Client(project=settings.project)
        self.max_bytes = settings.max_bytes

    def run(self, plan):
        # SQL is fixed: neither the model nor user can supply executable SQL.
        params = [bigquery.ScalarQueryParameter("tag", "STRING", plan.tag),
                  bigquery.ScalarQueryParameter("months", "INT64", plan.months)]
        job = bounded_query(self.client, (SQL/"trends.sql").read_text(), params, self.max_bytes)
        rows = []
        for row in job.result(timeout=120):
            rows.append({k:v.isoformat() if hasattr(v,"isoformat") else v for k,v in dict(row).items()})
        table = self.client.get_table("bigquery-public-data.stackoverflow.posts_questions")
        return dict(rows=rows, tag=plan.tag, months=plan.months,
                    queried_at=datetime.now(timezone.utc).isoformat(),
                    dataset_modified_at=table.modified.isoformat() if table.modified else None,
                    job_id=job.job_id, bytes_processed=job.total_bytes_processed,
                    note="Queried now against the public dataset; this is not a real-time Stack Overflow feed.")
