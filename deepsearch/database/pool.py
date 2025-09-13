"""
数据库连接池管理模块

提供高效的数据库连接池管理，支持 PostgreSQL、MySQL 和 SQLite
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Dict, Any
import time

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy import event, pool
from loguru import logger

from deepsearch.config import get_config


class DatabasePool:
    """
    数据库连接池管理器
    
    提供高效的连接池管理，支持：
    - 连接池配置优化
    - 健康检查
    - 连接回收
    - 性能监控
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据库连接池
        
        Args:
            config: 数据库配置字典，如果为None则从全局配置获取
        """
        if config is None:
            settings = get_config()
            config = settings.database.main.model_dump() if hasattr(settings, 'database') else {}
        
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
        
        # 连接池统计
        self.stats = {
            'connections_created': 0,
            'connections_recycled': 0,
            'connections_failed': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'total_queries': 0,
            'slow_queries': 0,
            'last_health_check': None
        }
        
        # 性能配置
        self.pool_size = config.get('pool_size', 50)
        self.max_overflow = config.get('max_overflow', 20)
        self.pool_timeout = config.get('pool_timeout', 30)
        self.pool_recycle = config.get('pool_recycle', 3600)
        self.echo_pool = config.get('echo_pool', False)
        
    async def initialize(self) -> bool:
        """
        初始化数据库连接池
        
        Returns:
            是否初始化成功
        """
        if self._initialized:
            return True
        
        try:
            # 构建数据库URL
            db_url = self._build_database_url()
            if not db_url:
                logger.warning("数据库未配置或已禁用")
                return False
            
            # 根据数据库类型选择连接池策略
            pool_class = self._get_pool_class()
            
            # 创建异步引擎
            self.engine = create_async_engine(
                db_url,
                poolclass=pool_class,
                pool_size=self.pool_size if pool_class == QueuePool else None,
                max_overflow=self.max_overflow if pool_class == QueuePool else None,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                echo_pool=self.echo_pool,
                # 连接参数
                connect_args={
                    "server_settings": {
                        "jit": "off",  # 关闭JIT以提高稳定性
                        "application_name": "DeepSearch"
                    },
                    "command_timeout": 60,
                    "connection_timeout": 10,
                } if 'postgresql' in db_url else {}
            )
            
            # 设置连接池事件监听
            self._setup_pool_events()
            
            # 创建会话工厂
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
            
            # 测试连接
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda c: c.execute("SELECT 1"))
            
            self._initialized = True
            logger.info(f"数据库连接池初始化成功 - 池大小: {self.pool_size}, 最大溢出: {self.max_overflow}")
            return True
            
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            self.stats['connections_failed'] += 1
            return False
    
    def _build_database_url(self) -> Optional[str]:
        """构建数据库连接URL"""
        if not self.config.get('enabled', True):
            return None
        
        db_type = self.config.get('type', 'postgresql')
        
        # SQLite
        if db_type == 'sqlite':
            path = self.config.get('path', './data/deepsearch.db')
            return f"sqlite+aiosqlite:///{path}"
        
        # PostgreSQL
        elif db_type == 'postgresql':
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 5432)
            database = self.config.get('database', 'deepsearch')
            username = self.config.get('username', 'postgres')
            password = self.config.get('password', '')
            
            # 处理加密密码
            if password and password.startswith('encrypted:'):
                try:
                    from deepsearch.config.crypto import decrypt_password
                    password = decrypt_password(password[10:])
                except Exception as e:
                    logger.warning(f"密码解密失败: {e}")
            
            if password:
                return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
            return f"postgresql+asyncpg://{username}@{host}:{port}/{database}"
        
        # MySQL
        elif db_type == 'mysql':
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 3306)
            database = self.config.get('database', 'deepsearch')
            username = self.config.get('username', 'root')
            password = self.config.get('password', '')
            
            if password:
                return f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database}"
            return f"mysql+aiomysql://{username}@{host}:{port}/{database}"
        
        return None
    
    def _get_pool_class(self):
        """根据数据库类型选择合适的连接池类"""
        db_type = self.config.get('type', 'postgresql')
        
        if db_type == 'sqlite':
            # SQLite 使用静态池（单连接）
            return StaticPool
        elif db_type in ['postgresql', 'mysql']:
            # PostgreSQL 和 MySQL 使用队列池
            return QueuePool
        else:
            # 默认使用空池（每次创建新连接）
            return NullPool
    
    def _setup_pool_events(self):
        """设置连接池事件监听"""
        if not self.engine:
            return
        
        # 监听连接创建事件
        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            self.stats['connections_created'] += 1
            connection_record.info['connect_time'] = time.time()
            logger.debug(f"数据库连接创建 - 总连接数: {self.stats['connections_created']}")
        
        # 监听连接回收事件
        @event.listens_for(self.engine.sync_engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            self.stats['idle_connections'] = self.stats.get('idle_connections', 0) + 1
            self.stats['active_connections'] = max(0, self.stats.get('active_connections', 0) - 1)
        
        # 监听连接检出事件
        @event.listens_for(self.engine.sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            self.stats['active_connections'] = self.stats.get('active_connections', 0) + 1
            self.stats['idle_connections'] = max(0, self.stats.get('idle_connections', 0) - 1)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话
        
        使用上下文管理器自动管理会话生命周期
        
        Yields:
            AsyncSession: 数据库会话
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.session_factory:
            raise RuntimeError("数据库连接池未初始化")
        
        async with self.session_factory() as session:
            try:
                self.stats['total_queries'] += 1
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"数据库会话错误: {e}")
                raise
            finally:
                await session.close()
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        执行数据库查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果
        """
        async with self.get_session() as session:
            result = await session.execute(query, params or {})
            return result.fetchall()
    
    async def health_check(self) -> bool:
        """
        执行健康检查
        
        Returns:
            数据库是否健康
        """
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda c: c.execute("SELECT 1"))
            
            self.stats['last_health_check'] = time.time()
            return True
            
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            self.stats['connections_failed'] += 1
            return False
    
    async def close(self):
        """关闭数据库连接池"""
        if self.engine:
            await self.engine.dispose()
            self._initialized = False
            logger.info("数据库连接池已关闭")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.stats.copy()
        
        # 添加连接池状态
        if self.engine and hasattr(self.engine.pool, 'status'):
            stats['pool_status'] = self.engine.pool.status()
        
        return stats


# 全局连接池实例
_global_pool: Optional[DatabasePool] = None


async def get_database_pool() -> DatabasePool:
    """
    获取全局数据库连接池实例
    
    Returns:
        DatabasePool: 数据库连接池
    """
    global _global_pool
    
    if _global_pool is None:
        _global_pool = DatabasePool()
        await _global_pool.initialize()
    
    return _global_pool


async def close_database_pool():
    """关闭全局数据库连接池"""
    global _global_pool
    
    if _global_pool:
        await _global_pool.close()
        _global_pool = None