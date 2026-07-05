import os
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv("../.env")

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

query = "핫케이크 만드는 레시피를 알려줘"

results = vectorstore.similarity_search(query, k=3)

print(f"\n질문: {query}")
print(f"검색 결과 개수: {len(results)}\n")

for i, doc in enumerate(results, start=1):
    print("=" * 50)
    print(f"[검색 결과 {i}]")
    print("metadata:", doc.metadata)
    print("content:")
    print(doc.page_content[:1000])
    print()
