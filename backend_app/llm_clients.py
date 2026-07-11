from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import OPENAI_CHAT_MODEL, OPENAI_CHAT_MODEL_STRONG, OPENAI_EMBEDDING_MODEL

embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)
llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)
strong_llm = ChatOpenAI(model=OPENAI_CHAT_MODEL_STRONG, temperature=0)


def embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"
