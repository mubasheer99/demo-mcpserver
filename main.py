import asyncio
import contextlib
import os
import sys

import ngrok
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    ScalekitAuthMiddleware,
    ScalekitConfigurationError,
    ScalekitResourceSettings,
    get_server_scope,
)
from chroma_store import initialize_chroma
from mcp_chroma import mcp as chroma_mcp_server
from gnews_server import mcp as gnews_mcp_server
from mcp_weather import mcp as weather_mcp_server

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 10000


def connect_ngrok() -> ngrok.Listener:
    options: dict[str, object] = {"authtoken_from_env": True}
    domain = os.environ.get("NGROK_DOMAIN", "").strip()
    if domain:
        options["domain"] = domain

    forwarder = ngrok.forward(f"{SERVER_HOST}:{SERVER_PORT}", **options)
    print(f"Available at: {forwarder.url()}")
    return forwarder


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_chroma()
    forwarder = await asyncio.to_thread(connect_ngrok)
    try:
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(gnews_mcp_server.session_manager.run())
            await stack.enter_async_context(weather_mcp_server.session_manager.run())
            await stack.enter_async_context(chroma_mcp_server.session_manager.run())
            yield
    finally:
        await forwarder.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(ScalekitAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RESOURCE_METADATA_SERVERS = {
    "gnews": "GNEWS",
    "weather": "WEATHER",
    "chroma": "CHROMA",
    "mcp": "GNEWS",
}


@app.get("/.well-known/oauth-protected-resource/{resource}")
async def oauth_protected_resource_metadata(resource: str) -> dict[str, object]:
    """Return OAuth metadata for the selected MCP resource."""
    server = RESOURCE_METADATA_SERVERS.get(resource)
    if server is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown MCP resource.",
        )

    try:
        scope = get_server_scope(server)
        resource_settings = ScalekitResourceSettings.from_env(server, scope)
    except ScalekitConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "authorization_servers": [resource_settings.authorization_server],
        "bearer_methods_supported": ["header"],
        "resource": resource_settings.resource_name,
        "scopes_supported": [resource_settings.scope],
    }


app.mount("/gnews", gnews_mcp_server.streamable_http_app())


app.mount("/weather", weather_mcp_server.streamable_http_app())

app.mount("/documents", chroma_mcp_server.streamable_http_app())

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="debug")
