#!/usr/bin/env python3
import os
import tempfile
import logging
from datetime import datetime, timedelta, timezone

from src.indexer import MailIndexer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_index(db_path: str):
    indexer = MailIndexer(db_path)
    now = datetime.now(timezone.utc)
    messages = [
        {
            "id": "m1",
            "from": {"emailAddress": {"address": "alice@example.com"}},
            "subject": "Project Alpha update",
            "bodyPreview": "Status update about Alpha milestones and timelines.",
            "receivedDateTime": (now - timedelta(days=1)).isoformat() + "Z",
        },
        {
            "id": "m2",
            "from": {"emailAddress": {"address": "bob@example.com"}},
            "subject": "Re: Lunch plans",
            "bodyPreview": "Let’s meet for lunch tomorrow at noon.",
            "receivedDateTime": (now - timedelta(days=2)).isoformat() + "Z",
        },
        {
            "id": "m3",
            "from": {"emailAddress": {"address": "alice@example.com"}},
            "subject": "Alpha roadmap and pricing",
            "bodyPreview": "Discussing pricing details and roadmap items for Alpha.",
            "receivedDateTime": (now - timedelta(hours=3)).isoformat() + "Z",
        },
    ]
    indexer.upsert_messages(messages)


def test_retrieval_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_mail_index.sqlite")
        seed_index(db_path)

        # Ensure INDEX_PATH is set before reloading dependent modules
        os.environ["INDEX_PATH"] = db_path

        import importlib
        import src.config as config_mod
        import src.indexer as indexer_mod
        import src.retrieval as retrieval_mod

        importlib.reload(config_mod)
        importlib.reload(indexer_mod)
        importlib.reload(retrieval_mod)

        citations = retrieval_mod.retrieve_citations(["alpha", "pricing"], sender="alice@example.com", top_k=5)
        logger.info(f"Citations: {citations}")

        assert len(citations) >= 1, "Expected at least one citation"
        ids = {c.get("id") for c in citations}
        # Message m3 is the most recent and contains Alpha/pricing terms
        assert "m3" in ids, "Expected the most recent matching message to appear in citations"


if __name__ == "__main__":
    test_retrieval_basic()
    logger.info("Retrieval test passed.")


