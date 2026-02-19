from __future__ import annotations

from apps.api.api.providers import DataProviderFactory


def test_invoke_cleanup_uses_static_method_and_avoids_dynamic_close() -> None:
    class _ProxyCleanupProvider:
        def __init__(self) -> None:
            self.cleanup_called = False
            self.dynamic_called = False

        async def cleanup(self) -> None:
            self.cleanup_called = True

        def __getattr__(self, _name):
            self.dynamic_called = True

            async def _proxy(*_args, **_kwargs):
                self.dynamic_called = True
                return None

            return _proxy

    provider = _ProxyCleanupProvider()

    DataProviderFactory._invoke_cleanup(provider, "amazingdata")

    assert provider.cleanup_called is True
    assert provider.dynamic_called is False
