-- DBeaver에서 검토 후 직접 실행하세요. 애플리케이션은 자동 실행하지 않습니다.
-- 테이블 rename 후에도 옛 public.faq_request_messages_kyj를 조회하는
-- FAQ 메시지 채번 트리거 함수만 현재 테이블명으로 교정합니다.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.faq_messages') IS NULL THEN
        RAISE EXCEPTION 'public.faq_messages 테이블이 없습니다.';
    END IF;
END
$$;

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

COMMIT;

-- 실행 후 함수 본문에 public.faq_messages가 표시되는지 확인합니다.
SELECT pg_get_functiondef('public.assign_faq_chat_id_kyj()'::regprocedure);
