"""MCP server for GNews article search and top headlines."""

import os
from typing import Literal

import requests
from mcp.server.fastmcp import FastMCP

API_BASE_URL = "https://gnews.io/api/v4"
REQUEST_TIMEOUT_SECONDS = 30
MAX_QUERY_LENGTH = 200

Category = Literal[
    "general",
    "world",
    "nation",
    "business",
    "technology",
    "entertainment",
    "sports",
    "science",
    "health",
]
SortOrder = Literal["publishedAt", "relevance"]

mcp = FastMCP("gnews-news-server")

def _require_api_key() -> str:
    api_key = os.environ.get("GNEWS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GNEWS_API_KEY is not set. Add it to your environment or .env file.")
    return api_key


def _validate_limit(value: int) -> None:
    if not 1 <= value <= 100:
        raise ValueError("max must be between 1 and 100.")


def _validate_page(value: int) -> None:
    if value < 1:
        raise ValueError("page must be at least 1.")


def _validate_optional_code(value: str | None, name: str) -> None:
    if value is None:
        return
    if len(value) != 2 or not value.isascii() or not value.isalpha():
        raise ValueError(f"{name} must be a 2-letter code.")


def _validate_query(query: str, field_name: str = "q") -> str:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty.")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise ValueError(f"{field_name} must be at most {MAX_QUERY_LENGTH} characters.")
    return cleaned


def _request_articles(endpoint: str, params: dict[str, str | int]) -> dict:
    response = None
    try:
        response = requests.get(
            f"{API_BASE_URL}/{endpoint}",
            params={**params, "apikey": _require_api_key()},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        raise RuntimeError(
            f"GNews API returned HTTP {status}. Check your API key and request parameters."
        ) from None
    except requests.RequestException as error:
        raise RuntimeError(f"Unable to reach GNews API ({type(error).__name__}).") from None
    except ValueError as error:
        raise RuntimeError("GNews API returned invalid JSON.") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise RuntimeError("GNews API returned an unexpected response.")

    return payload


def _build_search_params(
    q: str,
    lang: str | None,
    country: str | None,
    max_results: int,
    in_fields: str,
    sortby: SortOrder,
    date_from: str | None,
    date_to: str | None,
    page: int,
) -> dict[str, str | int]:
    # GNews accepts a comma-separated list of searchable article fields.
    fields = [field.strip() for field in in_fields.split(",")]
    allowed_fields = {"title", "description", "content"}

    if not fields or any(field not in allowed_fields for field in fields):
        raise ValueError("in_fields may contain only title, description, and/or content.")
    if sortby not in ("publishedAt", "relevance"):
        raise ValueError("sortby must be publishedAt or relevance.")

    params: dict[str, str | int] = {
        "q": q,
        "max": max_results,
        "in": ",".join(fields),
        "sortby": sortby,
        "page": page,
    }

    if lang is not None:
        params["lang"] = lang.lower()
    if country is not None:
        params["country"] = country.lower()
    if date_from is not None:
        params["from"] = date_from
    if date_to is not None:
        params["to"] = date_to

    return params


@mcp.tool()
def search(
    q: str,
    lang: str | None = None,
    country: str | None = None,
    max: int = 10,
    in_fields: str = "title,description",
    sortby: SortOrder = "publishedAt",
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> dict:
    """Search GNews articles by query, language, country, date, and relevance."""
    query = _validate_query(q)
    _validate_limit(max)
    _validate_page(page)
    _validate_optional_code(lang, "lang")
    _validate_optional_code(country, "country")

    params = _build_search_params(
        q=query,
        lang=lang,
        country=country,
        max_results=max,
        in_fields=in_fields,
        sortby=sortby,
        date_from=date_from,
        date_to=date_to,
        page=page,
    )
    return _request_articles("search", params)


@mcp.tool()
def top_headlines(
    category: Category = "general",
    lang: str | None = None,
    country: str | None = None,
    max: int = 10,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> dict:
    """Get the latest GNews headlines, optionally filtered by category or keyword."""
    _validate_limit(max)
    _validate_page(page)
    _validate_optional_code(lang, "lang")
    _validate_optional_code(country, "country")

    clean_query = _validate_query(q, "q") if q is not None else None

    params: dict[str, str | int] = {
        "category": category,
        "max": max,
        "page": page,
    }

    if lang is not None:
        params["lang"] = lang.lower()
    if country is not None:
        params["country"] = country.lower()
    if clean_query is not None:
        params["q"] = clean_query
    if date_from is not None:
        params["from"] = date_from
    if date_to is not None:
        params["to"] = date_to

    return _request_articles("top-headlines", params)



