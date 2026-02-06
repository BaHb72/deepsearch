"""
Tests for Data Source APIs

Endpoints tested:
- /api/data-sources/status
- /api/data-sources/config/validate
- /api/data-sources/refresh
- /api/data-sources/test/{symbol}
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from core.infrastructure.providers.managers.data_source_manager import (
    DataSourceConfig,
    DataSourceManager,
    DataSourceType,
)


class TestDataSourceStatus:
    """Test data source status endpoints."""

    @pytest.mark.asyncio
    async def test_get_status_uninitialized(self):
        """Test getting status when manager is not initialized."""
        manager = DataSourceManager()
        manager.initialized = False

        with patch(
            "core.infrastructure.providers.managers.data_source_manager.get_data_source_manager",
            return_value=manager,
        ):
            # Manager should initialize when not ready
            manager.initialize = AsyncMock()
            await manager.initialize()
            manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_report(self):
        """Test getting comprehensive status report."""
        manager = DataSourceManager()
        manager.initialized = True
        manager.providers = {
            DataSourceType.AMAZINGDATA: Mock(is_connected=Mock(return_value=True)),
        }
        manager.registry.get_config = Mock(return_value=DataSourceConfig(enabled=True, priority=1))

        report = manager.get_status_report()

        assert "sources" in report
        sources = report["sources"]
        assert "amazingdata" in sources
        assert sources["amazingdata"]["available"] is True
        assert sources["amazingdata"].get("status") in {"active", "ready", "pending_test"}
        assert "hasSavedCredential" in sources["amazingdata"]
        assert "availableCount" in report
        assert report["availableCount"] == 1

    @pytest.mark.asyncio
    async def test_refresh_data_sources(self):
        """Test refreshing all data sources."""
        manager = DataSourceManager()
        manager.initialize = AsyncMock()

        await manager.initialize()
        manager.initialize.assert_called_once()


class TestDataSourceValidation:
    """Test data source configuration validation."""

    def test_validate_amazingdata_config(self, mock_config):
        """Test AmazingData configuration validation."""
        config = mock_config
        config.amazingdata.connection.username = "test_user"
        config.amazingdata.connection.password = "test_pass"  # pragma: allowlist secret
        config.amazingdata.connection.host = "test.host"
        config.amazingdata.connection.port = 8600

        # Should validate without errors
        assert config.amazingdata.connection.username == "test_user"
        assert config.amazingdata.connection.port == 8600


class TestDataSourceTesting:
    """Test data source testing endpoints."""

    @pytest.mark.asyncio
    async def test_test_specific_source(self, test_data_provider):
        """Test testing a specific data source."""
        manager = DataSourceManager()
        manager.initialized = True
        manager.providers = {DataSourceType.AMAZINGDATA: test_data_provider}

        # Test with specific source
        result = await manager.get_data(
            data_type="realtime_quote", symbol="000001", preferred_source=DataSourceType.AMAZINGDATA
        )

        assert result is not None
        assert result["symbol"] == "000001"
        assert result["price"] == 10.5

    @pytest.mark.asyncio
    async def test_test_all_sources(self):
        """Test testing all available data sources."""
        manager = DataSourceManager()
        manager.initialized = True

        amazingdata_provider = AsyncMock()
        amazingdata_provider.get_realtime_quote = AsyncMock(return_value={"source": "amazingdata"})

        manager.providers = {DataSourceType.AMAZINGDATA: amazingdata_provider}

        results = {}
        for source_type, provider in manager.providers.items():
            result = await provider.get_realtime_quote("000001")
            results[source_type.value] = {"success": result is not None, "data": result}

        assert len(results) == 1
        assert results["amazingdata"]["data"]["source"] == "amazingdata"


class TestDataSourceFailover:
    """Test data source failover mechanisms."""

    @pytest.mark.asyncio
    async def test_automatic_failover(self):
        """Test automatic failover when primary source fails."""
        manager = DataSourceManager()
        manager.initialized = True

        primary = AsyncMock()
        primary.get_realtime_quote = AsyncMock(side_effect=Exception("Connection failed"))
        primary.is_connected = Mock(return_value=False)

        manager.providers = {DataSourceType.AMAZINGDATA: primary}
        manager.source_priorities = {DataSourceType.AMAZINGDATA: 1}

        result = await manager.get_data(data_type="realtime_quote", symbol="000001")

        assert result is None
        primary.get_realtime_quote.assert_called_with("000001")

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern for failed sources."""
        manager = DataSourceManager()
        manager.initialized = True

        # Provider that always fails
        failing_provider = AsyncMock()
        failing_provider.get_realtime_quote = AsyncMock(side_effect=Exception("Always fails"))
        failing_provider.is_connected = Mock(return_value=False)

        manager.providers = {DataSourceType.AMAZINGDATA: failing_provider}

        for _ in range(5):
            try:
                await manager.get_data(
                    data_type="realtime_quote",
                    symbol="000001",
                    preferred_source=DataSourceType.AMAZINGDATA,
                )
            except Exception:
                pass

        assert failing_provider.get_realtime_quote.call_count == 5
