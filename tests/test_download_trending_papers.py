import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from download_trending_papers import download_top_five_papers


class DownloadTrendingPapersTests(unittest.TestCase):
    @patch("download_trending_papers.requests.get")
    def test_downloads_five_paper_pdfs(self, get: Mock) -> None:
        api_response = Mock()
        api_response.json.return_value = [
            {
                "paper": {
                    "id": f"2611.0000{index}",
                    "title": f"Paper title {index}",
                }
            }
            for index in range(5)
        ]
        pdf_responses = []
        for _ in range(5):
            pdf_response = Mock()
            pdf_response.__enter__ = Mock(return_value=pdf_response)
            pdf_response.__exit__ = Mock(return_value=None)
            pdf_response.iter_content.return_value = [b"%PDF-1.4 test"]
            pdf_responses.append(pdf_response)
        get.side_effect = [api_response, *pdf_responses]

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            downloaded = download_top_five_papers(
                output_dir, "https://papers.example/papers"
            )

            self.assertEqual(len(downloaded), 5)
            self.assertTrue(all(path.read_bytes() == b"%PDF-1.4 test" for path in downloaded))
            self.assertEqual(downloaded[0].name, "Paper-title-0-2611.00000.pdf")
            self.assertEqual(len(list(output_dir.glob("*.pdf"))), 5)
            self.assertEqual(get.call_count, 6)
            self.assertEqual(
                get.call_args_list[0].args[0],
                "https://papers.example/api/daily_papers",
            )


if __name__ == "__main__":
    unittest.main()
