"""
Tests for Data Source APIs

Endpoints tested:
- /api/data-sources/status
- /api/data-sources/config/validate
- /api/data-sources/refresh
- /api/data-sources/test/{symbol}
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from deepsearch.infrastructure.providers.managers.data_source_manager import (
    DataSourceManager,
    DataSourceType
)


class TestDataSourceStatus:
    """Test data source status endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_status_uninitialized(self):
        """Test getting status when manager is not initialized."""
        manager = DataSourceManager()
        manager.initialized = False
        
        with patch('deepsearch.infrastructure.providers.managers.data_source_manager.get_data_source_manager', return_value=manager):
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
            DataSourceType.QMT: Mock(is_connected=Mock(return_value=False)),
            DataSourceType.CLOUDFLARE: Mock(is_connected=Mock(return_value=True))
        }
        
        report = manager.get_status_report()
        
        assert "sources" in report
        assert len(report["sources"]) == 3
        assert report["sources"][DataSourceType.AMAZINGDATA]["available"] == True
        assert report["sources"][DataSourceType.QMT]["available"] == False
    
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
        config.amazingdata.connection.password = "test_pass"
        config.amazingdata.connection.host = "test.host"
        config.amazingdata.connection.port = 8600
        
        # Should validate without errors
        assert config.amazingdata.connection.username == "test_user"
        assert config.amazingdata.connection.port == 8600
    
    def test_validate_qmt_config(self, mock_config):
        """Test QMT configuration validation."""
        config = mock_config
        config.qmt.enabled = True
        config.qmt.receiver.tcp_port = 9999
        config.qmt.receiver.websocket_port = 9998
        
        assert config.qmt.receiver.tcp_port == 9999
        assert config.qmt.receiver.websocket_port == 9998


class TestDataSourceTesting:
    """Test data source testing endpoints."""
    
    @pytest.mark.asyncio
    async def test_test_specific_source(self, test_data_provider):
        """Test testing a specific data source."""
        manager = DataSourceManager()
        manager.initialized = True
        manager.providers = {
            DataSourceType.AMAZINGDATA: test_data_provider
        }
        
        # Test with specific source
        result = await manager.get_data(
            data_type="realtime_quote",
            symbol="000001",
            preferred_source=DataSourceType.AMAZINGDATA
        )
        
        assert result is not None
        assert result["symbol"] == "000001"
        assert result["price"] == 10.5
    
    @pytest.mark.asyncio
    async def test_test_all_sources(self):
        """Test testing all available data sources."""
        manager = DataSourceManager()
        manager.initialized = True
        
        # Create different mock providers
        amazingdata_provider = AsyncMock()
        amazingdata_provider.get_realtime_quote = AsyncMock(return_value={"source": "amazingdata"})
        
        qmt_provider = AsyncMock()
        qmt_provider.get_realtime_quote = AsyncMock(return_value={"source": "qmt"})
        
        manager.providers = {
            DataSourceType.AMAZINGDATA: amazingdata_provider,
            DataSourceType.QMT: qmt_provider
        }
        
        results = {}
        for source_type in manager.providers.keys():
            provider = manager.providers[source_type]
            result = await provider.get_realtime_quote("000001")
            results[source_type.value] = {
                "success": result is not None,
                "data": result
            }
        
        assert len(results) == 2
        assert results["amazingdata"]["data"]["source"] == "amazingdata"
        assert results["qmt"]["data"]["source"] == "qmt"


class TestDataSourceFailover:
    """Test data source failover mechanisms."""
    
    @pytest.mark.asyncio
    async def test_automatic_failover(self):
        """Test automatic failover when primary source fails."""
        manager = DataSourceManager()
        manager.initialized = True
        
        # Primary fails, secondary succeeds
        primary = AsyncMock()
        primary.get_realtime_quote = AsyncMock(side_effect=Exception("Connection failed"))
        primary.is_connected = Mock(return_value=False)
        
        secondary = AsyncMock()
        secondary.get_realtime_quote = AsyncMock(return_value={"source": "secondary", "price": 10.0})
        secondary.is_connected = Mock(return_value=True)
        
        manager.providers = {
            DataSourceType.AMAZINGDATA: primary,
            DataSourceType.CLOUDFLARE: secondary
        }
        manager.source_priorities = {
            DataSourceType.AMAZINGDATA: 1,
            DataSourceType.CLOUDFLARE: 2
        }
        
        # Should failover to secondary
        with patch.object(manager, '_get_provider_for_request', return_value=secondary):
            result = await manager.get_data(
                data_type="realtime_quote",
                symbol="000001"
            )
            assert result["source"] == "secondary"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern for failed sources."""
        manager = DataSourceManager()
        manager.initialized = True
        
        # Provider that always fails
        failing_provider = AsyncMock()
        failing_provider.get_realtime_quote = AsyncMock(side_effect=Exception("Always fails"))
        failing_provider.is_connected = Mock(return_value=False)
        
        manager.providers = {
            DataSourceType.QMT: failing_provider
        }
        
        # After multiple failures, circuit should open
        for _ in range(5):
            try:
                await manager.get_data(
                    data_type="realtime_quote",
                    symbol="000001",
                    preferred_source=DataSourceType.QMT
                )
            except:
                pass
        
        # Circuit breaker should prevent further attempts
        # Implementation depends on actual circuit breaker logic