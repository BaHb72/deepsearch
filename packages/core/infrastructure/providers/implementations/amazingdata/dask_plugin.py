"""Dask Worker Plugin for AmazingData SDK session management.

This plugin ensures that AmazingData SDK login is properly coordinated
across Dask workers, preventing multiple workers from attempting
simultaneous logins.

Usage:
    from distributed import Client
    from core.infrastructure.providers.implementations.amazingdata.dask_plugin import (
        AmazingDataWorkerPlugin,
    )

    client = Client("tcp://scheduler:8786")
    plugin = AmazingDataWorkerPlugin(redis_url="redis://localhost:6379")
    client.register_plugin(plugin)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from distributed import Worker


class AmazingDataWorkerPlugin:
    """Dask Worker Plugin for AmazingData SDK session management.

    This plugin:
    1. Initializes AmazingData provider on worker startup
    2. Uses distributed session management to coordinate login
    3. Properly shuts down on worker teardown

    Attributes:
        name: Plugin name for Dask registration.
        redis_url: Redis URL for distributed session management.
    """

    name = "amazingdata-session"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        only_on_windows: bool = True,
    ) -> None:
        """Initialize the plugin.

        Args:
            redis_url: Redis URL for distributed session management.
            only_on_windows: If True, only activate on Windows workers (WIN:1 resource).
        """
        self.redis_url = redis_url
        self.only_on_windows = only_on_windows
        self._provider: Any = None
        self._initialized = False

    def setup(self, worker: "Worker") -> None:
        """Called when the plugin is attached to a worker.

        This method runs synchronously. We schedule async initialization
        to run in the worker's event loop.
        """
        # Check if this worker should handle AmazingData
        if self.only_on_windows:
            # 优先使用新 API (Dask 2025.12+) - worker.state.total_resources
            resources = getattr(worker.state, "total_resources", {})
            if not resources:
                # 向后兼容：尝试旧 API (Dask < 2025.12)
                resources = getattr(worker, "resources", {}) or {}

            if not resources.get("WIN"):
                logger.info(
                    f"AmazingData plugin skipped on non-Windows worker | " f"resources={resources}"
                )
                return

        logger.info(f"AmazingData plugin setup on worker {worker.address}")

        # Schedule async initialization
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self._async_setup(worker))
        else:
            loop.run_until_complete(self._async_setup(worker))

    async def _async_setup(self, worker: "Worker") -> None:
        """Async setup of AmazingData provider."""
        try:
            from core.config import get_config
            from core.infrastructure.providers.implementations.amazingdata.amazingdata import (
                AmazingDataProvider,
            )
            from core.infrastructure.providers.implementations.amazingdata.config import (
                ensure_amazingdata_provider_config,
            )

            # Get configuration
            app_config = get_config()
            data_sources = getattr(app_config, "data_sources", None)
            if not data_sources:
                logger.warning("No data_sources configuration found")
                return

            providers = getattr(data_sources, "providers", {})
            if hasattr(providers, "model_dump"):
                providers = providers.model_dump()

            amazingdata_config = providers.get("amazingdata", {})
            if hasattr(amazingdata_config, "model_dump"):
                amazingdata_config = amazingdata_config.model_dump()

            if not amazingdata_config.get("config"):
                logger.warning("No AmazingData configuration found")
                return

            # Inject redis_url into config
            config_data = dict(amazingdata_config.get("config", {}))
            config_data["distributed_session_enabled"] = True
            config_data["redis_url"] = self.redis_url

            # Create and initialize provider
            provider_config = ensure_amazingdata_provider_config(
                {
                    **amazingdata_config,
                    "config": config_data,
                }
            )

            self._provider = AmazingDataProvider(provider_config)
            await self._provider.initialize()
            self._initialized = True

            logger.info(
                f"AmazingData provider initialized on worker | "
                f"worker={worker.address}, "
                f"connected={self._provider.is_connected()}"
            )

        except Exception as exc:
            logger.error(f"Failed to initialize AmazingData on worker: {exc}")

    def teardown(self, worker: "Worker") -> None:
        """Called when the plugin is removed or worker shuts down."""
        if not self._initialized or self._provider is None:
            return

        logger.info(f"AmazingData plugin teardown on worker {worker.address}")

        # Schedule async cleanup
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self._async_teardown())
        else:
            loop.run_until_complete(self._async_teardown())

    async def _async_teardown(self) -> None:
        """Async teardown of AmazingData provider."""
        try:
            if self._provider is not None:
                await self._provider.stop_async()
                logger.info("AmazingData provider stopped")
        except Exception as exc:
            logger.error(f"Error stopping AmazingData provider: {exc}")
        finally:
            self._provider = None
            self._initialized = False

    def transition(
        self,
        key: str,
        start: str,
        finish: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Called on task state transitions.

        This can be used for monitoring or custom logic on task events.
        Currently a no-op.
        """
        pass


def register_amazingdata_plugin(
    client: Any,
    redis_url: str = "redis://localhost:6379",
    only_on_windows: bool = True,
) -> None:
    """Convenience function to register the AmazingData plugin.

    Args:
        client: Dask distributed Client.
        redis_url: Redis URL for session coordination.
        only_on_windows: Only activate on Windows workers.
    """
    plugin = AmazingDataWorkerPlugin(
        redis_url=redis_url,
        only_on_windows=only_on_windows,
    )
    client.register_plugin(plugin)
    logger.info(f"AmazingData worker plugin registered | redis_url={redis_url}")
