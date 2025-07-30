"""
Redis 缓存组件

提供 Redis 缓存服务的连接和管理功能
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional

import redis.asyncio as redis
from redis.exceptions import ConnectionError, AuthenticationError, TimeoutError

from .component_manager import Component, ComponentType, ComponentStatus
from ..config import get_config


class CacheComponent(Component):
    """Redis 缓存组件"""

    def __init__(self, name: str = 'cache'):
        super().__init__(name, ComponentType.INFRASTRUCTURE)
        self.config = get_config().database.cache
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        self._connection_info = {}
        self._last_health_check = None
        self._disconnect_reason = None

    def is_connected(self) -> bool:
        """检查是否已连接到 Redis"""
        return self.redis_client is not None

    def initialize(self) -> None:
        """初始化组件"""
        self._logger.info(f"正在初始化 {self.name} 组件...")

        # 检查是否启用
        if not self.config.enabled:
            self._logger.info("Redis 缓存功能已禁用")
            self._status = ComponentStatus.INITIALIZED
            return

        # 如果配置了自动连接，尝试连接
        if getattr(self.config, 'auto_connect', True):
            try:
                asyncio.run(self.connect_async())
                self._logger.info("✓ Redis 缓存自动连接成功")
            except Exception as e:
                self._logger.warning(f"Redis 缓存自动连接失败: {e}")
                self._disconnect_reason = f"自动连接失败: {str(e)}"

        self._status = ComponentStatus.INITIALIZED
        self._logger.info(f"✓ {self.name} 组件初始化成功")

    def start(self) -> None:
        """启动组件"""
        asyncio.run(self.start_async())

    def stop(self) -> None:
        """停止组件"""
        asyncio.run(self.stop_async())

    def health_check(self) -> bool:
        """同步健康检查"""
        try:
            # 使用 asyncio.run 来安全地执行异步代码
            # 这会自动创建和清理事件循环，避免线程问题
            result = asyncio.run(self.health_check_async())

            # 如果未连接，设置明确的错误信息
            if result.get('status') == 'disconnected':
                self._error_message = "Redis 服务未连接，无法读写 tick 数据"
            elif result.get('status') == 'unhealthy':
                self._error_message = f"Redis 服务异常: {result.get('error', '未知错误')}"
            else:
                self._error_message = None
            return result.get('status') == 'healthy'
        except RuntimeError as e:
            # 如果已经在事件循环中运行，使用同步方式检查
            if "cannot be called from a running event loop" in str(e):
                return self._sync_health_check()
            else:
                self._logger.warning(f"健康检查运行时错误: {e}")
                self._error_message = f"健康检查异常: {str(e)}"
                return False
        except Exception as e:
            self._logger.warning(f"健康检查失败: {e}")
            self._error_message = f"健康检查异常: {str(e)}"
            return False

    def _sync_health_check(self) -> bool:
        """同步健康检查（备用方法）"""
        try:
            if not self.is_connected():
                self._error_message = "Redis 服务未连接，无法读写 tick 数据"
                return False

            # 创建独立的同步连接进行测试
            try:
                import redis as sync_redis
                sync_client = sync_redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                sync_client.ping()
                sync_client.close()  # 关闭连接
                self._error_message = None
                return True
            except Exception as e:
                # 记录完整的错误信息
                error_msg = str(e)
                self._logger.debug(f"同步健康检查详细错误: {type(e).__name__}: {error_msg}")

                # 根据错误类型提供更清晰的信息
                if "Connection refused" in error_msg or "拒绝连接" in error_msg:
                    self._error_message = f"Redis 连接被拒绝 ({self.config.host}:{self.config.port})"
                elif "timeout" in error_msg.lower():
                    self._error_message = "Redis 连接超时"
                elif "password" in error_msg.lower() or "auth" in error_msg.lower():
                    self._error_message = "Redis 认证失败"
                else:
                    # 保留完整错误信息
                    self._error_message = f"Redis 服务异常: {error_msg}"
                return False
        except Exception as e:
            self._logger.warning(f"同步健康检查失败: {e}")
            self._error_message = f"健康检查异常: {str(e)}"
            return False

    async def connect_async(self) -> None:
        """异步连接到 Redis"""
        if self.is_connected():
            self._logger.warning("Redis 已连接，无需重复连接")
            return

        try:
            # 验证配置
            if not self.config.host:
                raise ValueError("Redis 主机地址未配置")

            # 创建连接池
            pool_size = getattr(self.config, 'poolSize', 10) or getattr(self.config, 'pool_size', 10)
            self.connection_pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password if self.config.password else None,
                max_connections=pool_size,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 创建 Redis 客户端
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)

            # 测试连接
            await self.redis_client.ping()

            # 获取 Redis 信息
            info = await self.redis_client.info()
            self._connection_info = {
                'version': info.get('redis_version', 'unknown'),
                'mode': info.get('redis_mode', 'standalone'),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'unknown')
            }

            self._disconnect_reason = None
            self._logger.info(f"Redis 连接成功 - 版本: {self._connection_info['version']}, "
                              f"内存使用: {self._connection_info['used_memory_human']}")

        except AuthenticationError as e:
            self._disconnect_reason = "Redis 认证失败，请检查密码"
            raise RuntimeError(f"Redis 认证失败: {e}")
        except TimeoutError as e:
            self._disconnect_reason = "Redis 连接超时，请检查网络和服务状态"
            raise RuntimeError(f"Redis 连接超时: {e}")
        except ConnectionError as e:
            self._disconnect_reason = f"Redis 连接失败，请检查服务是否运行在 {self.config.host}:{self.config.port}"
            raise RuntimeError(f"Redis 连接失败: {e}")
        except Exception as e:
            self._disconnect_reason = f"Redis 连接失败: {str(e)}"
            raise RuntimeError(f"Redis 连接失败: {e}")

    async def disconnect_async(self) -> None:
        """异步断开 Redis 连接"""
        if self.redis_client:
            try:
                await self.redis_client.close()
                if self.connection_pool:
                    await self.connection_pool.disconnect()
            except Exception as e:
                self._logger.warning(f"断开 Redis 连接时出错: {e}")
            finally:
                self.redis_client = None
                self.connection_pool = None
                self._connection_info = {}
                self._logger.info("Redis 连接已断开")

    async def start_async(self) -> None:
        """异步启动组件"""
        self._logger.info(f"正在启动 {self.name} 组件...")

        if not self.config.enabled:
            self._logger.info("Redis 缓存功能已禁用，跳过启动")
            self._status = ComponentStatus.RUNNING
            return

        # 如果未连接，尝试连接
        if not self.is_connected():
            await self.connect_async()

        self._status = ComponentStatus.RUNNING
        self._logger.info(f"✓ {self.name} 组件启动成功")

    async def stop_async(self) -> None:
        """异步停止组件"""
        self._logger.info(f"正在停止 {self.name} 组件...")

        # 断开连接
        await self.disconnect_async()

        self._status = ComponentStatus.STOPPED
        self._logger.info(f"✓ {self.name} 组件已停止")

    async def health_check_async(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            'status': 'unknown',
            'connected': self.is_connected(),
            'details': {}
        }

        if not self.is_connected():
            health['status'] = 'disconnected'
            health['error'] = self._disconnect_reason or 'Redis 未连接'
            return health

        try:
            # Ping 测试
            start_time = time.perf_counter()
            await self.redis_client.ping()
            ping_time = (time.perf_counter() - start_time) * 1000

            # 获取 Redis 信息
            info = await self.redis_client.info()

            health['status'] = 'healthy'
            health['details'] = {
                'ping_ms': round(ping_time, 2),
                'version': info.get('redis_version', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'unknown'),
                'used_memory_peak_human': info.get('used_memory_peak_human', 'unknown'),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0)
            }

            self._last_health_check = datetime.now().isoformat()

        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            # 根据错误类型使用不同的日志级别
            error_str = str(e)
            if "connecting to" in error_str or "Connect call failed" in error_str or "拒绝网络连接" in error_str:
                self._logger.debug(f"Redis 连接不可用: {e}")
            else:
                self._logger.warning(f"Redis 健康检查异常: {e}")

        return health

    def get_status_info(self) -> Dict[str, Any]:
        """获取组件状态信息"""
        # 获取基础状态信息
        info = super().get_status_info()

        # 添加缓存组件特定的状态信息
        info.update({
            'connection_status': 'connected' if self.is_connected() else 'disconnected',
            'connected': self.is_connected(),  # 添加布尔值方便前端使用
            'config': {
                'host': self.config.host,
                'port': self.config.port,
                'db': self.config.db,
                'pool_size': getattr(self.config, 'poolSize', 10) or getattr(self.config, 'pool_size', 10),
                'enabled': self.config.enabled,
                'auto_connect': getattr(self.config, 'auto_connect', True)
            },
            'connection_info': self._connection_info,
            'last_health_check': self._last_health_check,
            'disconnect_reason': self._disconnect_reason,
            'health': {
                'status': 'healthy' if self.is_connected() else 'disconnected',
                'connected': self.is_connected()
            }
        })
        return info

    async def execute_command(self, command: str, *args, **kwargs) -> Any:
        """执行 Redis 命令"""
        if not self.is_connected():
            raise RuntimeError("Redis 未连接")

        try:
            # 获取 Redis 命令方法
            cmd_func = getattr(self.redis_client, command.lower())
            if not cmd_func:
                raise ValueError(f"不支持的 Redis 命令: {command}")

            # 执行命令
            result = await cmd_func(*args, **kwargs)
            return result

        except Exception as e:
            self._logger.error(f"执行 Redis 命令 {command} 失败: {e}")
            raise
