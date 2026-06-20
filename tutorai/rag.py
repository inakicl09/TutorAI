"""RAG logic: load PDFs uploaded by students, embed them, and store/query
them in chromaDB so the tutor can ask more specific questions.
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings

from tutorai import config


def get_vector_store() -> Chroma:
    """Open (or create) the chromaDB collection where document chunks are
    stored."""
    embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    return Chroma(
        persist_directory=config.CHROMA_DIR,
        embedding_function=embeddings,
    )


def add_pdf_to_vector_store(pdf_path: str) -> int:
    """Split a PDF into chunks and add them to chromaDB.

    Returns the number of chunks added.
    """
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)

    vector_store = get_vector_store()
    vector_store.add_documents(chunks)

    return len(chunks)


def retrieve_relevant_chunks(question: str) -> list[str]:
    """Find the document chunks most relevant to the student's question."""
    vector_store = get_vector_store()
    results = vector_store.similarity_search(
        question, k=config.NUM_CHUNKS_TO_RETRIEVE
    )
    return [result.page_content for result in results]
