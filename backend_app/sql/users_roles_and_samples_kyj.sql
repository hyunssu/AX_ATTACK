-- 사용자 역할 컬럼과 샘플 계정을 추가하는 DBeaver 수동 실행 SQL입니다.
-- 애플리케이션은 이 파일을 자동 실행하지 않습니다.

BEGIN;

ALTER TABLE public.users_kyj
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'LocalUser';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_kyj_role_check'
          AND conrelid = 'public.users_kyj'::regclass
    ) THEN
        ALTER TABLE public.users_kyj
            ADD CONSTRAINT users_kyj_role_check
            CHECK (role IN ('Admin', 'Developer', 'LocalUser'));
    END IF;
END
$$;

-- 현재 사용 중인 kyj 계정에 FAQ 검수 권한을 부여합니다.
UPDATE public.users_kyj
SET role = 'Admin'
WHERE username = 'kyj';

-- 샘플 비밀번호는 개발용이며 운영 사용 전 반드시 변경하세요.
-- admin_sample     / ChangeMe_Admin_2026!
-- developer_sample / ChangeMe_Dev_2026!
-- localuser_sample / ChangeMe_Local_2026!
INSERT INTO public.users_kyj (username, password_hash, role)
VALUES
    ('admin_sample', '$2b$12$t/4YWY5EzkafzcrzII5MweSeuNNzwTb3Ra/.2Ul/ZfcJaIn.R9uKu', 'Admin'),
    ('developer_sample', '$2b$12$MRzKrjPMueyP/6Jwa0GISeEgwlI58LH./i3MMigl9Rxzim49HcNJ6', 'Developer'),
    ('localuser_sample', '$2b$12$Lx.ZYW9u0C3grZwIXfrIROc.eCEcF4RVwyaCJqWCm/Zg4WBzhBSQG', 'LocalUser')
ON CONFLICT (username) DO NOTHING;

COMMIT;

-- 실행 후 확인
SELECT username, role, created_at
FROM public.users_kyj
WHERE username IN ('kyj', 'admin_sample', 'developer_sample', 'localuser_sample')
ORDER BY username;
