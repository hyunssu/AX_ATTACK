-- 매뉴얼 부모-자식 청크 테이블 신설 + lang_c 컬럼 추가 마이그레이션
-- DBeaver에서 직접 실행하세요.

BEGIN;

-- 1. manuals 테이블에 lang_c 추가
ALTER TABLE public.manuals
    ADD COLUMN IF NOT EXISTS lang_c CHAR(2);

UPDATE public.manuals
SET lang_c = 'ko'
WHERE lang_c IS NULL;

ALTER TABLE public.manuals
    ALTER COLUMN lang_c SET DEFAULT 'ko',
    ALTER COLUMN lang_c SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'manuals_lang_c_check'
          AND conrelid = 'public.manuals'::regclass
    ) THEN
        ALTER TABLE public.manuals
            ADD CONSTRAINT manuals_lang_c_check
            CHECK (lang_c IN ('ko', 'en'));
    END IF;
END $$;

-- 2. manual_parent_chunks: LLM 컨텍스트용 대형 청크 (~1500자)
CREATE TABLE IF NOT EXISTS public.manual_parent_chunks (
    id SERIAL PRIMARY KEY,
    manual_id INTEGER NOT NULL REFERENCES public.manuals(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL REFERENCES public.manual_versions(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS manual_parent_chunks_manual_id_idx
    ON public.manual_parent_chunks (manual_id);

-- 3. manual_child_chunks: 검색용 소형 청크 (~300자)
CREATE TABLE IF NOT EXISTS public.manual_child_chunks (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES public.manual_parent_chunks(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (parent_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS manual_child_chunks_embedding_idx
    ON public.manual_child_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS manual_child_chunks_tsv_idx
    ON public.manual_child_chunks USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS manual_child_chunks_parent_id_idx
    ON public.manual_child_chunks (parent_id);

COMMIT;

SELECT
    (SELECT COUNT(*) FROM public.manual_parent_chunks) AS parent_chunks,
    (SELECT COUNT(*) FROM public.manual_child_chunks) AS child_chunks,
    (SELECT COUNT(*) FROM public.manuals WHERE lang_c IS NOT NULL) AS manuals_with_lang;
