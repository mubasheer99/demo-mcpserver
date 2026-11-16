import os
import unittest
from unittest.mock import Mock, patch

import requests

import mcp_server


class GNewsToolTests(unittest.TestCase):
    @patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"})
    @patch("mcp_server.requests.get")
    def test_search_maps_mcp_arguments_to_gnews_parameters(
        self, get: Mock
    ) -> None:
        response = Mock()
        response.json.return_value = {"articles": []}
        get.return_value = response

        result = mcp_server.search(
            "  climate change ",
            lang="EN",
            country="US",
            max=5,
            in_fields="title, content",
            sortby="relevance",
            date_from="2026-01-01",
            date_to="2026-01-31",
            page=2,
        )

        self.assertEqual(result, {"articles": []})
        get.assert_called_once_with(
            "https://gnews.io/api/v4/search",
            params={
                "q": "climate change",
                "max": 5,
                "in": "title,content",
                "sortby": "relevance",
                "page": 2,
                "lang": "en",
                "country": "us",
                "from": "2026-01-01",
                "to": "2026-01-31",
                "apikey": "test-key",
            },
            timeout=mcp_server.REQUEST_TIMEOUT_SECONDS,
        )

    @patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"})
    @patch("mcp_server.requests.get")
    def test_top_headlines_maps_arguments(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"articles": []}
        get.return_value = response

        mcp_server.top_headlines(category="technology", max=20, q="AI")

        self.assertEqual(
            get.call_args.kwargs["params"],
            {
                "category": "technology",
                "max": 20,
                "page": 1,
                "q": "AI",
                "apikey": "test-key",
            },
        )

    def test_missing_api_key_is_reported(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GNEWS_API_KEY is not set"):
                mcp_server.search("news")

    def test_invalid_search_parameters_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 200"):
            mcp_server.search("x" * 201)
        with self.assertRaisesRegex(ValueError, "in_fields"):
            mcp_server.search("news", in_fields="author")
        with self.assertRaisesRegex(ValueError, "max must be"):
            mcp_server.search("news", max=101)
        with self.assertRaisesRegex(ValueError, "2-letter code"):
            mcp_server.search("news", lang="éa")
        with self.assertRaisesRegex(ValueError, "q must not be empty"):
            mcp_server.top_headlines(q=" ")

    @patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"})
    @patch("mcp_server.requests.get")
    def test_http_errors_do_not_expose_the_api_key(self, get: Mock) -> None:
        response = Mock()
        response.status_code = 401
        get.return_value = response
        get.return_value.raise_for_status.side_effect = requests.HTTPError(
            "request failed"
        )

        with self.assertRaisesRegex(RuntimeError, "HTTP 401") as context:
            mcp_server.search("news")
        self.assertNotIn("test-key", str(context.exception))


if __name__ == "__main__":
    unittest.main()
