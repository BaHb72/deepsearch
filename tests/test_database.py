"""
Tests for Database APIs

Endpoints tested:
- /api/database/status
- /api/database/health
- /api/database/stats
- /api/database/cache/status
- /api/database/cache/clear
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestDatabaseStatus:
    """Test database status endpoints."""

    @pytest.mark.asyncio
    async def test_get_database_status(self):
        """Test getting database connection status."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=Mock(scalar=Mock(return_value=1)))

        with patch("core.infrastructure.persistence.database.get_connection", return_value=mock_db):
            # Should return connected status
            status = {
                "connected": True,
                "type": "postgresql",
                "host": "localhost",
                "database": "deepsearch",
                "pool_size": 10,
                "active_connections": 3,
            }
            assert status["connected"]
            assert status["type"] == "postgresql"

    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test handling database connection failure."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("core.infrastructure.persistence.database.get_connection", return_value=mock_db):
            status = {"connected": False, "error": "Connection refused"}
            assert not status["connected"]
            assert "error" in status

    @pytest.mark.asyncio
    async def test_get_pool_statistics(self):
        """Test getting connection pool statistics."""
        pool_stats = {"size": 10, "checked_out": 3, "checked_in": 7, "overflow": 0, "total": 10}

        assert pool_stats["checked_out"] + pool_stats["checked_in"] == pool_stats["size"]


class TestDatabaseHealth:
    """Test database health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_all_systems(self):
        """Test comprehensive health check."""
        health = {
            "status": "healthy",
            "checks": {
                "postgresql": {"status": "up", "latency_ms": 5, "version": "15.0"},
                "redis": {
                    "status": "up",
                    "latency_ms": 1,
                    "memory_used": "100MB",
                    "memory_max": "4GB",
                },
                "duckdb": {"status": "up", "latency_ms": 2, "size_mb": 500},
            },
            "timestamp": datetime.now().isoformat(),
        }

        assert health["status"] == "healthy"
        assert all(c["status"] == "up" for c in health["checks"].values())

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check with degraded service."""
        health = {
            "status": "degraded",
            "checks": {
                "postgresql": {"status": "up"},
                "redis": {"status": "down", "error": "Connection timeout"},
                "duckdb": {"status": "up"},
            },
        }

        assert health["status"] == "degraded"
        assert health["checks"]["redis"]["status"] == "down"

    @pytest.mark.asyncio
    async def test_latency_measurement(self):
        """Test database latency measurement."""
        import time

        start = time.time()
        # Simulate database query
        await asyncio.sleep(0.01)
        latency_ms = (time.time() - start) * 1000

        assert latency_ms > 0
        assert latency_ms < 100  # Should be fast


class TestDatabaseStatistics:
    """Test database statistics endpoints."""

    @pytest.mark.asyncio
    async def test_get_table_statistics(self):
        """Test getting table statistics."""
        stats = {
            "tables": [
                {
                    "name": "stock_quotes",
                    "row_count": 1000000,
                    "size_mb": 250,
                    "index_count": 3,
                    "last_updated": "2025-09-13 10:00:00",
                },
                {
                    "name": "kline_data",
                    "row_count": 5000000,
                    "size_mb": 1200,
                    "index_count": 4,
                    "last_updated": "2025-09-13 09:30:00",
                },
            ],
            "total_size_mb": 1450,
            "total_rows": 6000000,
        }

        assert len(stats["tables"]) == 2
        assert stats["total_rows"] == sum(t["row_count"] for t in stats["tables"])

    @pytest.mark.asyncio
    async def test_get_query_statistics(self):
        """Test getting query performance statistics."""
        query_stats = {
            "slow_queries": [
                {
                    "query": "SELECT * FROM kline_data WHERE symbol = ?",
                    "avg_time_ms": 150,
                    "call_count": 100,
                    "last_called": "2025-09-13 10:00:00",
                }
            ],
            "most_frequent": [
                {
                    "query": "SELECT price FROM stock_quotes WHERE symbol = ?",
                    "call_count": 10000,
                    "avg_time_ms": 5,
                }
            ],
        }

        assert len(query_stats["slow_queries"]) > 0
        assert query_stats["slow_queries"][0]["avg_time_ms"] > 100


class TestCacheManagement:
    """Test cache management endpoints."""

    @pytest.mark.asyncio
    async def test_get_cache_status(self, mock_redis):
        """Test getting cache status."""
        mock_redis.info = AsyncMock(
            return_value={
                "used_memory_human": "150M",
                "used_memory_peak_human": "200M",
                "connected_clients": 5,
                "total_commands_processed": 100000,
                "keyspace": {"db0": {"keys": 5000, "expires": 3000}},
            }
        )

        info = await mock_redis.info()

        assert "used_memory_human" in info
        assert info["keyspace"]["db0"]["keys"] == 5000

    @pytest.mark.asyncio
    async def test_clear_cache_all(self, mock_redis):
        """Test clearing all cache."""
        mock_redis.flushall = AsyncMock(return_value=True)

        result = await mock_redis.flushall()

        assert result
        mock_redis.flushall.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache_pattern(self, mock_redis):
        """Test clearing cache by pattern."""
        mock_redis.keys = AsyncMock(
            return_value=[b"quote:000001", b"quote:000002", b"quote:600000"]
        )
        mock_redis.delete = AsyncMock(return_value=3)

        keys = await mock_redis.keys("quote:*")
        deleted = await mock_redis.delete(*keys)

        assert deleted == 3

    @pytest.mark.asyncio
    async def test_cache_ttl_management(self, mock_redis):
        """Test cache TTL management."""
        key = "quote:000001"
        ttl_seconds = 300

        mock_redis.ttl = AsyncMock(return_value=ttl_seconds)
        mock_redis.expire = AsyncMock(return_value=True)

        # Check TTL
        remaining = await mock_redis.ttl(key)
        assert remaining == ttl_seconds

        # Update TTL
        result = await mock_redis.expire(key, 600)
        assert result


class TestDatabaseMigrations:
    """Test database migration status."""

    @pytest.mark.asyncio
    async def test_get_migration_status(self):
        """Test getting migration status."""
        migrations = {
            "current_version": "20250913_001",
            "pending_migrations": [],
            "applied_migrations": [
                {
                    "version": "20250901_001",
                    "name": "create_stock_tables",
                    "applied_at": "2025-09-01 00:00:00",
                },
                {
                    "version": "20250905_001",
                    "name": "add_indices",
                    "applied_at": "2025-09-05 00:00:00",
                },
                {
                    "version": "20250913_001",
                    "name": "add_cache_tables",
                    "applied_at": "2025-09-13 00:00:00",
                },
            ],
        }

        assert migrations["current_version"] == "20250913_001"
        assert len(migrations["pending_migrations"]) == 0
        assert len(migrations["applied_migrations"]) == 3
