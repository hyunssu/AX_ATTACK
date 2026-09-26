-- faq_requests_kyj에 FAQ 요약 언어코드(lang_c)를 추가하는 수동 마이그레이션입니다.
-- PostgreSQL은 ALTER TABLE ADD COLUMN ... BEFORE를 지원하지 않으므로,
-- lang_c를 regis_date 바로 앞에 배치하기 위해 _kyj 원장을 트랜잭션 안에서 재구성합니다.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- DBeaver에서 검토 후 사용자가 직접 실행하세요.

BEGIN;

LOCK TABLE public.faq_requests_kyj IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.faq_request_messages_kyj IN ACCESS EXCLUSIVE MODE;

ALTER TABLE public.faq_request_messages_kyj
    DROP CONSTRAINT IF EXISTS faq_request_messages_kyj_faq_id_fkey;

ALTER SEQUENCE public.faq_requests_kyj_faq_id_seq OWNED BY NONE;

ALTER TABLE public.faq_requests_kyj
    RENAME TO faq_requests_kyj_before_lang_c;
ALTER TABLE public.faq_requests_kyj_before_lang_c
    RENAME CONSTRAINT faq_requests_kyj_pkey
    TO faq_requests_kyj_before_lang_c_pkey;

CREATE TABLE public.faq_requests_kyj (
    faq_id BIGINT NOT NULL DEFAULT nextval('public.faq_requests_kyj_faq_id_seq'::regclass),
    requester_username TEXT NOT NULL,
    requester_chat_room_id INTEGER NOT NULL,
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
    lang_c CHAR(2) NOT NULL,
    regis_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    regis_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    last_change_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    last_change_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    CONSTRAINT faq_requests_kyj_pkey PRIMARY KEY (faq_id),
    CONSTRAINT faq_requests_kyj_status_check
        CHECK (status IN ('pending', 'assigned', 'approved', 'rejected')),
    CONSTRAINT faq_requests_kyj_knowledge_search_check
        CHECK (knowledge_search_allowed IN ('Y', 'N')),
    CONSTRAINT faq_requests_kyj_target_business_check
        CHECK (target_business IN ('수신', '여신', '고객', '외환', '채널', '공통', '총무', '카드', 'UMS', '기타')),
    CONSTRAINT faq_requests_kyj_confidence_check
        CHECK (assignment_confidence IS NULL OR assignment_confidence IN ('높음', '보통', '낮음')),
    CONSTRAINT faq_requests_kyj_lang_c_check CHECK (lang_c IN ('ko', 'en')),
    CONSTRAINT faq_requests_kyj_regis_date_check CHECK (regis_date ~ '^[0-9]{8}$'),
    CONSTRAINT faq_requests_kyj_regis_time_check CHECK (regis_time ~ '^[0-9]{6}$'),
    CONSTRAINT faq_requests_kyj_last_change_date_check CHECK (last_change_date ~ '^[0-9]{8}$'),
    CONSTRAINT faq_requests_kyj_last_change_time_check CHECK (last_change_time ~ '^[0-9]{6}$')
);

INSERT INTO public.faq_requests_kyj (
    faq_id, requester_username, requester_chat_room_id, knowledge_search_allowed,
    original_question, refined_question, target_business, screen_number, country,
    assignee_username, assignee_display_name, assignee_team, assignment_reason,
    assignment_confidence, summarized_question_embedding, summarized_answer_embedding,
    status, summarized_question, summarized_answer, final_keywords, last_change_user,
    rejection_reason, lang_c, regis_date, regis_time, last_change_date, last_change_time
)
SELECT
    faq_id, requester_username, requester_chat_room_id, knowledge_search_allowed,
    original_question, refined_question, target_business, screen_number, country,
    assignee_username, assignee_display_name, assignee_team, assignment_reason,
    assignment_confidence, summarized_question_embedding, summarized_answer_embedding,
    status, summarized_question, summarized_answer, final_keywords, last_change_user,
    rejection_reason,
    CASE
        WHEN original_question ~ '[ㄱ-ㅎㅏ-ㅣ가-힣]' THEN 'ko'
        ELSE 'en'
    END,
    regis_date, regis_time, last_change_date, last_change_time
FROM public.faq_requests_kyj_before_lang_c;

DROP TABLE public.faq_requests_kyj_before_lang_c;

ALTER SEQUENCE public.faq_requests_kyj_faq_id_seq
    OWNED BY public.faq_requests_kyj.faq_id;
SELECT setval(
    'public.faq_requests_kyj_faq_id_seq',
    GREATEST(COALESCE((SELECT MAX(faq_id) FROM public.faq_requests_kyj), 1), 1),
    EXISTS (SELECT 1 FROM public.faq_requests_kyj)
);

ALTER TABLE public.faq_requests_kyj
    ADD CONSTRAINT faq_requests_kyj_requester_room_fk
    FOREIGN KEY (requester_chat_room_id)
    REFERENCES public.chat_rooms_kyj(room_id) ON DELETE RESTRICT;

ALTER TABLE public.faq_request_messages_kyj
    ADD CONSTRAINT faq_request_messages_kyj_faq_id_fkey
    FOREIGN KEY (faq_id)
    REFERENCES public.faq_requests_kyj(faq_id) ON DELETE CASCADE;

CREATE INDEX faq_requests_kyj_status_assignee_updated_idx
    ON public.faq_requests_kyj
        (status, assignee_username, last_change_date DESC, last_change_time DESC);
CREATE INDEX faq_requests_kyj_room_status_idx
    ON public.faq_requests_kyj (requester_chat_room_id, status);
CREATE INDEX faq_requests_kyj_question_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_question_embedding vector_cosine_ops)
    WHERE status = 'approved' AND knowledge_search_allowed = 'Y'
      AND summarized_question_embedding IS NOT NULL;
CREATE INDEX faq_requests_kyj_answer_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_answer_embedding vector_cosine_ops)
    WHERE status = 'approved' AND knowledge_search_allowed = 'Y'
      AND summarized_answer_embedding IS NOT NULL;

CREATE TRIGGER faq_requests_last_change_kyj
BEFORE UPDATE ON public.faq_requests_kyj
FOR EACH ROW
EXECUTE FUNCTION public.touch_faq_requests_last_change_kyj();

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'faq_requests_kyj'
ORDER BY ordinal_position;

SELECT lang_c, status, COUNT(*)
FROM public.faq_requests_kyj
GROUP BY lang_c, status
ORDER BY lang_c, status;
