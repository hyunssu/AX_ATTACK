import json

import requests

from config import DIFY_API_KEY, DIFY_URL


def answer_question(question: str, manual_id: int | None, history: list[dict] | None, username: str) -> dict:
    payload = {
        "inputs": {
            "query": question,
            "history": json.dumps(history or [], ensure_ascii=False),
            "manual_id": str(manual_id) if manual_id is not None else "",
        },
        "response_mode": "blocking",
        "user": username,
    }
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(DIFY_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    raw_result = response.json()["data"]["outputs"]["result"]

    parsed = json.loads(raw_result)
    return {
        "type": parsed.get("type", "answer"),
        "text": parsed.get("text", ""),
        "options": parsed.get("options", []),
    }
