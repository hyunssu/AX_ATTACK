# 매뉴얼 관리 시스템 - 기술 스택 정리

이 프로젝트에서 사용한 기술들을 "왜 썼는지", "무슨 역할인지" 중심으로 정리했습니다.

## 전체 구조 한눈에 보기

```
[브라우저]
   │ HTTP
   ▼
[Nginx] ──── 정적 파일(React 빌드 결과) 서빙
   │ /api/* 는 백엔드로 프록시
   ▼
[FastAPI 백엔드]
   │
   ├── Postgres(pgvector) : 매뉴얼 메타데이터 + 임베딩 벡터
   ├── MinIO : 매뉴얼 원본 PDF 파일
   └── OpenAI API : 임베딩 생성 + 질문 답변(LLM)
```

전체가 Docker Compose로 하나로 묶여서, 로컬에서 `docker compose up`만 하면
nginx, backend, postgres 세 컨테이너가 같이 뜹니다.

---

## 1. FastAPI (백엔드 프레임워크)

Python으로 REST API를 만드는 웹 프레임워크입니다. 함수에 데코레이터만 붙이면
바로 API 엔드포인트가 됩니다.

```python
@router.post("/login")
def login(req: LoginRequest):
    ...
```

- **Pydantic 모델**(`LoginRequest` 같은 클래스)로 요청 body의 타입을 강제합니다.
  타입이 안 맞으면 자동으로 422 에러를 내려주기 때문에 입력 검증 코드를 직접 안 짜도 됩니다.
- **`Depends()`**: 이 프로젝트에서는 인증 체크에 씁니다. `Depends(get_current_user)`를
  파라미터로 넣으면, 그 엔드포인트가 호출되기 전에 먼저 `get_current_user`가 실행되어
  토큰을 검사합니다. 통과 못 하면 401을 던지고 본문 코드는 실행되지 않습니다.

## 2. SQLAlchemy ([db.py](backend_app/db.py))

Python에서 SQL을 실행하기 위한 라이브러리(ORM이지만 여기선 raw SQL 실행 용도로만 사용).
`engine.connect()`/`engine.begin()`으로 커넥션을 빌려서 `text("SELECT ...")` 형태로
직접 SQL을 씁니다. ORM 모델 클래스를 만들지 않은 건, 테이블이 단순(`manuals`,
`manual_versions`, `users`)해서 SQL을 직접 쓰는 게 더 빠르고 명확하기 때문입니다.

## 3. Postgres + pgvector

- **Postgres**: 매뉴얼 제목, 버전 정보, 사용자 계정 같은 일반 데이터 저장.
- **pgvector**: Postgres 확장(extension). 벡터(숫자 배열)를 컬럼에 저장하고
  "이 벡터와 가장 비슷한 벡터 N개를 찾아줘" 같은 유사도 검색을 SQL로 할 수 있게 해줍니다.
  RAG(아래 설명)에서 "질문과 의미가 비슷한 문서 조각을 찾는" 핵심 기능이 여기서 나옵니다.

별도 벡터 DB(Chroma 등)를 안 쓰고 Postgres에 얹은 이유: 이미 메타데이터용 Postgres를
쓰고 있어서 인프라를 하나 더 안 늘려도 되고, 메타데이터와 벡터를 같은 트랜잭션으로
다룰 수 있어서 더 단순합니다.

## 4. LangChain ([rag.py](backend_app/rag.py))

"LLM을 활용한 애플리케이션을 만들기 위한 조립 키트"라고 보면 됩니다. OpenAI API를
직접 호출할 수도 있지만, LangChain은 자주 쓰는 패턴(문서 쪼개기, 벡터 저장소 연동,
검색기 만들기 등)을 표준화된 인터페이스로 제공해서 다른 벡터 DB/LLM으로 바꿀 때도
코드를 거의 안 고쳐도 되게 해줍니다.

이 프로젝트에서 LangChain이 하는 일 (RAG = Retrieval-Augmented Generation):

1. **`PyPDFLoader`**: 업로드된 PDF를 텍스트로 읽어들임
2. **`RecursiveCharacterTextSplitter`**: 긴 텍스트를 1000자 단위(겹치는 200자 포함)로 쪼갬.
   LLM에 한 번에 다 넣을 수 없고, 검색 단위도 작아야 정확도가 좋아지기 때문
3. **`OpenAIEmbeddings`**: 각 텍스트 조각을 숫자 벡터로 변환(임베딩). 의미가 비슷한
   문장은 벡터 공간에서 가까운 위치에 놓이게 됨
4. **`PGVector`**: 이 벡터들을 Postgres에 저장 + 질문이 들어오면 가장 가까운 벡터
   N개(`k=4`)를 검색해서 가져옴
5. **`ChatOpenAI`**: 검색된 매뉴얼 조각들을 프롬프트에 끼워 넣고, 그걸 바탕으로
   답변을 생성하도록 GPT 모델에 요청

즉 "사용자 질문 → 관련 매뉴얼 조각 검색 → 그 내용을 참고해서 LLM이 답변 생성"
흐름이 RAG이고, LangChain은 이 파이프라인의 각 단계를 이어주는 접착제 역할입니다.

> 참고로 처음엔 Dify(노코드 LLM 워크플로우 툴)를 썼다가 LangChain으로 바꿨습니다.
> Dify는 외부 SaaS에 워크플로우를 등록해서 호출하는 방식이라 커스터마이징이 제한적이고,
> LangChain은 코드로 직접 파이프라인을 짜기 때문에 자유도가 높습니다.

## 5. MinIO ([storage.py](backend_app/storage.py))

S3 호환 오브젝트 스토리지. 매뉴얼 원본 PDF 파일 자체를 저장하는 곳입니다
(벡터DB에는 텍스트 조각의 "의미"만 저장되고, 원본 파일은 따로 보관).
업로드 후 presigned URL(임시 다운로드 링크)을 만들어서 프론트엔드에 내려줍니다.

## 6. 인증 - JWT + bcrypt ([auth.py](backend_app/auth.py))

- **bcrypt**: 비밀번호를 평문으로 저장하지 않고 해시(되돌릴 수 없는 변환)로 저장.
  로그인 시 입력한 비밀번호를 같은 방식으로 해시해서 저장된 해시와 비교(`checkpw`)합니다.
- **JWT (JSON Web Token)**: 로그인에 성공하면 서버가 "이 사용자는 인증됐다"는 정보를
  담은 토큰을 발급합니다. 이 토큰은 서버가 비밀키(`JWT_SECRET`)로 서명했기 때문에
  위조할 수 없습니다. 프론트엔드는 이후 모든 API 요청에 이 토큰을
  `Authorization: Bearer <token>` 헤더로 함께 보내고, 서버는 서명을 검증해서
  "누가 요청했는지" 확인합니다 (`get_current_user`).
  - 서버는 로그인 상태를 따로 저장(세션)하지 않습니다 — 토큰 자체에 정보가 들어있고
    서명만 검증하면 되는 구조(stateless)라 서버를 여러 대로 늘려도 그대로 동작합니다.

## 7. Docker / Docker Compose

- **Docker**: 애플리케이션과 그 실행 환경(파이썬 버전, 라이브러리 등)을 하나의
  "이미지"로 묶어서, 어느 컴퓨터에서든 똑같이 돌아가게 해줍니다.
- **Docker Compose**: 여러 컨테이너(nginx, backend, postgres)를 한 번에 정의하고
  `docker compose up`으로 같이 띄우는 도구. `docker-compose.yml`에 각 서비스가
  어떤 이미지를 쓰는지, 포트는 뭘 여는지, 어떤 환경변수를 받는지 등을 적어둡니다.
- `volumes: - pgdata:/var/lib/postgresql/data`: 컨테이너를 지웠다 다시 만들어도
  DB 데이터가 사라지지 않게 디스크에 영속화하는 설정입니다.

## 8. Nginx

웹 서버 + 리버스 프록시. 두 가지 역할을 합니다.

1. React 빌드 결과(정적 HTML/JS/CSS)를 그대로 서빙
2. `/api/`로 들어오는 요청은 FastAPI 백엔드(`backend:8000`)로 그대로 전달(프록시)

브라우저 입장에서는 한 도메인(`localhost:8080`)만 보고, 그 뒤에서 nginx가
"이건 화면, 이건 API"를 구분해서 알맞은 곳으로 보내주는 셈입니다.

`try_files $uri $uri/ /index.html;` 설정은 React Router 때문에 필요합니다.
React는 클라이언트 사이드 라우팅(SPA)을 쓰는데, `/manuals`처럼 실제로는 존재하지
않는 경로로 브라우저가 직접 요청하면 nginx가 404를 내기 쉽습니다. 이 설정은
"파일을 못 찾으면 일단 index.html을 내려줘서 React가 자기 라우터로 처리하게 하라"는 뜻입니다.

## 9. React + Vite (프론트엔드)

- **React**: UI를 컴포넌트 단위로 쪼개서 만드는 라이브러리. 이 프로젝트에서는
  `Header`, `ManualList`, `ManualItem`, `ManualUploadForm`, `ChatPanel`로 분리했습니다.
  각 컴포넌트는 자기 상태(state)와 화면을 갖고, 데이터가 바뀌면 화면이 자동으로 다시 그려집니다.
- **Vite**: React 코드를 브라우저가 실행할 수 있는 JS/CSS 파일로 변환·압축(빌드)하는 도구.
  개발 중에는 빠른 핫리로드(코드 고치면 새로고침 없이 바로 반영)를 제공합니다.
  `npm run build` 결과(`dist/`)를 nginx가 서빙합니다.
- **react-router-dom**: 페이지 전환(`/login`, `/manuals`, `/qa`)을 새로고침 없이
  처리해주는 라우팅 라이브러리. `ProtectedLayout`에서 로그인 토큰이 없으면
  `/login`으로 강제 이동시키는 방식으로 화면 보호를 구현했습니다.

## 10. 백엔드 코드를 모듈로 분리한 이유

처음엔 `main.py` 한 파일에 DB 연결, 인증, MinIO, LangChain, 모든 API가 다 들어있었습니다.
지금은 역할별로 나눴습니다.

| 파일 | 역할 |
|---|---|
| [config.py](backend_app/config.py) | 환경변수 읽기 (한 군데서만 관리) |
| [db.py](backend_app/db.py) | DB 커넥션(엔진) |
| [auth.py](backend_app/auth.py) | 로그인/토큰 검증 로직 |
| [storage.py](backend_app/storage.py) | MinIO 업로드 |
| [rag.py](backend_app/rag.py) | LangChain 기반 인덱싱/질의응답 |
| [routers/](backend_app/routers/) | API 엔드포인트 (auth/manuals/chat) |
| [main.py](backend_app/main.py) | 앱을 만들고 라우터들을 연결만 하는 진입점 |

이렇게 나누면 "로그인 로직을 고치고 싶다"고 했을 때 `auth.py`만 보면 되고,
다른 파일과 안 엉켜서 영향 범위를 예측하기 쉬워집니다.
