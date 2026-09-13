from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from chat.prompts import QA_SYSTEM_PROMPT, QUERY_CHECK_PROMPT, QUERY_REWRITE_PROMPT
from db import engine
from llm_clients import embedding_to_sql, embeddings, llm


class ClarifyOrAnswer(BaseModel):
    type: Literal["clarify", "answer"] = Field(
        description="매뉴얼 내용과 대화 맥락만으로 바로 답변할 수 있으면 'answer', "
        "질문이 모호하거나 추가 정보가 필요하면 'clarify'"
    )
    text: str = Field(description="사용자에게 보여줄 답변 또는 되묻는 질문 내용")
    options: list[str] = Field(
        default_factory=list,
        description="type이 clarify일 때 사용자가 고를 수 있는 2~4개의 선택지. answer일 때는 빈 배열",
    )


structured_llm = llm.with_structured_output(ClarifyOrAnswer)


class QueryCheck(BaseModel):
    proceed: bool = Field(
        description="검색(RAG)을 진행해도 되는 질문이면 true, 인사말/잡담/매뉴얼과 무관하거나 "
        "너무 모호해서 되물어야 하면 false"
    )
    clarify_text: str = Field(description="proceed가 false일 때 사용자에게 되물을 질문. true일 때는 빈 문자열")
    clarify_options: list[str] = Field(
        default_factory=list,
        description="proceed가 false일 때 사용자가 고를 수 있는 2~4개의 선택지. true일 때는 빈 배열",
    )


query_check_llm = llm.with_structured_output(QueryCheck)


def _format_history_text(history: list[dict] | None) -> str:
    return "\n".join(f"{turn.get('role')}: {turn.get('text', '')}" for turn in (history or [])) or "(없음)"


def _check_query(question: str, history: list[dict] | None) -> QueryCheck:
    prompt = QUERY_CHECK_PROMPT.format(history_text=_format_history_text(history), question=question)
    return query_check_llm.invoke(prompt)


class QueryRewrite(BaseModel):
    standalone_question: str = Field(
        description="검색에 사용할, 대화 맥락이 반영된 독립형 질문. 맥락이 필요 없으면 원래 질문 그대로"
    )


query_rewrite_llm = llm.with_structured_output(QueryRewrite)


def _rewrite_query(question: str, history: list[dict] | None) -> str:
    if not history:
        return question
    prompt = QUERY_REWRITE_PROMPT.format(history_text=_format_history_text(history), question=question)
    rewrite: QueryRewrite = query_rewrite_llm.invoke(prompt)
    return rewrite.standalone_question or question


def _search_candidates(question: str, manual_id: int | None, k: int):
    query_vector = embedding_to_sql(embeddings.embed_query(question))
    manual_filter = "AND manual_id = :manual_id" if manual_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                SELECT
                    content,
                    section_title,
                    (1 - (embedding <=> CAST(:query_vector AS vector))) AS vector_score,
                    ts_rank(content_tsv, plainto_tsquery('simple', :question)) AS keyword_score
                FROM manual_chunks_khs
                WHERE embedding IS NOT NULL {manual_filter}
                ORDER BY
                    (0.7 * (1 - (embedding <=> CAST(:query_vector AS vector))))
                    + (0.3 * ts_rank(content_tsv, plainto_tsquery('simple', :question))) DESC
                LIMIT :k
            """),
            {"query_vector": query_vector, "question": question, "manual_id": manual_id, "k": k}
        ).mappings().all()
    return rows


def answer_question(question: str, manual_id: int | None, history: list[dict] | None = None) -> dict:
    check = _check_query(question, history)
    check_step = {
        "node": "check_query",
        "label": "질문 적합성 판단",
        "input": {"question": question, "history": history or []},
        "output": {
            "proceed": check.proceed,
            "clarify_text": check.clarify_text,
            "clarify_options": check.clarify_options,
        },
    }
    if not check.proceed:
        return {
            "type": "clarify",
            "text": check.clarify_text,
            "options": check.clarify_options,
            "trace": {"engine": "langchain", "steps": [check_step]},
        }

    search_query = _rewrite_query(question, history)
    rewrite_step = {
        "node": "rewrite_query",
        "label": "질의 재구성",
        "input": {"question": question, "history": history or []},
        "output": {"search_query": search_query},
    }

    top_chunks = _search_candidates(search_query, manual_id, k=4)
    context = "\n\n".join(
        f"[{row['section_title'] or '제목 없음'}]\n{row['content']}"
        for row in top_chunks
    )

    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    messages = [SystemMessage(content=system_prompt)]
    for turn in history or []:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn.get("text", "")))
        else:
            messages.append(AIMessage(content=turn.get("text", "")))
    messages.append(HumanMessage(content=question))

    result: ClarifyOrAnswer = structured_llm.invoke(messages)

    trace = {
        "engine": "langchain",
        "steps": [
            check_step,
            rewrite_step,
            {
                "node": "retrieve_candidates",
                "label": "관련 청크 검색",
                "input": {"search_query": search_query, "manual_id": manual_id, "k": 4},
                "output": [
                    {
                        "section_title": row["section_title"] or "",
                        "content": row["content"],
                        "vector_score": round(float(row["vector_score"]), 4),
                        "keyword_score": round(float(row["keyword_score"]), 4),
                    }
                    for row in top_chunks
                ],
            },
            {
                "node": "build_context",
                "label": "컨텍스트 조립",
                "input": {"chunk_count": len(top_chunks)},
                "output": {"context": context},
            },
            {
                "node": "llm_invoke",
                "label": "LLM 응답 생성",
                "input": {
                    "system_prompt": system_prompt,
                    "history": history or [],
                    "question": question,
                },
                "output": {"type": result.type, "text": result.text, "options": result.options},
            },
        ]
    }
    return {"type": result.type, "text": result.text, "options": result.options, "trace": trace}
