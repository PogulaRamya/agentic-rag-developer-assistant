from pathlib import Path
import json
import re
import numpy as np
import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

class Embedder:
    def __init__(self, model):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name=model)
        self.name = model
    def encode(self, texts):
        vectors = list(self.model.embed(texts))
        if any(len(v) != 384 or not np.isfinite(v).all() for v in vectors):
            raise ValueError("Invalid embedding shape or non-finite values")
        return vectors
    def query(self, text):
        return self.encode(["Represent this sentence for searching relevant passages: " + text])[0]

class HybridRetriever:
    def __init__(self, settings):
        self.dsn = settings.database_url
        self.embedder = Embedder(settings.embedding_model)

    def search(self, query, limit=12):
        vector = self.embedder.query(query)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            register_vector(conn)
            conn.execute("SET LOCAL statement_timeout = '10s'")
            rows = conn.execute("""
             WITH sem_candidates AS (
               SELECT chunk_id, embedding <=> %(v)s::vector AS distance
               FROM chunks ORDER BY embedding <=> %(v)s::vector LIMIT 40
             ), sem AS (
               SELECT chunk_id, row_number() OVER (ORDER BY distance, chunk_id) AS rank FROM sem_candidates
             ), kw_candidates AS (
               SELECT chunk_id, ts_rank_cd(search_vector, websearch_to_tsquery('english', %(q)s)) AS score
               FROM chunks WHERE search_vector @@ websearch_to_tsquery('english', %(q)s)
               ORDER BY score DESC, chunk_id LIMIT 40
             ), kw AS (
               SELECT chunk_id, row_number() OVER (ORDER BY score DESC, chunk_id) AS rank FROM kw_candidates
             ), fused AS (
               SELECT COALESCE(sem.chunk_id,kw.chunk_id) AS chunk_id,
               COALESCE(1.0/(60+sem.rank),0)+COALESCE(1.0/(60+kw.rank),0) AS score
               FROM sem FULL OUTER JOIN kw USING(chunk_id)
             )
             SELECT c.chunk_id AS id,c.text,d.question_id,d.answer_id,d.title,d.source_url,
                    d.attribution,d.indexed_at,d.source_updated_at,f.score
             FROM fused f JOIN chunks c USING(chunk_id) JOIN documents d USING(question_id)
             WHERE d.embedding_model=%(model)s
             ORDER BY f.score DESC,c.chunk_id LIMIT %(limit)s
            """, dict(v=vector, q=query, model=self.embedder.name, limit=limit)).fetchall()
        return [dict(row, score=float(row['score']), indexed_at=row['indexed_at'].isoformat(),
                     source_updated_at=row['source_updated_at'].isoformat()) for row in rows]

class DemoRetriever:
    """Original fixtures, lexical ranking; no network or Stack Overflow content."""
    def __init__(self):
        self.docs = json.loads((Path(__file__).parent/"fixtures/demo.json").read_text())
    def search(self, query, limit=12):
        words = set(re.findall(r"[a-z0-9]+",query.lower())) - {"how","do","i","a","the","in","to","what","is"}
        scored = []
        for d in self.docs:
            overlap = len(words & set(re.findall(r"[a-z0-9]+",(d['title']+' '+d['text']).lower())))
            if overlap:
                scored.append(dict(d, score=overlap))
        return sorted(scored,key=lambda d:(-d['score'],d['id']))[:limit]
