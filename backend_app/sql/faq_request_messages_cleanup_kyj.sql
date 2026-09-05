-- faq_request_messages_kyj 정리용 1회성 수동 마이그레이션입니다.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- faq_requests_cleanup_kyj.sql 적용 후 DBeaver에서 검토·실행하세요.
-- 모든 변경 대상은 public 스키마의 _kyj 개인 테이블뿐입니다.

BEGIN;

-- 기존 전역 id를 FAQ별 순번으로 변환할 대응표를 먼저 보관한다.
CREATE TEMP TABLE faq_request_message_id_map_kyj ON COMMIT DROP AS
SELECT
    id AS old_message_id,
    request_id AS faq_id,
    row_number() OVER (
        PARTITION BY request_id
        ORDER BY created_at, id
    )::INTEGER AS faq_chat_id
FROM public.faq_request_messages_kyj;

ALTER TABLE public.faq_request_messages_kyj
    RENAME TO faq_request_messages_kyj_old;
ALTER TABLE public.faq_request_messages_kyj_old
    RENAME CONSTRAINT faq_request_messages_kyj_pkey
    TO faq_request_messages_kyj_old_pkey;

CREATE TABLE public.faq_request_messages_kyj (
    faq_id BIGINT NOT NULL,
    faq_chat_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    author_role TEXT NOT NULL,
    message_type TEXT NOT NULL,
    message_text TEXT NOT NULL,
    regis_date CHAR(8) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    regis_time CHAR(6) NOT NULL DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    CONSTRAINT faq_request_messages_kyj_pkey PRIMARY KEY (faq_id, faq_chat_id),
    CONSTRAINT faq_request_messages_kyj_faq_id_fkey
        FOREIGN KEY (faq_id)
        REFERENCES public.faq_requests_kyj(faq_id) ON DELETE CASCADE,
    CONSTRAINT faq_request_messages_kyj_role_check
        CHECK (author_role IN ('requester', 'assignee', 'admin', 'agent')),
    CONSTRAINT faq_request_messages_kyj_type_check
        CHECK (message_type IN ('question', 'answer', 'additional_question', 'note', 'summary')),
    CONSTRAINT faq_request_messages_kyj_regis_date_check
        CHECK (regis_date ~ '^[0-9]{8}$'),
    CONSTRAINT faq_request_messages_kyj_regis_time_check
        CHECK (regis_time ~ '^[0-9]{6}$')
);

INSERT INTO public.faq_request_messages_kyj (
    faq_id,
    faq_chat_id,
    author_username,
    author_role,
    message_type,
    message_text,
    regis_date,
    regis_time
)
SELECT
    map.faq_id,
    map.faq_chat_id,
    old.author_username,
    old.author_role,
    old.message_type,
    old.message_text,
    to_char(old.created_at AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    to_char(old.created_at AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
FROM public.faq_request_messages_kyj_old old
JOIN faq_request_message_id_map_kyj map
  ON map.old_message_id = old.id;

-- 원본 채팅방에 전달한 추가질의의 연결값도 새 FAQ별 채팅번호로 바꾼다.
UPDATE public.chat_messages_kyj chat
SET trace = (chat.trace - 'faq_request_message_id')
            || jsonb_build_object('faq_chat_id', map.faq_chat_id)
FROM faq_request_message_id_map_kyj map
WHERE chat.trace ->> 'source' = 'faq_agent'
  AND chat.trace ->> 'faq_request_id' = map.faq_id::TEXT
  AND chat.trace ->> 'faq_request_message_id' = map.old_message_id::TEXT;

DROP TABLE public.faq_request_messages_kyj_old;

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

CREATE TRIGGER faq_request_messages_assign_chat_id_kyj
BEFORE INSERT ON public.faq_request_messages_kyj
FOR EACH ROW
EXECUTE FUNCTION public.assign_faq_chat_id_kyj();

CREATE INDEX faq_request_messages_kyj_faq_regis_idx
    ON public.faq_request_messages_kyj
        (faq_id, regis_date, regis_time, faq_chat_id);

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT ordinal_position, column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'faq_request_messages_kyj'
ORDER BY ordinal_position;

SELECT faq_id, faq_chat_id, author_username, message_type, regis_date, regis_time
FROM public.faq_request_messages_kyj
ORDER BY faq_id DESC, faq_chat_id;

SELECT faq_id, MIN(faq_chat_id) AS first_chat_id, MAX(faq_chat_id) AS last_chat_id,
       COUNT(*) AS message_count
FROM public.faq_request_messages_kyj
GROUP BY faq_id
ORDER BY faq_id DESC;
