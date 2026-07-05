import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_community.document_loaders import PyPDFLoader

from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv("../.env")

DOCS_DIR = Path("docs")
COLLECTION_NAME = "manual_collection_kyj"

#connection = str(URL.create(
#    drivername="postgresql+psycopg",
#    username=os.getenv("DB_USER"),
#    password=os.getenv("DB_PASSWORD"),
#    host=os.getenv("DB_HOST"),
#    port=int(os.getenv("DB_PORT")),
#    database=os.getenv("DB_NAME"),
#))

connection_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(connection_url)

def load_documents():
    documents = []

    for file_path in DOCS_DIR.iterdir():
        suffix = file_path.suffix.lower()

        if suffix == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
            documents.extend(loader.load())

        elif suffix == ".pptx":
            loader = UnstructuredPowerPointLoader(str(file_path), mode="single")
            documents.extend(loader.load())

        elif suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
            documents.extend(loader.load())

    return documents


def main():
    documents = load_documents()

    if not documents:
        print("docs 폴더에 txt 또는 pptx 파일이 없습니다.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    chunks = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        #connection=connection,
        connection=engine,
        use_jsonb=True,
    )

    vectorstore.add_documents(chunks)

    print(f"문서 적재 완료: 원본문서 {len(documents)}개, 청크 {len(chunks)}개")


if __name__ == "__main__":
    main()
