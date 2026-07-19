from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from config import OPENAI_CHAT_MODEL


class FAQItem(BaseModel):
    question: str = Field(description="실제 사용자가 다시 검색할 법한 독립적인 질문")
    answer: str = Field(description="대화에서 확인된 내용만 사용한 간결하고 완결된 답변")
    keywords: list[str] = Field(default_factory=list, description="검색용 핵심 키워드 3~7개")


class ConversationFAQ(BaseModel):
    summary: str = Field(description="대화의 목적과 해결 내용을 담은 짧은 요약")
    faqs: list[FAQItem] = Field(
        default_factory=list,
        description="대화에서 답이 확정된 재사용 가능한 FAQ 목록. 없으면 빈 배열",
    )


faq_llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0).with_structured_output(ConversationFAQ)


FAQ_EXTRACTION_PROMPT = """너는 고객 상담 대화를 검토해 재사용 가능한 FAQ 후보를 만드는 편집자야.

규칙:
- 대화에서 사용자의 질문과 최종적으로 확인된 답만 사용하고 새로운 사실을 만들지 마.
- 답이 확정되지 않았거나 오류 메시지만 나온 주제는 FAQ에 넣지 마.
- 한 대화에 서로 다른 해결 주제가 있으면 FAQ를 여러 개 만들어.
- 질문은 이전 대화 없이도 이해되는 독립적인 문장으로 써.
- 답변에는 이름, 아이디, 이메일, 전화번호, 토큰 등 개인정보나 인증정보를 넣지 마.
- 개인 사례는 일반적인 표현으로 바꿔.
- 동일한 의미의 질문은 하나로 합쳐.
- FAQ로 재사용할 만한 내용이 없으면 faqs를 빈 배열로 반환해.

[대화]
{conversation}
"""


def summarize_conversation(messages: list[dict]) -> ConversationFAQ:
    conversation = "\n".join(
        f"{'사용자' if message['role'] == 'user' else '도우미'}: {message['text']}"
        for message in messages
    )
    return faq_llm.invoke(FAQ_EXTRACTION_PROMPT.format(conversation=conversation))
