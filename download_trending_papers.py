"""Download the five current Hugging Face Daily Papers as PDFs."""

import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

DEFAULT_PAPERS_WEBSITE_URL = "https://huggingface.co/papers"
ARXIV_PDF_URL = "https://arxiv.org/pdf"
PAPER_COUNT = 5
REQUEST_TIMEOUT_SECONDS = 60
DATA_DIRECTORY = Path(__file__).resolve().parent / "data" / "papers"


def _paper_filename(title: str, paper_id: str) -> str:
    if not paper_id or ".." in paper_id or not re.fullmatch(
        r"[A-Za-z0-9._/-]+", paper_id
    ):
        raise ValueError(f"Invalid paper ID from Hugging Face: {paper_id!r}")
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip(".-_")[:100]
    safe_id = re.sub(r"[/\\]+", "_", paper_id)
    return f"{safe_title or 'paper'}-{safe_id}.pdf"


def _papers_api_url(website_url: str) -> str:
    parsed_url = urlsplit(website_url.strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError(
            "PAPERS_WEBSITE_URL must be an absolute HTTP or HTTPS papers page URL."
        )
    return f"{parsed_url.scheme}://{parsed_url.netloc}/api/daily_papers"


def _download_pdf(paper_id: str, destination: Path) -> None:
    url = f"{ARXIV_PDF_URL}/{quote(paper_id, safe='/.')}"
    temporary_path = destination.with_suffix(".pdf.part")
    try:
        with requests.get(
            url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()
            first_chunk = True
            with temporary_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    if first_chunk and not chunk.startswith(b"%PDF-"):
                        raise RuntimeError(f"arXiv returned a non-PDF for {paper_id}.")
                    first_chunk = False
                    output.write(chunk)
            if first_chunk:
                raise RuntimeError(f"arXiv returned an empty PDF for {paper_id}.")
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def download_top_five_papers(
    output_dir: Path = DATA_DIRECTORY, website_url: str | None = None
) -> list[Path]:
    """Fetch the top five daily papers and save their PDFs using website titles."""
    website_url = website_url or os.environ.get(
        "PAPERS_WEBSITE_URL", DEFAULT_PAPERS_WEBSITE_URL
    )
    api_url = _papers_api_url(website_url)
    response = requests.get(
        api_url,
        params={"limit": PAPER_COUNT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    papers = response.json()
    if not isinstance(papers, list) or len(papers) < PAPER_COUNT:
        raise RuntimeError("The papers website returned fewer than five daily papers.")

    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for item in papers[:PAPER_COUNT]:
        paper = item.get("paper") if isinstance(item, dict) else None
        paper_id = paper.get("id") if isinstance(paper, dict) else None
        title = paper.get("title") if isinstance(paper, dict) else None
        if not isinstance(paper_id, str):
            raise RuntimeError("The papers website returned a paper without a valid ID.")
        if not isinstance(title, str):
            title = ""

        destination = output_dir / _paper_filename(title, paper_id)
        _download_pdf(paper_id, destination)
        downloaded.append(destination)
        print(f"Downloaded {paper_id} to {destination}")

    return downloaded


if __name__ == "__main__":
    download_top_five_papers()
