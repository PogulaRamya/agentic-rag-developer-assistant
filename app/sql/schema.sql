CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
 question_id bigint PRIMARY KEY, answer_id bigint NOT NULL, title text NOT NULL,
 source_url text NOT NULL, attribution jsonb NOT NULL, source_updated_at timestamptz NOT NULL,
 content_hash text NOT NULL, embedding_model text NOT NULL, indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chunks (
 chunk_id text PRIMARY KEY, question_id bigint NOT NULL REFERENCES documents(question_id) ON DELETE CASCADE,
 text text NOT NULL, embedding vector(384) NOT NULL,
 search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_search_gin ON chunks USING gin (search_vector);
CREATE INDEX IF NOT EXISTS chunks_question_id ON chunks(question_id);
CREATE TABLE IF NOT EXISTS ingestion_state (
 name text PRIMARY KEY, cursor_time timestamptz NOT NULL, cursor_id bigint NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now()
);
