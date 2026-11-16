<div align="center">

# 🧭 MCP Tool Servers

### News, weather, and document search — one small MCP service.

Connect AI clients to live GNews headlines, Open-Meteo forecasts, and a
searchable Chroma document collection. Run the tools over stdio or host them
behind authenticated Streamable HTTP endpoints.

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Model Context Protocol](https://img.shields.io/badge/Protocol-MCP-7858Ff?style=for-the-badge)
![Package manager: uv](https://img.shields.io/badge/Packages-uv-DE5FE9?style=for-the-badge)
![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=for-the-badge&logo=render&logoColor=111111)

</div>

---

## ✨ What's inside

<table>
<tr>
<td width="33%" valign="top">

### 🔵 GNews
Search articles and retrieve top headlines by topic, country, language, and
date.

**Tools:** `search` · `top_headlines`

</td>
<td width="33%" valign="top">

### 🟢 Weather
Look up current conditions and multi-day forecasts by city.

**Tools:** `get_current_weather` · `get_weather_forecast`

</td>
<td width="33%" valign="top">

### 🟣 Documents
Download trending research papers, index PDF text, and search relevant passages.

**Tools:** `download_trending_papers` · `ingest_documents` · `query_documents` · `get_db_status`

</td>
</tr>
</table>

## 🚀 Quick start

**Requirements:** Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
Copy-Item .env.example .env
```

Add the API keys and settings for the tools you plan to use to `.env`. See
[Configuration](#-configuration) for details.

### Run an individual server

These servers use stdio and are intended to be launched by an MCP client:

```powershell
uv run --env-file .env python gnews_server.py
uv run --env-file .env python mcp_weather.py
uv run --env-file .env python mcp_chroma.py
```

The workspace MCP client configuration is in [`.vscode/mcp.json`](./.vscode/mcp.json).

### Run the combined HTTP service

```powershell
uv run --env-file .env python main.py
```

The service listens at `http://localhost:10000` by default. It honors the
`PORT` environment variable, so on Render set the start command to:

```text
python main.py
```

## 🧩 MCP endpoints

| Server | Local endpoint | Required scope |
|:--|:--|:--|
| 🔵 GNews | `http://localhost:10000/gnews/mcp` | `GNEWS_SCOPE` |
| 🟢 Weather | `http://localhost:10000/weather/mcp` | `WEATHER_SCOPE` |
| 🟣 Documents | `http://localhost:10000/documents/mcp` | `CHROMA_SCOPE` |

On Render, replace the local base URL with your service’s HTTPS URL. Use the
full route when connecting an MCP client; the base URL alone is not an MCP
endpoint.

Protected-resource metadata is available at:

- `/.well-known/oauth-protected-resource/gnews`
- `/.well-known/oauth-protected-resource/weather`
- `/.well-known/oauth-protected-resource/chroma`

## 🎨 Configuration

Start with [`.env.example`](./.env.example). Set only the values needed for your
use case:

| Setting | Used for |
|:--|:--|
| `GNEWS_API_KEY` | GNews search and headlines |
| `LLAMA_CLOUD_API_KEY` | Parsing PDFs for document ingestion |
| `SCALEKIT_ENVIRONMENT_URL`, `SCALEKIT_CLIENT_ID`, `SCALEKIT_CLIENT_SECRET` | Validating bearer tokens for hosted HTTP endpoints |
| `SCALEKIT_<SERVER>_*` | Authorization server, resource identifier, resource name, and metadata URL for each protected resource |
| `GNEWS_SCOPE`, `WEATHER_SCOPE`, `CHROMA_SCOPE` | Required scopes for the corresponding MCP endpoints |
| `PORT` | Listening port; Render provides this automatically (local default: `10000`) |
| `PAPERS_WEBSITE_URL` | Optional papers page; defaults to `https://huggingface.co/papers` |
| `LLAMA_CLOUD_BASE_URL` | Optional; set to `https://api.cloud.eu.llamaindex.ai` for EU LlamaCloud accounts |

Open-Meteo needs no API key. The HTTP endpoints require Scalekit bearer tokens;
OAuth metadata endpoints are public. For hosted use, set each
`SCALEKIT_<SERVER>_RESOURCE_NAME` and
`SCALEKIT_<SERVER>_RESOURCE_METADATA_URL` to URLs on your public HTTPS service,
not `localhost`. The resource identifier is also used as the token audience.

LlamaCloud API keys are region-specific. For North America, leave
`LLAMA_CLOUD_BASE_URL` unset and use a North American key.

## 📚 Document workflow

ChromaDB uses a persistent `documents` collection in `chroma_db/`, initialized
automatically. Downloaded PDFs and the database are local data and excluded
from Git.

`PAPERS_WEBSITE_URL` defaults to `https://huggingface.co/papers`. The configured
page must provide a compatible `/api/daily_papers` endpoint with arXiv paper
IDs.

1. Download the top five papers from the configured papers page:

   ```powershell
   uv run --env-file .env python download_trending_papers.py
   ```

2. Parse PDFs under `data/` with LlamaParse and index their page text:

   ```powershell
   uv run --env-file .env python ingest_documents.py
   ```

You can also call `download_trending_papers` and `ingest_documents` through the
Chroma MCP server. Ingestion requires PDFs under `data/` and a valid
`LLAMA_CLOUD_API_KEY`.

## 🛠️ Tool details

<details>
<summary><strong>🔵 GNews</strong></summary>

- `search` — search articles with optional language, country, date range,
  searchable fields, sort order, result count (1–100), and page.
- `top_headlines` — retrieve category headlines with optional language,
  country, keyword, date range, result count (1–100), and page.
- Both tools require `GNEWS_API_KEY`.

</details>

<details>
<summary><strong>🟢 Open-Meteo weather</strong></summary>

- `get_current_weather(city, units="metric", country=None)`
- `get_weather_forecast(city, days=3, units="metric", country=None)`
- Forecasts support 1–5 days. Units are `metric`, `imperial`, or `standard`
  (Kelvin for temperature).
- No API key is required. The free Open-Meteo API is intended for
  non-commercial use; review its terms before commercial deployment.

</details>

<details>
<summary><strong>🟣 Chroma documents</strong></summary>

- `query_documents(query, n_results=5)` — find relevant passages (1–10 results),
  including text, source, page, and vector-search distance.
- `ingest_documents()` — parse PDFs under `data/` and index extracted page text.
- `download_trending_papers()` — save the current top five papers under
  `data/papers/`.
- `get_db_status()` — report the number of indexed document chunks.

</details>

## 🔗 References

- [GNews API](https://gnews.io/)
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs)
- [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- [Open-Meteo pricing and usage terms](https://open-meteo.com/en/pricing)
