-- 채팅 원장 컬럼 정리용 1회성 수동 마이그레이션입니다.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- DBeaver에서 검토 후 사용자가 직접 실행하세요.
-- 모든 변경 대상은 public 스키마의 _kyj 개인 테이블뿐입니다.

BEGIN;

-- 피드백 기능과 기존 데이터 전체 제거
DROP TABLE IF EXISTS public.chat_answer_feedback_kyj;

-- 기존 인덱스는 삭제 대상 컬럼을 참조하므로 먼저 제거
DROP INDEX IF EXISTS public.chat_rooms_kyj_checkpoint_idx;
DROP INDEX IF EXISTS public.chat_messages_kyj_checkpoint_idx;

-- 식별자와 업무 컬럼명 정리. 연결된 FK는 PostgreSQL이 새 컬럼명을 추적한다.
ALTER TABLE public.chat_rooms_kyj RENAME COLUMN id TO room_id;
ALTER TABLE public.chat_rooms_kyj RENAME COLUMN username TO room_user;
ALTER TABLE public.chat_rooms_kyj RENAME COLUMN conversation_summary TO summary;
ALTER TABLE public.chat_messages_kyj RENAME COLUMN id TO chat_id;
ALTER SEQUENCE IF EXISTS public.chat_rooms_kyj_id_seq RENAME TO chat_rooms_kyj_room_id_seq;
ALTER SEQUENCE IF EXISTS public.chat_messages_kyj_id_seq RENAME TO chat_messages_kyj_chat_id_seq;

-- KST 기준 등록일자/등록시간 및 최종변경일자/최종변경시간 컬럼 추가
ALTER TABLE public.chat_messages_kyj
    ADD COLUMN regis_date CHAR(8),
    ADD COLUMN regis_time CHAR(6);

ALTER TABLE public.chat_rooms_kyj
    ADD COLUMN regis_date CHAR(8),
    ADD COLUMN regis_time CHAR(6),
    ADD COLUMN last_change_date CHAR(8),
    ADD COLUMN last_change_time CHAR(6);

-- 기존 TIMESTAMP WITHOUT TIME ZONE 값은 당시 DB 세션 타임존의 시각으로 보고 KST로 변환
UPDATE public.chat_messages_kyj
SET regis_date = to_char(
        created_at AT TIME ZONE current_setting('TIMEZONE') AT TIME ZONE 'Asia/Seoul',
        'YYYYMMDD'
    ),
    regis_time = to_char(
        created_at AT TIME ZONE current_setting('TIMEZONE') AT TIME ZONE 'Asia/Seoul',
        'HH24MISS'
    );

UPDATE public.chat_rooms_kyj
SET regis_date = to_char(
        created_at AT TIME ZONE current_setting('TIMEZONE') AT TIME ZONE 'Asia/Seoul',
        'YYYYMMDD'
    ),
    regis_time = to_char(
        created_at AT TIME ZONE current_setting('TIMEZONE') AT TIME ZONE 'Asia/Seoul',
        'HH24MISS'
    );

-- 메시지가 있으면 가장 마지막 chat_id의 등록시각, 없으면 채팅방 생성시각을 사용
UPDATE public.chat_rooms_kyj r
SET last_change_date = COALESCE(
        (
            SELECT m.regis_date
            FROM public.chat_messages_kyj m
            WHERE m.room_id = r.room_id
            ORDER BY m.chat_id DESC
            LIMIT 1
        ),
        r.regis_date
    ),
    last_change_time = COALESCE(
        (
            SELECT m.regis_time
            FROM public.chat_messages_kyj m
            WHERE m.room_id = r.room_id
            ORDER BY m.chat_id DESC
            LIMIT 1
        ),
        r.regis_time
    );

ALTER TABLE public.chat_messages_kyj
    ALTER COLUMN regis_date SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    ALTER COLUMN regis_time SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    ALTER COLUMN regis_date SET NOT NULL,
    ALTER COLUMN regis_time SET NOT NULL;

ALTER TABLE public.chat_rooms_kyj
    ALTER COLUMN regis_date SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    ALTER COLUMN regis_time SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    ALTER COLUMN last_change_date SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
    ALTER COLUMN last_change_time SET DEFAULT to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'),
    ALTER COLUMN regis_date SET NOT NULL,
    ALTER COLUMN regis_time SET NOT NULL,
    ALTER COLUMN last_change_date SET NOT NULL,
    ALTER COLUMN last_change_time SET NOT NULL;

ALTER TABLE public.chat_messages_kyj
    ADD CONSTRAINT chat_messages_kyj_regis_date_check CHECK (regis_date ~ '^[0-9]{8}$'),
    ADD CONSTRAINT chat_messages_kyj_regis_time_check CHECK (regis_time ~ '^[0-9]{6}$');

ALTER TABLE public.chat_rooms_kyj
    ADD CONSTRAINT chat_rooms_kyj_regis_date_check CHECK (regis_date ~ '^[0-9]{8}$'),
    ADD CONSTRAINT chat_rooms_kyj_regis_time_check CHECK (regis_time ~ '^[0-9]{6}$'),
    ADD CONSTRAINT chat_rooms_kyj_last_change_date_check CHECK (last_change_date ~ '^[0-9]{8}$'),
    ADD CONSTRAINT chat_rooms_kyj_last_change_time_check CHECK (last_change_time ~ '^[0-9]{6}$');

-- 실사용하지 않는 채팅방 컬럼과 기존 통합 생성시각 제거
ALTER TABLE public.chat_rooms_kyj
    DROP COLUMN engine,
    DROP COLUMN manual_id,
    DROP COLUMN ended_at,
    DROP COLUMN last_summarized_at,
    DROP COLUMN created_at;

ALTER TABLE public.chat_messages_kyj
    DROP COLUMN created_at;

CREATE INDEX chat_rooms_kyj_checkpoint_idx
    ON public.chat_rooms_kyj (room_user, last_summarized_message_id);

CREATE INDEX chat_messages_kyj_checkpoint_idx
    ON public.chat_messages_kyj (room_id, chat_id, regis_date, regis_time);

COMMIT;

-- 실행 후 읽기 전용 검증
SELECT table_name, ordinal_position, column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('chat_rooms_kyj', 'chat_messages_kyj')
ORDER BY table_name, ordinal_position;

SELECT to_regclass('public.chat_answer_feedback_kyj') AS feedback_table_should_be_null;

SELECT room_id, room_user, title, summary, last_summarized_message_id,
       regis_date, regis_time, last_change_date, last_change_time
FROM public.chat_rooms_kyj
ORDER BY room_id DESC
LIMIT 20;

SELECT chat_id, room_id, role, regis_date, regis_time
FROM public.chat_messages_kyj
ORDER BY chat_id DESC
LIMIT 20;
