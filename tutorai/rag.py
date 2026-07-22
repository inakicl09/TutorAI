"""RAG logic: load PDFs uploaded by students or teachers, embed them, and
store/query them in chromaDB so the tutor (or Logos) can ask more
specific questions.

Student course material and teacher exam material live in separate
chromaDB collections (TEACHER_MATERIALS_COLLECTION vs the default), so a
teacher's exam content can never leak into a student's tutoring session.
"""

from typing import Optional

import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from tutorai import config

# NOTE: RecursiveCharacterTextSplitter and PyPDFLoader are imported lazily
# inside add_pdf_to_vector_store to keep app startup fast -- they're only
# needed when someone actually uploads a PDF.

TEACHER_MATERIALS_COLLECTION = "teacher_materials"

# langchain_chroma uses "langchain" as the default collection name when none
# is specified -- this must match what Chroma() creates internally.
_DEFAULT_COLLECTION = "langchain"


def _collection_has_documents(collection_name: Optional[str]) -> bool:
    """Check whether a ChromaDB collection has any documents, WITHOUT loading
    the embedding model. The embedding model is heavy (~22 MB download) and
    currently broken on this machine, so we skip it entirely when the
    collection is empty and there is nothing to search anyway."""
    chroma_name = collection_name if collection_name else _DEFAULT_COLLECTION
    try:
        client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        col = client.get_collection(chroma_name)
        return col.count() > 0
    except Exception:
        return False  # collection doesn't exist yet = empty


def get_vector_store(collection_name: Optional[str] = None) -> Chroma:
    """Open (or create) a chromaDB collection where document chunks are
    stored. Only call this when you know the collection has documents --
    it loads the embedding model, which is expensive.
    """
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)
    kwargs = {"persist_directory": config.CHROMA_DIR, "embedding_function": embeddings}
    if collection_name:
        kwargs["collection_name"] = collection_name
    return Chroma(**kwargs)


def add_pdf_to_vector_store(pdf_path: str, collection_name: Optional[str] = None) -> int:
    """Split a PDF into chunks and add them to chromaDB.

    Returns the number of chunks added.
    """
    # Deferred imports -- see the NOTE at the top of this module.
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    """Find the document chunks most relevant to the question.

    Returns an empty list immediately if the collection has no documents yet,
    without ever loading the embedding model (which is expensive and currently
    broken on this machine due to a torch/numpy version conflict).
    """
    if not _collection_has_documents(collection_name):
        return []

    vector_store = get_vector_store(collection_name)
    results = vector_store.similarity_search(
        question, k=config.NUM_CHUNKS_TO_RETRIEVE
    )
    return [result.page_content for result in results]
