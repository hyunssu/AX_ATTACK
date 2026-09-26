-- 카테고리(=파트) 카드를 team_info 조직과 연결하는 마이그레이션입니다.
-- DBeaver에서 검토 후 직접 실행하세요. 애플리케이션은 이 SQL을 자동 실행하지 않습니다.
--
-- manual_categories.org_code가 채워진 카테고리는 team_info의 해당 팀/파트
-- 소속 직원만 수정 가능하고, org_code가 NULL인 카테고리(카드/기타 등 조직에
-- 매칭되지 않는 카테고리)는 ADMIN만 수정 가능합니다.

BEGIN;

ALTER TABLE public.manual_categories
    ADD COLUMN IF NOT EXISTS org_code CHAR(4) REFERENCES public.team_info(org_code);

UPDATE public.manual_categories SET org_code = '1111' WHERE name = '고객';
UPDATE public.manual_categories SET org_code = '1112' WHERE name = '수신';
UPDATE public.manual_categories SET org_code = '1113' WHERE name = '여신';
UPDATE public.manual_categories SET org_code = '1114' WHERE name = '외환';
UPDATE public.manual_categories SET org_code = '1115' WHERE name = '자금';
-- '카드', '기타'는 team_info에 대응하는 파트가 없어 org_code를 NULL로 둡니다 (ADMIN 전용).

COMMIT;

SELECT c.name, c.org_code, t.team_name_ko, t.part_name_ko
FROM public.manual_categories c
LEFT JOIN public.team_info t ON t.org_code = c.org_code
ORDER BY c.sort_order;
