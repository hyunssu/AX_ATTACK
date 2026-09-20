-- 신규 회원관리(직원) 기능이 사용하는 테이블 정의.
-- 기존 테이블(users_kyj 등)은 전혀 건드리지 않으며, 완전히 새로운 테이블만 추가한다.
-- 프로젝트 관례에 따라 backend_app은 이 파일을 자동 실행하지 않는다.
-- 검토 후 DBeaver 등에서 직접 실행할 것.

-- 2-1. 직급정보 (메타)
CREATE TABLE IF NOT EXISTS position_info (
    code VARCHAR(3) PRIMARY KEY,
    name_ko VARCHAR(50) NOT NULL,
    name_en VARCHAR(50) NOT NULL
);

INSERT INTO position_info (code, name_ko, name_en) VALUES
    ('L', '부장', 'Director'),
    ('M', '부부장', 'Vice Director'),
    ('S2', '차장', 'Assistant Manager'),
    ('S1', '과장', 'Manager'),
    ('J2', '대리', 'Specialist'),
    ('J1', '사원', 'Employee'),
    ('XS2', '차장', 'Assistant Manager'),
    ('XS1', '과장', 'Manager'),
    ('XJ2', '대리', 'Specialist'),
    ('XJ1', '사원', 'Employee')
ON CONFLICT (code) DO NOTHING;

-- 2-2. 권한정보 (메타)
CREATE TABLE IF NOT EXISTS permission_info (
    code VARCHAR(20) PRIMARY KEY,
    name_ko VARCHAR(50) NOT NULL,
    name_en VARCHAR(50) NOT NULL
);

INSERT INTO permission_info (code, name_ko, name_en) VALUES
    ('GENERAL', '일반사용자', 'General User'),
    ('ADMIN', '관리자', 'Administrator')
ON CONFLICT (code) DO NOTHING;

-- 2-3. 언어정보 (메타)
CREATE TABLE IF NOT EXISTS language_info (
    code VARCHAR(2) PRIMARY KEY,
    name_ko VARCHAR(50) NOT NULL,
    name_en VARCHAR(50) NOT NULL
);

INSERT INTO language_info (code, name_ko, name_en) VALUES
    ('KO', '한국어', 'Korean'),
    ('EN', '영어', 'English')
ON CONFLICT (code) DO NOTHING;

-- 1-2. team_info : 조직도정보
-- org_code는 company_code + team_code + part_code를 이어붙인 값이며,
-- employee_info.team_code가 이 값을 그대로 참조한다.
CREATE TABLE IF NOT EXISTS team_info (
    org_code CHAR(3) PRIMARY KEY,
    company_code CHAR(1) NOT NULL,
    company_name_ko VARCHAR(100) NOT NULL,
    company_name_en VARCHAR(100) NOT NULL,
    team_code CHAR(1) NOT NULL,
    team_name_ko VARCHAR(100) NOT NULL,
    team_name_en VARCHAR(100) NOT NULL,
    part_code CHAR(1) NOT NULL,
    part_name_ko VARCHAR(100) NOT NULL,
    part_name_en VARCHAR(100) NOT NULL,
    UNIQUE (company_code, team_code, part_code),
    CHECK (org_code = company_code || team_code || part_code)
);

-- 예시 데이터 (회사 1:SHBDS, 팀 1:뱅킹글로벌, 파트 1:공통 -> 111)
INSERT INTO team_info (org_code, company_code, company_name_ko, company_name_en, team_code, team_name_ko, team_name_en, part_code, part_name_ko, part_name_en)
VALUES
    ('111', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '1', '고객', 'Customer'),
    ('112', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '2', '수신', 'Deposit'),
    ('113', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '3', '여신', 'Loan'),
    ('114', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '4', '외환', 'Foreign Exchange'),
    ('115', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '5', '자금', 'Funding'),
    ('116', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '6', '채널', 'Channel'),
    ('117', '1', 'SHB', 'SHB', '1', '글로벌개발부', 'Global Development Department', '7', '디지털', 'Digital'),
    
    ('211', '2', 'SHDS', 'SHDS', '2', '뱅킹글로벌', 'Banking Global', '1', 'DS공통', 'DS Common'),
    ('212', '2', 'SHDS', 'SHDS', '2', '뱅킹글로벌', 'Banking Global', '2', 'DS수신', 'DS Deposit'),
    ('213', '2', 'SHDS', 'SHDS', '2', '뱅킹글로벌', 'Banking Global', '3', 'DS여신', 'DS Credit'),
    ('214', '2', 'SHDS', 'SHDS', '2', '뱅킹글로벌', 'Banking Global', '4', 'DS외환', 'DS Foreign Exchange'),
    ('216', '2', 'SHDS', 'SHDS', '2', '뱅킹글로벌', 'Banking Global', '6', 'DS채널', 'DS Channel')
ON CONFLICT (org_code) DO NOTHING;

-- 1-1. employee_info : 사용자별 정보
-- id 컬럼 자체가 로그인 아이디이자 기본키다 (별도 surrogate 키 없음).
CREATE TABLE IF NOT EXISTS employee_info (
    id VARCHAR(50) PRIMARY KEY,
    password_hash TEXT NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    team_code CHAR(3) NOT NULL REFERENCES team_info(org_code),
    position_code VARCHAR(3) NOT NULL REFERENCES position_info(code),
    permission_code VARCHAR(20) NOT NULL REFERENCES permission_info(code),
    lang_code VARCHAR(2) NOT NULL DEFAULT 'EN' REFERENCES language_info(code),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- 회원가입 이메일 인증(2-2)용 임시 저장소.
-- 이메일 하나당 최신 인증번호 1건만 유지한다 (재요청 시 덮어씀).
CREATE TABLE IF NOT EXISTS email_verifications (
    email VARCHAR(255) PRIMARY KEY,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
