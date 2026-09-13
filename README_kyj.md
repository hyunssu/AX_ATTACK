# 아이테르 Ask AI / FAQ Review 현재 구조

> 기준일: 2026-08-17  
> 기준: 현재 `C:\Users\kkyj1\AX_ATTACK` 소스와 적용 완료된 `_kyj` 스키마

이 문서는 아이테르의 **Ask AI 채팅**과 **FAQ Review 검수**가 어떤 테이블과 파일을 사용하며, 한 건의 질문이 어떤 순서로 처리되는지 설명한다.

## 1. 핵심 원칙

- 애플리케이션 테이블은 모두 `_kyj` 접미사를 사용한다.
- 테이블명은 `backend_app/db_tables.py`에서 한 번만 정의하고, 접미사가 빠진 이름이 있으면 애플리케이션 로딩 단계에서 오류를 발생시킨다.
- FastAPI 시작 시 테이블 또는 인덱스를 자동 생성하지 않는다. `backend_app/main.py`는 라우터 등록과 DB 스키마 오류의 JSON 변환만 담당한다.
- LangChain 기본 테이블인 `langchain_pg_collection`, `langchain_pg_embedding`은 사용하지 않는다.
- FAQ 요청과 승인 지식을 별도 원장으로 나누지 않는다. `faq_requests_kyj` 한 테이블에서 상태와 지식검색 허용 여부로 구분한다.
- 채팅 종료 또는 체크포인트만으로 대화 내용을 FAQ로 자동 복제하지 않는다. 지식으로 답하지 못한 질문을 사용자가 최종 확인한 경우에만 FAQ 요청을 생성한다.

## 2. 전체 구조

```mermaid
flowchart LR
    U["사용자 / Ask AI"] --> QP["QAPage.jsx · ChatPanel.jsx"]
    QP --> CR["chat_router.py"]
    CR --> CTX["대화 맥락 요약·업무 여부 판정"]
    CTX --> OWNER["화면 담당자 정확 조회/변경"]
    CTX --> KR["FAQ + 매뉴얼 지식 검색"]
    KR --> FR["faq_requests_kyj\napproved + Y"]
    KR --> MR["manual_chunks_kyj"]
    KR -->|미해결| FI["추가질의·FAQ 접수"]
    FI --> FREQ["faq_requests_kyj"]
    FI --> FMSG["faq_request_messages_kyj"]
    R["Admin / Developer"] --> FP["FAQReviewPage.jsx"]
    FP --> FAQAPI["faq_router.py"]
    FAQAPI --> FREQ
    FAQAPI --> FMSG
    FAQAPI -->|추가질의·승인·반려 알림| CM["chat_messages_kyj"]
    FAQAPI -->|승인 + 검색 허용| EMB["질문·답변 embedding 저장"]
    EMB --> FR
```

## 3. 사용하는 테이블

### 3.1 핵심 채팅/FAQ 테이블

| 테이블 | 역할 | 주요 읽기/쓰기 시점 |
|---|---|---|
| `public.chat_rooms_kyj` | Ask AI 채팅방 원장 | 새 대화 생성, 방 목록 조회, 첫 질문으로 제목 변경, 체크포인트 갱신 |
| `public.chat_messages_kyj` | 원본 사용자/AI 메시지 원장 | 사용자의 질문과 AI 답변 저장, FAQ 담당자의 추가질의·승인·반려 알림 전달 |
| `public.faq_requests_kyj` | FAQ 요청·배정·승인 지식을 합친 단일 원장 | 미해결 질문 접수, 담당자 배정/재배정, 자동요약, 승인/반려, 승인 FAQ 벡터 검색 |
| `public.faq_request_messages_kyj` | FAQ 한 건 안에서 질문자·담당자·관리자가 주고받는 메시지 | 최초 질문/AI 요약, 답변, 추가질의, 질문자 회신, 내부 메모 저장 |

### 3.2 채팅 테이블의 주요 컬럼

`chat_rooms_kyj`

| 컬럼 | 의미 |
|---|---|
| `room_id` | 채팅방 식별자 |
| `room_user` | 채팅방 소유 사용자명 |
| `title` | 최초 질문 앞 30자로 정한 방 제목 |
| `summary` | 채팅방 요약 저장 영역. 현재 실시간 답변 생성에는 직접 사용하지 않는다. |
| `last_summarized_message_id` | 마지막 체크포인트까지 처리했다고 표시한 `chat_id` |
| `regis_date`, `regis_time` | 방 생성 KST 일자 `YYYYMMDD`, 시각 `HHMMSS` |
| `last_change_date`, `last_change_time` | 최근 메시지 시각. Ask AI 방 목록 조회 시 마지막 메시지를 기준으로 동기화 |

`chat_messages_kyj`

| 컬럼 | 의미 |
|---|---|
| `chat_id` | 전체 채팅 메시지 식별자 |
| `room_id` | 소속 채팅방 |
| `role` | `user` 또는 `ai` |
| `text` | 메시지 본문 |
| `type` | 일반 답변/추가 확인 등 UI 표시 유형 |
| `options` | 사용자가 누를 수 있는 선택지 JSON |
| `trace` | 분기, 검색 점수, FAQ 알림 연결정보 등 처리 과정 JSON |
| `sources` | 매뉴얼/FAQ 등 답변 근거와 기준일 JSON |
| `regis_date`, `regis_time` | 메시지 생성 KST 일자와 시각 |

### 3.3 FAQ 원장의 주요 컬럼

`faq_requests_kyj`

| 영역 | 컬럼 | 의미 |
|---|---|---|
| 식별/연결 | `faq_id` | FAQ 요청 식별자 |
| 식별/연결 | `requester_username` | 원 질문자 |
| 식별/연결 | `requester_chat_room_id` | 알림과 추가 답변을 주고받을 원본 Ask AI 방 |
| 검색 | `knowledge_search_allowed` | `Y`이면 승인 후 지식검색에 사용, `N`이면 완료 목록에서만 조회 |
| 질문 | `original_question` | 접수 전 원 질문 |
| 질문 | `refined_question` | 접수 과정에서 정제한 질문 |
| 분류 | `target_business` | `수신/여신/고객/외환/채널/공통/총무/카드/UMS/기타` 중 하나 |
| 분류 | `screen_number`, `country` | 화면번호와 대상 국가 |
| 배정 | `assignee_username` | 실제 `users_kyj`에 존재하는 주 담당자 계정 |
| 배정 | `assignee_display_name`, `assignee_team` | 화면 표시용 이름과 팀 |
| 배정 | `assignment_reason`, `assignment_confidence` | 배정 근거와 `높음/보통/낮음` 신뢰도 |
| 지식 | `summarized_question`, `summarized_answer` | 검수자가 최종 확정하는 FAQ 질문/답변 |
| 지식 | `summarized_question_embedding`, `summarized_answer_embedding` | 승인된 질문과 답변의 1536차원 벡터 |
| 지식 | `final_keywords` | 최종 검색/분류 키워드 배열 |
| 상태 | `status` | `pending`, `assigned`, `approved`, `rejected` |
| 변경 | `last_change_user`, `rejection_reason` | 마지막 변경자와 반려 사유 |
| 일시 | `regis_date/time`, `last_change_date/time` | 등록 및 최종 변경 KST 일시 |

검색 대상은 다음 조건을 모두 만족해야 한다.

```sql
status = 'approved'
AND knowledge_search_allowed = 'Y'
AND (
  summarized_question_embedding IS NOT NULL
  OR summarized_answer_embedding IS NOT NULL
)
```

`faq_request_messages_kyj`

| 컬럼 | 의미 |
|---|---|
| `faq_id` | 소속 FAQ 요청 |
| `faq_chat_id` | FAQ별로 1부터 시작하는 메시지 순번. PK는 `(faq_id, faq_chat_id)` |
| `author_username`, `author_role` | 작성자와 역할(`requester`, `agent`, `assignee`, `admin`) |
| `message_type` | `question`, `summary`, `answer`, `additional_question`, `note` 등 |
| `message_text` | 메시지 본문 |
| `regis_date`, `regis_time` | KST 등록 일자와 시각 |

### 3.4 함께 참조하는 테이블

| 테이블 | 역할 |
|---|---|
| `public.users_kyj` | 로그인, 역할, 언어, 표시 이름, 부서, 이메일 및 FAQ 담당자 후보 제공 |
| `public.manuals_kyj` | 매뉴얼 원장 |
| `public.manual_versions_kyj` | 매뉴얼 버전과 검색 기준일 제공 |
| `public.manual_chunks_kyj` | 매뉴얼 청크 본문, 키워드 검색값, embedding 저장 |
| `public.screen_owners_kyj` | 화면번호별 담당자 정확 조회 및 현재 담당자 원장 |
| `public.screen_owner_changes_kyj` | 사용자가 확인한 화면 담당자 변경 이력 |

### 3.5 더 이상 사용하지 않는 테이블

- `faq_registry_kyj`: 삭제됨. 승인 지식은 `faq_requests_kyj`에 통합되었다.
- `faq_request_participants_kyj`: 삭제됨. FAQ는 원 질문자/원 채팅방과 일대일로 연결한다.
- `chat_answer_feedback_kyj`: 삭제됨. “도움이 되었나요?” 피드백 UI도 제거되었다.
- `langchain_pg_collection`, `langchain_pg_embedding`: 사용하지 않으며 LangChain 기본 저장소도 자동 생성하지 않는다.

## 4. 파일 목록과 역할

### 4.1 프론트엔드

| 파일 | 역할 |
|---|---|
| `frontend/src/App.jsx` | `/qa`, `/faqs` 라우팅과 로그인 보호. FAQ Review는 `Admin`, `Developer`만 접근 허용 |
| `frontend/src/components/Header.jsx` | 역할에 따라 FAQ Review 메뉴 표시 |
| `frontend/src/pages/QAPage.jsx` | Ask AI 방 생성/선택/삭제 및 10초 간격 방 목록 갱신. FAQ 알림 방을 분홍/하늘색으로 표시 |
| `frontend/src/components/ChatPanel.jsx` | 메시지 조회/전송, 15초 폴링, Markdown 답변, 선택지, 답변 근거·기준일·처리 과정 표시 |
| `frontend/src/pages/FAQReviewPage.jsx` | 상태별 FAQ 목록, 담당자 대화, 메시지 삭제, 재배정, 자동요약, 최종 질문/답변 편집, 승인/반려 UI |
| `frontend/src/api.js` | Ask AI와 FAQ Review의 HTTP API 호출 및 JSON 오류 처리 |
| `frontend/src/auth.jsx` | JWT, 사용자명, 역할을 보관하고 로그인/로그아웃 상태 관리 |

### 4.2 백엔드

| 파일 | 역할 |
|---|---|
| `backend_app/main.py` | FastAPI 앱 생성, 인증/매뉴얼/채팅/FAQ 라우터 등록, DB 스키마 오류를 JSON으로 반환 |
| `backend_app/db_tables.py` | 모든 `_kyj` 테이블명의 단일 정의점 및 접미사 검증 |
| `backend_app/db.py` | SQLAlchemy DB 연결 엔진 |
| `backend_app/config.py` | OpenAI 모델, 검색 임계값, JWT, SMTP 등 환경설정 |
| `backend_app/auth.py` | JWT 사용자 확인, `users_kyj` 비밀번호/역할/언어 조회 |
| `backend_app/routers/auth_router.py` | 로그인 및 현재 사용자 API |
| `backend_app/routers/chat_router.py` | 채팅방/메시지 API와 Ask AI의 전체 분기 오케스트레이션 |
| `backend_app/faq_intake.py` | 대화 맥락 요약, 업무 질문 판정, 미해결 질문 분석, 필수 대상국가 추가질의, 접수 확인/수정/취소, 담당자 선정, FAQ 생성 |
| `backend_app/knowledge_router.py` | 승인 FAQ와 매뉴얼을 모두 평가하고 임계값 및 기준일로 최종 답변 선택 |
| `backend_app/faq_search.py` | `faq_requests_kyj`의 승인·검색허용 질문/답변 embedding을 검색 |
| `backend_app/rag.py` | 매뉴얼 질의 재작성, hybrid 검색, 컨텍스트 구성 및 LLM 답변 생성 |
| `backend_app/screen_owners.py` | 화면 담당자 조회/변경 의도를 규칙으로 판정하고 원장 정확 조회, 사용자 확인 후 변경 이력 저장 |
| `backend_app/routers/faq_router.py` | FAQ 목록/상세/메시지/삭제/자동요약/재배정/승인/반려 API |
| `backend_app/faq_mailer.py` | FAQ 배정 메일과 승인 완료 메일을 Gmail SMTP로 비동기 발송하고 재시도 |
| `backend_app/prompts.py` | 한국어/영어 LLM 프롬프트와 구조화 출력 설명의 중앙 관리 |

## 5. Ask AI 거래 흐름

### 5.1 채팅방 생성과 조회

1. 사용자가 **새 대화**를 누른다.
2. `POST /api/chat/rooms`가 `chat_rooms_kyj`에 `room_user`를 넣는다.
3. 첫 질문이 오면 방 제목을 질문의 앞 30자로 바꾼다.
4. Ask AI 방 목록을 조회할 때 각 방의 마지막 `chat_messages_kyj` 일시를 `last_change_date/time`에 동기화한다.
5. 방 목록은 10초, 열린 방 메시지는 15초 간격으로 다시 조회한다.

### 5.2 메시지 한 건의 처리 순서

```mermaid
flowchart TD
    A["사용자 메시지 INSERT"] --> B["LLM: 전체 대화 맥락 요약"]
    B --> C{"진행 중인 FAQ 작업인가?"}
    C -->|등록 확인·수정·취소·추가질의 답변| P["FAQ 선처리"]
    C -->|아니오| D["LLM: 아이테르 업무 질문 판정"]
    D -->|비업무| E["LLM: 아이테르 업무 문의로 유도"]
    D -->|업무| F{"화면 담당자 조회/변경인가?"}
    F -->|예| G["담당자 원장 정확 처리"]
    F -->|아니오| H["승인 FAQ 벡터 검색"]
    H --> I["매뉴얼 hybrid 검색 + LLM 답변"]
    I --> J{"임계값 충족 결과"}
    J -->|둘 다| K["기준일이 최신인 답변 선택"]
    J -->|하나| L["해당 지식만 사용"]
    J -->|없음| M["LLM: 질문 분석 및 2~3회 추가질의"]
    M --> N["FAQ 등록 제안"]
    N --> O{"사용자 응답"}
    O -->|그대로 등록| Q["FAQ 요청 INSERT"]
    O -->|내용 수정| N
    O -->|등록 거절| R["접수 취소"]
    O -->|새 질문| D
    P --> S["LLM: 사용자 언어로 최종 표현 통일"]
    E --> S
    G --> S
    K --> S
    L --> S
    Q --> S
    R --> S
    S --> T["AI 메시지 INSERT"]
```

상세 순서는 다음과 같다.

1. 현재 방의 기존 메시지를 읽고 새 사용자 메시지를 `chat_messages_kyj`에 저장한다.
2. `faq_intake.summarize_conversation_context()`가 LLM으로 현재 업무 질문, 확정 사실, 대기 중 추가질의를 한 번에 요약한다.
3. `handle_pre_search_action()`이 검색보다 먼저 다음 상태를 처리한다.
   - FAQ 등록 제안에 대한 그대로 등록/내용 수정/취소/무관한 새 질문
   - 접수된 FAQ의 담당자 변경 요청
   - FAQ Review에서 전달한 추가질의에 대한 질문자 답변
4. 진행 중 FAQ 처리가 아니면 LLM이 아이테르 업무 매뉴얼 질문인지 판정한다.
   - 비업무 질문이면 현재 구현은 일반 ChatGPT 답을 제공하지 않고, 아이테르 업무 관련 질문을 해 달라고 안내한다.
   - 기존 업무 대화의 후속 답변이면 업무 문맥을 유지한다.
5. 업무 질문이면 `screen_owners.py`가 화면 담당자 조회/변경 요청인지 먼저 검사한다.
6. 담당자 요청이 아니면 승인 FAQ와 전체 매뉴얼을 모두 검색한다.
7. 둘 다 임계값을 충족하면 FAQ의 `last_change_date/time`과 매뉴얼 버전 `created_at`을 비교해 더 최근 근거의 답변을 사용한다. 화면에는 양쪽 출처를 함께 표시한다.
8. 한쪽만 임계값을 충족하면 “승인 FAQ 기준” 또는 “매뉴얼 기준”임을 알리고 그 답만 사용한다.
9. 둘 다 미달하면 질문을 분석하고 최대 2~3개의 추가정보를 한 번에 하나씩 묻는다. 국가가 없으면 **대상 국가를 필수로 질문**한다.
10. 추가정보까지 반영해 매 턴 지식검색을 다시 수행하고, 계속 미해결이면 FAQ 등록안을 보여준다.
11. 사용자가 그대로 등록하면 `faq_requests_kyj` 한 행과 `faq_request_messages_kyj`의 최초 질문/AI 요약 두 행을 저장한다.
12. 최종 응답을 사용자의 언어로 통일한 뒤 AI 메시지를 `chat_messages_kyj`에 저장한다.
13. FAQ가 생성되었으면 트랜잭션 커밋 후 담당자 배정 메일을 백그라운드에서 발송한다. 메일 실패는 FAQ 접수를 롤백하지 않는다.

### 5.3 LLM 또는 embedding 호출 시점

| 시점 | 호출 | 목적 |
|---|---|---|
| 모든 사용자 메시지 | 대화 맥락 구조화 LLM | 이전 턴과 현재 턴의 업무 문맥 결합 |
| 메인 분기 진입 | 업무/비업무 판정 LLM | 매뉴얼 질문인지 분류 |
| 비업무 질문 | 일반 LLM | 자유답변이 아니라 아이테르 업무 문의 유도문 생성 |
| FAQ 검색 | Embedding API | 질문 벡터와 승인 FAQ 질문/답변 벡터 비교 |
| 매뉴얼 검색 | 질의 재작성 LLM + Embedding API | 대화 문맥을 반영한 검색문 생성 및 청크 검색 |
| 매뉴얼 답변 | 구조화 LLM | 검색 청크만 근거로 답변 또는 추가확인 생성 |
| 지식검색 실패 | FAQ intake 구조화 LLM | 업무분류, 국가, 화면번호, 정제 질문, 담당자 단서, 부족정보 추출 |
| 등록 제안 후 자유입력 | 후속 의도 LLM + intake LLM | 확인/거절/수정/새 질문 판정 및 수정안 재작성 |
| 모든 최종 응답 | 언어 통일 LLM | DB 값이 포함되어도 사용자 언어가 섞이지 않게 정리 |

화면 담당자 조회와 확인 후 변경 자체는 LLM이 아니라 규칙 판정과 SQL 정확 조회/갱신으로 처리한다.

### 5.4 Ask AI 예시

#### 예시 A: 승인 FAQ와 매뉴얼 중 최신 근거 선택

```text
사용자: 인도 9043 화면의 공통업무 처리방법을 알려줘.

시스템:
1) 사용자 메시지 저장
2) 업무 질문으로 판정
3) 승인 FAQ 질문/답변 embedding 검색
4) 매뉴얼 청크 검색 및 답변 생성
5) 두 결과가 기준치를 넘으면 각 기준일 비교
6) 더 최신인 쪽의 답변을 선택하고 양쪽 출처/일자를 함께 표시
7) AI 메시지 저장
```

#### 예시 B: 미해결 질문을 FAQ로 접수

```text
사용자: 9043 화면 처리방법 알려줘.
AI: 답변을 다시 찾기 위해 한 가지만 더 알려주세요. 어느 국가에서 발생한 업무인가요?
사용자: 인도야.
AI: 답변을 다시 찾기 위해 한 가지만 더 알려주세요. 어떤 업무에 해당하나요?
사용자: 공통업무야. 김연진 프로가 담당자 같아.
AI: 매뉴얼과 승인 FAQ에서 답을 찾지 못했습니다. 아래 내용으로 FAQ를 등록할까요?
사용자: 담당팀을 DS공통으로 수정해줘.
AI: 수정된 등록안을 다시 표시
사용자: 그대로 등록해줘.
AI: FAQ에 등록 완료하였습니다. 요청 번호는 #12입니다.
```

이때 `faq_requests_kyj`에는 요청/업무/국가/화면/담당자 정보가 저장되고, `faq_request_messages_kyj`에는 `faq_chat_id=1` 원 질문과 `faq_chat_id=2` AI 요약이 저장된다.

#### 예시 C: 화면 담당자 변경

```text
사용자: 화면번호 1492 담당자를 홍길동으로 변경해줘.
AI: 현재 담당자와 변경 내용을 보여주고 확인 선택지를 제시
사용자: 변경 확인: 화면번호 1492 담당자를 홍길동으로 변경
시스템: screen_owners_kyj 갱신 + screen_owner_changes_kyj 이력 INSERT
AI: 변경 완료 안내
```

## 6. FAQ Review 거래 흐름

### 6.1 접근 권한과 목록

- 프론트와 백엔드 모두 `Admin`, `Developer`만 FAQ Review 접근을 허용한다.
- `Admin`은 전체 요청을 조회한다.
- `Developer`는 `assignee_username`이 자기 계정인 요청만 조회한다.
- 상태 탭은 답변 대기(`pending`), 재배정(`assigned`), 완료(`approved`), 반려(`rejected`), 전체다.

### 6.2 담당자 대화

담당자는 입력창 드롭다운에서 다음 유형을 선택한다.

| 유형 | DB 저장 | 원본 Ask AI 전달 | 메일 |
|---|---|---|---|
| 답변 작성 `answer` | `faq_request_messages_kyj` | 즉시 전달하지 않음 | 없음 |
| 질문자에게 추가질의 `additional_question` | `faq_request_messages_kyj` | `chat_messages_kyj`에 `faq_agent` AI 메시지로 전달 | 없음 |
| 내부 메모 `note` | `faq_request_messages_kyj` | 전달하지 않음 | 없음 |

질문자가 원본 방에서 추가질의에 답하면 Ask AI의 선처리 로직이 답변을 `faq_request_messages_kyj`에 `requester/answer`로 그대로 추가한다. FAQ 상태는 `pending` 또는 `assigned`를 유지한다.

담당자 메시지의 휴지통은 `answer`, `additional_question`, `note`만 삭제할 수 있다. 추가질의를 삭제하면 `trace`의 `faq_request_id`, `faq_chat_id`로 연결된 원본 채팅방 AI 메시지도 함께 삭제된다. 최초 질문과 시스템 요약은 삭제할 수 없다.

### 6.3 자동요약과 최종 편집

1. **자동요약**을 누르면 원본 `chat_messages_kyj`와 해당 FAQ의 `faq_request_messages_kyj`를 시간순으로 합친다.
2. 질문자/AI/담당자/관리자의 모든 메시지와 내부 메모까지 LLM에 전달한다.
3. LLM이 가장 중요한 질문, 현재까지의 답변, 키워드를 생성한다.
4. 결과를 `summarized_question`, `summarized_answer`, `final_keywords`에 저장하고 화면 입력칸에 표시한다.
5. 담당자/관리자는 승인 전까지 질문, 답변, 키워드를 자유롭게 수정할 수 있다. 승인 API에는 화면 입력칸의 최종값이 전달된다.

### 6.4 재배정

1. 담당자 후보는 `users_kyj`에서 `Admin` 또는 `Developer`인 계정만 조회한다.
2. 재배정하면 `assignee_*`, 배정 근거, 상태(`assigned`), 마지막 변경자/일시를 갱신한다.
3. 커밋 후 새 담당자 이메일로 배정 알림을 비동기 발송한다.

### 6.5 승인

```mermaid
sequenceDiagram
    participant R as "Reviewer"
    participant UI as "FAQReviewPage"
    participant API as "faq_router.py"
    participant DB as "faq_requests_kyj"
    participant Chat as "원본 chat_messages_kyj"
    participant Mail as "faq_mailer.py"

    R->>UI: 최종 질문/답변 편집, 지식검색 허용 선택
    UI->>API: POST /api/faqs/{faq_id}/approve
    alt 지식검색 허용
        API->>API: 질문/답변 embedding 각각 생성
        API->>DB: approved + Y + 두 embedding 저장
    else 지식검색 미허용
        API->>DB: approved + N + embedding NULL 저장
    end
    API->>Chat: 승인 질문/답변 완료 알림 INSERT
    API-->>UI: 승인 결과
    API-->>Mail: 커밋 후 요청자 완료 메일 비동기 발송
```

- 체크박스 기본값은 켜짐이다.
- `Y`로 승인한 FAQ만 이후 Ask AI 검색 지식으로 재사용한다.
- `N`으로 승인하면 완료 목록에서는 볼 수 있지만 동일 질문 검색에는 사용하지 않는다.
- 완료된 건의 체크박스는 비활성 상태로 조회만 가능하다.
- 승인 알림이 원본 채팅방에 들어오면 왼쪽 방 목록이 분홍색이 된다. 사용자가 그 방을 열면 브라우저 `localStorage`에 확인한 최신 메시지 ID를 저장하고 하늘색으로 바뀐다.
- 승인 완료 메일은 요청자의 `users_kyj.email`로만 보낸다. 추가질의와 내부 메모에는 메일을 보내지 않는다.

### 6.6 반려

1. `status='rejected'`, 반려 사유, 마지막 변경자/일시를 저장한다.
2. 원본 채팅방에 반려 사유를 AI 메시지로 전달한다.
3. embedding을 새로 만들지 않으며 지식검색에 사용하지 않는다.
4. 현재 반려 시에는 요청자 완료 메일을 보내지 않는다.

### 6.7 FAQ Review 예시

```text
1. Developer가 FAQ 요청 #12를 연다.
2. “질문자에게 추가질의”로 오류 메시지를 요청한다.
   - FAQ 대화에 저장
   - 원본 Ask AI 방에도 AI 메시지로 전달
   - 방 목록은 분홍색 표시
3. 질문자가 원본 방에서 오류 메시지를 답한다.
   - FAQ 대화에 requester/answer로 저장
4. 담당자가 답변과 내부 메모를 추가한다.
5. 자동요약을 눌러 전체 원본 채팅 + FAQ 대화를 질문/답변 한 쌍으로 정리한다.
6. 담당자가 질문/답변을 직접 보정한다.
7. 지식검색 허용을 체크하고 “답변 완료 및 승인”을 누른다.
   - FAQ 요청 status=approved
   - 최종 질문/답변과 두 embedding 저장
   - 원본 방에 완료 답변 전달
   - 요청자에게 완료 메일 발송
8. 이후 유사 질문은 이 FAQ의 질문/답변 embedding 검색 대상이 된다.
```

## 7. 상태와 연결 규칙

| 상태 | 의미 | 편집 | 지식검색 |
|---|---|---|---|
| `pending` | 최초 접수/답변 대기 | 가능 | 불가 |
| `assigned` | 담당자 수동 변경/재배정 | 가능 | 불가 |
| `approved` + `Y` | 답변 완료 및 검색 허용 | 읽기 전용 | 가능 |
| `approved` + `N` | 답변 완료, 보관 전용 | 읽기 전용 | 불가 |
| `rejected` | 반려 완료 | 읽기 전용 | 불가 |

- `faq_requests_kyj.requester_chat_room_id`는 `chat_rooms_kyj.room_id`를 `ON DELETE RESTRICT`로 참조한다. FAQ가 연결된 원본 채팅방은 먼저 FAQ 관계를 정리하지 않으면 삭제되지 않는다.
- `faq_request_messages_kyj.faq_id`는 FAQ 요청을 `ON DELETE CASCADE`로 참조한다.
- 한 FAQ에는 한 원 질문자와 한 원 채팅방, 한 주 담당자 계정만 둔다. 관심 질문자 참여 테이블은 없다.

## 8. 체크포인트와 메일

### 채팅 체크포인트

- 방 전환, 방 삭제 전, 마지막 AI 답변 후 30분 비활성, 로그아웃 전 전체 방에서 호출될 수 있다.
- 체크포인트는 새 메시지 중 마지막 `chat_id`를 `last_summarized_message_id`에 기록할 뿐이다.
- 현재 체크포인트는 `summary`를 새로 만들거나 FAQ를 자동 생성하지 않는다.

### 메일

- 발신 기본값: `shds.yj.k@gmail.com`
- SMTP: `smtp.gmail.com:587`, STARTTLS
- 발송 조건: `FAQ_MAIL_ENABLED=true`이고 `FAQ_SMTP_APP_PASSWORD`가 설정되어 있어야 한다.
- 배정/재배정 메일 수신자: 담당자의 `users_kyj.email`
- 승인 완료 메일 수신자: 질문자의 `users_kyj.email`
- 발송은 DB 커밋 이후 백그라운드에서 수행하며 기본 3회 재시도한다. 실패해도 FAQ 등록/승인 트랜잭션은 취소하지 않는다.

## 9. 현재 구현상 주의할 점

- “유사한 pending 요청을 전체 FAQ에서 찾아 관심 질문자로 추가”하는 흐름은 현재 코드에 없다. 현재는 **같은 원본 채팅방**에 `pending/assigned` 요청이 있는지만 확인한다.
- 승인 FAQ 검색 기본 임계값은 `0.84`, 매뉴얼 검색 기본 임계값은 `0.70`이며 환경변수로 바꿀 수 있다.
- FAQ 기준일은 `last_change_date/time`, 매뉴얼 기준일은 `manual_versions_kyj.created_at`이다.
- 매뉴얼 검색 점수는 벡터 유사도 70%와 키워드 점수 30%의 결합값이다.
- `faq_requests_kyj`에 승인 FAQ가 통합되었으므로 FAQ Review의 수정과 Ask AI 검색은 같은 원장을 바라본다.
- 스키마 변경 SQL은 서버가 자동 실행하지 않는다. 향후 DDL이나 `INSERT/SELECT` 외 DB 변경은 반드시 사전 승인 후 별도로 실행해야 한다.
