import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

TEST_GNEWS_SCOPE = "test:gnews:read"
TEST_WEATHER_SCOPE = "test:weather:read"
TEST_CHROMA_SCOPE = "test:chroma:access"

RESOURCE_ENV = {
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


class ScalekitResourceMetadataTests(unittest.TestCase):
    @patch.dict(os.environ, RESOURCE_ENV, clear=True)
    def test_metadata_is_specific_to_each_registered_server(self) -> None:
        client = TestClient(app)
        resources = (
            ("gnews", "https://example.com/gnews/mcp", TEST_GNEWS_SCOPE),
            ("weather", "https://example.com/weather/mcp", TEST_WEATHER_SCOPE),
            ("chroma", "https://example.com/documents/mcp", TEST_CHROMA_SCOPE),
        )

        for server, resource, scope in resources:
            with self.subTest(server=server):
                response = client.get(
                    f"/.well-known/oauth-protected-resource/{server}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json(),
                    {
                        "authorization_servers": [
                            f"https://test.scalekit.com/resources/{server}"
                        ],
                        "bearer_methods_supported": ["header"],
                        "resource": resource,
                        "scopes_supported": [scope],
                    },
                )


if __name__ == "__main__":
    unittest.main()
