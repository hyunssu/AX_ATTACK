-- 
--

[] 매뉴얼 작성 후 보정(AI기능추가).
[] 매뉴얼 함수 제공.
[] 휴지통 삭제/복원.
[] 카드 등록/삭제/이동.
[] 카드명 변경 없음.
[] 언어설정(ko, en) => 매뉴얼은 언어별로 만들어줘야해.
[] 동시편집 기능.
[] 임베딩 모델 컬럼 추가.

-- 
[] _kyj 제거....
[] terms 테이블 등록

-- public.terms definition

-- Drop table

-- DROP TABLE public.terms;

CREATE TABLE public.terms (
	term_id int4 NULL,
  status
	term_name varchar(100) NULL,
	synonyms varchar(255) NULL, => text로 필요해보임.
 	definition text NULL,      
	category varchar(50) NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL
);


