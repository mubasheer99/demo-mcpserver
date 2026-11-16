"""Persistent local ChromaDB initialization."""

from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

CHROMA_DB_PATH = Path(__file__).resolve().parent / "chroma_db"
CHROMA_COLLECTION_NAME = "documents"
CHROMA_EMBEDDING_FUNCTION = DefaultEmbeddingFunction()


def initialize_chroma(path: Path = CHROMA_DB_PATH) -> Collection:
    """Open the persistent ChromaDB and create its documents collection if needed."""
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=CHROMA_EMBEDDING_FUNCTION,
    )
