-- DBeaver에서 검토 후 직접 실행하세요. 애플리케이션은 자동 실행하지 않습니다.
-- public의 최신 chat/FAQ 테이블에 남은 _kyj 및 이전 테이블명 인덱스를 정리합니다.
-- 인덱스를 재생성하지 않고 이름만 변경하므로 저장된 데이터와 검색 방식은 바뀌지 않습니다.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.chat_rooms') IS NULL
       OR to_regclass('public.chat_messages') IS NULL
       OR to_regclass('public.faq_rooms') IS NULL
       OR to_regclass('public.faq_messages') IS NULL THEN
        RAISE EXCEPTION 'public의 최신 chat/FAQ 테이블 4개 중 하나 이상이 없습니다.';
    END IF;

    IF to_regclass('public.chat_rooms_pkey') IS NOT NULL
       OR to_regclass('public.chat_messages_pkey') IS NOT NULL
       OR to_regclass('public.faq_rooms_pkey') IS NOT NULL
       OR to_regclass('public.faq_messages_pkey') IS NOT NULL
       OR to_regclass('public.chat_rooms_checkpoint_idx') IS NOT NULL
       OR to_regclass('public.chat_rooms_room_user_idx') IS NOT NULL
       OR to_regclass('public.chat_messages_checkpoint_idx') IS NOT NULL
       OR to_regclass('public.chat_messages_room_id_idx') IS NOT NULL
       OR to_regclass('public.faq_messages_faq_regis_idx') IS NOT NULL
       OR to_regclass('public.faq_rooms_question_embedding_idx') IS NOT NULL
       OR to_regclass('public.faq_rooms_answer_embedding_idx') IS NOT NULL
       OR to_regclass('public.faq_rooms_room_status_idx') IS NOT NULL
       OR to_regclass('public.faq_rooms_status_assignee_last_change_idx') IS NOT NULL THEN
        RAISE EXCEPTION '변경할 최신 인덱스명 중 하나 이상이 이미 존재합니다. 현재 상태를 다시 확인하세요.';
    END IF;
END
$$;

-- PK 제약조건 rename은 연결된 PK 인덱스명도 함께 변경합니다.
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

-- 실행 후 최신 인덱스 목록 확인
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('chat_rooms', 'chat_messages', 'faq_rooms', 'faq_messages')
ORDER BY tablename, indexname;

-- 0건이어야 합니다.
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('chat_rooms', 'chat_messages', 'faq_rooms', 'faq_messages')
  AND (
      indexname LIKE '%kyj%'
      OR indexname LIKE 'faq_request%'
  )
ORDER BY tablename, indexname;
