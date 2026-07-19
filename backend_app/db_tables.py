"""애플리케이션이 접근할 수 있는 개인화 테이블 이름의 단일 정의점."""

USERS = "users_kyj"
MANUALS = "manuals_kyj"
MANUAL_VERSIONS = "manual_versions_kyj"
MANUAL_CHUNKS = "manual_chunks_kyj"
CHAT_ROOMS = "chat_rooms_kyj"
CHAT_MESSAGES = "chat_messages_kyj"
FAQ_HISTORY = "faq_history_kyj"
SCREEN_OWNERS = "screen_owners_kyj"
SCREEN_OWNER_CHANGES = "screen_owner_changes_kyj"

ALL_TABLES = (
    USERS,
    MANUALS,
    MANUAL_VERSIONS,
    MANUAL_CHUNKS,
    CHAT_ROOMS,
    CHAT_MESSAGES,
    FAQ_HISTORY,
    SCREEN_OWNERS,
    SCREEN_OWNER_CHANGES,
)

if len(set(ALL_TABLES)) != len(ALL_TABLES) or not all(name.endswith("_kyj") for name in ALL_TABLES):
    raise RuntimeError("모든 애플리케이션 테이블은 고유한 _kyj 이름이어야 합니다.")
