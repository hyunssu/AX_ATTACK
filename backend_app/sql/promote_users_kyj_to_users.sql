-- 목적:
--   1) public.users 스키마를 현재 public.users_kyj와 동일하게 맞춘다.
--   2) public.users의 기존 데이터를 모두 비운다.
--   3) public.users_kyj의 사용자 데이터를 public.users로 그대로 복사한다.
--
-- 주의: 애플리케이션에서 자동 실행하지 않는다. 내용을 검토한 뒤 DBeaver에서 직접 실행한다.

BEGIN;

LOCK TABLE public.users_kyj IN SHARE MODE;
LOCK TABLE public.users IN ACCESS EXCLUSIVE MODE;

-- 현재 users를 참조하는 외래키가 없는 것을 확인한 상태에서 기존 2건을 제거한다.
TRUNCATE TABLE public.users;

-- users_kyj에만 존재하는 컬럼을 추가한다.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS role TEXT,
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS department TEXT,
    ADD COLUMN IF NOT EXISTS countries TEXT[],
    ADD COLUMN IF NOT EXISTS expertise_keywords TEXT[],
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS lang_c CHAR(2),
    ADD COLUMN IF NOT EXISTS team_code CHAR(4),
    ADD COLUMN IF NOT EXISTS position_code VARCHAR(3);

-- users_kyj와 자료형·기본값을 동일하게 맞춘다.
ALTER TABLE public.users
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN role TYPE TEXT USING role::TEXT,
    ALTER COLUMN role SET DEFAULT 'GENERAL',
    ALTER COLUMN countries TYPE TEXT[] USING countries::TEXT[],
    ALTER COLUMN countries SET DEFAULT ARRAY[]::TEXT[],
    ALTER COLUMN expertise_keywords TYPE TEXT[] USING expertise_keywords::TEXT[],
    ALTER COLUMN expertise_keywords SET DEFAULT ARRAY[]::TEXT[],
    ALTER COLUMN lang_c TYPE CHAR(2) USING lang_c::CHAR(2),
    ALTER COLUMN lang_c SET DEFAULT 'KO',
    ALTER COLUMN team_code TYPE CHAR(4) USING team_code::CHAR(4),
    ALTER COLUMN position_code TYPE VARCHAR(3) USING position_code::VARCHAR(3);

-- 기존 이름으로 재실행해도 안전하도록 대상 제약조건을 먼저 정리한다.
ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_id_8_digits_check,
    DROP CONSTRAINT IF EXISTS users_role_permission_fkey,
    DROP CONSTRAINT IF EXISTS users_lang_c_language_fkey,
    DROP CONSTRAINT IF EXISTS users_team_code_fkey,
    DROP CONSTRAINT IF EXISTS users_position_code_fkey;

-- 원본 데이터를 모든 사용자 컬럼 기준으로 그대로 복사한다.
INSERT INTO public.users (
    id,
    username,
    password_hash,
    created_at,
    role,
    display_name,
    department,
    countries,
    expertise_keywords,
    email,
    lang_c,
    team_code,
    position_code
)
SELECT
    id,
    username,
    password_hash,
    created_at,
    role,
    display_name,
    department,
    countries,
    expertise_keywords,
    email,
    lang_c,
    team_code,
    position_code
FROM public.users_kyj;

-- users_kyj의 NOT NULL 및 참조 무결성 규칙을 users에 적용한다.
ALTER TABLE public.users
    ALTER COLUMN role SET NOT NULL,
    ALTER COLUMN countries SET NOT NULL,
    ALTER COLUMN expertise_keywords SET NOT NULL,
    ALTER COLUMN email SET NOT NULL,
    ALTER COLUMN lang_c SET NOT NULL,
    ADD CONSTRAINT users_id_8_digits_check
        CHECK (id >= 10000000 AND id <= 99999999),
    ADD CONSTRAINT users_role_permission_fkey
        FOREIGN KEY (role) REFERENCES public.permission_info(code),
    ADD CONSTRAINT users_lang_c_language_fkey
        FOREIGN KEY (lang_c) REFERENCES public.language_info(code),
    ADD CONSTRAINT users_team_code_fkey
        FOREIGN KEY (team_code) REFERENCES public.team_info(org_code),
    ADD CONSTRAINT users_position_code_fkey
        FOREIGN KEY (position_code) REFERENCES public.position_info(code);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_key
    ON public.users USING btree (email);

-- countries 배열의 각 코드가 countries_info에 존재하는지 검증한다.
CREATE OR REPLACE FUNCTION public.users_countries_fkey_check()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    invalid TEXT[];
BEGIN
    SELECT array_agg(country_code)
      INTO invalid
      FROM unnest(NEW.countries) AS country_code
     WHERE country_code NOT IN (SELECT code FROM public.countries_info);

    IF invalid IS NOT NULL THEN
        RAISE EXCEPTION USING
            MESSAGE = format('users.countries references unknown country code(s): %s', invalid),
            ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS users_countries_fkey_trigger ON public.users;
CREATE TRIGGER users_countries_fkey_trigger
BEFORE INSERT OR UPDATE OF countries ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.users_countries_fkey_check();

-- 복사 누락 여부를 트랜잭션 안에서 검증한다.
DO $block$
BEGIN
    IF (SELECT count(*) FROM public.users)
       <> (SELECT count(*) FROM public.users_kyj) THEN
        RAISE EXCEPTION 'users copy count mismatch';
    END IF;
END;
$block$;

COMMIT;

-- 실행 결과 확인용 조회문
SELECT
    (SELECT count(*) FROM public.users_kyj) AS source_count,
    (SELECT count(*) FROM public.users) AS copied_count;

SELECT
    id,
    username,
    email,
    role,
    lang_c,
    team_code,
    position_code,
    countries
FROM public.users
ORDER BY id;
