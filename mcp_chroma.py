"""MCP tools for searching documents indexed in ChromaDB."""

from typing_extensions import TypedDict

from chroma_store import initialize_chroma
from download_trending_papers import download_top_five_papers
from ingest_documents import ingest_data_dir
from mcp.server.fastmcp import FastMCP

MAX_RESULTS = 10

mcp = FastMCP("chroma-document-search")


class DocumentMatch(TypedDict):
    text: str
    source: str
    page: str
    distance: float | None


class IngestionResult(TypedDict):
    indexed_chunks: int
    message: str


class DownloadResult(TypedDict):
    downloaded_count: int
    files: list[str]
    message: str


def search_documents(query: str, n_results: int = 5) -> list[DocumentMatch]:
    """Find relevant indexed document passages using Chroma vector search."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty.")
    if not 1 <= n_results <= MAX_RESULTS:
        raise ValueError(f"n_results must be between 1 and {MAX_RESULTS}.")

    collection = initialize_chroma()
    collection_size = collection.count()
    if collection_size == 0:
        raise RuntimeError(
            "The ChromaDB documents collection is empty. "
            "Run ingest_documents.py first."
        )

    result = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection_size),
        include=["documents", "metadatas", "distances"],
    )
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    matches: list[DocumentMatch] = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        if text is None:
            continue
        matches.append(
            {
                "text": text,
                "source": str(metadata.get("source", "unknown")),
                "page": str(metadata.get("page", "")),
                "distance": float(distance) if distance is not None else None,
            }
        )
    return matches


@mcp.tool()
def query_documents(query: str, n_results: int = 5) -> list[DocumentMatch]:
    """Search indexed papers and documents by meaning. Returns matching text, source, page, and distance."""
    return search_documents(query, n_results)


@mcp.tool()
def ingest_documents() -> IngestionResult:
    """Parse PDFs in the local data directory with LlamaParse and index them in ChromaDB."""
    indexed_chunks = ingest_data_dir()
    return {
        "indexed_chunks": indexed_chunks,
        "message": f"Indexed {indexed_chunks} document chunks in ChromaDB.",
    }


@mcp.tool()
def download_trending_papers() -> DownloadResult:
    """Download the five current trending papers as PDFs into the local data/papers directory."""
    downloaded_files = download_top_five_papers()
    files = [str(path) for path in downloaded_files]
    return {
        "downloaded_count": len(files),
        "files": files,
        "message": f"Downloaded {len(files)} trending papers.",
    }


@mcp.tool()
def get_db_status() -> dict:
    """Get the status of the ChromaDB collection."""
    collection = initialize_chroma()
    collection_size = collection.count()
    return {
        "collection_size": collection_size,
        "message": f"ChromaDB collection contains {collection_size} indexed document chunks.",
    }