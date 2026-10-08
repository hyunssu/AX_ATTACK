BEGIN;

-- Clone the live schema only; leave existing chunks and application routing intact.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS public.manual_parent_chunks_v2 (
    LIKE public.manual_parent_chunks INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS public.manual_child_chunks_v2 (
    LIKE public.manual_child_chunks INCLUDING ALL
);

-- LIKE copies serial defaults, so replace their links to the original sequences.
CREATE SEQUENCE IF NOT EXISTS public.manual_parent_chunks_v2_id_seq AS integer;
ALTER SEQUENCE public.manual_parent_chunks_v2_id_seq
    OWNED BY public.manual_parent_chunks_v2.id;
ALTER TABLE public.manual_parent_chunks_v2
    ALTER COLUMN id SET DEFAULT nextval('public.manual_parent_chunks_v2_id_seq'::regclass);

CREATE SEQUENCE IF NOT EXISTS public.manual_child_chunks_v2_id_seq AS integer;
ALTER SEQUENCE public.manual_child_chunks_v2_id_seq
    OWNED BY public.manual_child_chunks_v2.id;
ALTER TABLE public.manual_child_chunks_v2
    ALTER COLUMN id SET DEFAULT nextval('public.manual_child_chunks_v2_id_seq'::regclass);

ALTER TABLE public.manual_child_chunks_v2
    ADD COLUMN IF NOT EXISTS lang_c CHAR(2) NOT NULL DEFAULT 'ko';

-- Foreign keys are not included by LIKE; recreate them with an isolated parent link.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.manual_parent_chunks_v2'::regclass
          AND conname = 'manual_parent_chunks_v2_manual_id_fkey'
    ) THEN
        ALTER TABLE public.manual_parent_chunks_v2
            ADD CONSTRAINT manual_parent_chunks_v2_manual_id_fkey
            FOREIGN KEY (manual_id) REFERENCES public.manuals(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.manual_parent_chunks_v2'::regclass
          AND conname = 'manual_parent_chunks_v2_version_id_fkey'
    ) THEN
        ALTER TABLE public.manual_parent_chunks_v2
            ADD CONSTRAINT manual_parent_chunks_v2_version_id_fkey
            FOREIGN KEY (version_id) REFERENCES public.manual_versions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.manual_child_chunks_v2'::regclass
          AND conname = 'manual_child_chunks_v2_parent_id_fkey'
    ) THEN
        ALTER TABLE public.manual_child_chunks_v2
            ADD CONSTRAINT manual_child_chunks_v2_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES public.manual_parent_chunks_v2(id) ON DELETE CASCADE;
    END IF;
END
$$;

COMMIT;
