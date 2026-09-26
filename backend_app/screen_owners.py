"""화면 담당자 원장의 정확 조회와 승인 기반 변경 처리."""

import re
from dataclasses import dataclass

from sqlalchemy import text

from db import engine
from db_tables import SCREEN_OWNER_CHANGES, SCREEN_OWNERS


UPDATE_VERBS = ("변경", "수정", "업데이트", "바꿔", "바꾸", "교체")
LOOKUP_WORDS = ("누구", "조회", "찾", "알려", "확인", "담당자?")
CONFIRM_PREFIX = "변경 확인:"
CANCEL_OPTION = "변경 취소"

_CONFIRM_RE = re.compile(
    r"^변경\s*확인:\s*화면번호\s*(?P<screen>\d{1,20})\s*"
    r"담당자를\s*(?P<owner>.+?)\s*(?:으)?로\s*변경$"
)
_SCREEN_LABEL_RE = re.compile(r"화면(?:번호)?\s*#?\s*(?P<screen>\d{1,20})", re.IGNORECASE)
_OWNER_RE = re.compile(
    r"담당자(?:명)?(?:를|을|는|은)?\s*[\"']?"
    r"(?P<owner>[가-힣A-Za-z][가-힣A-Za-z0-9 ._-]{0,49}?)"
    r"[\"']?\s*(?:으)?로\s*(?:변경|수정|업데이트|바꿔|바꾸|교체)"
)


@dataclass(frozen=True)
class ScreenOwnerIntent:
    action: str
    screen_number: str | None = None
    new_owner: str | None = None


def _screen_number(question: str) -> str | None:
    labelled = _SCREEN_LABEL_RE.search(question)
    if labelled:
        return labelled.group("screen")

    # 화면/담당자 문맥 안에서 숫자가 하나뿐이면 화면번호로 해석한다.
    numbers = re.findall(r"(?<!\d)\d{1,20}(?!\d)", question)
    if len(numbers) == 1 and ("화면" in question or "담당자" in question):
        return numbers[0]
    return None


def parse_screen_owner_intent(question: str) -> ScreenOwnerIntent:
    normalized = " ".join(question.strip().split())

    if normalized == CANCEL_OPTION:
        return ScreenOwnerIntent(action="cancel")

    confirmed = _CONFIRM_RE.match(normalized)
    if confirmed:
        return ScreenOwnerIntent(
            action="update_confirm",
            screen_number=confirmed.group("screen"),
            new_owner=confirmed.group("owner").strip(),
        )

    screen_number = _screen_number(normalized)
    has_owner_context = "담당자" in normalized
    has_update_verb = any(word in normalized for word in UPDATE_VERBS)

    if has_owner_context and has_update_verb:
        owner_match = _OWNER_RE.search(normalized)
        return ScreenOwnerIntent(
            action="update_request",
            screen_number=screen_number,
            new_owner=owner_match.group("owner").strip() if owner_match else None,
        )

    if screen_number and has_owner_context and (
        any(word in normalized for word in LOOKUP_WORDS) or len(normalized) <= 30
    ):
        return ScreenOwnerIntent(action="lookup", screen_number=screen_number)

    return ScreenOwnerIntent(action="none")


def _trace(label: str, input_data: dict, output_data: dict) -> dict:
    return {
        "engine": "database",
        "steps": [
            {
                "node": "screen_owner_registry",
                "label": label,
                "input": input_data,
                "output": output_data,
            }
        ],
    }


def _answer(text_value: str, *, trace_output: dict, sources: list[dict] | None = None) -> dict:
    return {
        "type": "answer",
        "text": text_value,
        "options": [],
        "sources": sources or [],
        "trace": _trace("담당자 원장 처리", {}, trace_output),
    }


def _lookup(screen_number: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT screen_number, country, owner_team, owner_name, note, updated_at
                FROM {SCREEN_OWNERS}
                WHERE screen_number = :screen_number
            """),
            {"screen_number": screen_number},
        ).mappings().first()

    if not row:
        return _answer(
            f"화면번호 {screen_number}은(는) 담당자 원장에서 찾지 못했습니다.",
            trace_output={"found": False, "screen_number": screen_number},
        )

    note = f" 비고는 '{row['note']}'입니다." if row["note"] else ""
    response = (
        f"화면번호 **{row['screen_number']}**의 담당자는 **{row['owner_name']}**입니다. "
        f"국가는 {row['country']}, 담당팀은 {row['owner_team']}입니다.{note}"
    )
    return _answer(
        response,
        sources=[
            {
                "type": "screen_owner_registry",
                "id": row["screen_number"],
                "title": "화면 담당자 원장",
                "detail": f"화면번호 {row['screen_number']}",
                "created_at": row["updated_at"].isoformat(),
                "date_label": "근거 갱신일",
            }
        ],
        trace_output={
            "found": True,
            "screen_number": row["screen_number"],
            "country": row["country"],
            "owner_team": row["owner_team"],
            "owner_name": row["owner_name"],
            "llm_called": False,
        },
    )


def _request_confirmation(screen_number: str, new_owner: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT screen_number, country, owner_team, owner_name, updated_at
                FROM {SCREEN_OWNERS}
                WHERE screen_number = :screen_number
            """),
            {"screen_number": screen_number},
        ).mappings().first()

    if not row:
        return _answer(
            f"화면번호 {screen_number}은(는) 담당자 원장에서 찾지 못해 변경할 수 없습니다.",
            trace_output={"found": False, "screen_number": screen_number, "mutation": False},
        )

    if row["owner_name"] == new_owner:
        return _answer(
            f"화면번호 {screen_number}의 담당자는 이미 **{new_owner}**입니다. DB는 변경하지 않았습니다.",
            trace_output={"changed": False, "reason": "same_owner", "llm_called": False},
        )

    confirm_option = f"{CONFIRM_PREFIX} 화면번호 {screen_number} 담당자를 {new_owner}로 변경"
    return {
        "type": "clarify",
        "text": (
            f"화면번호 **{screen_number}**의 담당자를 **{row['owner_name']}**에서 "
            f"**{new_owner}**(으)로 변경할까요? 확인 전에는 DB를 수정하지 않습니다."
        ),
        "options": [confirm_option, CANCEL_OPTION],
        "sources": [
            {
                "type": "screen_owner_registry",
                "id": row["screen_number"],
                "title": "화면 담당자 원장",
                "detail": f"화면번호 {row['screen_number']}",
                "created_at": row["updated_at"].isoformat(),
                "date_label": "근거 갱신일",
            }
        ],
        "trace": _trace(
            "담당자 변경 확인",
            {"screen_number": screen_number, "new_owner": new_owner},
            {"current_owner": row["owner_name"], "mutation": False, "llm_called": False},
        ),
    }


def _apply_update(screen_number: str, new_owner: str, room_id: int, username: str, request_text: str) -> dict:
    with engine.begin() as conn:
        current = conn.execute(
            text(f"""
                SELECT screen_number, country, owner_team, owner_name
                FROM {SCREEN_OWNERS}
                WHERE screen_number = :screen_number
                FOR UPDATE
            """),
            {"screen_number": screen_number},
        ).mappings().first()

        if not current:
            return _answer(
                f"화면번호 {screen_number}은(는) 담당자 원장에서 찾지 못해 변경하지 않았습니다.",
                trace_output={"changed": False, "reason": "not_found"},
            )

        old_owner = current["owner_name"]
        if old_owner == new_owner:
            return _answer(
                f"화면번호 {screen_number}의 담당자는 이미 **{new_owner}**입니다. DB는 변경하지 않았습니다.",
                trace_output={"changed": False, "reason": "same_owner"},
            )

        conn.execute(
            text(f"""
                UPDATE {SCREEN_OWNERS}
                SET owner_name = :new_owner,
                    updated_by = :username,
                    updated_at = now()
                WHERE screen_number = :screen_number
            """),
            {"screen_number": screen_number, "new_owner": new_owner, "username": username},
        )
        change = conn.execute(
            text(f"""
                INSERT INTO {SCREEN_OWNER_CHANGES}
                    (screen_number, old_owner_name, new_owner_name, changed_by,
                     source_room_id, request_text)
                VALUES
                    (:screen_number, :old_owner, :new_owner, :username,
                     :room_id, :request_text)
                RETURNING id, changed_at
            """),
            {
                "screen_number": screen_number,
                "old_owner": old_owner,
                "new_owner": new_owner,
                "username": username,
                "room_id": room_id,
                "request_text": request_text,
            },
        ).mappings().one()

    return _answer(
        (
            f"변경했습니다. 화면번호 **{screen_number}**의 담당자는 이제 **{new_owner}**입니다. "
            f"변경 이력 #{change['id']}을 담당자 변경 감사 원장에 저장했습니다."
        ),
        sources=[
            {
                "type": "screen_owner_registry",
                "id": screen_number,
                "title": "화면 담당자 원장",
                "detail": f"화면번호 {screen_number}",
                "created_at": change["changed_at"].isoformat(),
                "date_label": "근거 갱신일",
            }
        ],
        trace_output={
            "changed": True,
            "screen_number": screen_number,
            "old_owner": old_owner,
            "new_owner": new_owner,
            "change_id": change["id"],
            "faq_status": "pending",
            "llm_called": False,
        },
    )


def answer_screen_owner_request(
    question: str,
    *,
    room_id: int,
    username: str,
    history: list[dict] | None = None,
    allow_lookup: bool = True,
) -> dict | None:
    """담당자 변경을 처리한다. allow_lookup=False이면 조회는 지식검색으로 넘긴다."""
    intent = parse_screen_owner_intent(question)

    if intent.action == "none":
        return None
    if intent.action == "lookup" and not allow_lookup:
        return None
    if intent.action == "cancel":
        return _answer(
            "담당자 변경을 취소했습니다. DB는 변경하지 않았습니다.",
            trace_output={"changed": False, "reason": "cancelled", "llm_called": False},
        )
    if intent.action == "lookup":
        return _lookup(intent.screen_number)
    if intent.action == "update_confirm":
        previous = (history or [])[-1] if history else {}
        offered_options = previous.get("options") or []
        was_offered = (
            previous.get("role") == "ai"
            and previous.get("type") == "clarify"
            and question in offered_options
        )
        if not was_offered:
            return {
                "type": "clarify",
                "text": "유효한 변경 확인 단계가 아닙니다. 먼저 담당자 변경을 요청한 뒤 표시되는 확인 버튼을 눌러 주세요.",
                "options": [],
                "trace": _trace(
                    "담당자 변경 승인 검증",
                    {"question": question},
                    {"authorized": False, "mutation": False, "llm_called": False},
                ),
            }
        return _apply_update(intent.screen_number, intent.new_owner, room_id, username, question)
    if not intent.screen_number or not intent.new_owner:
        return {
            "type": "clarify",
            "text": "화면번호와 새 담당자명을 모두 입력해 주세요. 예: `화면번호 1492 담당자를 홍길동으로 변경해줘`",
            "options": [],
            "trace": _trace(
                "담당자 변경 정보 확인",
                {"question": question},
                {
                    "screen_number": intent.screen_number,
                    "new_owner": intent.new_owner,
                    "mutation": False,
                    "llm_called": False,
                },
            ),
        }
    return _request_confirmation(intent.screen_number, intent.new_owner)
