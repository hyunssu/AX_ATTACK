"""애플리케이션이 접근할 수 있는 테이블 이름의 단일 정의점."""

# 매뉴얼 (정식 테이블 — suffix 없음)
MANUALS = "manuals"
MANUAL_VERSIONS = "manual_versions"
MANUAL_PARENT_CHUNKS = "manual_parent_chunks"
MANUAL_CHILD_CHUNKS = "manual_child_chunks"

# 임시 _kyj 테이블 (추후 정식화 예정)
USERS = "users_kyj"
CHAT_ROOMS = "chat_rooms"
CHAT_MESSAGES = "chat_messages"
FAQ_REQUESTS = "faq_rooms"
FAQ_REQUEST_MESSAGES = "faq_messages"
SCREEN_OWNERS = "screen_owners_kyj"
SCREEN_OWNER_CHANGES = "screen_owner_changes_kyj"

ALL_TABLES = (
    MANUALS,
    MANUAL_VERSIONS,
    MANUAL_PARENT_CHUNKS,
    MANUAL_CHILD_CHUNKS,
    USERS,
    CHAT_ROOMS,
    CHAT_MESSAGES,
    FAQ_REQUESTS,
    FAQ_REQUEST_MESSAGES,
    SCREEN_OWNERS,
    SCREEN_OWNER_CHANGES,
)

if len(set(ALL_TABLES)) != len(ALL_TABLES):
    raise RuntimeError("테이블 이름이 중복되었습니다.")
