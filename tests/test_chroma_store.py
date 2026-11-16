import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from chroma_store import (
    CHROMA_COLLECTION_NAME,
    CHROMA_EMBEDDING_FUNCTION,
    initialize_chroma,
)


class ChromaStoreTests(unittest.TestCase):
    @patch("chroma_store.chromadb.PersistentClient")
    def test_initializes_persistent_documents_collection(
        self, persistent_client: Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "chroma_db"
            collection = Mock()
            client = persistent_client.return_value
            client.get_or_create_collection.return_value = collection

            result = initialize_chroma(path)

            persistent_client.assert_called_once_with(path=str(path))
            client.get_or_create_collection.assert_called_once_with(
                name=CHROMA_COLLECTION_NAME,
                embedding_function=CHROMA_EMBEDDING_FUNCTION,
            )
            self.assertIs(result, collection)


if __name__ == "__main__":
    unittest.main()
