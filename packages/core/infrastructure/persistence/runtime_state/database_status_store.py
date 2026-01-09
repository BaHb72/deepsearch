"""Database runtime status store.

This module keeps track of activation/connectivity state for configured
connections. It persists a small JSON snapshot under ``data/runtime`` so
that WebUI, CLI tools and background jobs can share a consistent view of the
current database lifecycle state.
"""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, cast

from loguru import logger

DEFAULT_STORE_FILENAME = "database_status.json"


@dataclass(frozen=True)
class ConnectionStateKeys:
    activation: str = "activation"
    connectivity: str = "connectivity"


class DatabaseStatusStore:
    """Persist activation/connectivity state for database connections."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        base_path = storage_path or self._default_storage_path()
        self._path = base_path.resolve()
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {"active_connection_id": None, "connections": {}}
        self._load()

    @staticmethod
    def _default_storage_path() -> Path:
        project_root = Path.cwd()
        runtime_dir = project_root / "data" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return runtime_dir / DEFAULT_STORE_FILENAME

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> None:
        if not self._path.exists():
            return

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                connections = payload.get("connections")
                if isinstance(connections, dict):
                    self._state["connections"] = connections
                active_id = payload.get("active_connection_id")
                if isinstance(active_id, (str, int)) or active_id is None:
                    self._state["active_connection_id"] = active_id
        except Exception as exc:  # pragma: no cover - corrupted payload fallback
            logger.warning("Failed to load database status store at {}: {}", self._path, exc)

    def _persist_locked(self) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self._path)

    def _ensure_entry(self, connection_id: str) -> Dict[str, Any]:
        entry = self._state["connections"].setdefault(
            connection_id,
            {ConnectionStateKeys.activation: {}, ConnectionStateKeys.connectivity: {}},
        )
        entry.setdefault(ConnectionStateKeys.activation, {})
        entry.setdefault(ConnectionStateKeys.connectivity, {})
        return cast(Dict[str, Any], entry)

    def set_active_connection(self, connection_id: Optional[int]) -> None:
        with self._lock:
            self._state["active_connection_id"] = connection_id
            self._persist_locked()

    def get_active_connection_id(self) -> Optional[int]:
        active_id = self._state.get("active_connection_id")
        if isinstance(active_id, int):
            return active_id
        if isinstance(active_id, str) and active_id.isdigit():
            return int(active_id)
        return None

    def save_activation_status(
        self, connection_id: int | str, status: Dict[str, Any]
    ) -> Dict[str, Any]:
        serialised_status = self._serialise_activation(status)
        with self._lock:
            entry = self._ensure_entry(str(connection_id))
            activation = entry.get(ConnectionStateKeys.activation, {})
            activation.update(serialised_status)
            if "enabled" not in activation and "state" in activation:
                activation["enabled"] = activation["state"] in {"active", "pending"}
            if "updated_at" not in activation:
                activation["updated_at"] = self._now_iso()
            entry[ConnectionStateKeys.activation] = activation
            self._persist_locked()
            return cast(Dict[str, Any], copy.deepcopy(activation))

    def save_connectivity_status(
        self, connection_id: int | str, status: Dict[str, Any]
    ) -> Dict[str, Any]:
        serialised_status = self._serialise_connectivity(status)
        with self._lock:
            entry = self._ensure_entry(str(connection_id))
            connectivity = entry.get(ConnectionStateKeys.connectivity, {})
            connectivity.update(serialised_status)
            if "state" not in connectivity:
                connectivity["state"] = "unknown"
            entry[ConnectionStateKeys.connectivity] = connectivity
            self._persist_locked()
            return cast(Dict[str, Any], copy.deepcopy(connectivity))

    def get_state(self, connection_id: int | str) -> Dict[str, Any]:
        with self._lock:
            entry = self._state["connections"].get(str(connection_id), {})
            return cast(Dict[str, Any], copy.deepcopy(entry))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return cast(Dict[str, Any], copy.deepcopy(self._state))

    @staticmethod
    def _serialise_activation(status: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(status)
        updated_at = payload.get("updated_at")
        if isinstance(updated_at, datetime):
            payload["updated_at"] = updated_at.astimezone(timezone.utc).isoformat()
        return payload

    @staticmethod
    def _serialise_connectivity(status: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(status)
        for key in ("last_success_at", "last_error_at"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.astimezone(timezone.utc).isoformat()
        return payload


_store_instance: Optional[DatabaseStatusStore] = None
_store_lock = threading.Lock()


def get_database_status_store(storage_path: Optional[Path] = None) -> DatabaseStatusStore:
    """Singleton-style accessor used across the backend."""
    global _store_instance
    if _store_instance is not None and storage_path is None:
        return _store_instance

    with _store_lock:
        if _store_instance is None or storage_path is not None:
            _store_instance = DatabaseStatusStore(storage_path=storage_path)
        return _store_instance
