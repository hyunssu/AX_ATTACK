-- DBeaver에서 내용을 검토한 뒤 직접 실행하세요.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
--
-- 최종 테이블:
--   public.chat_rooms
--   public.chat_messages
--   public.faq_rooms
--   public.faq_messages
--
-- 주의: 기존 public.chat_rooms(6건)와 public.chat_messages(10건)는
-- 구형 구조이므로 요청에 따라 삭제하며 데이터를 이관하지 않습니다.
-- public.faq_history.source_room_id가 구형 chat_rooms를 참조하므로
-- 해당 외래키도 명시적으로 제거합니다. faq_history의 행 자체는 삭제하지 않습니다.
-- 요청의 faq_request_kyj는 실제 테이블 public.faq_requests_kyj로 해석했습니다.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.chat_rooms') IS NULL
       OR to_regclass('public.chat_messages') IS NULL THEN
        RAISE EXCEPTION '삭제 대상인 구형 public.chat_rooms/chat_messages 중 하나가 없습니다.';
    END IF;

    IF to_regclass('public.chat_rooms_kyj') IS NULL
       OR to_regclass('public.chat_messages_kyj') IS NULL
       OR to_regclass('public.faq_requests_kyj') IS NULL
       OR to_regclass('public.faq_request_messages_kyj') IS NULL THEN
        RAISE EXCEPTION '이름을 변경할 _kyj 원본 테이블 4개 중 하나 이상이 없습니다.';
    END IF;

    IF to_regclass('public.faq_rooms') IS NOT NULL
       OR to_regclass('public.faq_messages') IS NOT NULL THEN
        RAISE EXCEPTION 'public.faq_rooms 또는 public.faq_messages가 이미 존재합니다.';
    END IF;
END
$$;

LOCK TABLE public.chat_rooms IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.chat_messages IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.chat_rooms_kyj IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.chat_messages_kyj IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.faq_requests_kyj IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.faq_request_messages_kyj IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.faq_history IN ACCESS EXCLUSIVE MODE;

-- 구형 공용 채팅 원장을 제거합니다. CASCADE를 사용하지 않아 영향 범위를 명시합니다.
DROP TABLE public.chat_messages;

ALTER TABLE public.faq_history
    DROP CONSTRAINT IF EXISTS faq_history_source_room_id_fkey;

DROP TABLE public.chat_rooms;

-- _kyj 원장의 스키마와 데이터는 유지하고 테이블 이름만 바꿉니다.
ALTER TABLE public.chat_rooms_kyj RENAME TO chat_rooms;
ALTER TABLE public.chat_messages_kyj RENAME TO chat_messages;
ALTER TABLE public.faq_requests_kyj RENAME TO faq_rooms;
ALTER TABLE public.faq_request_messages_kyj RENAME TO faq_messages;

-- 트리거 함수 본문의 고정 테이블명은 ALTER TABLE RENAME으로 자동 변경되지 않는다.
CREATE OR REPLACE FUNCTION public.assign_faq_chat_id_kyj()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.faq_chat_id IS NULL THEN
        PERFORM pg_advisory_xact_lock(NEW.faq_id);
        SELECT COALESCE(MAX(m.faq_chat_id), 0) + 1
          INTO NEW.faq_chat_id
          FROM public.faq_messages m
         WHERE m.faq_id = NEW.faq_id;
    END IF;
    RETURN NEW;
END;
$function$;

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

-- 채팅방 상태코드: 10=정상, 90=삭제
ALTER TABLE public.chat_rooms
    DROP CONSTRAINT IF EXISTS chat_rooms_kyj_status_check;

ALTER TABLE public.chat_rooms
    ALTER COLUMN status DROP DEFAULT,
    ALTER COLUMN status TYPE CHAR(2)
        USING (
            CASE
                WHEN status IN ('deleted', '90') THEN '90'
                ELSE '10'
            END
        )::CHAR(2),
    ALTER COLUMN status SET DEFAULT '10',
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE public.chat_rooms
    ADD CONSTRAINT chat_rooms_status_check
        CHECK (status IN ('10', '90'));

DROP INDEX IF EXISTS public.chat_rooms_kyj_status_idx;
CREATE INDEX chat_rooms_status_idx
    ON public.chat_rooms (room_user, status, room_id DESC);

-- 테이블 rename으로 자동 변경되지 않는 PK/일반/HNSW 인덱스명도 최신화합니다.
ALTER TABLE public.chat_rooms
    RENAME CONSTRAINT chat_rooms_kyj_pkey TO chat_rooms_pkey;
ALTER TABLE public.chat_messages
    RENAME CONSTRAINT chat_messages_kyj_pkey TO chat_messages_pkey;
ALTER TABLE public.faq_rooms
    RENAME CONSTRAINT faq_requests_kyj_pkey TO faq_rooms_pkey;
ALTER TABLE public.faq_messages
    RENAME CONSTRAINT faq_request_messages_kyj_pkey TO faq_messages_pkey;

ALTER INDEX public.chat_rooms_kyj_checkpoint_idx
    RENAME TO chat_rooms_checkpoint_idx;
ALTER INDEX public.chat_rooms_kyj_username_idx
    RENAME TO chat_rooms_room_user_idx;
ALTER INDEX public.chat_messages_kyj_checkpoint_idx
    RENAME TO chat_messages_checkpoint_idx;
ALTER INDEX public.chat_messages_kyj_room_id_idx
    RENAME TO chat_messages_room_id_idx;
ALTER INDEX public.faq_request_messages_kyj_faq_regis_idx
    RENAME TO faq_messages_faq_regis_idx;
ALTER INDEX public.faq_requests_kyj_question_embedding_idx
    RENAME TO faq_rooms_question_embedding_idx;
ALTER INDEX public.faq_requests_kyj_answer_embedding_idx
    RENAME TO faq_rooms_answer_embedding_idx;
ALTER INDEX public.faq_requests_kyj_room_status_idx
    RENAME TO faq_rooms_room_status_idx;
ALTER INDEX public.faq_requests_kyj_status_assignee_updated_idx
    RENAME TO faq_rooms_status_assignee_last_change_idx;

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT to_regclass('public.chat_rooms') AS chat_rooms,
       to_regclass('public.chat_messages') AS chat_messages,
       to_regclass('public.faq_rooms') AS faq_rooms,
       to_regclass('public.faq_messages') AS faq_messages;

SELECT to_regclass('public.chat_rooms_kyj') AS old_chat_rooms_should_be_null,
       to_regclass('public.chat_messages_kyj') AS old_chat_messages_should_be_null,
       to_regclass('public.faq_requests_kyj') AS old_faq_rooms_should_be_null,
       to_regclass('public.faq_request_messages_kyj') AS old_faq_messages_should_be_null;

SELECT status, COUNT(*)
FROM public.chat_rooms
GROUP BY status
ORDER BY status;

SELECT table_schema, table_name, ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('chat_rooms', 'chat_messages', 'faq_rooms', 'faq_messages')
ORDER BY table_name, ordinal_position;
