"""Scalekit token validation and authentication middleware for MCP routes."""

from dataclasses import dataclass
from functools import lru_cache
import os

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

GNEWS_PATH = "/gnews"
WEATHER_PATH = "/weather"
DOCUMENTS_PATH = "/documents"
SCOPE_ENV_VARS = {
    "GNEWS": "GNEWS_SCOPE",
    "WEATHER": "WEATHER_SCOPE",
    "CHROMA": "CHROMA_SCOPE",
}
PROTECTED_PATH_SERVERS = (
    (GNEWS_PATH, "GNEWS"),
    (WEATHER_PATH, "WEATHER"),
    (DOCUMENTS_PATH, "CHROMA"),
)


def get_llama_cloud_api_key() -> str:
    """Return the configured LlamaCloud API key."""
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LLAMA_CLOUD_API_KEY is not set. Add it to your environment or .env file."
        )
    return api_key


class ScalekitConfigurationError(RuntimeError):
    """Raised when required Scalekit settings are missing."""


def get_server_scope(server: str) -> str:
    scope_env_var = SCOPE_ENV_VARS.get(server)
    if scope_env_var is None:
        raise ScalekitConfigurationError(f"No scope is configured for server {server!r}.")

    scope = os.environ.get(scope_env_var, "").strip()
    if not scope:
        raise ScalekitConfigurationError(
            f"{scope_env_var} is not set. Add it to your .env file."
        )
    return scope


@dataclass(frozen=True)
class ScalekitResourceSettings:
    authorization_server: str
    resource_identifier: str
    audience: str
    resource_name: str
    resource_metadata_url: str
    scope: str

    @classmethod
    def from_env(cls, server: str, scope: str) -> "ScalekitResourceSettings":
        required = (
            f"SCALEKIT_{server}_AUTHORIZATION_SERVER",
            f"SCALEKIT_{server}_RESOURCE_IDENTIFIER",
            f"SCALEKIT_{server}_RESOURCE_NAME",
            f"SCALEKIT_{server}_RESOURCE_METADATA_URL",
        )
        values = {name: os.environ.get(name, "").strip() for name in required}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ScalekitConfigurationError(
                f"Missing required Scalekit settings: {', '.join(missing)}."
            )

        return cls(
            authorization_server=values[required[0]],
            resource_identifier=values[required[1]],
            audience=values[required[1]],
            resource_name=values[required[2]],
            resource_metadata_url=values[required[3]],
            scope=scope,
        )


@dataclass(frozen=True)
class ScalekitSettings:
    environment_url: str
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> "ScalekitSettings":
        required = (
            "SCALEKIT_ENVIRONMENT_URL",
            "SCALEKIT_CLIENT_ID",
            "SCALEKIT_CLIENT_SECRET",
        )
        values = {name: os.environ.get(name, "").strip() for name in required}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ScalekitConfigurationError(
                f"Missing required Scalekit settings: {', '.join(missing)}."
            )
        return cls(
            environment_url=values["SCALEKIT_ENVIRONMENT_URL"],
            client_id=values["SCALEKIT_CLIENT_ID"],
            client_secret=values["SCALEKIT_CLIENT_SECRET"],
        )


@lru_cache(maxsize=8)
def _scalekit_client(
    settings: ScalekitSettings, resource: ScalekitResourceSettings
) -> tuple[ScalekitClient, TokenValidationOptions]:
    client = ScalekitClient(
        env_url=settings.environment_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
    )
    options = TokenValidationOptions(
        issuer=resource.authorization_server,
        audience=[resource.audience],
        required_scopes=[resource.scope],
    )
    return client, options


def validate_access_token(
    token: str, settings: ScalekitSettings, resource: ScalekitResourceSettings
) -> bool:
    """Validate a bearer token against the configured issuer, audience, and scope."""
    client, options = _scalekit_client(settings, resource)
    return client.validate_access_token(token, options=options)


class ScalekitAuthMiddleware(BaseHTTPMiddleware):
    """Require Scalekit bearer tokens for requests to the MCP servers."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        protected_server = next(
            (
                server
                for prefix, server in PROTECTED_PATH_SERVERS
                if path == prefix or path.startswith(f"{prefix}/")
            ),
            None,
        )
        if request.method == "OPTIONS" or protected_server is None:
            return await call_next(request)

        try:
            required_scope = get_server_scope(protected_server)
            resource = ScalekitResourceSettings.from_env(
                protected_server, required_scope
            )
            settings = ScalekitSettings.from_env()
        except ScalekitConfigurationError as error:
            return JSONResponse(
                status_code=503,
                content={"detail": str(error)},
            )

        auth_scheme, separator, token = request.headers.get(
            "Authorization", ""
        ).partition(" ")
        if (
            not separator
            or auth_scheme.lower() != "bearer"
            or not token.strip()
            or not await run_in_threadpool(
                validate_access_token, token.strip(), settings, resource
            )
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "A valid Scalekit access token is required."},
                headers={
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="'
                        f'{resource.resource_metadata_url}"'
                    )
                },
            )

        return await call_next(request)
