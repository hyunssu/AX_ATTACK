# 직원 회원관리 시스템 — 종합 안내 (users_kyj 통합 완료)

기준일: 2026-09-20
작성 범위: 로그인/회원가입/마이페이지 기능 전체 + `employee_info` → `users_kyj` 통합 작업

> **2026-09-20 업데이트**: 이 기능은 원래 `employee_info`라는 별도 테이블 기반으로
> 만들어졌고, 기존 `users_kyj` 로그인과 한동안 병행 운영됐다. 이후 세션에서
> `users_kyj` 스키마 자체를 확장(`team_code`/`position_code`/`countries` 추가,
> `role`/`lang_c`를 메타테이블 FK로 전환)해서 `employee_info`가 갖고 있던 정보를
> 전부 흡수했고, 이번 작업에서 애플리케이션 코드(로그인/회원가입/마이페이지/헤더)도
> `users_kyj` 하나만 바라보도록 정리했다. **`employee_info` 테이블은 더 이상 어떤
> 코드에서도 참조하지 않는다** (DB에는 아직 테이블 자체가 남아있을 수 있으나 죽은
> 데이터다).

## 1. 현재 기능 정의

### 1.1 로그인 화면 (`/login`)
- "AITHER → AI → AGENT" 로고 조립 애니메이션 + 단순 로그인 폼.
- **`POST /api/employees/login` 단일 경로로 통일** — 과거처럼 신규(employee)/레거시(users_kyj) 두 API를 순차 시도하지 않는다. `LoginPage.jsx`는 `loginEmployee()` 하나만 호출한다.
- 로그인 폼의 "아이디"는 `users_kyj.username`, "비밀번호"는 `users_kyj.password_hash`(bcrypt)를 그대로 조회/검증한다.
- ID 기억하기 체크박스는 그대로(프론트 전용, `localStorage`).

### 1.2 회원가입 (`/signup`)
- 입력 항목: **사번**(`users_kyj.id`, 8자리 숫자, 중복 불가), **ID**(`users_kyj.username`, 영문/숫자/언더스코어 3~50자 — 더 이상 8자리 숫자 제한 아님), PW(8자 이상 영숫자) + PW 확인, 이메일, 소속(**본국행원여부 → 회사 → 팀 → 파트 4단 캐스케이딩** select), 직급, 보유 권한, 언어코드, **담당국가(체크박스, 다중 선택, 선택 사항)**.
- **사번(`id`)과 ID(`username`)는 서로 다른 컬럼이다.** `id`는 `users_kyj`의 정수 PK이자 헤더에 표시되는 값(1.6 참고), `username`은 로그인 시 입력하는 아이디다. 둘 다 유일해야 하고, 회원가입 시 각각 따로 중복 검사한다(`id`는 409 "이미 사용 중인 사번입니다.", `username`은 409 "이미 사용 중인 ID입니다.").
- 사번 형식 검증은 `emp_validators.py`의 `EMP_NO_PATTERN`(`^\d{8}$`)이 프론트(`EMP_NO_RE`)와 동일하게 적용된다.
- 소속 4단 캐스케이딩은 `team_info.org_code = domestic_code‖company_code‖team_code‖part_code`(4자리) 구조를 그대로 따라간다. `domestic_code`는 별도 이름 메타테이블이 없어서 프론트에 라벨을 하드코딩한다: `'1' → '본국직원'`, `'2' → '현지직원'`(그 외 코드는 값 그대로 표시). `SignupPage.jsx`/`MyPage.jsx` 양쪽에 `DOMESTIC_CODE_LABELS` 상수로 존재.
- 담당국가는 `users_kyj.countries`(`TEXT[]`)에 저장되고, `countries_info` 참조 무결성은 DB 트리거(`users_kyj_countries_fkey_trigger`)가 검증한다 — 목록은 `GET /api/employees/meta`의 `countries` 필드로 내려준다. 라벨은 `langCode === 'EN' ? name_en : name_ko`.
- select 표시 형식은 `{code}-{name_en}({name_ko})` (언어코드만 `{code}` 단독).
- 가입하려면 이메일 본인인증 완료 필요(1.3).

> ✅ **`users_kyj.id`(정수 PK, 사번) 입력이 완성됐다.** 한동안은 `id` 컬럼에
> 자동증가 default가 없어서(추후 입력 항목으로 받을 예정) 회원가입 시
> `nextval('users_kyj_id_seq')`로 임시 채번했었는데, 이제 회원가입 화면에서
> 사용자가 직접 입력하고 서버가 형식(8자리 숫자)·중복을 검증해 그대로 저장한다.
> 로그인 ID(`username`)와는 별개 값이라는 점을 헷갈리지 않아야 한다 — 로그인은
> 여전히 `username`/`password`로 한다.

### 1.3 이메일 본인인증
- 변경 없음: `idle → sent(5분 타이머) → verified` 3단계, 회원가입/마이페이지 공용.

### 1.4 로그인 (통일)
- 과거엔 "신규 employee 우선 시도 → 실패 시 기존 users_kyj로 폴백"하는 이중 로그인 로직이었으나, DB가 하나로 통합됐으므로 **`POST /api/employees/login` 하나만 쓴다.** `frontend/src/api.js`의 레거시 `login()`(`/api/auth/login` 호출)은 이제 어디서도 호출되지 않는 죽은 코드다(삭제 요청은 없어서 남겨둠 — 7장 참고).
- JWT도 하나로 통일됐다: `emp_router.py`가 더 이상 자체 토큰 함수를 쓰지 않고 `auth/service.py`의 `create_access_token()`/`get_current_user()`를 그대로 재사용한다. 자세한 내용은 5.1 참고.

### 1.5 마이페이지 (`/mypage`)
- 회원가입과 동일한 4단 소속 캐스케이딩 + 담당국가 체크박스 적용.
- 화면 상단에 **사번(`id`)과 ID(`username`)를 각각 별도 읽기 전용 필드로 표시**한다(둘 다 회원가입 이후 변경 불가). `GET /api/employees/me` 응답에 이제 `id`(정수 사번)와 `username`(로그인 ID)이 각각 따로 내려온다.
- **ID(`username`), 사번(`id`), 보유 권한(`role`)은 변경 불가**(읽기 전용). 나머지(PW, 이메일, 소속, 직급, 언어코드, 담당국가)는 전부 변경 가능.
- 저장 전 이메일 본인인증 재확인 필요, 비밀번호는 비워두면 미변경.
- **레거시 계정 리다이렉트 가드를 제거했다.** 예전에는 `users_kyj`로 로그인한 계정이 `/mypage`에 들어오면 자동으로 `/mindmap`으로 돌려보냈는데(employee 전용 기능이었으므로), 이제 모든 계정이 `users_kyj` 기반이라 `/api/employees/me`가 항상 성공하므로 그 가드는 의미가 없어져 삭제했다.

### 1.6 헤더 사용자 정보 표시
- `app-header__user` 표시에서 **"employee vs 레거시" 분기를 완전히 제거**했다 — 이제 모든 계정이 동일한 형식을 쓴다:
  - `GENERAL`: `{ID} · {직급명}({권한명})`
  - `ADMIN`: `{ID} · {직급명}({권한명}) · ADMIN`
- 여기서 **`{ID}`는 `users_kyj.id`(정수 사번)다 — 로그인에 쓰는 `username`이 아니다.** `emp_service.py::get_employee()`가 `SELECT id, username, ...`으로 둘 다 조회해서, `/login`·`/me` 응답의 `id` 필드는 진짜 정수 PK를 담고(과거엔 `username AS id`로 별칭 처리했었다), 그 값이 `auth.jsx`의 `resolveEmployeeProfile()` → `Header.jsx`의 `employee.id`로 그대로 흘러간다.
- 직급/권한 명칭은 여전히 로그인한 사용자의 언어코드에 따라 자동 전환(`lang_code === 'EN'`이면 `name_en`).
- "마이페이지" 버튼도 모든 계정에서 노출(과거엔 employee 계정만). 로딩 중 깜빡임 방지용 `employee &&` 가드는 유지.

## 2. 파일 구성

### 백엔드 (`backend_app/auth/`) — 파일 구조는 유지, 내부 쿼리만 `users_kyj`로 교체
| 파일 | 역할 | 참조 테이블 |
|---|---|---|
| `emp_tables.py` | 메타테이블 이름 상수 (`EMPLOYEE_INFO` 제거, `COUNTRIES_INFO` 추가) | - |
| `emp_config.py` | 이메일 인증 TTL, 본인인증 메일 발송 계정 설정 (JWT 관련 상수는 제거됨) | - |
| `emp_validators.py` | ID/PW/이메일 형식 정규식 + 에러 문구 | - |
| `emp_service.py` | 로그인 검증, 직원 조회 (JWT 함수는 삭제, `auth/service.py`로 통합) | `users_kyj` |
| `emp_meta.py` | 회사/팀/파트/직급/권한/언어/**담당국가** 목록 조회 | `team_info`, `position_info`, `permission_info`, `language_info`, `countries_info` |
| `emp_mailer.py` | 인증번호 이메일 발송 | - |
| `emp_verify.py` | 인증번호 발급/확인/만료 | `email_verifications` |
| `emp_register.py` | 회원가입(INSERT) | `users_kyj` |
| `emp_profile.py` | 마이페이지 조회/수정(UPDATE) | `users_kyj` |
| `emp_router.py` | API 엔드포인트 (`/api/employees/*`), 토큰 발급/검증은 `auth/service.py` 재사용 | - |

`auth/service.py`(레거시 `users_kyj` 인증 로직)는 변경 없음 — 오히려 이번 통합으로 이 모듈이 **유일한 인증 원천**이 됐다. `auth/router.py`(`/api/auth/*`)도 코드는 그대로 남아있지만 프론트 어디에서도 호출하지 않는다(7장 참고).

### API 엔드포인트 (`/api/employees` prefix) — 변경 없음, `meta`만 `countries` 추가
| Method | Path | 설명 |
|---|---|---|
| POST | `/login` | `users_kyj` 로그인, `auth/service.create_access_token()`으로 발급 |
| GET | `/me` | 내 정보 조회 (`countries` 포함) |
| PUT | `/me` | 내 정보 수정 — ID·role 제외 (`countries` 포함) |
| GET | `/meta` | 회사/팀/파트/직급/권한/언어/**담당국가** 전체 목록 |
| POST | `/verify-email/request` \| `/verify-email/confirm` | 이메일 인증 |
| POST | `/register` | 회원가입 |

## 3. `users_kyj` 스키마 요약 (직원 관련 컬럼만)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | `INTEGER PK` | 자동증가 default 없음. 회원가입 화면에서 사용자가 직접 입력(8자리 숫자, 중복검사) — "사번", 헤더에 표시되는 값(1.6). `username`(로그인 ID)과는 별개 |
| `username` | `TEXT UNIQUE NOT NULL` | 로그인 ID |
| `password_hash` | `TEXT` | bcrypt |
| `email` | `TEXT` | |
| `role` | `TEXT` | FK → `permission_info(code)` (`GENERAL`/`ADMIN`) |
| `lang_c` | `CHAR(2)` | FK → `language_info(code)` (`KO`/`EN`, 대문자) |
| `team_code` | `CHAR(4)` | FK → `team_info(org_code)` |
| `position_code` | `VARCHAR(3)` | FK → `position_info(code)` |
| `countries` | `TEXT[]` | 트리거로 `countries_info(code)` 참조 검증 |
| `department`, `expertise_keywords` | | FAQ 자동배정 전용 (직원 회원관리 화면과는 무관) |

메타테이블: `team_info`(`org_code` PK, `domestic_code`+`company_code`+`team_code`+`part_code` 조합), `position_info`, `permission_info`, `language_info`, `countries_info`, `email_verifications`.

## 4. 알려진 제약

### 4.1 언어 라벨 한계
`position_info`/`permission_info`는 `name_ko`/`name_en`만 있고 `name_jp`가 없다. `language_info`에도 현재 `JP`는 없음(`KO`/`EN`만).

### 4.2 `team_info` 비정규화 구조
회사/팀/파트/본국여부가 정규화된 여러 테이블이 아니라 조합별 1행짜리 단일 테이블. 새 조직 조합을 추가하려면 `team_info`에 새 행을 INSERT해야 한다(관리 화면 없음, SQL 직접 실행).

### 4.3 `domestic_code` 라벨이 프론트에 하드코딩되어 있음
`'1'`/`'2'` 외의 코드가 추가되면(`team_info`에 실제로 `'0'` 값도 존재) 화면엔 코드 그대로 표시된다. 이름이 필요하면 별도 메타테이블을 만들거나 `DOMESTIC_CODE_LABELS`(SignupPage.jsx/MyPage.jsx)를 갱신해야 한다.

### 4.4 이 작업과 무관하게 발견된 이슈
`/api/chat/rooms` 등 채팅 관련 API가 500을 내는 문제가 있었는데, 원인은 `.env`가 가리키는 DB에 `chat_rooms_kyj`/`chat_messages_kyj` 테이블 자체가 없어서였다(별도 스키마 마이그레이션 필요, 직원 회원관리 기능과 무관).

## 5. JWT 통합 (완료)

과거엔 employee 토큰을 `auth/service.py`의 `JWT_SECRET`/`JWT_ALGORITHM`을 재사용하되 **만료시간만 10분으로 별도로 짧게** 발급하는 "임시 다리"였다(자세한 배경은 git 히스토리의 이전 버전 README 참고). 이번 통합으로:

- `emp_service.py`의 `create_employee_access_token()`/`get_current_employee_id()`는 **삭제**.
- `emp_router.py`는 `auth/service.py`의 `create_access_token()`/`get_current_user()`를 그대로 `import`해서 쓴다.
- `emp_config.py`의 `EMP_JWT_SECRET`/`EMP_JWT_ALGORITHM`/`EMP_JWT_EXPIRE_MINUTES`는 **삭제**(이메일 인증 관련 설정만 남음).

이제 `/api/employees/login`으로 받은 토큰과 `/api/auth/login`으로 받은 토큰은 완전히 동일한 방식(같은 시크릿, 같은 만료시간, 같은 `sub`=username)으로 발급되고, `sub` 값이 실제로 `users_kyj.username`이므로 `chat/router.py`, `faq/router.py`, `manuals/router.py` 등 다른 모든 라우터의 `get_current_user()`/`get_user_role()`/`get_user_language()`가 별도 처리 없이 정확하게 동작한다 — 과거 "로그인은 되지만 역할/언어 정보가 비어있다"는 어중간한 상태가 완전히 해소됐다.

## 6. 권한 게이트 현황

`Header.jsx`/`App.jsx`의 `FAQRoleGate`는 `role === 'ADMIN'`만 확인한다(과거 `['Admin','Developer'].includes(role)` 방식에서 마이그레이션됨). FAQ 검수 기능(`faq/router.py`, `faq/intake.py`)은 여기서 한 단계 더 나아가, **`role !== 'ADMIN'`이어도 `team_code`의 첫 글자(`domestic_code`)가 `'1'`이면 통과**시키는 `_is_domestic_staff()` 게이트가 추가로 있다 — 옛 3단계 체계(`Admin`/`Developer`/`LocalUser`)의 `Developer` 등급을 "국내 소속(`domestic_code='1'`) + `role=GENERAL`" 조합으로 복원한 것이다. 적용 위치: `_require_reviewer()`, `list_assignees()`, FAQ 재배정 대상 검증, `_assignment_candidates()`(자동배정 후보) 4곳. FAQ 전체조회 권한(`_get_request`/`list_faqs`)과 메시지 작성자 태깅(`add_message`)은 원래도 `Admin` 전용이었으므로 그대로 `role === 'ADMIN'`만 본다.

팀 단위 제한(예: "내 팀 데이터만 보인다")은 아직 어떤 화면에도 구현되어 있지 않다 — 필요해지면 `employee.teamCode`(프론트) / `users_kyj.team_code`(백엔드)를 같은 방식으로 검사하면 된다.

## 7. 정리 후보 (삭제하진 않았지만 사실상 미사용)

- `backend_app/auth/router.py`, `service.py`의 `/api/auth/login`, `/api/auth/register` — `LoginPage.jsx`가 더 이상 호출하지 않는다. 단, `auth/service.py`의 `get_current_user()`/`get_user_role()`/`get_user_language()`/`create_access_token()`은 **여전히 전체 시스템의 인증 백본**이라 절대 지우면 안 된다 — 지울 후보는 `router.py`의 HTTP 엔드포인트 2개(`/login`, `/register`)와 `service.py`의 `create_user()`뿐이다. `create_user()`는 애초에 `users_kyj.id` 자동증가가 없어진 뒤로 호출하면 무조건 실패하는 상태였다.
- `frontend/src/api.js`의 `login()`/`register()` 함수 — 호출부 없음.

## 8. 검증 이력

- (사번 입력 기능 이전) 신규 계정 회원가입 E2E(이메일 인증 → 4단 소속 선택 → 담당국가 체크 → 가입 → 로그인 → 헤더 표시 → 마이페이지 재조회) 브라우저로 직접 수행, `users_kyj`에 기대한 값(`team_code`, `role`, `lang_c`, `countries`)이 정확히 저장되는 것까지 확인.
- (사번 입력 기능 이전) ADMIN 계정 헤더 표시(`· ADMIN` 접미사) 확인.
- (사번 입력 기능 이전) FAQ 권한 게이트(ADMIN 전체 접근 / 국내 소속 GENERAL 접근 / 그 외 403) 회귀 없음 확인.

> ⚠️ **사번(`id`) 입력 기능은 아직 실기동 검증을 못 했다.** 작업 중 개발 환경의
> 디스크 용량이 가득 차서 Docker 데몬이 응답을 멈췄다(`docker ps`조차 타임아웃).
> 코드 변경(백엔드 5개 파일, 프론트 3개 파일)은 전부 반영했지만, 백엔드 재기동·
> 회원가입 E2E·사번 중복 검사 동작은 디스크 공간을 확보하고 Docker를 복구한
> 뒤에 다시 검증해야 한다.
