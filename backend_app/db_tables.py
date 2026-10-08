"""애플리케이션이 접근할 수 있는 테이블 이름의 단일 정의점."""

import os

# 매뉴얼 (정식 테이블 — suffix 없음)
MANUALS = "manuals"
MANUAL_VERSIONS = "manual_versions"
MANUAL_CHUNK_TABLE_VERSION = os.getenv("MANUAL_CHUNK_TABLE_VERSION", "v1").strip().lower()
if MANUAL_CHUNK_TABLE_VERSION not in {"v1", "v2"}:
    raise ValueError("MANUAL_CHUNK_TABLE_VERSION must be v1 or v2")
_chunk_suffix = "_v2" if MANUAL_CHUNK_TABLE_VERSION == "v2" else ""
MANUAL_PARENT_CHUNKS = "manual_parent_chunks" + _chunk_suffix
MANUAL_CHILD_CHUNKS = "manual_child_chunks" + _chunk_suffix

# 사용자 및 챗/FAQ 정식 테이블
USERS = "users"
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
    CHAT_ROOMS,
    CHAT_MESSAGES,
    FAQ_ROOMS,
    FAQ_MESSAGES,
)

if len(set(ALL_TABLES)) != len(ALL_TABLES):
    raise RuntimeError("테이블 이름이 중복되었습니다.")
