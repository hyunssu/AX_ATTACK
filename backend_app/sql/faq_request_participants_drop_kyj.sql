-- FAQ와 질문자를 1:1로 운영하므로 관심 질문자 연결 테이블을 제거합니다.
-- 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
-- DBeaver에서 검토 후 사용자가 직접 실행하세요.
-- 변경 대상은 public.faq_request_participants_kyj 하나뿐입니다.

BEGIN;

DROP TABLE IF EXISTS public.faq_request_participants_kyj;

COMMIT;

-- 실행 후 NULL이면 정상입니다.
SELECT to_regclass('public.faq_request_participants_kyj')
    AS participant_table_should_be_null;
