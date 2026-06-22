from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import DB_URL, OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL, VECTOR_COLLECTION_NAME

embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)
llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)

vector_store = PGVector(
    embeddings=embeddings,
    collection_name=VECTOR_COLLECTION_NAME,
    connection=DB_URL,
)


def index_pdf(file_path: str, manual_id: int, version_id: int):
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    for chunk in chunks:
        chunk.metadata["manual_id"] = manual_id
        chunk.metadata["version_id"] = version_id
    vector_store.add_documents(chunks)


def answer_question(question: str, manual_id: int | None) -> str:
    search_kwargs = {"k": 4}
    if manual_id is not None:
        search_kwargs["filter"] = {"manual_id": manual_id}

    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
    relevant_docs = retriever.invoke(question)
    context = "\n\n".join(doc.page_content for doc in relevant_docs)

    prompt = (
        "다음 매뉴얼 내용을 참고해서 질문에 답해줘. 내용에 없는 건 모른다고 답해.\n\n"
        f"[매뉴얼 내용]\n{context}\n\n[질문]\n{question}"
    )
    response = llm.invoke(prompt)
    return response.content
