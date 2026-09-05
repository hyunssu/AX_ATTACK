"""Centralized bilingual prompts used by every LLM call.

Set ``PROMPT_LANGUAGE=ko`` or ``PROMPT_LANGUAGE=en`` in the environment.
Korean remains the default so existing deployments keep their current behavior.
"""

import os


SUPPORTED_PROMPT_LANGUAGES = {"ko", "en"}
DEFAULT_PROMPT_LANGUAGE = "ko"


def get_prompt_language(language: str | None = None) -> str:
    """Return a supported two-letter prompt language code."""
    requested = (language or os.getenv("PROMPT_LANGUAGE", DEFAULT_PROMPT_LANGUAGE)).strip().lower()
    normalized = requested.replace("_", "-").split("-", 1)[0]
    if normalized not in SUPPORTED_PROMPT_LANGUAGES:
        supported = ", ".join(sorted(SUPPORTED_PROMPT_LANGUAGES))
        raise ValueError(f"Unsupported PROMPT_LANGUAGE '{requested}'. Use one of: {supported}")
    return normalized


PROMPTS = {
    "conversation_context_summary": {
        "ko": (
            "너는 Aither 업무 지원 채팅의 대화 맥락을 압축하는 Agent다. 답변을 생성하지 말고 구조화된 맥락만 만든다.\n"
            "최초 업무 질문의 목적을 유지하면서 화면번호, 국가, 업무명, 오류, 담당자/담당팀처럼 확인된 사실을 합친다.\n"
            "현재 메시지가 'India', '모르겠어요', yes/no처럼 짧더라도 직전 AI의 추가질문에 대한 답이면 후속답변으로 판정한다.\n"
            "사용자가 명백히 새 주제로 전환하지 않았다면 활성 업무 질문을 종료하지 않는다. 사실을 추측하지 않는다.\n\n"
            "[이전 대화]\n{history_text}\n\n[현재 사용자 메시지]\n{message}"
        ),
        "en": (
            "You compress the conversation context for an Aither business-support chat. Do not answer the user; only create structured context.\n"
            "Preserve the goal of the original business question and combine confirmed facts such as screen number, country, business area, error, assignee, and team.\n"
            "Even when the current message is short, such as 'India', 'I don't know', or yes/no, mark it as a follow-up when it answers the AI's preceding clarification.\n"
            "Do not end an active business inquiry unless the user clearly changes topics. Never invent facts.\n\n"
            "[Prior conversation]\n{history_text}\n\n[Current user message]\n{message}"
        ),
    },
    "chunk_meta": {
        "ko": (
            "다음은 매뉴얼에서 잘라낸 한 청크(chunk)야. "
            "이 청크의 섹션 제목과 핵심 키워드를 뽑아줘.\n\n"
            "[청크 내용]\n{chunk_text}"
        ),
        "en": (
            "The following is a chunk extracted from a manual. "
            "Extract its section title and primary keywords.\n\n"
            "[Chunk]\n{chunk_text}"
        ),
    },
    "query_check": {
        "ko": (
            "너는 사용자의 질문이 매뉴얼 검색(RAG)으로 답할 수 있는 질문인지 먼저 판단하는 게이트야.\n"
            "인사말, 잡담, 매뉴얼과 무관한 요청, 너무 모호해서 무엇을 검색해야 할지 알 수 없는 질문이면 "
            "proceed를 false로 하고 되묻는 질문을 clarify_text에 담아.\n"
            "매뉴얼 내용을 검색해서 답할 수 있을 만큼 구체적인 질문이면 proceed를 true로 해.\n\n"
            "[압축된 최종 대화 맥락]\n{conversation_context}\n\n[대화 이력]\n{history_text}\n\n[이번 질문]\n{question}"
        ),
        "en": (
            "You are a gate that decides whether a user's question can be answered through manual search (RAG).\n"
            "For greetings, small talk, requests unrelated to manuals, or questions too vague to search, "
            "set proceed to false and put a follow-up question in clarify_text.\n"
            "If the question is specific enough to answer by searching the manuals, set proceed to true.\n\n"
            "[Condensed final conversation context]\n{conversation_context}\n\n[Conversation history]\n{history_text}\n\n[Current question]\n{question}"
        ),
    },
    "query_rewrite": {
        "ko": (
            "다음은 사용자와의 대화 이력과 마지막 질문이야.\n"
            "마지막 질문이 대명사('그거', '그럼', '거기')나 생략된 맥락 때문에 이전 대화 없이는 무엇을 "
            "검색해야 할지 알 수 없다면, 대화 이력의 맥락을 반영해서 검색에 적합한 완전한 독립형 질문으로 다시 써줘.\n"
            "이미 맥락 없이도 뜻이 통하는 질문이면 그대로 반환해. 답을 하지 말고 질문만 다시 써.\n\n"
            "[압축된 최종 대화 맥락]\n{conversation_context}\n\n[대화 이력]\n{history_text}\n\n[마지막 질문]\n{question}"
        ),
        "en": (
            "Below are the conversation history and the user's latest question.\n"
            "If pronouns or omitted context make the latest question impossible to search without the history, "
            "rewrite it as a complete, standalone question suitable for retrieval using the conversation context.\n"
            "If it already makes sense on its own, return it unchanged. Do not answer it; only rewrite the question.\n\n"
            "[Condensed final conversation context]\n{conversation_context}\n\n[Conversation history]\n{history_text}\n\n[Latest question]\n{question}"
        ),
    },
    "qa_system": {
        "ko": (
            "너는 매뉴얼 내용을 참고해 사용자 질문에 답하는 도우미야.\n"
            "매뉴얼 내용과 지금까지의 대화만으로 정확히 답할 수 있으면 type을 'answer'로 하고 답변을 text에 담아.\n"
            "질문이 모호하거나, 매뉴얼에 여러 경우(버전/상황 등)가 있어 의도를 좁혀야 답할 수 있으면 "
            "type을 'clarify'로 하고 text에 되묻는 질문을, options에 2~4개의 선택지를 담아.\n"
            "options에는 구체적인 선택지만 담고, '기타'/'그 외'/'다른 경우' 같은 포괄적 항목은 넣지 마. "
            "화면에서 자유 입력용 '내용수정' 버튼은 항상 자동으로 추가돼.\n"
            "매뉴얼 내용에 없는 건 모른다고 답해. 사용자 질문의 언어와 관계없이 항상 한국어로 답해.\n\n"
            "[매뉴얼 내용]\n{context}"
        ),
        "en": (
            "You answer user questions using the supplied manual content.\n"
            "If the manual and conversation are sufficient for an accurate answer, set type to 'answer' and put the answer in text.\n"
            "If the question is ambiguous or the manual contains multiple relevant cases (such as versions or situations), "
            "set type to 'clarify', put a follow-up question in text, and provide 2 to 4 choices in options.\n"
            "Only include specific choices in options. Do not add broad choices such as 'Other' or 'Different case'; "
            "the UI automatically adds an 'Edit details' free-input button.\n"
            "If the manual does not contain the answer, say that you do not know. Always reply in English, regardless of the question language.\n\n"
            "[Manual content]\n{context}"
        ),
    },
    "intake_analysis": {
        "ko": (
            "너는 아이테르 업무 문의 접수 Agent다.\n"
            "매뉴얼과 승인 FAQ 검색으로 답을 찾지 못한 질문을 담당자에게 전달할 수 있게 정리한다.\n\n"
            "규칙:\n"
            "- target_business는 질문의 단순 키워드가 아니라 업무범위 성격을 추론하여 "
            "수신, 여신, 고객, 외환, 채널, 공통, 총무, 카드, UMS, 기타 중 하나만 선택한다.\n"
            "- 어느 분류에도 명확히 속하지 않으면 기타를 선택한다.\n"
            "- 이전 대화에서 이미 답한 정보는 다시 묻지 않는다.\n"
            "- missing_information은 답변에 꼭 필요한 것만 최대 3개로 제한한다.\n"
            "- 대상 국가는 필수 정보다. 대화에서 대상 국가가 확인되지 않으면 반드시 missing_information의 첫 항목으로 질문한다.\n"
            "- 화면번호, 오류 메시지, 발생 국가/업무 중 질문에 실제로 필요한 항목만 고른다.\n"
            "- 정보가 충분하면 missing_information은 빈 배열이다.\n"
            "- 사용자가 예상 담당자를 여러 명 말하면 preferred_assignee_names에 모두 보존한다.\n"
            "- 사용자가 담당팀을 말하면 preferred_team에 보존한다.\n"
            "- 사실을 추측하지 않는다. missing_information은 한국어로 작성한다.\n\n"
            "[압축된 최종 대화 맥락]\n{conversation_context}\n\n[이전 대화]\n{history_text}\n\n[현재 사용자 메시지]\n{question}"
        ),
        "en": (
            "You are an intake agent for Aither business inquiries.\n"
            "Organize questions that could not be answered through manual and approved-FAQ search so they can be sent to an assignee.\n\n"
            "Rules:\n"
            "- Infer target_business from the nature of the business scope, not simple keywords, and select exactly one of "
            "수신, 여신, 고객, 외환, 채널, 공통, 총무, 카드, UMS, 기타.\n"
            "- Select 기타 when no category clearly applies.\n"
            "- Do not ask again for information already provided in the conversation.\n"
            "- Limit missing_information to at most three items that are essential to answering.\n"
            "- The target country is mandatory. If it is not identified, ask for it as the first missing_information item.\n"
            "- Only request screen number, error message, country, or business details that are actually needed.\n"
            "- Use an empty missing_information array when the information is sufficient.\n"
            "- Preserve every named expected assignee in preferred_assignee_names.\n"
            "- Preserve a named team in preferred_team.\n"
            "- Do not invent facts. Write missing_information in English.\n\n"
            "[Condensed final conversation context]\n{conversation_context}\n\n[Conversation history]\n{history_text}\n\n[Current user message]\n{question}"
        ),
    },
    "registration_revision": {
        "ko": (
            "너는 FAQ 등록 제안서를 수정하는 Agent다.\n"
            "이전 대화와 가장 최근의 FAQ 등록 제안 내용을 모두 읽고, 사용자의 수정 지시를 반영한 완전한 등록 제안 정보를 다시 작성한다.\n\n"
            "규칙:\n"
            "- target_business는 전체 대화의 업무범위를 추론하여 수신, 여신, 고객, 외환, 채널, 공통, 총무, 카드, UMS, 기타 중 하나만 선택한다.\n"
            "- 기존 제안의 대상업무, 화면번호, 국가, 정제 질문, 예상 담당자와 담당팀 정보를 빠뜨리지 않는다.\n"
            "- 사용자가 변경하거나 추가하라고 한 내용만 정확히 반영하고 나머지는 유지한다.\n"
            "- 사용자가 사람 이름이나 담당팀을 추가하면 preferred_assignee_names와 preferred_team에 보존한다.\n"
            "- 수정 지시가 빈 문자열이면 가장 최근 등록 제안과 그 이전 대화만으로 현재 제안 정보를 복원한다.\n"
            "- 사실을 새로 추측하지 않는다.\n"
            "- 대상 국가는 필수 정보이며 확인되지 않았으면 missing_information에 포함한다.\n\n"
            "[이전 대화와 현재 등록 제안]\n{history_text}\n\n[사용자의 수정 지시]\n{instruction}"
        ),
        "en": (
            "You are an agent that revises an FAQ registration proposal.\n"
            "Read the prior conversation and latest proposal, then produce a complete proposal incorporating the user's revision.\n\n"
            "Rules:\n"
            "- Infer target_business from the full conversation and select exactly one of "
            "수신, 여신, 고객, 외환, 채널, 공통, 총무, 카드, UMS, 기타.\n"
            "- Preserve the existing business scope, screen number, country, refined question, expected assignees, and team.\n"
            "- Apply only requested changes or additions and preserve everything else.\n"
            "- Preserve added person names and team names in preferred_assignee_names and preferred_team.\n"
            "- If the revision is empty, reconstruct the current proposal from the latest proposal and preceding conversation.\n"
            "- Do not invent facts.\n"
            "- The target country is mandatory; include it in missing_information when unknown.\n\n"
            "[Conversation and current proposal]\n{history_text}\n\n[User revision]\n{instruction}"
        ),
    },
    "registration_followup": {
        "ko": (
            "너는 FAQ 등록 확인 단계의 사용자 후속 메시지를 분류한다.\n\n"
            "분류 기준:\n"
            "- confirm: 현재 제안 그대로 FAQ 등록을 승인한다.\n"
            "- cancel: FAQ를 등록하지 않거나 보내지 말라고 거절한다.\n"
            "- revise: 현재 FAQ 제안의 질문, 업무, 국가, 화면번호, 담당자, 담당팀 또는 기타 등록 내용을 수정·추가·삭제해 달라는 요청이다.\n"
            "- new_message: 현재 FAQ 등록 제안과 관계없는 인사, 일반 대화, 또는 완전히 새로운 질문이다.\n\n"
            "단순히 자유입력으로 보냈다는 이유로 revise로 판단하지 말고 의미를 기준으로 판정한다.\n\n"
            "[직전 대화]\n{history_text}\n\n[현재 사용자 메시지]\n{message}"
        ),
        "en": (
            "Classify the user's follow-up message at the FAQ registration confirmation step.\n\n"
            "Classes:\n"
            "- confirm: approve registration of the current proposal unchanged.\n"
            "- cancel: decline or cancel FAQ registration.\n"
            "- revise: request a change, addition, or deletion to the question, business, country, screen number, assignee, team, or other proposal details.\n"
            "- new_message: a greeting, general conversation, or entirely new question unrelated to the current proposal.\n\n"
            "Classify by meaning; do not select revise merely because the user typed free-form text.\n\n"
            "[Recent conversation]\n{history_text}\n\n[Current user message]\n{message}"
        ),
    },
    "main_chat_route": {
        "ko": (
            "사용자의 현재 메시지가 아이테르 업무 매뉴얼이나 업무 지식에서 정보를 찾아야 하는 질문인지 판정한다.\n\n"
            "business_manual에 해당하는 경우:\n"
            "- 업무 절차, 처리 방법, 오류 조치, 시스템 기능, 화면번호, 메뉴, 권한, 환경설정 문의\n"
            "- 담당자·담당팀·담당 국가 조회 또는 변경 요청\n"
            "- 직전 업무 문의에 필요한 국가, 업무명, 화면번호, 오류 메시지 등의 후속 답변\n\n"
            "general_chat에 해당하는 경우:\n"
            "- 아이테르 매뉴얼에 대해 질문하도록 유도\n"
            "압축된 대화 맥락에서 활성 업무 질문이 있고 현재 메시지가 그 후속답변이면, 메시지만 보면 의미가 없거나 '모른다'는 답이어도 반드시 business_manual이다.\n"
            "사용자가 명백히 새 주제로 전환한 경우에만 활성 업무 맥락을 종료할 수 있다.\n\n"
            "[압축된 최종 대화 맥락]\n{conversation_context}\n\n[최근 대화]\n{history_text}\n\n[현재 사용자 메시지]\n{message}"
        ),
        "en": (
            "Decide whether the user's current message requires information from Aither business manuals or business knowledge.\n\n"
            "Use business_manual for:\n"
            "- business procedures, handling methods, error resolution, system functions, screen numbers, menus, permissions, or configuration\n"
            "- requests to find or change an assignee, team, or responsible country\n"
            "- follow-up details needed for a preceding business inquiry, such as country, business name, screen number, or error message\n\n"
            "Use general_chat for:\n"
            "- lead user to ask question related to Aither manuals\n"
            "- meaningless short messages or conversation-ending expressions\n\n"
            "When the condensed context contains an active business question and the current message follows it, always use business_manual even if the message alone is meaningless or says 'I don't know'.\n"
            "Only end an active business context when the user clearly changes topics.\n\n"
            "[Condensed final conversation context]\n{conversation_context}\n\n[Recent conversation]\n{history_text}\n\n[Current user message]\n{message}"
        ),
    },
    "business_scope_redirect": {
        "ko": (
            "너는 Aither 업무 지원 챗봇이다. 다음 메시지는 Aither 업무 질문으로 분류되지 않았다.\n"
            "사용자의 일반 질문에 직접 답하지 말고, Aither 업무에 관한 질문이 맞는지 친절하게 확인한다.\n"
            "Aither 업무 문의가 맞다면 업무 절차, 처리 방법, 오류 메시지, 화면번호, 메뉴, 권한, 환경설정, "
            "담당자·담당팀·담당 국가 중 관련 정보를 포함해 다시 질문하도록 구체적으로 안내한다.\n"
            "사용자가 바로 다시 질문할 수 있도록 2~3개의 짧은 질문 예시를 제시한다.\n"
            "Aither 업무 자료를 검색했다고 말하거나 사용자의 의도를 임의로 추측하지 않는다.\n"
            "답변은 간결하고 자연스러운 한국어로 작성한다.\n\n"
            "[최근 대화]\n{history_text}\n\n[현재 사용자 메시지]\n{message}"
        ),
        "en": (
            "You are an Aither business support assistant. The following message was not classified as an Aither business question.\n"
            "Do not answer the general question directly. Politely ask whether the user intended to ask about Aither business.\n"
            "If so, guide them to ask again with relevant details such as the business procedure, handling method, error message, "
            "screen number, menu, permission, configuration, assignee, responsible team, or responsible country.\n"
            "Give two or three short example questions so the user can immediately try again.\n"
            "Do not claim that Aither resources were searched and do not guess the user's intent.\n"
            "Keep the response concise and natural, and always reply in English.\n\n"
            "[Recent conversation]\n{history_text}\n\n[Current user message]\n{message}"
        ),
    },
    "translate_knowledge_answer": {
        "ko": (
            "다음 업무 지식 답변을 정확하고 자연스러운 한국어로 번역해.\n"
            "의미, 수치, 화면번호, 고유명사, Markdown 형식을 그대로 보존하고 설명이나 머리말을 추가하지 마.\n\n"
            "[번역할 답변]\n{answer}"
        ),
        "en": (
            "Translate the following business-knowledge answer into accurate, natural English.\n"
            "Preserve its meaning, numbers, screen identifiers, proper nouns, and Markdown formatting. "
            "Do not add commentary or a preface.\n\n"
            "[Answer to translate]\n{answer}"
        ),
    },
    "localize_chat_response": {
        "ko": (
            "다음은 Aither 챗봇이 완성한 최종 응답과 선택지다. 전체 내용을 자연스러운 한국어로 현지화해.\n"
            "업무분류, 직책, 부서/팀명, 상태, 신뢰도 등 사용자에게 표시되는 한국어가 아닌 모든 일반 문구를 한국어로 바꾼다.\n"
            "화면번호, FAQ 요청번호, 사용자명, 이메일, URL, 제품명, 코드 값처럼 의미가 바뀌면 안 되는 식별자는 보존한다.\n"
            "사람 이름은 번역하지 않는다. Markdown 구조, 줄바꿈, 수치와 의미를 유지하고 설명이나 머리말을 추가하지 않는다.\n"
            "본문뿐 아니라 모든 선택지도 한국어로 반환한다.\n\n"
            "[최종 응답]\n{text}\n\n[선택지]\n{options_text}"
        ),
        "en": (
            "The following is a completed Aither chatbot response with its options. Localize all displayed content into natural English.\n"
            "Translate every general-language value shown to the user, including business categories, job titles, department/team names, statuses, and confidence levels.\n"
            "Preserve identifiers whose meaning must not change, including screen numbers, FAQ request numbers, usernames, email addresses, URLs, product names, and code values.\n"
            "Do not translate personal names. Preserve Markdown structure, line breaks, numbers, and meaning. Do not add commentary or a preface.\n"
            "Return both the body and every option in English.\n\n"
            "[Final response]\n{text}\n\n[Options]\n{options_text}"
        ),
    },
    "faq_refinement": {
        "ko": (
            "너는 FAQ 편집자다. 최초 사용자 질문부터 현재까지 오간 모든 메시지를 읽고, "
            "전체 대화에서 가장 중요한 질문과 현재까지 확인된 가장 유용한 답변을 FAQ 질문/답변 한 쌍으로 정리한다.\n\n"
            "규칙:\n"
            "- 발화 주체와 메시지 유형에 상관없이 사용자 질문, AI 답변, 담당자 답변, 추가질의, 사용자 회신, 내부 메모를 모두 근거로 사용한다.\n"
            "- 서로 중복되거나 충돌하는 내용은 전체 맥락을 기준으로 통합하되, 확인되지 않은 사실을 새로 만들지 않는다.\n"
            "- 최종 답변으로 명시된 메시지가 없어도 현재까지 확인된 설명, 처리 방향, 담당자 의견과 진행 상태를 종합해 answer를 반드시 작성한다.\n"
            "- 확정되지 않은 부분은 확정된 것처럼 쓰지 말고 '현재까지 확인된 내용'과 '추가 확인이 필요한 내용'으로 구분한다.\n"
            "- answer를 빈 문자열로 반환하지 않는다. 답변할 정보가 전혀 없다면 그 사실과 추가로 필요한 정보를 짧게 적는다.\n"
            "- 개인정보·인증정보는 제거한다.\n"
            "- 질문과 답변은 이전 대화 없이 이해되게 작성한다.\n"
            "- question은 전체 대화에서 해결하려는 핵심 질문 하나로 정제한다.\n"
            "- keywords는 검색에 유용한 핵심어 3~7개로 작성한다.\n"
            "- 질문과 답변은 원래 문의에서 사용한 언어로 작성한다.\n\n"
            "[최초 질문]\n{original_question}\n\n[현재 정제 질문]\n{refined_question}\n\n[협업 대화]\n{conversation}"
        ),
        "en": (
            "You are an FAQ editor. Read every message from the initial question through the current conversation, "
            "then produce one FAQ question-and-answer pair containing the central question and most useful confirmed answer.\n\n"
            "Rules:\n"
            "- Use user questions, AI answers, assignee answers, follow-up questions, user replies, and internal notes regardless of speaker or message type.\n"
            "- Reconcile duplicates or conflicts using the full context, but do not invent unconfirmed facts.\n"
            "- Always produce an answer by combining confirmed explanations, handling direction, assignee opinions, and progress, even without an explicitly final response.\n"
            "- Separate confirmed information from items requiring further confirmation.\n"
            "- Never return an empty answer. If no answer is available, briefly state that and what additional information is needed.\n"
            "- Remove personal data and credentials.\n"
            "- Make the question and answer understandable without the preceding conversation.\n"
            "- Refine question into the single central issue the conversation is trying to resolve.\n"
            "- Provide 3 to 7 useful search terms in keywords.\n"
            "- Write the question and answer in the language of the original inquiry.\n\n"
            "[Original question]\n{original_question}\n\n[Current refined question]\n{refined_question}\n\n[Collaboration conversation]\n{conversation}"
        ),
    },
}


SCHEMA_DESCRIPTIONS = {
    "localization.text": {
        "ko": "대상 언어로 전체 현지화된 최종 채팅 본문",
        "en": "The complete final chat body localized into the target language",
    },
    "localization.options": {
        "ko": "대상 언어로 현지화된 선택지 전체",
        "en": "All response options localized into the target language",
    },
    "conversation.summary": {
        "ko": "최초 업무 목적과 현재까지 확인된 사실을 합친 독립적인 대화 요약",
        "en": "A standalone summary combining the original business goal and all facts confirmed so far",
    },
    "conversation.active_business_question": {
        "ko": "현재 해결 중인 Aither 업무 질문. 없으면 빈 문자열",
        "en": "The active Aither business question being resolved, or an empty string",
    },
    "conversation.confirmed_facts": {
        "ko": "대화에서 사용자가 확인한 화면번호, 국가, 업무, 오류, 담당자 등의 사실",
        "en": "Facts confirmed by the user, such as screen number, country, business area, error, or assignee",
    },
    "conversation.pending_clarification": {
        "ko": "직전 AI가 답변을 기다리고 있는 추가질문. 없으면 빈 문자열",
        "en": "The latest AI clarification awaiting an answer, or an empty string",
    },
    "conversation.is_aither_business_context": {
        "ko": "전체 대화가 현재 Aither 업무 문의를 해결하는 흐름이면 true",
        "en": "True when the conversation is currently resolving an Aither business inquiry",
    },
    "conversation.current_message_is_followup": {
        "ko": "현재 메시지가 기존 업무 질문 또는 직전 추가질문에 대한 후속답변이면 true",
        "en": "True when the current message follows the active business question or latest clarification",
    },
    "intake.target_business": {
        "ko": "질문의 업무범위 성격을 추론한 단일 분류",
        "en": "Exactly one inferred classification for the business scope of the question",
    },
    "intake.screen_number": {
        "ko": "확인된 화면번호. 없으면 빈 문자열",
        "en": "Confirmed screen number, or an empty string when unknown",
    },
    "intake.country": {
        "ko": "확인된 담당 국가. 없으면 빈 문자열",
        "en": "Confirmed responsible country, or an empty string when unknown",
    },
    "intake.refined_question": {
        "ko": "대화 맥락을 반영한 독립적이고 정제된 질문",
        "en": "A standalone refined question incorporating the conversation context",
    },
    "intake.missing_information": {
        "ko": "담당자가 답하려면 꼭 필요한 추가 정보. 중요도 순 최대 3개",
        "en": "Essential additional information needed by the assignee, at most three items in priority order",
    },
    "intake.assignment_keywords": {
        "ko": "담당자 배정용 핵심어",
        "en": "Keywords used to select an assignee",
    },
    "intake.preferred_assignee_names": {
        "ko": "사용자가 예상 담당자로 직접 언급한 사람 이름/직급. 여러 명이면 모두 포함",
        "en": "Names or titles explicitly mentioned as expected assignees; preserve all when multiple are given",
    },
    "intake.preferred_team": {
        "ko": "사용자가 직접 언급한 예상 담당팀",
        "en": "Expected responsible team explicitly mentioned by the user",
    },
    "refined_pair.question": {
        "ko": "FAQ 지식으로 등록할 수 있는 독립적이고 정제된 질문",
        "en": "A standalone refined question suitable for registration as FAQ knowledge",
    },
    "refined_pair.answer": {
        "ko": "대화에서 담당자가 확인한 사실만 담은 완결된 답변",
        "en": "A complete answer containing only facts confirmed in the conversation",
    },
    "refined_pair.keywords": {
        "ko": "검색용 핵심어 3~7개",
        "en": "Three to seven keywords for retrieval",
    },
    "main_route.route": {
        "ko": "업무 매뉴얼·FAQ·화면·담당자 검색 질문이면 business_manual, 아니면 general_chat",
        "en": "Use business_manual for manual, FAQ, screen, or assignee lookup questions; otherwise general_chat",
    },
    "common.reason": {"ko": "판정 근거", "en": "Reason for the decision"},
    "registration.action": {
        "ko": "FAQ 등록 확정, 취소, 등록 내용 보완, 또는 기존 등록과 무관한 새 메시지",
        "en": "Confirm FAQ registration, cancel it, revise proposal details, or identify an unrelated new message",
    },
    "rag.answer_type": {
        "ko": "매뉴얼 내용과 대화 맥락만으로 바로 답변할 수 있으면 'answer', 질문이 모호하거나 추가 정보가 필요하면 'clarify'",
        "en": "Use 'answer' when the manual and context are sufficient; use 'clarify' when the question is ambiguous or needs more information",
    },
    "rag.answer_text": {
        "ko": "사용자에게 보여줄 답변 또는 되묻는 질문 내용",
        "en": "The answer or follow-up question shown to the user",
    },
    "rag.answer_options": {
        "ko": "type이 clarify일 때 사용자가 고를 수 있는 2~4개의 선택지. answer일 때는 빈 배열",
        "en": "Two to four choices when type is clarify; an empty array when type is answer",
    },
    "rag.query_proceed": {
        "ko": "검색(RAG)을 진행해도 되는 질문이면 true, 인사말/잡담/매뉴얼과 무관하거나 너무 모호해서 되물어야 하면 false",
        "en": "True when RAG search should proceed; false for greetings, small talk, unrelated, or overly vague questions",
    },
    "rag.clarify_text": {
        "ko": "proceed가 false일 때 사용자에게 되물을 질문. true일 때는 빈 문자열",
        "en": "A follow-up question when proceed is false; an empty string when true",
    },
    "rag.clarify_options": {
        "ko": "proceed가 false일 때 사용자가 고를 수 있는 2~4개의 선택지. true일 때는 빈 배열",
        "en": "Two to four choices when proceed is false; an empty array when true",
    },
    "rag.standalone_question": {
        "ko": "검색에 사용할, 대화 맥락이 반영된 독립형 질문. 맥락이 필요 없으면 원래 질문 그대로",
        "en": "A standalone search question incorporating context, or the original question when no context is needed",
    },
    "rag.section_title": {
        "ko": "이 청크가 속한 섹션/항목의 제목. 알 수 없으면 빈 문자열",
        "en": "The section or item title containing this chunk, or an empty string when unknown",
    },
    "rag.chunk_keywords": {
        "ko": "이 청크의 핵심 키워드 3~7개. 사용자가 검색할 때 쓸 법한 용어 위주로",
        "en": "Three to seven primary chunk keywords, favoring terms users are likely to search",
    },
}


PROMPT_LABELS = {
    "user": {"ko": "사용자", "en": "User"},
    "ai": {"ko": "AI", "en": "AI"},
    "participant": {"ko": "참여자", "en": "Participant"},
    "empty_history": {"ko": "(이전 대화 없음)", "en": "(No previous conversation)"},
    "empty_value": {"ko": "(없음)", "en": "(None)"},
    "no_revision": {"ko": "(수정 없이 현재 제안 유지)", "en": "(Keep the current proposal unchanged)"},
}


def format_prompt(name: str, *, language: str | None = None, **values) -> str:
    """Render a named prompt in Korean or English."""
    selected = get_prompt_language(language)
    try:
        template = PROMPTS[name][selected]
    except KeyError as exc:
        raise KeyError(f"Unknown prompt '{name}' or missing '{selected}' translation") from exc
    return template.format(**values)


def schema_description(name: str, *, language: str | None = None) -> str:
    """Return a localized structured-output field description."""
    selected = get_prompt_language(language)
    try:
        return SCHEMA_DESCRIPTIONS[name][selected]
    except KeyError as exc:
        raise KeyError(f"Unknown schema description '{name}' or missing '{selected}' translation") from exc


def prompt_label(name: str, *, language: str | None = None) -> str:
    """Return localized labels used while assembling prompt input."""
    selected = get_prompt_language(language)
    try:
        return PROMPT_LABELS[name][selected]
    except KeyError as exc:
        raise KeyError(f"Unknown prompt label '{name}' or missing '{selected}' translation") from exc
