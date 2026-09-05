from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

import rag
from chat.prompts import format_prompt


class RAGState(TypedDict):
    question: str
    manual_id: int | None
    history: list[dict]
    proceed: bool
    search_query: str
    chunks: list[dict]
    context: str
    result: dict
    trace_steps: list[dict]
    force_search: bool


def node_check_query(state: RAGState) -> dict:
    check: rag.QueryCheck = (
        rag.QueryCheck(proceed=True, clarify_text="", clarify_options=[])
        if state["force_search"]
        else rag._check_query(state["question"], state["history"])
    )
    step = {
        "node": "check_query",
        "label": "질문 적합성 판단",
        "input": {"question": state["question"], "history": state["history"]},
        "output": {
            "proceed": check.proceed,
            "forced": state["force_search"],
            "clarify_text": check.clarify_text,
            "clarify_options": check.clarify_options,
        },
    }
    update = {"proceed": check.proceed, "trace_steps": state["trace_steps"] + [step]}
    if not check.proceed:
        update["result"] = {"type": "clarify", "text": check.clarify_text, "options": check.clarify_options}
    return update


def _route_after_check(state: RAGState) -> str:
    return "continue" if state["proceed"] else "stop"


def node_rewrite_query(state: RAGState) -> dict:
    search_query = rag._rewrite_query(state["question"], state["history"])
    step = {
        "node": "rewrite_query",
        "label": "질의 재구성",
        "input": {"question": state["question"], "history": state["history"]},
        "output": {"search_query": search_query},
    }
    return {"search_query": search_query, "trace_steps": state["trace_steps"] + [step]}


def node_retrieve_candidates(state: RAGState) -> dict:
    top_chunks = rag._search_candidates(state["search_query"], state["manual_id"], k=4)
    chunks = [
        {
            "chunk_id": row["chunk_id"],
            "section_title": row["section_title"] or "",
            "content": row["content"],
            "manual_id": row["manual_id"],
            "manual_title": row["manual_title"],
            "version_id": row["version_id"],
            "version_no": row["version_no"],
            "source_created_at": row["source_created_at"].isoformat(),
            "vector_score": round(float(row["vector_score"]), 4),
            "keyword_score": round(float(row["keyword_score"]), 4),
            "combined_score": round(float(row["combined_score"]), 4),
        }
        for row in top_chunks
    ]
    step = {
        "node": "retrieve_candidates",
        "label": "관련 청크 검색",
        "input": {"search_query": state["search_query"], "manual_id": state["manual_id"], "k": 4},
        "output": chunks,
    }
    return {"chunks": chunks, "trace_steps": state["trace_steps"] + [step]}


def node_build_context(state: RAGState) -> dict:
    context = "\n\n".join(
        f"[{c['section_title'] or '제목 없음'}]\n{c['content']}"
        for c in state["chunks"]
    )
    step = {
        "node": "build_context",
        "label": "컨텍스트 조립",
        "input": {"chunk_count": len(state["chunks"])},
        "output": {"context": context},
    }
    return {"context": context, "trace_steps": state["trace_steps"] + [step]}


def node_llm_invoke(state: RAGState) -> dict:
    system_prompt = format_prompt("qa_system", context=state["context"])

    messages = [SystemMessage(content=system_prompt)]
    for turn in state["history"]:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn.get("text", "")))
        else:
            messages.append(AIMessage(content=turn.get("text", "")))
    messages.append(HumanMessage(content=state["question"]))

    result: rag.ClarifyOrAnswer = rag.structured_llm.invoke(messages)
    output = {"type": result.type, "text": result.text, "options": result.options}
    step = {
        "node": "llm_invoke",
        "label": "LLM 응답 생성",
        "input": {
            "system_prompt": system_prompt,
            "history": state["history"],
            "question": state["question"],
        },
        "output": output,
    }
    return {"result": output, "trace_steps": state["trace_steps"] + [step]}


def _build_graph():
    graph = StateGraph(RAGState)
    graph.add_node("check_query", node_check_query)
    graph.add_node("rewrite_query", node_rewrite_query)
    graph.add_node("retrieve_candidates", node_retrieve_candidates)
    graph.add_node("build_context", node_build_context)
    graph.add_node("llm_invoke", node_llm_invoke)
    graph.set_entry_point("check_query")
    graph.add_conditional_edges(
        "check_query",
        _route_after_check,
        {"continue": "rewrite_query", "stop": END},
    )
    graph.add_edge("rewrite_query", "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "build_context")
    graph.add_edge("build_context", "llm_invoke")
    graph.add_edge("llm_invoke", END)
    return graph.compile()


compiled_graph = _build_graph()


def answer_question(
    question: str,
    manual_id: int | None,
    history: list[dict] | None = None,
    *,
    force_search: bool = False,
) -> dict:
    initial_state: RAGState = {
        "question": question,
        "manual_id": manual_id,
        "history": history or [],
        "proceed": True,
        "search_query": "",
        "chunks": [],
        "context": "",
        "result": {},
        "trace_steps": [],
        "force_search": force_search,
    }
    final_state = compiled_graph.invoke(initial_state)
    result = final_state["result"]
    chunks = final_state["chunks"]
    top_score = chunks[0]["combined_score"] if chunks else 0.0
    manual_matched = bool(chunks) and top_score >= rag.MANUAL_MATCH_THRESHOLD and result["type"] == "answer"
    basis_date = chunks[0]["source_created_at"] if chunks else None
    return {
        "type": result["type"],
        "text": result["text"],
        "options": result["options"],
        "sources": [
            {
                "type": "manual",
                "id": chunk["chunk_id"],
                "title": chunk["manual_title"],
                "detail": f"버전 {chunk['version_no']} · {chunk['section_title'] or '제목 없음'}",
                "created_at": chunk["source_created_at"],
                "date_label": "매뉴얼 버전 생성일",
                "basis_date": chunk["source_created_at"],
                "basis_date_label": "매뉴얼 기준일",
            }
            for chunk in final_state["chunks"]
        ] if result["type"] == "answer" else [],
        "knowledge_match": {
            "matched": manual_matched,
            "reason": "matched" if manual_matched else "below_threshold",
            "score": top_score,
            "threshold": rag.MANUAL_MATCH_THRESHOLD,
            "basis_date": basis_date,
        },
        "trace": {"engine": "langgraph", "steps": final_state["trace_steps"]},
    }
