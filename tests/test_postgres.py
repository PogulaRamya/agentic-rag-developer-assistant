"""Runs against a disposable pgvector database only when TEST_DATABASE_URL is supplied."""
from datetime import datetime,timezone
import os
from pathlib import Path
import numpy as np
import psycopg
from pgvector.psycopg import register_vector
import pytest
from app.ingest import apply_document
from app.retrieval import HybridRetriever
from app.settings import Settings

DSN=os.getenv('TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not DSN,reason='TEST_DATABASE_URL is not configured')

def test_atomic_replacement_removal_and_hybrid_search():
    with psycopg.connect(DSN,autocommit=True) as conn:
        conn.execute((Path('app/sql/schema.sql')).read_text())
        register_vector(conn)
        # Only dedicated test data, no bulk truncation of unrelated records.
        qid=9999999001
        row=dict(question_id=qid,answer_id=100,title='Python list duplicates',
                 question_author_id=None,answer_author_id=None,updated_at=datetime.now(timezone.utc))
        vector=np.zeros(384,dtype=np.float32);vector[0]=1
        try:
            apply_document(conn,row,['Python list duplicates'],[vector],'BAAI/bge-small-en-v1.5')
            apply_document(conn,row,['Python list duplicates'],[vector],'BAAI/bge-small-en-v1.5')
            assert conn.execute('SELECT count(*) FROM chunks WHERE question_id=%s',(qid,)).fetchone()[0]==1
            retriever=object.__new__(HybridRetriever)
            retriever.dsn=DSN
            class FakeEmbeddings:
                name='BAAI/bge-small-en-v1.5'
                def query(self,q):return vector
            retriever.embedder=FakeEmbeddings()
            assert retriever.search('Python list duplicates')[0]['question_id']==qid
            # Transaction rolls back both the deletion and cursor when chunk insert fails.
            with pytest.raises(Exception):
                apply_document(conn,dict(row,answer_id=101),['bad'],[np.zeros(2)],'BAAI/bge-small-en-v1.5')
            assert conn.execute('SELECT answer_id FROM documents WHERE question_id=%s',(qid,)).fetchone()[0]==100
            apply_document(conn,dict(row,answer_id=101),['Replacement'],[vector],'BAAI/bge-small-en-v1.5')
            assert conn.execute('SELECT chunk_id FROM chunks WHERE question_id=%s',(qid,)).fetchone()[0].endswith(':101:0')
            apply_document(conn,dict(row,answer_id=None),[],[],'BAAI/bge-small-en-v1.5')
            assert conn.execute('SELECT count(*) FROM chunks WHERE question_id=%s',(qid,)).fetchone()[0]==0
        finally:
            conn.execute('DELETE FROM documents WHERE question_id=%s',(qid,))
