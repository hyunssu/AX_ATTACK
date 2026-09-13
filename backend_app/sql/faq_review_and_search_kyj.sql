-- FAQ 검수·승인 검색·답변 출처 표시 기능을 위한 수동 마이그레이션입니다.
-- 애플리케이션은 이 파일을 자동 실행하지 않습니다. DBeaver에서 검토 후 직접 실행하세요.

BEGIN;

ALTER TABLE public.faq_history_kyj
    ADD COLUMN IF NOT EXISTS faq_type TEXT NOT NULL DEFAULT 'conversation',
    ADD COLUMN IF NOT EXISTS embedding vector(1536),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS approved_by TEXT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_by TEXT,
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'faq_history_kyj_faq_type_check'
          AND conrelid = 'public.faq_history_kyj'::regclass
    ) THEN
        ALTER TABLE public.faq_history_kyj
            ADD CONSTRAINT faq_history_kyj_faq_type_check
            CHECK (faq_type IN ('conversation', 'manual', 'screen_owner_change'));
    END IF;
END
$$;

-- 이전에 생성된 담당자 변경 FAQ가 일반 FAQ 검색에 섞이지 않도록 유형을 분리합니다.
UPDATE public.faq_history_kyj
SET faq_type = 'screen_owner_change',
    updated_at = now()
WHERE faq_type = 'conversation'
  AND question ~ '^화면번호 [0-9]+ 담당자 변경 이력 #[0-9]+';

ALTER TABLE public.chat_messages_kyj
    ADD COLUMN IF NOT EXISTS sources JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS faq_history_kyj_status_created_idx
    ON public.faq_history_kyj (status, created_at DESC);

CREATE INDEX IF NOT EXISTS faq_history_kyj_approved_embedding_idx
    ON public.faq_history_kyj
    USING hnsw (embedding vector_cosine_ops)
    WHERE status = 'approved' AND embedding IS NOT NULL;

COMMIT;

-- 실행 후 구조 검증
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('faq_history_kyj', 'chat_messages_kyj')
  AND column_name IN (
      'faq_type', 'embedding', 'updated_at', 'approved_by', 'approved_at',
      'rejected_by', 'rejected_at', 'sources'
  )
ORDER BY table_name, ordinal_position;

-- 상태별 FAQ 건수 검증
SELECT status, faq_type, COUNT(*)
FROM public.faq_history_kyj
GROUP BY status, faq_type
ORDER BY status, faq_type;
