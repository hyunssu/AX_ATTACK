"""기존 chat.qa 호출을 부모·자식 청크 기반 RAG 구현으로 연결한다."""

from rag import answer_question

__all__ = ["answer_question"]
