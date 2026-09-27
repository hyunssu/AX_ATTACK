import logging
import time

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    OPENAI_CHAT_MODEL,
    OPENAI_CHAT_MODEL_STRONG,
    OPENAI_EMBEDDING_DIMENSIONS,
    OPENAI_EMBEDDING_MODEL,
)

embeddings = OpenAIEmbeddings(
    model=OPENAI_EMBEDDING_MODEL,
    dimensions=OPENAI_EMBEDDING_DIMENSIONS,
)
llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)
strong_llm = ChatOpenAI(model=OPENAI_CHAT_MODEL_STRONG, temperature=0)

_logger = logging.getLogger("llm")


def embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


def call_llm(chain, input_, *, label: str = ""):
    """LLM 체인 호출 공통 래퍼: 재시도(최대 3회) + 소요 시간 로깅."""
    tag = f":{label}" if label else ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _invoke():
        t0 = time.monotonic()
        result = chain.invoke(input_)
        _logger.debug("[LLM%s] %.2fs", tag, time.monotonic() - t0)
        return result

    try:
        return _invoke()
    except Exception:
        _logger.error("[LLM%s] 최종 실패", tag, exc_info=True)
        raise
