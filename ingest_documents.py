"""Parse local PDFs with LlamaParse and store them in ChromaDB."""

import hashlib
import json
import os
from pathlib import Path
import time

import requests

from chroma_store import CHROMA_EMBEDDING_FUNCTION, initialize_chroma

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_LLAMA_CLOUD_BASE_URL = "https://api.cloud.llamaindex.ai"
PARSE_POLL_INTERVAL_SECONDS = 2
PARSE_TIMEOUT_SECONDS = 2000
REQUEST_TIMEOUT_SECONDS = 60


def _parse_pdf(
    path: Path, *, api_key: str, base_url: str
) -> list[tuple[str, str]]:
    """Upload a PDF to LlamaParse v2 and return its page text and page numbers."""
    endpoint = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    configuration = {"tier": "agentic", "version": "latest"}

    try:
        with path.open("rb") as pdf_file:
            response = requests.post(
                f"{endpoint}/api/v2/parse/upload",
                headers=headers,
                files={"file": (path.name, pdf_file, "application/pdf")},
                data={"configuration": json.dumps(configuration)},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        _raise_for_parse_response(response, "upload")
        job = response.json()
    except requests.RequestException as error:
        raise RuntimeError(f"Unable to submit {path.name} to LlamaParse v2.") from error
    except ValueError as error:
        raise RuntimeError("LlamaParse v2 returned invalid JSON for the upload.") from error

    job_id = job.get("id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError("LlamaParse v2 upload response did not contain a job ID.")

    deadline = time.monotonic() + PARSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"{endpoint}/api/v2/parse/{job_id}",
                headers=headers,
                params={"expand": "text"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_parse_response(response, "status check")
            result = response.json()
        except requests.RequestException as error:
            raise RuntimeError(
                f"Unable to retrieve LlamaParse v2 results for {path.name}."
            ) from error
        except ValueError as error:
            raise RuntimeError(
                f"LlamaParse v2 returned invalid results for {path.name}."
            ) from error

        job_result = result.get("job", {})
        status = str(job_result.get("status", "")).upper()
        if status == "COMPLETED":
            pages = result.get("text", {}).get("pages", [])
            parsed_pages = [
                (page["text"], str(page["page_number"]))
                for page in pages
                if isinstance(page, dict)
                and isinstance(page.get("text"), str)
                and page["text"].strip()
            ]
            if not parsed_pages:
                raise RuntimeError(
                    f"LlamaParse v2 completed {path.name} but returned no text."
                )
            return parsed_pages
        if status in {"FAILED", "CANCELLED"}:
            message = job_result.get("error_message") or "No error details returned."
            raise RuntimeError(f"LlamaParse v2 failed to parse {path.name}: {message}")
        if status not in {"PENDING", "RUNNING"}:
            raise RuntimeError(
                f"LlamaParse v2 returned unexpected status {status!r} for {path.name}."
            )
        time.sleep(PARSE_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"LlamaParse v2 did not finish parsing {path.name} "
        f"within {PARSE_TIMEOUT_SECONDS} seconds."
    )


def _raise_for_parse_response(response: requests.Response, operation: str) -> None:
    if response.ok:
        return
    try:
        body = response.json()
    except ValueError:
        body = response.text
    detail = body.get("detail", body.get("message", body)) if isinstance(body, dict) else body
    raise RuntimeError(
        f"LlamaParse v2 {operation} failed (HTTP {response.status_code}): {detail}"
    )


def ingest_data_dir() -> int:
    """Parse PDFs with LlamaParse v2 and upsert their text into ChromaDB."""
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LLAMA_CLOUD_API_KEY is not set. Load it from your .env file."
        )
    print("LLAMA_CLOUD_API_KEY loaded from the environment.")
    if not DATA_DIR.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {DATA_DIR}")

    base_url = (
        os.environ.get("LLAMA_CLOUD_BASE_URL", "").strip()
        or DEFAULT_LLAMA_CLOUD_BASE_URL
    )
    pdf_files = sorted(DATA_DIR.rglob("*.pdf"))
    if not pdf_files:
        raise RuntimeError(f"No PDF files found in {DATA_DIR}.")

    collection = initialize_chroma()
    total = 0
    for path in pdf_files:
        source = path.relative_to(DATA_DIR).as_posix()
        source_documents = _parse_pdf(path, api_key=api_key, base_url=base_url)
        collection.delete(where={"source": source})
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict[str, str]] = []
        for index, (text, page) in enumerate(source_documents, start=1):
            ids.append(
                hashlib.sha256(f"{source}:{index}".encode("utf-8")).hexdigest()
            )
            texts.append(text)
            metadatas.append(
                {"source": source, "filename": path.name, "page": page}
            )
        embeddings = CHROMA_EMBEDDING_FUNCTION(texts)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        total += len(texts)
        print(f"Indexed {source}: {len(texts)} document chunks.")

    print(f"Ingested {total} document chunks into ChromaDB.")
    return total


if __name__ == "__main__":
    ingest_data_dir()
