CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS manuals (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS manual_versions (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (manual_id, version_no)
);

CREATE TABLE IF NOT EXISTS chat_rooms (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '새 대화',
    engine TEXT NOT NULL DEFAULT 'langchain',
    manual_id INTEGER REFERENCES manuals(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    type TEXT,
    options JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS trace JSONB;

CREATE TABLE IF NOT EXISTS manual_chunks_khs (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL REFERENCES manual_versions(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    content TEXT NOT NULL,
    embedding vector(1536),
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS manual_chunks_khs_embedding_idx
    ON manual_chunks_khs USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS manual_chunks_khs_tsv_idx
    ON manual_chunks_khs USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS manual_chunks_khs_manual_id_idx
    ON manual_chunks_khs (manual_id);

CREATE TABLE IF NOT EXISTS manual_upload_jobs_khs (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL REFERENCES manual_versions(id) ON DELETE CASCADE,
    step TEXT NOT NULL DEFAULT 'converting',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_documents (
    id SERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    uploaded_by TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE manuals ADD COLUMN IF NOT EXISTS source_document_id INTEGER
    REFERENCES source_documents(id) ON DELETE SET NULL;
ALTER TABLE manuals ADD COLUMN IF NOT EXISTS category TEXT;
