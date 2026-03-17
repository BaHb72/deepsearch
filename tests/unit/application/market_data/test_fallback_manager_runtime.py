from __future__ import annotations

from unittest.mock import Mock

from core.application.market_data.fallback_manager import ModuleFallbackManager


def test_fallback_manager_reuses_existing_orchestrator() -> None:
    settings = Mock()
    orchestrator = Mock()

    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)

    assert manager._orchestrator is orchestrator


def test_fallback_manager_passes_provider_container(monkeypatch) -> None:
    settings = Mock()
    provider_container = object()
    captured: dict[str, object] = {}

    class _FakeOrchestrator:
        def __init__(self, settings_arg, provider_container=None):
            captured["settings"] = settings_arg
            captured["provider_container"] = provider_container

    monkeypatch.setattr(
        "core.application.market_data.orchestrator.RealtimeDataOrchestrator",
        _FakeOrchestrator,
    )

    ModuleFallbackManager(settings, provider_container=provider_container)

    assert captured["settings"] is settings
    assert captured["provider_container"] is provider_container
