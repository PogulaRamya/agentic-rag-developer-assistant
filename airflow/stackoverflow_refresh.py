"""Airflow 2.10.x; the worker needs this project's models extra and secret-backed credentials."""
from datetime import datetime,timedelta,timezone
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG('stackoverflow_weekly_refresh',start_date=datetime(2026,1,1,tzinfo=timezone.utc),
         schedule='0 3 * * 0',catchup=False,max_active_runs=1,
         default_args={'retries':2,'retry_delay':timedelta(minutes=5)},tags=['rag','stackoverflow']) as dag:
    refresh=BashOperator(task_id='refresh_accepted_answers',
        bash_command='python -m app.ingest --max-posts 500000 --overlap-hours 24',
        execution_timeout=timedelta(hours=12))
