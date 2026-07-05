import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
#load_dotenv(".env")

COLLECTION_NAME = "manual_collection_kyj"

connection_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(connection_url)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

vectorstore = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=engine,
    use_jsonb=True,
)

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)

query = "캐나다의 9041 화면 담당자가 누구야?"

# 1. 관련 청크 검색
results = vectorstore.similarity_search(query, k=3)

# 2. 검색된 청크를 context로 합치기
context = "\n\n---\n\n".join([doc.page_content for doc in results])

# 3. GPT 답변 생성용 프롬프트
prompt = ChatPromptTemplate.from_template("""
너는 문서 기반으로 답변하는 AI assistant야.

아래 [검색된 문서 내용]만 참고해서 사용자의 질문에 답변해.
문서에 없는 내용은 추측하지 말고 "검색된 문서에서 확인되지 않습니다."라고 답해.

[검색된 문서 내용]
{context}

[사용자 질문]
{question}

[답변]
""")

chain = prompt | llm

response = chain.invoke({
    "context": context,
    "question": query,
})

print(f"\n질문: {query}")
print(f"검색 결과 개수: {len(results)}\n")

print("=" * 50)
print("[GPT 답변]")
print(response.content)
print()

print("=" * 50)
print("[참고한 검색 청크]")
for i, doc in enumerate(results, start=1):
    print("-" * 50)
    print(f"[검색 결과 {i}]")
    print("metadata:", doc.metadata)
    print("content:")
    print(doc.page_content[:1000])
    print()
