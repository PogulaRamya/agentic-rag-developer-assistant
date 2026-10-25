"""Incremental accepted-answer ingestion with atomic per-document checkpoints."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import psycopg
from psycopg.types.json import Jsonb
from pgvector.psycopg import register_vector
from google.cloud import bigquery
from .settings import Settings
from .retrieval import Embedder
from .cleaning import clean_html,chunk_text
from .bigquery import bounded_query,SQL

def apply_document(conn,row,chunks,vectors,model):
    """Accepted-answer changes replace every old chunk; cursor advances in the same transaction."""
    qid=row['question_id']
    with conn.transaction():
        conn.execute('DELETE FROM documents WHERE question_id=%s',(qid,))
        if row.get('answer_id'):
            attribution={
                'question_author_url':f"https://stackoverflow.com/users/{row['question_author_id']}" if row.get('question_author_id') else None,
                'answer_author_url':f"https://stackoverflow.com/users/{row['answer_author_id']}" if row.get('answer_author_id') else None,
                'question_url':f'https://stackoverflow.com/q/{qid}',
                'answer_url':f"https://stackoverflow.com/a/{row['answer_id']}",
                'license_notice':'Stack Overflow user contributions: applicable CC BY-SA version; check original post revision history.',
                'license_url':'https://stackoverflow.com/help/licensing',
                'transformations':'HTML cleaned; overlapping token chunks generated.'}
            digest=hashlib.sha256(json.dumps(chunks,ensure_ascii=False).encode()).hexdigest()
            conn.execute("""INSERT INTO documents(question_id,answer_id,title,source_url,attribution,source_updated_at,content_hash,embedding_model)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
              (qid,row['answer_id'],row['title'],attribution['answer_url'],Jsonb(attribution),row['updated_at'],digest,model))
            for i,(text,vec) in enumerate(zip(chunks,vectors,strict=True)):
                conn.execute('INSERT INTO chunks(chunk_id,question_id,text,embedding) VALUES (%s,%s,%s,%s)',
                             (f"{qid}:{row['answer_id']}:{i}",qid,text,vec))
        conn.execute("""INSERT INTO ingestion_state(name,cursor_time,cursor_id) VALUES ('stackoverflow',%s,%s)
          ON CONFLICT(name) DO UPDATE SET cursor_time=excluded.cursor_time,cursor_id=excluded.cursor_id,updated_at=now()""",
                     (row['updated_at'],qid))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--max-posts',type=int,default=500000,help='Changed questions examined, including unaccepted questions')
    p.add_argument('--overlap-hours',type=int,default=24)
    p.add_argument('--init-db',action='store_true')
    a=p.parse_args()
    if a.max_posts<1 or a.overlap_hours<0:p.error('Invalid limits')
    settings=Settings.from_env()
    if not settings.database_url or not settings.project:p.error('Set DATABASE_URL and GCP_PROJECT')
    with psycopg.connect(settings.database_url,autocommit=True) as conn:
        if a.init_db:conn.execute((SQL/'schema.sql').read_text())
        register_vector(conn)
        if not conn.execute('SELECT pg_try_advisory_lock(7349021)').fetchone()[0]:
            raise RuntimeError('Another ingestion process holds the lock')
        try:
            cursor=conn.execute("SELECT cursor_time,cursor_id FROM ingestion_state WHERE name='stackoverflow'").fetchone()
            since=(cursor[0]-timedelta(hours=a.overlap_hours)) if cursor else datetime(2008,1,1,tzinfo=timezone.utc)
            cursor_id=0 if a.overlap_hours or not cursor else cursor[1]
            upper=datetime.now(timezone.utc)
            params=[bigquery.ScalarQueryParameter('cursor_time','TIMESTAMP',since),
                    bigquery.ScalarQueryParameter('cursor_id','INT64',cursor_id),
                    bigquery.ScalarQueryParameter('upper_bound','TIMESTAMP',upper),
                    bigquery.ScalarQueryParameter('limit','INT64',a.max_posts)]
            client=bigquery.Client(project=settings.project)
            job=bounded_query(client,(SQL/'extract.sql').read_text(),params,settings.max_bytes)
            embedder=Embedder(settings.embedding_model)
            from tokenizers import Tokenizer
            tokenizer=Tokenizer.from_pretrained(settings.embedding_model)
            tokenizer.no_truncation()
            counts={'examined':0,'accepted_indexed':0,'removed_or_unaccepted':0,'chunks':0}
            for record in job.result(page_size=1000,timeout=120):
                row=dict(record)
                parts=[]
                if row.get('answer_id'):
                    text=f"Question: {row['title']}\n{clean_html(row['question_body'])}\nAccepted answer:\n{clean_html(row['answer_body'])}"
                    parts=list(chunk_text(text,tokenizer))
                vectors=embedder.encode(parts) if parts else []
                apply_document(conn,row,parts,vectors,embedder.name)
                counts['examined']+=1;counts['accepted_indexed']+=bool(row.get('answer_id'))
                counts['removed_or_unaccepted']+=not bool(row.get('answer_id'));counts['chunks']+=len(parts)
            counts['bytes_processed']=job.total_bytes_processed
            counts['indexed_documents_total']=conn.execute('SELECT count(*) FROM documents').fetchone()[0]
            print(json.dumps(counts))
        finally:
            conn.execute('SELECT pg_advisory_unlock(7349021)')

if __name__=='__main__':main()
