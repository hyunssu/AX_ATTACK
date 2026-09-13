-- 미해결 질문 요청 → 담당자 협업 → 승인 FAQ 원장 흐름을 위한 수동 마이그레이션입니다.
-- 중요: 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- DBeaver에서 전체 내용을 검토한 뒤 사용자가 직접 실행하세요.
-- 모든 대상은 public 스키마의 _kyj 개인 테이블뿐입니다.

BEGIN;

-- 담당자 자동 배정에 사용할 사용자 프로필
ALTER TABLE public.users_kyj
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'LocalUser',
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS department TEXT,
    ADD COLUMN IF NOT EXISTS countries TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS expertise_keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_kyj_role_check'
          AND conrelid = 'public.users_kyj'::regclass
    ) THEN
        ALTER TABLE public.users_kyj
            ADD CONSTRAINT users_kyj_role_check
            CHECK (role IN ('Admin', 'Developer', 'LocalUser'));
    END IF;
END
$$;

-- 미해결 요청과 승인 FAQ 지식을 하나의 원장에서 관리합니다.
CREATE TABLE IF NOT EXISTS public.faq_requests_kyj (
    faq_id BIGSERIAL PRIMARY KEY,
    requester_username TEXT NOT NULL,
    requester_chat_room_id INTEGER NOT NULL
        REFERENCES public.chat_rooms_kyj(room_id) ON DELETE RESTRICT,
    knowledge_search_allowed CHAR(1) NOT NULL DEFAULT 'Y',
    original_question TEXT NOT NULL,
    refined_question TEXT NOT NULL,
    target_business TEXT NOT NULL,
    screen_number TEXT,
    country TEXT,
    assignee_username TEXT NOT NULL,
    assignee_display_name TEXT,
    assignee_team TEXT,
    assignment_reason TEXT,
    assignment_confidence TEXT,
    summarized_question_embedding vector(1536),
    summarized_answer_embedding vector(1536),
    status TEXT NOT NULL DEFAULT 'pending',
    summarized_question TEXT,
    summarized_answer TEXT,
    final_keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    last_change_user TEXT NOT NULL DEFAULT 'system',
    rejection_reason TEXT,
    regis_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    regis_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    last_change_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    last_change_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    CONSTRAINT faq_requests_kyj_status_check
        CHECK (status IN ('pending', 'assigned', 'approved', 'rejected')),
    CONSTRAINT faq_requests_kyj_knowledge_search_check
        CHECK (knowledge_search_allowed IN ('Y', 'N')),
    CONSTRAINT faq_requests_kyj_target_business_check
        CHECK (target_business IN ('수신', '여신', '고객', '외환', '채널', '공통', '총무', '카드', 'UMS', '기타')),
    CONSTRAINT faq_requests_kyj_confidence_check
        CHECK (assignment_confidence IS NULL OR assignment_confidence IN ('높음', '보통', '낮음')),
    CHECK (regis_date ~ '^[0-9]{8}$'),
    CHECK (regis_time ~ '^[0-9]{6}$'),
    CHECK (last_change_date ~ '^[0-9]{8}$'),
    CHECK (last_change_time ~ '^[0-9]{6}$')
);

-- 어떤 경로에서 UPDATE하더라도 원장의 최종 변경일시는 KST 기준으로 갱신한다.
CREATE OR REPLACE FUNCTION public.touch_faq_requests_last_change_kyj()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.last_change_date := to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD');
    NEW.last_change_time := to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS');
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS faq_requests_last_change_kyj ON public.faq_requests_kyj;
CREATE TRIGGER faq_requests_last_change_kyj
BEFORE UPDATE ON public.faq_requests_kyj
FOR EACH ROW
EXECUTE FUNCTION public.touch_faq_requests_last_change_kyj();

-- 질문자/담당자/관리자의 협업 대화
CREATE TABLE IF NOT EXISTS public.faq_request_messages_kyj (
    faq_id BIGINT NOT NULL
        REFERENCES public.faq_requests_kyj(faq_id) ON DELETE CASCADE,
    faq_chat_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    author_role TEXT NOT NULL,
    message_type TEXT NOT NULL,
    message_text TEXT NOT NULL,
    regis_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    regis_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    CONSTRAINT faq_request_messages_kyj_pkey PRIMARY KEY (faq_id, faq_chat_id),
    CONSTRAINT faq_request_messages_kyj_role_check
        CHECK (author_role IN ('requester', 'assignee', 'admin', 'agent')),
    CONSTRAINT faq_request_messages_kyj_type_check
        CHECK (message_type IN ('question', 'answer', 'additional_question', 'note', 'summary')),
    CHECK (regis_date ~ '^[0-9]{8}$'),
    CHECK (regis_time ~ '^[0-9]{6}$')
);

-- faq_chat_id는 FAQ별로 1부터 증가한다. 동시 INSERT는 FAQ 단위 advisory lock으로 직렬화한다.
CREATE OR REPLACE FUNCTION public.assign_faq_chat_id_kyj()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.faq_chat_id IS NULL THEN
        PERFORM pg_advisory_xact_lock(NEW.faq_id);
        SELECT COALESCE(MAX(m.faq_chat_id), 0) + 1
          INTO NEW.faq_chat_id
          FROM public.faq_request_messages_kyj m
         WHERE m.faq_id = NEW.faq_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS faq_request_messages_assign_chat_id_kyj
    ON public.faq_request_messages_kyj;
CREATE TRIGGER faq_request_messages_assign_chat_id_kyj
BEFORE INSERT ON public.faq_request_messages_kyj
FOR EACH ROW
EXECUTE FUNCTION public.assign_faq_chat_id_kyj();

CREATE INDEX IF NOT EXISTS faq_requests_kyj_status_assignee_updated_idx
    ON public.faq_requests_kyj
        (status, assignee_username, last_change_date DESC, last_change_time DESC);
CREATE INDEX IF NOT EXISTS faq_requests_kyj_room_status_idx
    ON public.faq_requests_kyj (requester_chat_room_id, status);
CREATE INDEX IF NOT EXISTS faq_requests_kyj_question_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_question_embedding vector_cosine_ops)
    WHERE status = 'approved' AND knowledge_search_allowed = 'Y'
      AND summarized_question_embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS faq_requests_kyj_answer_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_answer_embedding vector_cosine_ops)
    WHERE status = 'approved' AND knowledge_search_allowed = 'Y'
      AND summarized_answer_embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS faq_request_messages_kyj_faq_regis_idx
    ON public.faq_request_messages_kyj (faq_id, regis_date, regis_time, faq_chat_id);

-- 담당자 프로필 예시입니다. 실제 업무/국가에 맞게 값을 바꿔 실행해도 됩니다.
UPDATE public.users_kyj
SET display_name = COALESCE(display_name, 'KYJ 관리자'),
    department = COALESCE(department, 'AI Agent 관리'),
    countries = CASE WHEN cardinality(countries) = 0 THEN ARRAY['멕시코', '일본'] ELSE countries END,
    expertise_keywords = CASE
        WHEN cardinality(expertise_keywords) = 0
        THEN ARRAY['해외송금', 'SWIFT', '매뉴얼', 'FAQ']
        ELSE expertise_keywords
    END
WHERE username = 'kyj';

COMMIT;

-- 실행 후 검증(읽기 전용)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'faq_requests_kyj',
      'faq_request_messages_kyj'
  )
ORDER BY table_name;

SELECT status, COUNT(*)
FROM public.faq_requests_kyj
GROUP BY status
ORDER BY status;

SELECT COUNT(*) AS searchable_approved_faq_count
FROM public.faq_requests_kyj
WHERE status = 'approved'
  AND knowledge_search_allowed = 'Y'
  AND (summarized_question_embedding IS NOT NULL
       OR summarized_answer_embedding IS NOT NULL);
