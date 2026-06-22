"""RAG logic: load PDFs uploaded by students or teachers, embed them, and
store/query them in chromaDB so the tutor (or Logos) can ask more
specific questions.

Student course material and teacher exam material live in separate
chromaDB collections (TEACHER_MATERIALS_COLLECTION vs the default), so a
teacher's exam content can never leak into a student's tutoring session.
"""

from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings

from tutorai import config

TEACHER_MATERIALS_COLLECTION = "teacher_materials"


def get_vector_store(collection_name: Optional[str] = None) -> Chroma:
    """Open (or create) a chromaDB collection where document chunks are
    stored. Defaults to the student course-material collection; pass
    TEACHER_MATERIALS_COLLECTION for a teacher's exam material instead."""
    embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    kwargs = {"persist_directory": config.CHROMA_DIR, "embedding_function": embeddings}
    if collection_name:
        kwargs["collection_name"] = collection_name
    return Chroma(**kwargs)


def add_pdf_to_vector_store(pdf_path: str, collection_name: Optional[str] = None) -> int:
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

    vector_store = get_vector_store(collection_name)
    vector_store.add_documents(chunks)

    return len(chunks)


def retrieve_relevant_chunks(question: str, collection_name: Optional[str] = None) -> list[str]:
    """Find the document chunks most relevant to the question."""
    vector_store = get_vector_store(collection_name)
    results = vector_store.similarity_search(
        question, k=config.NUM_CHUNKS_TO_RETRIEVE
    )
    return [result.page_content for result in results]
