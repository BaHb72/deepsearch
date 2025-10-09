"""Tests for DatabaseStatusStore."""

from datetime import datetime, timezone

from deepsearch.infrastructure.persistence.runtime_state.database_status_store import (
    DatabaseStatusStore,
)


def test_save_activation_and_connectivity(tmp_path):
    storage_path = tmp_path / "database_status.json"
    store = DatabaseStatusStore(storage_path=storage_path)

    activation = store.save_activation_status(
        1,
        {
            "state": "active",
            "enabled": True,
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "error": None,
        },
    )

    assert activation["state"] == "active"
    assert activation["enabled"] is True
    assert "updated_at" in activation

    connectivity = store.save_connectivity_status(
        1,
        {
            "state": "connected",
            "last_success_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
            "last_error": None,
            "retrying": False,
        },
    )

    assert connectivity["state"] == "connected"
    state_snapshot = store.get_state(1)
    assert state_snapshot["connectivity"]["state"] == "connected"


def test_store_persists_to_disk(tmp_path):
    storage_path = tmp_path / "database_status.json"
    store = DatabaseStatusStore(storage_path=storage_path)
    store.save_activation_status(1, {"state": "pending", "enabled": True})

    reloaded = DatabaseStatusStore(storage_path=storage_path)
    state = reloaded.get_state(1)
    assert state["activation"]["state"] == "pending"
    assert state["activation"]["enabled"] is True
