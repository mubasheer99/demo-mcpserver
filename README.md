# Local MCP Servers

The combined HTTP service exposes three MCP servers:

- **GNews** (`gnews_server.py`) — search news articles and retrieve top headlines.
- **Open-Meteo** (`mcp_weather.py`) — look up current weather and forecasts by city.
- **Chroma documents** (`mcp_chroma.py`) — download trending papers, index local PDFs, and search indexed passages.

The servers can run individually over stdio or together as authenticated Streamable
HTTP endpoints using `main.py`.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

Install the project dependencies:

```powershell
uv sync
```

## Configuration

Copy `.env.example` to `.env` and set the values required for the features you
use. Never commit a populated `.env` file.

```env
GNEWS_API_KEY=your-gnews-api-key
LLAMA_CLOUD_API_KEY=your-llama-cloud-api-key
# Optional: set this only for an EU LlamaCloud account; leave unset for North America.
# LLAMA_CLOUD_BASE_URL=https://api.cloud.eu.llamaindex.ai
PAPERS_WEBSITE_URL=https://huggingface.co/papers
SCALEKIT_ENVIRONMENT_URL=https://your-environment.scalekit.com
SCALEKIT_CLIENT_ID=your-scalekit-client-id
SCALEKIT_CLIENT_SECRET=your-scalekit-client-secret
SCALEKIT_GNEWS_AUTHORIZATION_SERVER=https://your-environment.scalekit.com/resources/your-gnews-resource-id
SCALEKIT_GNEWS_RESOURCE_IDENTIFIER=your-gnews-resource-id
GNEWS_SCOPE=mcp:tools:search:read
WEATHER_SCOPE=mcp:tools:weather:read
CHROMA_SCOPE=mcp:tools:chroma:access
SCALEKIT_GNEWS_RESOURCE_NAME=https://your-service.onrender.com/gnews/mcp
SCALEKIT_GNEWS_RESOURCE_METADATA_URL=https://your-service.onrender.com/.well-known/oauth-protected-resource/gnews
SCALEKIT_WEATHER_AUTHORIZATION_SERVER=https://your-environment.scalekit.com/resources/your-weather-resource-id
SCALEKIT_WEATHER_RESOURCE_IDENTIFIER=your-weather-resource-id
SCALEKIT_WEATHER_RESOURCE_NAME=https://your-service.onrender.com/weather/mcp
SCALEKIT_WEATHER_RESOURCE_METADATA_URL=https://your-service.onrender.com/.well-known/oauth-protected-resource/weather
SCALEKIT_CHROMA_AUTHORIZATION_SERVER=https://your-environment.scalekit.com/resources/your-chroma-resource-id
SCALEKIT_CHROMA_RESOURCE_IDENTIFIER=your-chroma-resource-id
SCALEKIT_CHROMA_RESOURCE_NAME=https://your-service.onrender.com/documents/mcp
SCALEKIT_CHROMA_RESOURCE_METADATA_URL=https://your-service.onrender.com/.well-known/oauth-protected-resource/chroma
```

`GNEWS_API_KEY` is required for GNews. Open-Meteo requires no API key.
`LLAMA_CLOUD_API_KEY` is required to parse and index PDFs. The server listens
on the `PORT` environment variable when provided (defaulting to port 10000).
On Render, use its public service URL in the Scalekit resource configuration.

The HTTP endpoints require Scalekit bearer tokens. Register a protected resource
for each server with the corresponding scope: GNews uses `GNEWS_SCOPE`, weather
uses `WEATHER_SCOPE`, and Chroma uses `CHROMA_SCOPE`. Set each resource's
authorization server, resource identifier, resource name, and metadata URL in
the matching `SCALEKIT_<SERVER>_*` variables above. The resource identifier is
also used as the token audience. Replace `your-service.onrender.com` with the
public HTTPS hostname of your Render service; these resource URLs must not use
`localhost`. OAuth metadata endpoints are public; the MCP endpoints themselves
are protected.

LlamaCloud API keys are region-specific. For an EU account, set
`LLAMA_CLOUD_BASE_URL=https://api.cloud.eu.llamaindex.ai`; for North America,
leave it unset. Use an API key created in the matching region.

## Servers and tools

### GNews

`gnews_server.py` exposes:

- `search` — search articles by query, with optional language, country, date
  range, searchable fields, sort order, result count (1–100), and page.
- `top_headlines` — retrieve headlines by category, with optional language,
  country, keyword, date range, result count (1–100), and page.

Both tools require `GNEWS_API_KEY`.

### Open-Meteo weather

`mcp_weather.py` exposes:

- `get_current_weather(city, units="metric", country=None)`
- `get_weather_forecast(city, days=3, units="metric", country=None)`

City names are resolved through the Open-Meteo Geocoding API. Forecasts support
1–5 days. Units can be `metric`, `imperial`, or `standard` (Kelvin for
temperature). No API key is required. The free Open-Meteo API is intended for
non-commercial use; review its terms before commercial deployment.

### Chroma document search

`mcp_chroma.py` exposes:

- `query_documents(query, n_results=5)` — find relevant passages in indexed
  documents (1–10 results), returning the text, source, page, and vector-search
  distance.
- `ingest_documents()` — parse PDFs under `data/` with LlamaParse and index
  their extracted page text in ChromaDB.
- `download_trending_papers()` — download the current top five papers as PDFs
  into `data/papers/`.
- `get_db_status()` — report the number of indexed document chunks.

ChromaDB uses a local persistent `documents` collection in `chroma_db/`, which
is initialized automatically. Downloaded PDFs and the database are local data
and are excluded from Git.

## Download and index papers

`PAPERS_WEBSITE_URL` defaults to `https://huggingface.co/papers`. The configured
page must provide a compatible `/api/daily_papers` endpoint with arXiv paper
IDs. Download the top five PDFs with:

```powershell
uv run --env-file .env python download_trending_papers.py
```

PDFs are saved under `data/papers/`. To parse PDFs anywhere under `data/` and
index their page text and embeddings in ChromaDB, run:

```powershell
uv run --env-file .env python ingest_documents.py
```

Alternatively, call `download_trending_papers` and `ingest_documents` through
the Chroma MCP server. An empty `data/` directory or missing LlamaCloud API key
will produce an error when ingestion is attempted.

## Run the servers

Run an individual server over stdio:

```powershell
uv run --env-file .env python gnews_server.py
uv run --env-file .env python mcp_weather.py
uv run --env-file .env python mcp_chroma.py
```

These stdio servers are intended to be launched by an MCP client. The workspace
client configuration is in `.vscode/mcp.json`.

To serve all three through Streamable HTTP, start:

```powershell
uv run --env-file .env python main.py
```

The combined server listens at `http://localhost:10000` by default. On Render,
use `python main.py` as the start command; the service listens on Render's
assigned `PORT`. Its MCP routes are:

| Server | Local endpoint | Required scope |
| --- | --- | --- |
| GNews | `http://localhost:10000/gnews/mcp` | `GNEWS_SCOPE` |
| Weather | `http://localhost:10000/weather/mcp` | `WEATHER_SCOPE` |
| Chroma documents | `http://localhost:10000/documents/mcp` | `CHROMA_SCOPE` |

Use the full route on Render (for example,
`https://your-service.onrender.com/weather/mcp`); the service base URL alone is
not an MCP endpoint. Protected-resource metadata is available at
`/.well-known/oauth-protected-resource/gnews`,
`/.well-known/oauth-protected-resource/weather`, and
`/.well-known/oauth-protected-resource/chroma`.

## References

- GNews API: https://gnews.io/
- Open-Meteo Forecast API: https://open-meteo.com/en/docs
- Open-Meteo Geocoding API: https://open-meteo.com/en/docs/geocoding-api
- Open-Meteo pricing and usage terms: https://open-meteo.com/en/pricing
