-- users_kyj 사용자별 챗봇 응답 언어 코드 마이그레이션
-- 기존 사용자는 최초 실행 시에만 ko/en 중 하나로 무작위 배정됩니다.

BEGIN;

ALTER TABLE public.users_kyj
    ADD COLUMN IF NOT EXISTS lang_c CHAR(2);

UPDATE public.users_kyj
SET lang_c = CASE WHEN random() < 0.5 THEN 'ko' ELSE 'en' END
WHERE lang_c IS NULL;

ALTER TABLE public.users_kyj
    ALTER COLUMN lang_c SET DEFAULT 'ko',
    ALTER COLUMN lang_c SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_kyj_lang_c_check'
          AND conrelid = 'public.users_kyj'::regclass
    ) THEN
        ALTER TABLE public.users_kyj
            ADD CONSTRAINT users_kyj_lang_c_check
            CHECK (lang_c IN ('ko', 'en'));
    END IF;
END
$$;

COMMIT;

SELECT username, role, lang_c
FROM public.users_kyj
ORDER BY username;
