-- manuals_kyj 매뉴얼 언어 코드 마이그레이션
-- 기존 매뉴얼은 기본값 'ko'로 설정됩니다.

BEGIN;

ALTER TABLE public.manuals_kyj
    ADD COLUMN IF NOT EXISTS lang_c CHAR(2);

UPDATE public.manuals_kyj
SET lang_c = 'ko'
WHERE lang_c IS NULL;

ALTER TABLE public.manuals_kyj
    ALTER COLUMN lang_c SET DEFAULT 'ko',
    ALTER COLUMN lang_c SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'manuals_kyj_lang_c_check'
          AND conrelid = 'public.manuals_kyj'::regclass
    ) THEN
        ALTER TABLE public.manuals_kyj
            ADD CONSTRAINT manuals_kyj_lang_c_check
            CHECK (lang_c IN ('ko', 'en'));
    END IF;
END
$$;

COMMIT;

SELECT id, title, lang_c, created_at
FROM public.manuals_kyj
ORDER BY id;
