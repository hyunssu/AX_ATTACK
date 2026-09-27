-- DBeaver에서 검토 후 직접 실행하세요. 애플리케이션은 자동 실행하지 않습니다.
--
-- 현재 공용 원장 4개의 스키마와 데이터를 다른 브랜치가 기대하는 개인화 이름으로 복제합니다.
--   public.chat_rooms              -> public.chat_rooms_kyj
--   public.chat_messages           -> public.chat_messages_kyj
--   public.faq_rooms               -> public.faq_requests_kyj
--   public.faq_messages            -> public.faq_request_messages_kyj
--
-- 안전장치:
-- 1. 원본 4개 중 하나라도 없으면 중단합니다.
-- 2. 대상 4개 중 하나라도 이미 있으면 덮어쓰지 않고 중단합니다.
-- 3. 전체 작업은 한 트랜잭션이며, 오류가 나면 모두 롤백됩니다.
-- 4. 대상 PK는 원본 시퀀스를 공유하지 않고 별도 시퀀스를 사용합니다.

BEGIN;

DO $$
DECLARE
    missing_sources text[];
    existing_targets text[];
    existing_sequences text[];
BEGIN
    SELECT array_agg(name ORDER BY name)
      INTO missing_sources
      FROM unnest(ARRAY[
               'public.chat_rooms',
               'public.chat_messages',
               'public.faq_rooms',
               'public.faq_messages'
           ]) AS source(name)
     WHERE to_regclass(name) IS NULL;

    IF missing_sources IS NOT NULL THEN
        RAISE EXCEPTION '원본 테이블이 없습니다: %', array_to_string(missing_sources, ', ');
    END IF;

    SELECT array_agg(name ORDER BY name)
      INTO existing_targets
      FROM unnest(ARRAY[
               'public.chat_rooms_kyj',
               'public.chat_messages_kyj',
               'public.faq_requests_kyj',
               'public.faq_request_messages_kyj'
           ]) AS target(name)
     WHERE to_regclass(name) IS NOT NULL;

    IF existing_targets IS NOT NULL THEN
        RAISE EXCEPTION '덮어쓰지 않습니다. 이미 존재하는 대상 테이블: %',
            array_to_string(existing_targets, ', ');
    END IF;

    SELECT array_agg(name ORDER BY name)
      INTO existing_sequences
      FROM unnest(ARRAY[
               'public.chat_rooms_kyj_personal_room_id_seq',
               'public.chat_messages_kyj_personal_chat_id_seq',
               'public.faq_requests_kyj_personal_faq_id_seq'
           ]) AS sequence_name(name)
     WHERE to_regclass(name) IS NOT NULL;

    IF existing_sequences IS NOT NULL THEN
        RAISE EXCEPTION '복제용 시퀀스 이름이 이미 사용 중입니다: %',
            array_to_string(existing_sequences, ', ');
    END IF;
END
$$;

-- 복사 도중 원본 데이터가 바뀌지 않게 읽기 잠금을 잡습니다.
LOCK TABLE public.chat_rooms,
           public.chat_messages,
           public.faq_rooms,
           public.faq_messages
    IN SHARE MODE;

-- CHECK, NOT NULL, DEFAULT, 타입/스토리지/주석 등은 원본에서 복제합니다.
-- PK/FK와 일반 인덱스는 대상 이름과 참조 대상을 정확히 제어하기 위해 아래에서 별도 생성합니다.
CREATE TABLE public.chat_rooms_kyj
    (LIKE public.chat_rooms INCLUDING ALL EXCLUDING INDEXES);
CREATE TABLE public.chat_messages_kyj
    (LIKE public.chat_messages INCLUDING ALL EXCLUDING INDEXES);
CREATE TABLE public.faq_requests_kyj
    (LIKE public.faq_rooms INCLUDING ALL EXCLUDING INDEXES);
CREATE TABLE public.faq_request_messages_kyj
    (LIKE public.faq_messages INCLUDING ALL EXCLUDING INDEXES);

-- ALTER TABLE RENAME의 흔적으로 공용 테이블이 아직 과거 _kyj 시퀀스명을 사용하므로,
-- 새 개인화 테이블에는 충돌하지 않는 독립 시퀀스를 연결합니다.
CREATE SEQUENCE public.chat_rooms_kyj_personal_room_id_seq AS integer;
ALTER SEQUENCE public.chat_rooms_kyj_personal_room_id_seq
    OWNED BY public.chat_rooms_kyj.room_id;
ALTER TABLE public.chat_rooms_kyj
    ALTER COLUMN room_id SET DEFAULT
        nextval('public.chat_rooms_kyj_personal_room_id_seq'::regclass);

CREATE SEQUENCE public.chat_messages_kyj_personal_chat_id_seq AS integer;
ALTER SEQUENCE public.chat_messages_kyj_personal_chat_id_seq
    OWNED BY public.chat_messages_kyj.chat_id;
ALTER TABLE public.chat_messages_kyj
    ALTER COLUMN chat_id SET DEFAULT
        nextval('public.chat_messages_kyj_personal_chat_id_seq'::regclass);

CREATE SEQUENCE public.faq_requests_kyj_personal_faq_id_seq AS bigint;
ALTER SEQUENCE public.faq_requests_kyj_personal_faq_id_seq
    OWNED BY public.faq_requests_kyj.faq_id;
ALTER TABLE public.faq_requests_kyj
    ALTER COLUMN faq_id SET DEFAULT
        nextval('public.faq_requests_kyj_personal_faq_id_seq'::regclass);

-- 부모 원장을 먼저 복사합니다. LIKE로 컬럼 순서까지 같으므로 모든 데이터를 그대로 옮깁니다.
INSERT INTO public.chat_rooms_kyj
SELECT * FROM public.chat_rooms;

INSERT INTO public.chat_messages_kyj
SELECT * FROM public.chat_messages;

INSERT INTO public.faq_requests_kyj
SELECT * FROM public.faq_rooms;

INSERT INTO public.faq_request_messages_kyj
SELECT * FROM public.faq_messages;

-- 다음 INSERT가 기존 PK와 충돌하지 않도록 새 시퀀스를 현재 최댓값에 맞춥니다.
SELECT setval(
    'public.chat_rooms_kyj_personal_room_id_seq'::regclass,
    COALESCE((SELECT MAX(room_id) FROM public.chat_rooms_kyj), 1),
    EXISTS (SELECT 1 FROM public.chat_rooms_kyj)
);
SELECT setval(
    'public.chat_messages_kyj_personal_chat_id_seq'::regclass,
    COALESCE((SELECT MAX(chat_id) FROM public.chat_messages_kyj), 1),
    EXISTS (SELECT 1 FROM public.chat_messages_kyj)
);
SELECT setval(
    'public.faq_requests_kyj_personal_faq_id_seq'::regclass,
    COALESCE((SELECT MAX(faq_id) FROM public.faq_requests_kyj), 1),
    EXISTS (SELECT 1 FROM public.faq_requests_kyj)
);

-- PK와 개인화 테이블끼리의 FK를 복원합니다.
ALTER TABLE public.chat_rooms_kyj
    ADD CONSTRAINT chat_rooms_kyj_pkey PRIMARY KEY (room_id);
ALTER TABLE public.chat_messages_kyj
    ADD CONSTRAINT chat_messages_kyj_pkey PRIMARY KEY (chat_id),
    ADD CONSTRAINT chat_messages_kyj_room_id_fkey
        FOREIGN KEY (room_id)
        REFERENCES public.chat_rooms_kyj(room_id) ON DELETE CASCADE;

ALTER TABLE public.faq_requests_kyj
    ADD CONSTRAINT faq_requests_kyj_pkey PRIMARY KEY (faq_id),
    ADD CONSTRAINT faq_requests_kyj_requester_room_fk
        FOREIGN KEY (requester_chat_room_id)
        REFERENCES public.chat_rooms_kyj(room_id) ON DELETE RESTRICT;
ALTER TABLE public.faq_request_messages_kyj
    ADD CONSTRAINT faq_request_messages_kyj_pkey PRIMARY KEY (faq_id, faq_chat_id),
    ADD CONSTRAINT faq_request_messages_kyj_faq_id_fkey
        FOREIGN KEY (faq_id)
        REFERENCES public.faq_requests_kyj(faq_id) ON DELETE CASCADE;

-- 원본과 동등한 조회용 인덱스를 개인화 이름으로 생성합니다.
CREATE INDEX chat_rooms_kyj_checkpoint_idx
    ON public.chat_rooms_kyj (room_user, last_summarized_message_id);
CREATE INDEX chat_rooms_kyj_room_user_idx
    ON public.chat_rooms_kyj (room_user);
CREATE INDEX chat_rooms_kyj_status_idx
    ON public.chat_rooms_kyj (room_user, status, room_id DESC);

CREATE INDEX chat_messages_kyj_checkpoint_idx
    ON public.chat_messages_kyj (room_id, chat_id, regis_date, regis_time);
CREATE INDEX chat_messages_kyj_room_id_idx
    ON public.chat_messages_kyj (room_id);

CREATE INDEX faq_request_messages_kyj_faq_regis_idx
    ON public.faq_request_messages_kyj
        (faq_id, regis_date, regis_time, faq_chat_id);

CREATE INDEX faq_requests_kyj_question_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_question_embedding vector_cosine_ops)
    WHERE status = 'approved'
      AND knowledge_search_allowed = 'Y'
      AND summarized_question_embedding IS NOT NULL;
CREATE INDEX faq_requests_kyj_answer_embedding_idx
    ON public.faq_requests_kyj
    USING hnsw (summarized_answer_embedding vector_cosine_ops)
    WHERE status = 'approved'
      AND knowledge_search_allowed = 'Y'
      AND summarized_answer_embedding IS NOT NULL;
CREATE INDEX faq_requests_kyj_embedding_model_idx
    ON public.faq_requests_kyj (embedding_model, status, knowledge_search_allowed)
    WHERE summarized_question_embedding IS NOT NULL
       OR summarized_answer_embedding IS NOT NULL;
CREATE INDEX faq_requests_kyj_room_status_idx
    ON public.faq_requests_kyj (requester_chat_room_id, status);
CREATE INDEX faq_requests_kyj_status_assignee_last_change_idx
    ON public.faq_requests_kyj
        (status, assignee_username, last_change_date DESC, last_change_time DESC);

-- FAQ UPDATE 시 최종 변경일시를 KST로 갱신합니다.
-- 공용 원장의 기존 함수는 공용 테이블용으로 유지하고, 개인화 전용 함수를 따로 둡니다.
CREATE FUNCTION public.touch_faq_requests_kyj_copy_last_change()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.last_change_date := to_char(
        clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'
    );
    NEW.last_change_time := to_char(
        clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS'
    );
    RETURN NEW;
END;
$function$;

CREATE TRIGGER faq_requests_last_change_kyj
BEFORE UPDATE ON public.faq_requests_kyj
FOR EACH ROW
EXECUTE FUNCTION public.touch_faq_requests_kyj_copy_last_change();

-- faq_chat_id가 생략된 INSERT는 FAQ별 마지막 번호 다음 값으로 자동 채번합니다.
CREATE FUNCTION public.assign_faq_chat_id_kyj_copy()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.faq_chat_id IS NULL THEN
        PERFORM pg_advisory_xact_lock(NEW.faq_id);
        SELECT COALESCE(MAX(message.faq_chat_id), 0) + 1
          INTO NEW.faq_chat_id
          FROM public.faq_request_messages_kyj message
         WHERE message.faq_id = NEW.faq_id;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER faq_request_messages_assign_chat_id_kyj
BEFORE INSERT ON public.faq_request_messages_kyj
FOR EACH ROW
EXECUTE FUNCTION public.assign_faq_chat_id_kyj_copy();

-- INSERT ... SELECT 결과가 원본 행 수와 정확히 같은지 확인합니다.
DO $$
DECLARE
    mismatch text[];
BEGIN
    SELECT array_agg(table_name ORDER BY table_name)
      INTO mismatch
      FROM (
          SELECT 'chat_rooms' AS table_name,
                 (SELECT COUNT(*) FROM public.chat_rooms) AS source_count,
                 (SELECT COUNT(*) FROM public.chat_rooms_kyj) AS target_count
          UNION ALL
          SELECT 'chat_messages',
                 (SELECT COUNT(*) FROM public.chat_messages),
                 (SELECT COUNT(*) FROM public.chat_messages_kyj)
          UNION ALL
          SELECT 'faq_rooms',
                 (SELECT COUNT(*) FROM public.faq_rooms),
                 (SELECT COUNT(*) FROM public.faq_requests_kyj)
          UNION ALL
          SELECT 'faq_messages',
                 (SELECT COUNT(*) FROM public.faq_messages),
                 (SELECT COUNT(*) FROM public.faq_request_messages_kyj)
      ) AS counts
     WHERE source_count <> target_count;

    IF mismatch IS NOT NULL THEN
        RAISE EXCEPTION '원본/대상 행 수가 다릅니다: %', array_to_string(mismatch, ', ');
    END IF;
END
$$;

COMMIT;

-- 실행 후 읽기 전용 확인 결과입니다.
SELECT 'chat_rooms' AS source_table,
       'chat_rooms_kyj' AS copied_table,
       (SELECT COUNT(*) FROM public.chat_rooms) AS source_rows,
       (SELECT COUNT(*) FROM public.chat_rooms_kyj) AS copied_rows
UNION ALL
SELECT 'chat_messages', 'chat_messages_kyj',
       (SELECT COUNT(*) FROM public.chat_messages),
       (SELECT COUNT(*) FROM public.chat_messages_kyj)
UNION ALL
SELECT 'faq_rooms', 'faq_requests_kyj',
       (SELECT COUNT(*) FROM public.faq_rooms),
       (SELECT COUNT(*) FROM public.faq_requests_kyj)
UNION ALL
SELECT 'faq_messages', 'faq_request_messages_kyj',
       (SELECT COUNT(*) FROM public.faq_messages),
       (SELECT COUNT(*) FROM public.faq_request_messages_kyj);
