"""개인화된 RAG 검색 경로를 수동 점검하는 스크립트."""

import rag


def main() -> None:
    query = "짜장면 만드려면 무슨 재료가 필요해?"
    result = rag.answer_question(query, manual_id=None)

    print(f"\n질문: {query}")
    print("=" * 50)
    print("[답변]")
    print(result["text"])
    print()

    print("=" * 50)
    print("[처리 과정]")
    for step in result.get("trace", {}).get("steps", []):
        print(f"- {step.get('label', step.get('node', ''))}")


if __name__ == "__main__":
    main()
