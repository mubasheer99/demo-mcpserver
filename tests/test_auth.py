import os
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import (
    ScalekitAuthMiddleware,
    get_llama_cloud_api_key,
)

TEST_GNEWS_SCOPE = "test:gnews:read"
TEST_WEATHER_SCOPE = "test:weather:read"
TEST_CHROMA_SCOPE = "test:chroma:access"

SCALEKIT_TEST_ENV = {
    "SCALEKIT_ENVIRONMENT_URL": "https://test.scalekit.com",
    "SCALEKIT_CLIENT_ID": "test-client",
    "SCALEKIT_CLIENT_SECRET": "test-secret",
    "GNEWS_SCOPE": TEST_GNEWS_SCOPE,
    "WEATHER_SCOPE": TEST_WEATHER_SCOPE,
    "CHROMA_SCOPE": TEST_CHROMA_SCOPE,
    "SCALEKIT_GNEWS_AUTHORIZATION_SERVER": "https://test.scalekit.com/resources/gnews",
    "SCALEKIT_GNEWS_RESOURCE_IDENTIFIER": "gnews-resource",
    "SCALEKIT_GNEWS_RESOURCE_NAME": "https://example.com/gnews/mcp",
    "SCALEKIT_GNEWS_RESOURCE_METADATA_URL": "https://example.com/.well-known/oauth-protected-resource/gnews",
    "SCALEKIT_WEATHER_AUTHORIZATION_SERVER": "https://test.scalekit.com/resources/weather",
    "SCALEKIT_WEATHER_RESOURCE_IDENTIFIER": "weather-resource",
    "SCALEKIT_WEATHER_RESOURCE_NAME": "https://example.com/weather/mcp",
    "SCALEKIT_WEATHER_RESOURCE_METADATA_URL": "https://example.com/.well-known/oauth-protected-resource/weather",
    "SCALEKIT_CHROMA_AUTHORIZATION_SERVER": "https://test.scalekit.com/resources/chroma",
    "SCALEKIT_CHROMA_RESOURCE_IDENTIFIER": "chroma-resource",
    "SCALEKIT_CHROMA_RESOURCE_NAME": "https://example.com/documents/mcp",
    "SCALEKIT_CHROMA_RESOURCE_METADATA_URL": "https://example.com/.well-known/oauth-protected-resource/chroma",
}


class LlamaCloudAuthTests(unittest.TestCase):
    def test_reads_and_trims_api_key(self) -> None:
        with patch.dict(os.environ, {"LLAMA_CLOUD_API_KEY": "  test-key  "}):
            self.assertEqual(get_llama_cloud_api_key(), "test-key")

    def test_missing_api_key_is_reported(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LLAMA_CLOUD_API_KEY is not set"):
                get_llama_cloud_api_key()


class ScalekitAuthMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.add_middleware(ScalekitAuthMiddleware)
        for path in ("/gnews/mcp", "/weather/mcp", "/documents/mcp", "/health"):
            self.app.add_api_route(path, lambda: {"ok": True})
        self.client = TestClient(self.app)

    @patch.dict(
        os.environ,
        SCALEKIT_TEST_ENV,
        clear=True,
    )
    @patch("auth.validate_access_token", return_value=True)
    def test_scalekit_token_is_required_for_each_mcp_server(
        self, validate_access_token: Mock
    ) -> None:
        expected_scopes = (
            ("/gnews/mcp", TEST_GNEWS_SCOPE),
            ("/weather/mcp", TEST_WEATHER_SCOPE),
            ("/documents/mcp", TEST_CHROMA_SCOPE),
        )
        for path, scope in expected_scopes:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Authorization": "Bearer token"})
                self.assertEqual(response.status_code, 200)

        self.assertEqual(validate_access_token.call_count, 3)
        self.assertEqual(
            [call.args[2].scope for call in validate_access_token.call_args_list],
            [TEST_GNEWS_SCOPE, TEST_WEATHER_SCOPE, TEST_CHROMA_SCOPE],
        )
        self.assertEqual(
            [call.args[2].audience for call in validate_access_token.call_args_list],
            ["gnews-resource", "weather-resource", "chroma-resource"],
        )
        self.assertEqual(
            [
                call.args[2].authorization_server
                for call in validate_access_token.call_args_list
            ],
            [
                "https://test.scalekit.com/resources/gnews",
                "https://test.scalekit.com/resources/weather",
                "https://test.scalekit.com/resources/chroma",
            ],
        )

    @patch.dict(
        os.environ,
        SCALEKIT_TEST_ENV,
        clear=True,
    )
    def test_missing_token_is_rejected_for_weather_and_documents(self) -> None:
        requests = (
            (
                "/weather/mcp",
                "https://example.com/.well-known/oauth-protected-resource/weather",
            ),
            (
                "/documents/mcp",
                "https://example.com/.well-known/oauth-protected-resource/chroma",
            ),
        )
        for path, metadata_path in requests:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertIn(metadata_path, response.headers["WWW-Authenticate"])

    @patch.dict(
        os.environ,
        {
            **SCALEKIT_TEST_ENV,
            "SCALEKIT_WEATHER_RESOURCE_IDENTIFIER": "",
        },
        clear=True,
    )
    def test_missing_server_resource_id_returns_configuration_error(self) -> None:
        response = self.client.get(
            "/weather/mcp", headers={"Authorization": "Bearer token"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("SCALEKIT_WEATHER_RESOURCE_IDENTIFIER", response.json()["detail"])

    @patch.dict(
        os.environ,
        {**SCALEKIT_TEST_ENV, "GNEWS_SCOPE": ""},
        clear=True,
    )
    def test_missing_scope_returns_configuration_error(self) -> None:
        scope_requests = (
            ("GNEWS_SCOPE", "/gnews/mcp"),
            ("WEATHER_SCOPE", "/weather/mcp"),
            ("CHROMA_SCOPE", "/documents/mcp"),
        )
        for scope_variable, path in scope_requests:
            with self.subTest(scope_variable=scope_variable):
                environment = {**SCALEKIT_TEST_ENV, scope_variable: ""}
                with patch.dict(os.environ, environment, clear=True):
                    response = self.client.get(
                        path, headers={"Authorization": "Bearer token"}
                    )
                self.assertEqual(response.status_code, 503)
                self.assertIn(scope_variable, response.json()["detail"])

    def test_non_mcp_routes_are_not_affected(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
