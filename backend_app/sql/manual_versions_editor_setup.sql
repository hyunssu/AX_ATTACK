-- manual_versions에 에디터 content 컬럼 추가 + manual_drafts 제거
-- DBeaver에서 직접 실행하세요.

BEGIN;

ALTER TABLE public.manual_versions
    ADD COLUMN IF NOT EXISTS content_json JSONB;

-- MinIO 오브젝트명 저장 (Presigned URL 만료 후 재다운로드용)
ALTER TABLE public.manual_versions
    ADD COLUMN IF NOT EXISTS storage_path TEXT;

DROP TABLE IF EXISTS public.manual_drafts CASCADE;

COMMIT;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'manual_versions'
ORDER BY ordinal_position;
