-- DBeaver에서 검토 후 직접 실행하세요. 애플리케이션은 자동 실행하지 않습니다.
-- 기존 FAQ의 embedding은 요청에 따라 text-embedding-3-small로 기록합니다.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.faq_rooms') IS NULL THEN
        RAISE EXCEPTION 'public.faq_rooms 테이블이 없습니다.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'faq_rooms'
          AND column_name = 'embedding_model'
    ) THEN
        RAISE EXCEPTION 'public.faq_rooms.embedding_model 컬럼이 이미 존재합니다.';
    END IF;
END
$$;

ALTER TABLE public.faq_rooms
    ADD COLUMN embedding_model TEXT;

UPDATE public.faq_rooms
SET embedding_model = 'text-embedding-3-small';

COMMENT ON COLUMN public.faq_rooms.embedding_model IS
    'summarized_question_embedding 및 summarized_answer_embedding 생성에 사용한 OpenAI embedding 모델명';

CREATE INDEX faq_rooms_embedding_model_idx
    ON public.faq_rooms (embedding_model, status, knowledge_search_allowed)
    WHERE summarized_question_embedding IS NOT NULL
       OR summarized_answer_embedding IS NOT NULL;

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT embedding_model,
       COUNT(*) AS faq_count,
       COUNT(summarized_question_embedding) AS question_embedding_count,
       COUNT(summarized_answer_embedding) AS answer_embedding_count
FROM public.faq_rooms
GROUP BY embedding_model
ORDER BY embedding_model;

SELECT ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'faq_rooms'
  AND column_name IN (
      'summarized_question_embedding',
      'summarized_answer_embedding',
      'embedding_model'
  )
ORDER BY ordinal_position;
