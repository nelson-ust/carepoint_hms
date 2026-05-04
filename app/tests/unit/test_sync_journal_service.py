"""Unit tests for SyncJournalService."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.sync_journal_service import SyncJournalService


class TestServiceConstruction:
    def test_default_origin_is_cloud(self):
        svc = SyncJournalService(MagicMock())
        assert svc.origin == "cloud"
        assert svc.origin_node_id is None

    def test_origin_overridable(self):
        svc = SyncJournalService(MagicMock(), origin="edge:acme", origin_node_id=42)
        assert svc.origin == "edge:acme"
        assert svc.origin_node_id == 42


class TestFetchSinceQuery:
    def test_constructs_filter_chain(self):
        db = MagicMock()
        svc = SyncJournalService(db)
        svc.fetch_since(cursor=10, limit=50)
        # ensure we built a query at all
        assert db.query.called
