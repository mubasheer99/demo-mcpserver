from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from mcp_chroma import (
    download_trending_papers,
    get_db_status,
    ingest_documents,
    search_documents,
)


class ChromaSearchTests(unittest.TestCase):
    @patch("mcp_chroma.initialize_chroma")
    def test_returns_matching_text_and_source_metadata(
        self, initialize_chroma: Mock
    ) -> None:
        collection = initialize_chroma.return_value
        collection.count.return_value = 2
        collection.query.return_value = {
            "documents": [["A relevant passage"]],
            "metadatas": [[{"source": "papers/example.pdf", "page": "4"}]],
            "distances": [[0.12]],
        }

        result = search_documents("  vector search  ", n_results=5)

        self.assertEqual(
            result,
            [
                {
                    "text": "A relevant passage",
                    "source": "papers/example.pdf",
                    "page": "4",
                    "distance": 0.12,
                }
            ],
        )
        collection.query.assert_called_once_with(
            query_texts=["vector search"],
            n_results=2,
            include=["documents", "metadatas", "distances"],
        )

    def test_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            search_documents(" ")

    def test_rejects_result_count_outside_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 10"):
            search_documents("query", n_results=11)

    @patch("mcp_chroma.initialize_chroma")
    def test_empty_collection_explains_how_to_ingest(
        self, initialize_chroma: Mock
    ) -> None:
        initialize_chroma.return_value.count.return_value = 0

        with self.assertRaisesRegex(RuntimeError, "Run ingest_documents.py first"):
            search_documents("query")


class ChromaIngestionToolTests(unittest.TestCase):
    @patch("mcp_chroma.ingest_data_dir", return_value=7)
    def test_ingest_tool_reports_indexed_chunk_count(
        self, ingest_data_dir: Mock
    ) -> None:
        result = ingest_documents()

        ingest_data_dir.assert_called_once_with()
        self.assertEqual(
            result,
            {
                "indexed_chunks": 7,
                "message": "Indexed 7 document chunks in ChromaDB.",
            },
        )

    @patch(
        "mcp_chroma.ingest_data_dir",
        side_effect=RuntimeError("LlamaParse failed"),
    )
    def test_ingest_tool_surfaces_parse_errors(self, _ingest_data_dir: Mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "LlamaParse failed"):
            ingest_documents()


class ChromaStatusToolTests(unittest.TestCase):
    @patch("mcp_chroma.initialize_chroma")
    def test_status_tool_reports_collection_size(
        self, initialize_chroma: Mock
    ) -> None:
        initialize_chroma.return_value.count.return_value = 3

        result = get_db_status()

        initialize_chroma.assert_called_once_with()
        self.assertEqual(
            result,
            {
                "collection_size": 3,
                "message": "ChromaDB collection contains 3 indexed document chunks.",
            },
        )


class TrendingPapersToolTests(unittest.TestCase):
    @patch(
        "mcp_chroma.download_top_five_papers",
        return_value=[
            Path("data/papers/one.pdf"),
            Path("data/papers/two.pdf"),
        ],
    )
    def test_download_tool_returns_saved_files(
        self, download_top_five_papers: Mock
    ) -> None:
        result = download_trending_papers()

        download_top_five_papers.assert_called_once_with()
        self.assertEqual(result["downloaded_count"], 2)
        self.assertEqual(
            result["files"],
            [str(Path("data/papers/one.pdf")), str(Path("data/papers/two.pdf"))],
        )

    @patch(
        "mcp_chroma.download_top_five_papers",
        side_effect=RuntimeError("paper site unavailable"),
    )
    def test_download_tool_surfaces_errors(
        self, _download_top_five_papers: Mock
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "paper site unavailable"):
            download_trending_papers()


if __name__ == "__main__":
    unittest.main()
