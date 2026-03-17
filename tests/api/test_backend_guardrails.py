from __future__ import annotations

from pathlib import Path

from core.observability import logger_manager
from fastapi.routing import APIRoute

from apps.api.server import app


def test_no_duplicate_routes() -> None:
    route_map: dict[tuple[str, tuple[str, ...]], list[str]] = {}

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = tuple(
            sorted(method for method in route.methods if method not in {"HEAD", "OPTIONS"})
        )
        if not methods:
            continue
        signature = (route.path, methods)
        route_map.setdefault(signature, []).append(
            f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        )

    duplicates = {
        signature: endpoints for signature, endpoints in route_map.items() if len(endpoints) > 1
    }
    assert not duplicates


def test_no_external_log_write_in_test_env() -> None:
    resolved = logger_manager.log_path.resolve()
    workspace_root = Path.cwd().resolve()
    assert resolved.is_relative_to(workspace_root)
