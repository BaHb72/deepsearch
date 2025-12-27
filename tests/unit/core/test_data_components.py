"""
单元测试 - 数据组件

测试DatabaseComponent和CacheComponent的功能
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from deepsearch.core.components.data_components import CacheComponent, DatabaseComponent
from deepsearch.core.utils.exceptions import ComponentLifecycleError


class TestDatabaseComponent:
    """DatabaseComponent 单元测试"""

    @pytest.fixture
    async def db_component(self):
        """创建数据库组件实例"""
        component = DatabaseComponent()
        yield component
        # 清理
        if component._engine and hasattr(component._engine, "dispose"):
            if asyncio.iscoroutinefunction(component._engine.dispose):
                await component._engine.dispose()
            else:
                component._engine.dispose()

    @pytest.fixture
    def mock_config(self):
        """模拟配置对象"""
        config = Mock()
        config.database.main.enabled = True
        config.database.main.auto_connect = False
        config.database.main.get_url.return_value = "postgresql://test:test@localhost/testdb"
        config.database.main.type = "postgresql"
        config.database.main.host = "localhost"
        config.database.main.port = 5432
        config.database.main.database = "testdb"
        config.app.env = "test"
        return config

    def test_validate_table_name(self):
        """测试表名验证"""
        # 有效的表名
        assert DatabaseComponent.validate_table_name("users")
        assert DatabaseComponent.validate_table_name("user_accounts")
        assert DatabaseComponent.validate_table_name("_temp_table")
        assert DatabaseComponent.validate_table_name("Table123")

        # 无效的表名
        assert not DatabaseComponent.validate_table_name("user-accounts")
        assert not DatabaseComponent.validate_table_name("users;")
        assert not DatabaseComponent.validate_table_name("drop table users")
        assert not DatabaseComponent.validate_table_name("123table")
        assert not DatabaseComponent.validate_table_name("")

    @pytest.mark.asyncio
    async def test_initialize_without_auto_connect(self, db_component, mock_config):
        """测试不自动连接的初始化"""
        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_config
        ):
            await db_component._initialize()

            # 验证组件已初始化但未连接
            assert db_component._instance == db_component
            assert db_component._engine is None
            assert not db_component.is_connected()

    @pytest.mark.asyncio
    async def test_initialize_with_auto_connect(self, db_component):
        """测试自动连接的初始化"""
        mock_config = Mock()
        mock_config.database.main.enabled = True
        mock_config.database.main.auto_connect = True
        mock_config.database.main.get_url.return_value = "postgresql://test:test@localhost/testdb"
        mock_config.app.env = "test"

        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_config
        ):
            with patch.object(
                db_component, "connect_async", new_callable=AsyncMock
            ) as mock_connect:
                await db_component._initialize()

                # 验证调用了connect_async
                mock_connect.assert_called_once()
                assert db_component._instance == db_component

    @pytest.mark.asyncio
    async def test_connect_async_success(self, db_component, mock_config):
        """测试成功的数据库连接"""
        mock_engine = Mock(spec=AsyncEngine)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_engine.begin = Mock(return_value=mock_conn)
        mock_engine.dispose = AsyncMock()

        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_config
        ):
            with patch(
                "deepsearch.core.components.data_components.create_async_engine",
                return_value=mock_engine,
            ):
                await db_component.connect_async()

                # 验证引擎已创建
                assert db_component._engine == mock_engine
                assert db_component._session_factory is not None
                assert db_component._instance == db_component

    @pytest.mark.asyncio
    async def test_connect_async_timeout(self, db_component, mock_config):
        """测试连接超时"""
        mock_engine = Mock(spec=AsyncEngine)
        mock_engine.begin = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_engine.dispose = AsyncMock()

        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_config
        ):
            with patch(
                "deepsearch.core.components.data_components.create_async_engine",
                return_value=mock_engine,
            ):
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                    with pytest.raises(RuntimeError, match="数据库连接超时"):
                        await db_component.connect_async()

                    # 验证资源已清理
                    assert db_component._engine is None
                    assert db_component._session_factory is None

    @pytest.mark.asyncio
    async def test_disconnect_async(self, db_component):
        """测试断开连接"""
        mock_engine = Mock(spec=AsyncEngine)
        mock_engine.dispose = AsyncMock()
        db_component._engine = mock_engine
        db_component._session_factory = Mock()

        await db_component.disconnect_async()

        # 验证引擎已释放
        mock_engine.dispose.assert_called_once()
        assert db_component._engine is None
        assert db_component._session_factory is None

    def test_get_session_without_initialization(self, db_component):
        """测试未初始化时获取会话"""
        with pytest.raises(ComponentLifecycleError, match="Database not initialized"):
            db_component.get_session()

    def test_get_session_with_initialization(self, db_component):
        """测试已初始化时获取会话"""
        mock_factory = Mock()
        mock_session = Mock()
        mock_factory.return_value = mock_session
        db_component._session_factory = mock_factory

        session = db_component.get_session()

        assert session == mock_session
        mock_factory.assert_called_once()

    def test_health_check_no_engine(self, db_component):
        """测试无引擎时的健康检查"""
        assert db_component._health_check() is False

    def test_health_check_with_engine(self, db_component):
        """测试有引擎时的健康检查"""
        mock_engine = Mock()
        mock_conn = Mock()
        mock_conn.execute = Mock()
        mock_conn.commit = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine.connect = Mock(return_value=mock_conn)

        db_component._engine = mock_engine

        result = db_component._health_check()

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_async_no_engine(self, db_component):
        """测试无引擎时的异步健康检查"""
        result = await db_component.health_check_async()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_async_with_engine(self, db_component):
        """测试有引擎时的异步健康检查"""
        mock_engine = Mock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_engine.begin = Mock(return_value=mock_conn)

        db_component._engine = mock_engine

        result = await db_component.health_check_async()

        assert result is True
        mock_conn.execute.assert_called_once()

    def test_get_pool_status_no_engine(self, db_component):
        """测试无引擎时获取连接池状态"""
        status = db_component._get_pool_status()
        assert status == {}

    def test_get_pool_status_with_engine(self, db_component):
        """测试有引擎时获取连接池状态"""
        mock_engine = Mock()
        mock_pool = Mock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 8
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.total.return_value = 10
        mock_engine.pool = mock_pool

        db_component._engine = mock_engine

        status = db_component._get_pool_status()

        assert status == {"size": 10, "checked_in": 8, "checked_out": 2, "overflow": 0, "total": 10}

    def test_get_component_statistics(self, db_component):
        """测试获取组件统计信息"""
        mock_engine = Mock()
        mock_pool = Mock()
        mock_pool.size.return_value = 10
        mock_engine.pool = mock_pool
        db_component._engine = mock_engine
        db_component._is_timescale_enabled = True

        stats = db_component._get_component_statistics()

        assert stats["connected"] is True
        assert stats["engine_type"] == type(mock_engine).__name__
        assert stats["timescale_enabled"] is True
        assert stats["pool_status"]["size"] == 10


class TestCacheComponent:
    """CacheComponent 单元测试"""

    @pytest.fixture
    async def cache_component(self):
        """创建缓存组件实例"""
        component = CacheComponent()
        yield component
        # 清理
        if component._redis_client:
            await component._stop()

    @pytest.fixture
    def mock_redis_config(self):
        """模拟Redis配置"""
        config = Mock()
        config.database.cache.enabled = True
        config.database.cache.model_dump.return_value = {
            "enabled": True,
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None,
            "pool_size": 10,
            "socket_keepalive": True,
            "retry_on_timeout": True,
            "health_check_interval": 30,
        }
        return config

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, cache_component):
        """测试禁用状态的初始化"""
        mock_config = Mock()
        mock_config.database.cache.enabled = False

        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_config
        ):
            await cache_component._initialize()

            assert cache_component._instance == cache_component
            assert cache_component._redis_client is None
            assert not cache_component._connected

    @pytest.mark.asyncio
    async def test_initialize_with_connection(self, cache_component, mock_redis_config):
        """测试启用连接的初始化"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch(
            "deepsearch.core.components.data_components.get_config", return_value=mock_redis_config
        ):
            with patch("redis.asyncio.ConnectionPool"):
                with patch("redis.asyncio.Redis", return_value=mock_redis):
                    await cache_component._initialize()

                    assert cache_component._instance == cache_component
                    assert cache_component._redis_client == mock_redis
                    assert cache_component._connected is True

    @pytest.mark.asyncio
    async def test_connect_to_redis_success(self, cache_component, mock_redis_config):
        """测试成功连接Redis"""
        cache_component._redis_config = mock_redis_config.database.cache.model_dump.return_value

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("redis.asyncio.ConnectionPool"):
            with patch("redis.asyncio.Redis", return_value=mock_redis):
                await cache_component._connect_to_redis()

                assert cache_component._redis_client == mock_redis
                assert cache_component._connected is True
                assert cache_component._connection_error is None
                mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_to_redis_timeout(self, cache_component, mock_redis_config):
        """测试连接Redis超时"""
        cache_component._redis_config = mock_redis_config.database.cache.model_dump.return_value

        # 创建一个永不完成的协程来模拟超时
        async def slow_ping():
            await asyncio.sleep(100)  # 模拟极慢的响应

        mock_redis = AsyncMock()
        mock_redis.ping = slow_ping
        mock_redis.close = AsyncMock()

        with patch("redis.asyncio.ConnectionPool"):
            with patch("redis.asyncio.Redis", return_value=mock_redis):
                # 使用极短的超时时间来触发超时
                with patch.object(
                    cache_component._timeout_manager,
                    "get_timeout",
                    return_value=0.001,  # 1毫秒超时
                ):
                    with pytest.raises(asyncio.TimeoutError):
                        await cache_component._connect_to_redis()

                    assert not cache_component._connected
                    assert "连接超时" in cache_component._connection_error

    @pytest.mark.asyncio
    async def test_get_operation(self, cache_component):
        """测试GET操作"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="test_value")
        cache_component._redis_client = mock_redis
        cache_component._connected = True

        result = await cache_component.get("test_key")

        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_operation_not_connected(self, cache_component):
        """测试未连接时的GET操作"""
        cache_component._connected = False

        result = await cache_component.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_operation(self, cache_component):
        """测试SET操作"""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache_component._redis_client = mock_redis
        cache_component._connected = True

        result = await cache_component.set("test_key", "test_value", ttl=60)

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", "test_value", ex=60)

    @pytest.mark.asyncio
    async def test_delete_operation(self, cache_component):
        """测试DELETE操作"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        cache_component._redis_client = mock_redis
        cache_component._connected = True

        result = await cache_component.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_health_check_async_connected(self, cache_component):
        """测试连接状态的异步健康检查"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        cache_component._redis_client = mock_redis
        cache_component._connected = True

        result = await cache_component.health_check_async()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_async_not_connected(self, cache_component):
        """测试未连接状态的异步健康检查"""
        cache_component._connected = False

        result = await cache_component.health_check_async()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_pool_stats(self, cache_component):
        """测试获取连接池统计信息"""
        mock_redis = AsyncMock()
        mock_pool = Mock()
        mock_pool.max_connections = 10
        mock_pool._created_connections = [1, 2, 3]
        mock_pool._available_connections = [1, 2]
        mock_pool._in_use_connections = [3]
        mock_redis.connection_pool = mock_pool
        cache_component._redis_client = mock_redis

        stats = await cache_component.get_pool_stats()

        assert stats == {
            "max_connections": 10,
            "created_connections": 3,
            "available_connections": 2,
            "in_use_connections": 1,
        }

    @pytest.mark.asyncio
    async def test_stop_with_client(self, cache_component):
        """测试停止时关闭客户端"""
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_redis.wait_closed = AsyncMock()
        cache_component._redis_client = mock_redis
        cache_component._connected = True

        await cache_component._stop()

        mock_redis.close.assert_called_once()
        mock_redis.wait_closed.assert_called_once()
        assert cache_component._redis_client is None
        assert not cache_component._connected
