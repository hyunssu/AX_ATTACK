CREATE TABLE IF NOT EXISTS users_kyj (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'LocalUser'
        CHECK (role IN ('Admin', 'Developer', 'LocalUser')),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS manuals_kyj (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS manual_versions_kyj (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES manuals_kyj(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    index_step TEXT NOT NULL DEFAULT 'converting',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (manual_id, version_no)
);

CREATE TABLE IF NOT EXISTS chat_rooms_kyj (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '새 대화',
    engine TEXT NOT NULL DEFAULT 'langchain',
    manual_id INTEGER REFERENCES manuals_kyj(id) ON DELETE SET NULL,
    ended_at TIMESTAMPTZ,
    conversation_summary TEXT NOT NULL DEFAULT '',
    last_summarized_message_id INTEGER NOT NULL DEFAULT 0,
    last_summarized_at TIMESTAMPTZ,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages_kyj (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES chat_rooms_kyj(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    type TEXT,
    options JSONB NOT NULL DEFAULT '[]',
    trace JSONB,
    sources JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_rooms_kyj_checkpoint_idx
    ON chat_rooms_kyj (username, last_summarized_message_id)
    WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS chat_messages_kyj_checkpoint_idx
    ON chat_messages_kyj (room_id, id, created_at);

CREATE TABLE IF NOT EXISTS faq_history_kyj (
    id SERIAL PRIMARY KEY,
    source_room_id INTEGER REFERENCES chat_rooms_kyj(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    manual_id INTEGER REFERENCES manuals_kyj(id) ON DELETE SET NULL,
    conversation_summary TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    faq_type TEXT NOT NULL DEFAULT 'conversation'
        CHECK (faq_type IN ('conversation', 'manual', 'screen_owner_change')),
    embedding vector(1536),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejected_by TEXT,
    rejected_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS faq_history_kyj_room_question_idx
    ON faq_history_kyj (source_room_id, question)
    WHERE source_room_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS faq_history_kyj_status_created_idx
    ON faq_history_kyj (status, created_at DESC);

CREATE INDEX IF NOT EXISTS faq_history_kyj_approved_embedding_idx
    ON faq_history_kyj USING hnsw (embedding vector_cosine_ops)
    WHERE status = 'approved' AND embedding IS NOT NULL;

CREATE TABLE IF NOT EXISTS manual_chunks_kyj (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES manuals_kyj(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL REFERENCES manual_versions_kyj(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    content TEXT NOT NULL,
    embedding vector(1536),
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS manual_chunks_kyj_embedding_idx
    ON manual_chunks_kyj USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS manual_chunks_kyj_tsv_idx
    ON manual_chunks_kyj USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS manual_chunks_kyj_manual_id_idx
    ON manual_chunks_kyj (manual_id);

-- 화면 담당자 원장은 backend_app/sql/screen_owners_kyj.sql을 DBeaver에서
-- 사용자가 직접 실행해 생성·적재한다. 애플리케이션은 DDL을 자동 실행하지 않는다.
