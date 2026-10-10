"""애플리케이션이 접근할 수 있는 테이블 이름의 단일 정의점."""

# 매뉴얼 (정식 테이블 — suffix 없음)
MANUALS = "manuals"
MANUAL_VERSIONS = "manual_versions"
MANUAL_CHUNK_TABLE_VERSION = "v2"
MANUAL_PARENT_CHUNKS = "manual_parent_chunks_v2"
MANUAL_CHILD_CHUNKS = "manual_child_chunks_v2"

# 사용자 및 챗/FAQ 정식 테이블
USERS = "users"
LEGACY_USERS = "users_kyj"
CHAT_ROOMS = "chat_rooms"
CHAT_MESSAGES = "chat_messages"
FAQ_ROOMS = "faq_rooms"
FAQ_MESSAGES = "faq_messages"

ALL_TABLES = (
    MANUALS,
    MANUAL_VERSIONS,
    MANUAL_PARENT_CHUNKS,
    MANUAL_CHILD_CHUNKS,
    USERS,
    LEGACY_USERS,
    CHAT_ROOMS,
    CHAT_MESSAGES,
    FAQ_ROOMS,
    FAQ_MESSAGES,
)

if len(set(ALL_TABLES)) != len(ALL_TABLES):
    raise RuntimeError("테이블 이름이 중복되었습니다.")
