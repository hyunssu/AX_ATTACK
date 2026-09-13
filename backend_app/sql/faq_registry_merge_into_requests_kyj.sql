-- faq_registry_kyj를 faq_requests_kyj 승인 데이터로 통합하는 1회성 수동 마이그레이션입니다.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- DBeaver에서 전체 내용을 검토한 뒤 사용자가 직접 실행하세요.
-- 모든 변경 대상은 public 스키마의 _kyj 개인 테이블뿐입니다.

BEGIN;

-- 이전 단계에서 제거하기로 한 관심 질문자 테이블이 남아 있으면 함께 정리한다.
-- 해당 FK가 faq_requests_kyj 재구성을 막지 않도록 먼저 처리한다.
DROP TABLE IF EXISTS public.faq_request_participants_kyj;

-- 연결되지 않은 레거시 FAQ도 모두 옮길 수 있는지 먼저 검증한다.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.faq_registry_kyj registry
        LEFT JOIN public.faq_history_kyj history
          ON history.id = registry.source_legacy_faq_id
        LEFT JOIN public.chat_rooms_kyj room
          ON room.room_id = history.source_room_id
        WHERE registry.source_request_id IS NULL
          AND (history.id IS NULL OR room.room_id IS NULL)
    ) THEN
        RAISE EXCEPTION '원본 faq_history_kyj 또는 chat_rooms_kyj가 없는 레거시 FAQ가 있어 이관을 중단합니다.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.users_kyj
        WHERE role IN ('Admin', 'Developer')
    ) THEN
        RAISE EXCEPTION '레거시 FAQ를 배정할 Admin/Developer 사용자가 없어 이관을 중단합니다.';
    END IF;
END
$$;

-- faq_requests_kyj를 재구성하기 위해 양방향 FK를 잠시 분리한다.
ALTER TABLE public.faq_request_messages_kyj
    DROP CONSTRAINT IF EXISTS faq_request_messages_kyj_faq_id_fkey;
ALTER TABLE public.faq_requests_kyj
    DROP CONSTRAINT IF EXISTS faq_requests_kyj_registry_fk;
ALTER TABLE public.faq_registry_kyj
    DROP CONSTRAINT IF EXISTS faq_registry_kyj_source_request_id_fkey;

ALTER SEQUENCE public.faq_requests_kyj_faq_id_seq OWNED BY NONE;
ALTER TABLE public.faq_requests_kyj RENAME TO faq_requests_kyj_old;
ALTER TABLE public.faq_requests_kyj_old
    RENAME CONSTRAINT faq_requests_kyj_pkey TO faq_requests_kyj_old_pkey;

-- 두 embedding 컬럼을 연속 배치하고 registry_id를 제거한 최종 원장이다.
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
    CONSTRAINT faq_requests_kyj_regis_date_check CHECK (regis_date ~ '^[0-9]{8}$'),
    CONSTRAINT faq_requests_kyj_regis_time_check CHECK (regis_time ~ '^[0-9]{6}$'),
    CONSTRAINT faq_requests_kyj_last_change_date_check CHECK (last_change_date ~ '^[0-9]{8}$'),
    CONSTRAINT faq_requests_kyj_last_change_time_check CHECK (last_change_time ~ '^[0-9]{6}$')
);

-- 기존 요청과 연결된 승인 FAQ는 최종 승인 질문/답변 및 질문 embedding을 요청 원장에 병합한다.
INSERT INTO public.faq_requests_kyj (
    faq_id, requester_username, requester_chat_room_id, knowledge_search_allowed,
    original_question, refined_question, target_business, screen_number, country,
    assignee_username, assignee_display_name, assignee_team, assignment_reason,
    assignment_confidence, summarized_question_embedding, summarized_answer_embedding,
    status, summarized_question, summarized_answer, final_keywords, last_change_user,
    rejection_reason, regis_date, regis_time, last_change_date, last_change_time
)
SELECT
    old.faq_id,
    old.requester_username,
    old.requester_chat_room_id,
    CASE
        WHEN registry.id IS NOT NULL THEN CASE WHEN registry.is_active THEN 'Y' ELSE 'N' END
        ELSE old.knowledge_search_allowed
    END,
    old.original_question,
    old.refined_question,
    old.target_business,
    old.screen_number,
    old.country,
    old.assignee_username,
    old.assignee_display_name,
    old.assignee_team,
    old.assignment_reason,
    old.assignment_confidence,
    CASE
        WHEN old.status = 'approved' THEN COALESCE(registry.embedding, old.embedding)
        ELSE NULL
    END,
    NULL::vector,
    old.status,
    COALESCE(registry.question, old.summarized_question),
    COALESCE(registry.answer, old.summarized_answer),
    COALESCE(registry.keywords, old.final_keywords, ARRAY[]::TEXT[]),
    COALESCE(registry.approved_by, old.last_change_user, 'system'),
    old.rejection_reason,
    old.regis_date,
    old.regis_time,
    old.last_change_date,
    old.last_change_time
FROM public.faq_requests_kyj_old old
LEFT JOIN public.faq_registry_kyj registry
  ON registry.source_request_id = old.faq_id;

-- 요청과 연결되지 않았던 레거시 승인 FAQ도 별도의 승인 요청 행으로 보존한다.
INSERT INTO public.faq_requests_kyj (
    requester_username, requester_chat_room_id, knowledge_search_allowed,
    original_question, refined_question, target_business, screen_number, country,
    assignee_username, assignee_display_name, assignee_team, assignment_reason,
    assignment_confidence, summarized_question_embedding, summarized_answer_embedding,
    status, summarized_question, summarized_answer, final_keywords, last_change_user,
    rejection_reason, regis_date, regis_time, last_change_date, last_change_time
)
SELECT
    COALESCE(history.username, 'legacy-migration'),
    history.source_room_id,
    CASE WHEN registry.is_active THEN 'Y' ELSE 'N' END,
    registry.question,
    registry.question,
    CASE
        WHEN lower(registry.question) ~ '(수신|예금|적금|입금|출금)' THEN '수신'
        WHEN lower(registry.question) ~ '(여신|대출|담보|한도|신용)' THEN '여신'
        WHEN lower(registry.question) ~ '(고객|고객정보|고객등록|고객관리)' THEN '고객'
        WHEN lower(registry.question) ~ '(외환|해외송금|swift|환율|환전)' THEN '외환'
        WHEN lower(registry.question) ~ '(채널|인터넷뱅킹|모바일|앱|웹)' THEN '채널'
        WHEN lower(registry.question) ~ '(공통|환경설정|권한|사용자관리)' THEN '공통'
        WHEN lower(registry.question) ~ '(총무|인사|복리|경비|자산)' THEN '총무'
        WHEN lower(registry.question) ~ '(카드|승인|가맹점|청구)' THEN '카드'
        WHEN lower(registry.question) ~ '(ums|통합메시지|메시징)' THEN 'UMS'
        ELSE '기타'
    END,
    NULL,
    NULL,
    assignee.username,
    COALESCE(assignee.display_name, assignee.username),
    COALESCE(assignee.department, ''),
    '기존 승인 FAQ 원장에서 이관',
    '낮음',
    registry.embedding,
    NULL::vector,
    'approved',
    registry.question,
    registry.answer,
    COALESCE(registry.keywords, ARRAY[]::TEXT[]),
    COALESCE(registry.approved_by, 'legacy-migration'),
    NULL,
    to_char(history.created_at AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    to_char(history.created_at AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    to_char(COALESCE(registry.updated_at, registry.approved_at, registry.created_at)
            AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    to_char(COALESCE(registry.updated_at, registry.approved_at, registry.created_at)
            AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
FROM public.faq_registry_kyj registry
JOIN public.faq_history_kyj history
  ON history.id = registry.source_legacy_faq_id
JOIN public.chat_rooms_kyj room
  ON room.room_id = history.source_room_id
CROSS JOIN LATERAL (
    SELECT username, display_name, department
    FROM public.users_kyj user_row
    WHERE user_row.role IN ('Admin', 'Developer')
    ORDER BY
        CASE WHEN user_row.username = registry.approved_by THEN 0
             WHEN user_row.role = 'Admin' THEN 1
             ELSE 2 END,
        user_row.username
    LIMIT 1
) assignee
WHERE registry.source_request_id IS NULL;

DROP TABLE public.faq_requests_kyj_old;

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

DROP TABLE public.faq_registry_kyj;

DROP INDEX IF EXISTS public.faq_requests_kyj_embedding_idx;
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

DROP TRIGGER IF EXISTS faq_requests_last_change_kyj ON public.faq_requests_kyj;
CREATE TRIGGER faq_requests_last_change_kyj
BEFORE UPDATE ON public.faq_requests_kyj
FOR EACH ROW
EXECUTE FUNCTION public.touch_faq_requests_last_change_kyj();

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT to_regclass('public.faq_registry_kyj') AS registry_table_should_be_null;

SELECT ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'faq_requests_kyj'
ORDER BY ordinal_position;

SELECT status, knowledge_search_allowed,
       COUNT(*) AS faq_count,
       COUNT(summarized_question_embedding) AS question_embedding_count,
       COUNT(summarized_answer_embedding) AS answer_embedding_count
FROM public.faq_requests_kyj
GROUP BY status, knowledge_search_allowed
ORDER BY status, knowledge_search_allowed;
