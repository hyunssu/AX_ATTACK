"""애플리케이션이 접근할 수 있는 개인화 테이블 이름의 단일 정의점."""

USERS = "users_kyj"
MANUALS = "manuals_kyj"
MANUAL_VERSIONS = "manual_versions_kyj"
MANUAL_CHUNKS = "manual_chunks_kyj"
CHAT_ROOMS = "public.chat_rooms"
CHAT_MESSAGES = "public.chat_messages"
FAQ_REQUESTS = "public.faq_rooms"
FAQ_REQUEST_MESSAGES = "public.faq_messages"
SCREEN_OWNERS = "screen_owners_kyj"
SCREEN_OWNER_CHANGES = "screen_owner_changes_kyj"

ALL_TABLES = (
    USERS,
    MANUALS,
    MANUAL_VERSIONS,
    MANUAL_CHUNKS,
    CHAT_ROOMS,
    CHAT_MESSAGES,
    FAQ_REQUESTS,
    FAQ_REQUEST_MESSAGES,
    SCREEN_OWNERS,
    SCREEN_OWNER_CHANGES,
)

RENAMED_PUBLIC_TABLES = {
    "public.chat_rooms",
    "public.chat_messages",
    "public.faq_rooms",
    "public.faq_messages",
}
CORE_TABLES = {CHAT_ROOMS, CHAT_MESSAGES, FAQ_REQUESTS, FAQ_REQUEST_MESSAGES}

if len(set(ALL_TABLES)) != len(ALL_TABLES):
    raise RuntimeError("애플리케이션 테이블 이름은 서로 달라야 합니다.")
if CORE_TABLES != RENAMED_PUBLIC_TABLES:
    raise RuntimeError("핵심 채팅/FAQ 테이블은 승인된 public 이름을 사용해야 합니다.")
if not all(
    name.endswith("_kyj") or name in RENAMED_PUBLIC_TABLES
    for name in ALL_TABLES
):
    raise RuntimeError("테이블은 _kyj 접미사 또는 승인된 public 이름을 사용해야 합니다.")
