"""
AmazingData Dask Actor

简化版 Actor - 只作为状态容器，不包含业务逻辑。
在 Windows Worker 上保持 AmazingData SDK 登录状态。

架构设计:
- Actor 只持有 SDK 实例引用和登录状态
- 提供简单的 call() 方法代理，不包含缓存/熔断逻辑
- 业务逻辑、缓存、熔断器都在 Adapter/Provider 层
- 保留分布式会话管理（AmazingData SDK 特殊需求）

延迟初始化模式（v2.0）:
- initialize() 只做轻量级准备（<100ms），不执行登录
- 首次 call() 时自动触发登录（~15秒）
- 解决 Dask Plugin 注册超时问题（原 ~15s → 现 <100ms）
- 使用双重检查锁防止并发登录

Usage:
    # 由 Plugin 自动创建和管理
    actor = AmazingDataActor(config)
    await actor.initialize()  # 轻量级初始化（<100ms）
    data = await actor.call("query_kline", code_list=["600000.SH"], ...)  # 首次调用触发登录
    await actor.shutdown()
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from core.utils.timeout import DataSourceState, get_timeout_manager
from loguru import logger

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

_ACTOR_ID = "AMAZINGDATA_ACTOR"
_SOURCE_NAME = "amazingdata"
_SDK_TIMEOUT_SECONDS = 30.0

_T = TypeVar("_T")


class AmazingDataActor:
    """AmazingData Dask Actor - 状态容器

    简化的 Actor 实现，只负责:
    1. 持有 SDK 实例引用（BaseData, MarketData, InfoData）
    2. 管理登录状态和分布式会话
    3. 提供方法调用代理
    4. 管理资源生命周期

    不包含:
    - ❌ 缓存逻辑 (由 Adapter 层负责)
    - ❌ 熔断器逻辑 (由 Provider 层负责)
    - ❌ 业务方法 (由 Adapter 层通过 call() 访问)
    - ❌ 心跳任务 (由 Plugin teardown 管理)

    Example:
        >>> actor = AmazingDataActor(config)
        >>> await actor.initialize()
        >>> data = await actor.call("query_kline", code_list=["600000.SH"])
        >>> await actor.shutdown()
    """

    # 类级别方法配置：外部接口 -> (SDK方法名, 允许的参数)
    # 元组格式: (目标方法名, 允许的参数集合)，None 表示不过滤参数
    METHOD_CONFIG: dict[str, tuple[str, frozenset[str] | None]] = {
        "get_stock_list": ("get_code_list", frozenset({"security_type"})),
    }

    # 类级别缓存：交易日历（一年只变一次，可跨实例共享）
    _calendar_cache: Any = None
    _calendar_cache_time: float = 0
    _CALENDAR_CACHE_TTL: float = 86400  # 24 小时缓存有效期（有效数据）
    _EMPTY_CACHE_TTL: float = 300  # 5 分钟缓存有效期（空数据，允许快速重试恢复）

    # 注意: Redis 同步连接池已改为实例级别（见 __init__）
    # 原因: 类级别缓存不随实例释放，可能导致内存泄漏

    def __init__(self, config: dict[str, Any] | None = None):
        """初始化 Actor

        Args:
            config: 配置字典，包含：
                - username: AmazingData 用户名
                - password: AmazingData 密码
                - host: 服务器地址
                - port: 服务器端口
                - redis_url: Redis URL (用于分布式会话)
                - prewarm: 是否在后台预热登录（默认 False）
        """
        self._config = config or {}

        # 核心状态
        self._logged_in = False
        self._login_lock: asyncio.Lock | None = None  # 延迟创建，避免跨事件循环问题
        self._last_activity = time.time()

        # SDK 引用
        self._sdk: Any = None
        self._base_data: Any = None  # BaseData 实例
        self._market_data: Any = None  # MarketData 实例
        self._info_data: Any = None  # InfoData 实例
        self._tgw: Any = None  # TGW 实例（可选，用于实时行情）

        # 方法路由映射（自动发现）
        self._method_routes: dict[str, str] = (
            {}
        )  # 方法名 -> SDK对象类型 ("base_data"|"market_data"|"info_data")

        # 分布式会话管理（AmazingData SDK 特性）
        self._redis: AsyncRedis | None = None
        self._redis_url = self._config.get("redis_url", "redis://localhost:6379")
        self._worker_id = f"amazingdata-actor-{os.getpid()}"
        self._session_key = "amazingdata:session"
        self._session_ttl = 60  # 秒

        # 实例级别 Redis 同步连接池（从类级别改为实例级别，确保随实例释放）
        self._sync_redis_pool: Any = None  # redis.ConnectionPool
        self._sync_redis_pool_url: str | None = None  # 用于检测 URL 变化

        logger.info(
            "[{}] AmazingDataActor 实例已创建 | worker_id={} | redis_url={}",
            _ACTOR_ID,
            self._worker_id,
            self._redis_url,
        )

    # ==================== 基础属性 ====================

    @property
    def name(self) -> str:
        """数据源名称"""
        return "amazingdata"

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._logged_in

    @property
    def METHOD_ALIASES(self) -> dict[str, str]:
        """向后兼容：返回方法别名映射（仅方法名）"""
        return {k: v[0] for k, v in self.METHOD_CONFIG.items()}

    # ==================== 初始化（延迟登录）====================

    async def initialize(self) -> bool:
        """初始化 Actor - 轻量级准备（延迟登录）

        采用延迟初始化模式：
        - 此方法只做轻量级准备工作（<100ms）
        - 实际登录延迟到首次 call() 调用时执行
        - 解决 Dask Plugin 注册超时问题（原耗时 ~15s，现 <100ms）

        Returns:
            初始化是否成功（始终返回 True）
        """
        logger.info("[{}] 开始轻量级初始化（延迟登录模式）...", _ACTOR_ID)

        try:
            # 1. 初始化 Redis 连接（用于分布式会话，快速操作）
            redis_ok = await self._init_redis()
            if not redis_ok:
                logger.warning("[{}] Redis 连接失败，跨平台会话将不可用", _ACTOR_ID)

            # 2. 可选：同步预热登录（阻塞 setup，消除首次调用延迟）
            if self._config.get("prewarm", False):
                logger.info("[{}] 开始同步预热登录（阻塞直到完成）...", _ACTOR_ID)
                await self._ensure_logged_in()
                logger.info("[{}] 同步预热登录完成，首次调用无延迟", _ACTOR_ID)
            else:
                logger.info("[{}] 轻量级初始化完成（登录将在首次调用时执行）", _ACTOR_ID)
            return True

        except Exception as e:
            logger.error("[{}] 初始化异常: {}", _ACTOR_ID, e)
            # 即使 Redis 失败也返回成功，登录可以独立工作
            return True

    async def _prewarm_login(self) -> None:
        """后台预热登录（不阻塞主流程）"""
        try:
            await self._ensure_logged_in()
            logger.info("[{}] 后台预热登录完成", _ACTOR_ID)
        except Exception as e:
            logger.warning("[{}] 后台预热登录失败: {}", _ACTOR_ID, e)

    async def _ensure_logged_in(self) -> None:
        """确保已登录（延迟初始化核心方法）

        使用双重检查锁模式，确保：
        1. 只有首次调用时执行登录
        2. 并发调用时不会重复登录
        3. 登录完成后快速返回

        Raises:
            RuntimeError: 登录失败时抛出
        """
        # 快速路径：已登录直接返回
        if self._logged_in:
            return

        # 延迟创建锁（避免跨事件循环问题）
        if self._login_lock is None:
            self._login_lock = asyncio.Lock()

        # 获取锁，执行登录
        async with self._login_lock:
            # 双重检查：可能在等待锁期间其他协程已完成登录
            if self._logged_in:
                return

            logger.info("[{}] 首次调用，开始延迟登录...", _ACTOR_ID)

            # 注意：不在此处调用 _check_distributed_session() 复用会话
            # 原因：此方法可能在 call_sync() 的临时事件循环中被调用，
            #      而 Redis 客户端绑定到 initialize() 时的主事件循环，
            #      跨循环调用会导致 "Future attached to a different loop" 错误，
            #      即使捕获异常也可能污染事件循环状态，导致后续操作失败

            # 直接执行完整登录
            login_ok = await self._login()
            if not login_ok:
                raise RuntimeError("AmazingData SDK 登录失败")

            logger.info("[{}] 延迟登录完成", _ACTOR_ID)

    async def _init_redis(self) -> bool:
        """初始化 Redis 连接（用于分布式会话）"""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.debug("[{}] Redis 连接成功 | url={}", _ACTOR_ID, self._redis_url)
            return True
        except ImportError:
            logger.debug("[{}] redis 包不可用", _ACTOR_ID)
            return False
        except Exception as e:
            logger.debug("[{}] Redis 连接失败: {}", _ACTOR_ID, e)
            return False

    async def _check_distributed_session(self) -> bool:
        """检查 Redis 中是否存在有效的分布式会话"""
        if self._redis is None:
            return False

        try:
            session_data = await self._redis.get(self._session_key)
            if not session_data:
                return False

            session = json.loads(session_data)
            if not session.get("logged_in"):
                return False

            # 检查心跳是否过期
            heartbeat_str = session.get("heartbeat", "")
            if not heartbeat_str:
                return False

            heartbeat_time = datetime.fromisoformat(heartbeat_str)
            age = (datetime.now() - heartbeat_time).total_seconds()

            if age > self._session_ttl:
                logger.warning("[{}] 分布式会话已过期 | age={:.1f}s", _ACTOR_ID, age)
                return False

            logger.info("[{}] 发现有效分布式会话 | age={:.1f}s", _ACTOR_ID, age)
            return True

        except Exception as e:
            logger.warning("[{}] 检查分布式会话失败: {}", _ACTOR_ID, e)
            return False

    @staticmethod
    def _resolve_sdk_module() -> Any:
        """统一解析 AmazingData SDK 模块并校验可用性。"""
        from core.infrastructure.providers.implementations.amazingdata._sdk_loader import (
            HAS_AMAZINGDATA,
            IMPORT_ERROR,
            ad,
        )

        if not HAS_AMAZINGDATA or ad is None:
            detail = str(IMPORT_ERROR) if IMPORT_ERROR else "unknown import error"
            raise RuntimeError(f"AmazingData SDK 不可用: {detail}")
        return ad

    async def _init_sdk_objects_without_login(self) -> bool:
        """初始化 SDK 数据对象（不调用 login，复用会话）"""
        try:
            sdk = self._resolve_sdk_module()

            self._sdk = sdk
            self._base_data = sdk.BaseData()  # type: ignore[misc]

            # 获取交易日历（优先使用缓存）
            calendar = await self._get_calendar_cached()

            self._market_data = sdk.MarketData(calendar) if calendar else None  # type: ignore[misc]
            self._info_data = sdk.InfoData()  # type: ignore[misc]

            self._logged_in = True
            self._last_activity = time.time()

            # 注意：不在此处调用 _update_session_heartbeat()
            # 原因：此方法可能在 call_sync() 的临时事件循环中被调用，
            #      而 Redis 客户端绑定到 initialize() 时的主事件循环
            # 会话状态已在原始登录时通过 _publish_session_state() 发布

            logger.info("[{}] SDK 数据对象初始化成功（复用会话）", _ACTOR_ID)
            return True

        except Exception as e:
            logger.warning("[{}] SDK 对象初始化失败: {}", _ACTOR_ID, e)
            return False

    async def _get_calendar_cached(self) -> Any:
        """获取交易日历（带类级别缓存）

        交易日历一年只变一次，可以安全缓存 24 小时。
        跨实例共享缓存，避免重复调用 SDK。

        缓存策略：
        - 有效数据：24 小时 TTL（_CALENDAR_CACHE_TTL）
        - 空数据：5 分钟 TTL（_EMPTY_CACHE_TTL），允许快速重试恢复

        Returns:
            交易日历数据（list 格式）
        """
        # 检查缓存是否有效（差异化 TTL：空数据用短 TTL，有效数据用长 TTL）
        if AmazingDataActor._calendar_cache_time > 0:
            cache_age = time.time() - AmazingDataActor._calendar_cache_time
            cache_is_empty = not AmazingDataActor._calendar_cache
            effective_ttl = self._EMPTY_CACHE_TTL if cache_is_empty else self._CALENDAR_CACHE_TTL

            if cache_age < effective_ttl:
                if cache_is_empty:
                    logger.debug(
                        "[{}] 缓存命中（空数据）| age={:.1f}s | ttl={:.0f}s",
                        _ACTOR_ID,
                        cache_age,
                        effective_ttl,
                    )
                else:
                    logger.debug(
                        "[{}] 使用缓存的交易日历 | age={:.1f}s",
                        _ACTOR_ID,
                        cache_age,
                    )
                return AmazingDataActor._calendar_cache

        # 缓存无效，重新获取
        logger.info("[{}] 缓存未命中，从 SDK 获取交易日历...", _ACTOR_ID)
        calendar = await self._run_sdk_with_timeout(
            lambda: self._base_data.get_calendar(),
            "BaseData.get_calendar",
            timeout=30.0,  # 增加超时时间，网络波动时需要更长时间
        )

        # 标准化数据格式
        if isinstance(calendar, dict):
            calendar = calendar.get("data", calendar.get("calendar", []))

        # 更新类级别缓存
        AmazingDataActor._calendar_cache = calendar
        AmazingDataActor._calendar_cache_time = time.time()
        logger.info("[{}] 交易日历已缓存 | 记录数={}", _ACTOR_ID, len(calendar) if calendar else 0)

        return calendar

    async def _login(self) -> bool:
        """执行 AmazingData SDK 登录"""
        import time as time_module

        overall_start = time_module.time()
        timeout_manager = get_timeout_manager()

        username = self._config.get("username")
        password = self._config.get("password")
        host = self._config.get("host", "101.230.159.234")
        port = self._config.get("port", 8600)

        if not username or not password:
            logger.error("[{}] 缺少登录凭据", _ACTOR_ID)
            return False

        logger.info(
            "[{}] === 开始完整登录流程 === | host={}:{} | username={}",
            _ACTOR_ID,
            host,
            port,
            username,
        )

        # 设置连接状态（登录可能需要 30-60 秒）
        timeout_manager.set_state(_SOURCE_NAME, DataSourceState.CONNECTING, "sdk_login")

        try:
            # 步骤 1: 导入 SDK
            step_start = time_module.time()
            logger.info("[{}] [步骤1/5] 导入 AmazingData SDK...", _ACTOR_ID)
            sdk = self._resolve_sdk_module()

            logger.info(
                "[{}] [步骤1/5] SDK 导入成功 | 耗时={:.3f}s",
                _ACTOR_ID,
                time_module.time() - step_start,
            )

            # 步骤 1.5: 预清理 - 先 logout 释放可能残留的连接
            # AmazingData SDK 限制同一账户的并发连接数，如果之前进程异常退出，
            # 连接可能没有被正确释放，导致 "Connections exceed max limitation" 错误
            # 注意：超时从 5.0 缩短到 1.0，logout 通常很快完成
            step_start = time_module.time()
            logger.info("[{}] [步骤1.5/5] 预清理: 尝试 logout 释放残留连接...", _ACTOR_ID)
            try:
                # sdk.logout() 需要 username 参数
                await self._run_sdk_with_timeout(
                    lambda: sdk.logout(username),
                    "sdk.logout (预清理)",
                    timeout=1.0,  # 从 5.0 缩短到 1.0（logout 通常很快）
                )
                logger.info(
                    "[{}] [步骤1.5/5] 预清理 logout 完成 | 耗时={:.3f}s",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                )
            except Exception as e:
                # 预清理失败不影响后续登录，仅记录日志
                logger.debug(
                    "[{}] [步骤1.5/5] 预清理 logout 跳过（可能无残留连接）| 耗时={:.3f}s | 原因={}",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                    str(e),
                )

            # 步骤 2: 调用 sdk.login()
            step_start = time_module.time()
            logger.info(
                "[{}] [步骤2/5] 调用 sdk.login() | host={}:{} | username={}",
                _ACTOR_ID,
                host,
                port,
                username,
            )
            try:
                await self._run_sdk_with_timeout(
                    lambda: sdk.login(username=username, password=password, host=host, port=port),
                    "sdk.login",
                    timeout=30.0,
                )
                logger.info(
                    "[{}] [步骤2/5] sdk.login() 成功 | 耗时={:.3f}s",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "[{}] [步骤2/5] sdk.login() 超时 | 耗时={:.3f}s | timeout=30s",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                )
                raise
            except Exception as e:
                logger.error(
                    "[{}] [步骤2/5] sdk.login() 失败 | 耗时={:.3f}s | 错误={}",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                    str(e),
                )
                raise

            self._sdk = sdk

            # 步骤 3: 初始化 BaseData
            step_start = time_module.time()
            logger.info("[{}] [步骤3/5] 初始化 sdk.BaseData()...", _ACTOR_ID)
            self._base_data = sdk.BaseData()  # type: ignore[misc]
            logger.info(
                "[{}] [步骤3/5] BaseData 初始化成功 | 耗时={:.3f}s",
                _ACTOR_ID,
                time_module.time() - step_start,
            )

            # 步骤 4: 获取交易日历（优先使用缓存）
            step_start = time_module.time()
            logger.info("[{}] [步骤4/5] 获取交易日历（优先使用缓存）...", _ACTOR_ID)
            try:
                calendar = await self._get_calendar_cached()
                calendar_count = len(calendar) if calendar else 0
                logger.info(
                    "[{}] [步骤4/5] 交易日历获取完成 | 耗时={:.3f}s | 记录数={}",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                    calendar_count,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "[{}] [步骤4/5] get_calendar() 超时 | 耗时={:.3f}s | timeout=10s",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                )
                raise
            except Exception as e:
                logger.error(
                    "[{}] [步骤4/5] get_calendar() 失败 | 耗时={:.3f}s | 错误={}",
                    _ACTOR_ID,
                    time_module.time() - step_start,
                    str(e),
                )
                raise

            # 步骤 5: 初始化其他数据对象
            step_start = time_module.time()
            logger.info("[{}] [步骤5/5] 初始化 MarketData 和 InfoData...", _ACTOR_ID)
            self._market_data = sdk.MarketData(calendar) if calendar else None  # type: ignore[misc]
            self._info_data = sdk.InfoData()  # type: ignore[misc]
            logger.info(
                "[{}] [步骤5/5] 数据对象初始化成功 | 耗时={:.3f}s",
                _ACTOR_ID,
                time_module.time() - step_start,
            )

            # 更新状态
            self._logged_in = True
            self._last_activity = time.time()

            # 登录完成，恢复 IDLE 状态
            timeout_manager.set_state(_SOURCE_NAME, DataSourceState.IDLE)

            # 注意：不在此处调用 _publish_session_state()
            # 原因：此方法可能在 call_sync() 的临时事件循环中被调用，
            #      而 Redis 客户端绑定到 initialize() 时的主事件循环
            # 分布式会话功能暂时禁用，避免跨事件循环问题

            total_elapsed = time_module.time() - overall_start
            logger.info("[{}] === 登录流程完成 === | 总耗时={:.3f}s", _ACTOR_ID, total_elapsed)
            return True

        except ImportError as e:
            # 登录失败，设置错误状态
            timeout_manager.set_state(_SOURCE_NAME, DataSourceState.ERROR, "import_error")
            logger.error(
                "[{}] 无法导入 AmazingData SDK | 错误={} | 总耗时={:.3f}s",
                _ACTOR_ID,
                e,
                time_module.time() - overall_start,
            )
            return False
        except Exception as e:
            # 登录失败，设置错误状态
            timeout_manager.set_state(_SOURCE_NAME, DataSourceState.ERROR, "login_error")
            logger.error(
                "[{}] 登录流程异常 | 错误={} | 总耗时={:.3f}s",
                _ACTOR_ID,
                e,
                time_module.time() - overall_start,
                exc_info=True,
            )
            return False

    async def _publish_session_state(self) -> None:
        """发布会话状态到 Redis"""
        if self._redis is None:
            return

        try:
            session = {
                "logged_in": True,
                "holder_id": self._worker_id,
                "login_time": datetime.now().isoformat(),
                "heartbeat": datetime.now().isoformat(),
                "source": "AmazingDataActor",
            }
            await self._redis.set(
                self._session_key,
                json.dumps(session),
                ex=self._session_ttl * 2,
            )
            logger.debug("[{}] 已发布会话状态到 Redis", _ACTOR_ID)
        except Exception as e:
            logger.warning("[{}] 发布会话状态失败: {}", _ACTOR_ID, e)

    async def _update_session_heartbeat(self) -> None:
        """更新 Redis 中的会话心跳时间戳"""
        if self._redis is None:
            return

        try:
            session_data = await self._redis.get(self._session_key)
            if session_data:
                session = json.loads(session_data)
                session["heartbeat"] = datetime.now().isoformat()
                await self._redis.set(
                    self._session_key,
                    json.dumps(session),
                    ex=self._session_ttl * 2,
                )
        except Exception as e:
            logger.debug("[{}] 更新心跳失败: {}", _ACTOR_ID, e)

    # 内存监控：上次记录时间和调用计数器
    _last_memory_log_time: float = 0
    _memory_check_count: int = 0
    _MEMORY_LOG_INTERVAL: float = 60.0  # 每 60 秒记录一次内存使用

    def _check_memory_pressure(self, threshold: float = 0.80) -> bool:
        """检查内存压力，必要时触发 GC

        当 Worker 内存使用超过阈值时，主动触发垃圾回收，
        防止内存持续增长导致 OOM。

        增强功能：
        - 定期记录内存使用日志（每 60 秒）
        - 显示更详细的内存信息（RSS、VMS、系统可用）
        - 记录调用次数，便于追踪内存增长趋势

        Args:
            threshold: 内存使用阈值（0.0-1.0），默认 80%

        Returns:
            True 如果触发了 GC，False 否则
        """
        import gc

        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()

            # 获取系统可用内存
            virtual_mem = psutil.virtual_memory()

            # 计算当前进程内存占系统可用内存的比例
            rss_gb = memory_info.rss / (1024**3)
            vms_gb = memory_info.vms / (1024**3)
            memory_ratio = memory_info.rss / virtual_mem.total

            # 增加调用计数
            AmazingDataActor._memory_check_count += 1

            # 定期记录内存使用日志（每 60 秒或首次调用）
            current_time = time.time()
            should_log = (
                current_time - AmazingDataActor._last_memory_log_time > self._MEMORY_LOG_INTERVAL
                or AmazingDataActor._last_memory_log_time == 0
            )

            if should_log:
                AmazingDataActor._last_memory_log_time = current_time
                logger.info(
                    "[{}] Worker 内存监控 | "
                    "RSS={:.2f}GB | VMS={:.2f}GB | 系统占比={:.1%} | "
                    "系统可用={:.1f}GB | 检查次数={}",
                    _ACTOR_ID,
                    rss_gb,
                    vms_gb,
                    memory_ratio,
                    virtual_mem.available / (1024**3),
                    AmazingDataActor._memory_check_count,
                )

            if memory_ratio > threshold:
                # 触发垃圾回收
                collected = gc.collect()
                # 再次获取内存信息，查看 GC 效果
                memory_after = process.memory_info()
                freed_mb = (memory_info.rss - memory_after.rss) / (1024**2)
                logger.warning(
                    "[{}] 内存压力告警，已触发 GC | "
                    "GC 前={:.2f}GB | GC 后={:.2f}GB | 释放={:.1f}MB | "
                    "回收对象={} | 阈值={:.0%}",
                    _ACTOR_ID,
                    rss_gb,
                    memory_after.rss / (1024**3),
                    freed_mb,
                    collected,
                    threshold,
                )
                return True

            return False

        except ImportError:
            # psutil 不可用时跳过检查
            return False
        except Exception as e:
            logger.debug("[{}] 内存压力检查失败: {}", _ACTOR_ID, e)
            return False

    # ==================== 核心方法代理 ====================

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """通用方法调用 - 简单代理，不包含缓存/熔断逻辑

        自动路由到 BaseData/MarketData/InfoData。
        供 RPC Client 通过 worker.actors["amazingdata"].call() 调用。

        采用延迟初始化模式：首次调用时自动触发登录。
        支持位置参数和关键字参数混用，自动使用 inspect.signature() 转换。

        Args:
            method: SDK 方法名 (如 "query_kline", "get_stock_basic")
            *args: 位置参数（会自动转换为关键字参数）
            **kwargs: 关键字参数

        Returns:
            API 返回数据（已标准化为可序列化格式）

        Raises:
            RuntimeError: 登录失败或方法不存在
        """
        # 内存压力检查：超过 80% 时触发 GC
        self._check_memory_pressure(threshold=0.80)

        # 延迟初始化：首次调用时自动登录
        await self._ensure_logged_in()

        # 在入口处统一转换别名并过滤参数
        config = self.METHOD_CONFIG.get(method)
        if config:
            actual_method, allowed_params = config
            if allowed_params is not None:
                # 过滤掉 SDK 不支持的参数
                kwargs = {k: v for k, v in kwargs.items() if k in allowed_params}
        else:
            actual_method = method

        self._last_activity = time.time()

        # 注意：不在此处调用 _update_session_heartbeat()
        # 原因：Redis 客户端绑定到 initialize() 时的事件循环，
        #      call_sync() 创建的临时循环会导致 "Event loop is closed" 错误
        # 心跳已在 _login() 成功后通过 _publish_session_state() 发布

        # 路由到对应的 SDK 对象（使用转换后的方法名）
        sdk_obj = self._route_method(actual_method)
        if sdk_obj is None:
            raise RuntimeError(f"Method '{actual_method}' not found in any SDK object")

        # 如果有位置参数，使用 inspect.signature() 转换为关键字参数
        if args:
            # 获取方法签名
            method_func = getattr(sdk_obj, actual_method, None)
            if method_func is None:
                raise RuntimeError(f"Method '{actual_method}' not found on SDK object")

            try:
                import inspect

                sig = inspect.signature(method_func)
                # 绑定位置参数和关键字参数
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                # 转换为纯关键字参数
                kwargs = dict(bound.arguments)
            except Exception as e:
                logger.warning(
                    "[{}] 无法使用 inspect.signature() 转换参数，使用原始参数 | method={} | 错误={}",
                    _ACTOR_ID,
                    actual_method,
                    e,
                )
                # 如果转换失败，保持原样（向后兼容）

        # 调用 SDK 方法（使用转换后的方法名，带超时保护）
        result = await self._call_sdk_method(sdk_obj, actual_method, kwargs)
        return self._to_records(result)

    def call_sync(
        self,
        method: str,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """同步版本的 call，供 Dask RPC 调用

        在 Dask Worker 的线程池中执行时使用此方法。
        内部创建临时事件循环来运行异步 call() 方法。

        如果提供了 task_id，会将结果存入 Redis，用于绕过 Dask Future 返回机制。
        这是为了解决 Dask tornado IOLoop 与 FastAPI asyncio 冲突的终极方案。

        Args:
            method: SDK 方法名 (如 "query_kline", "get_stock_basic")
            task_id: 可选的任务ID，如果提供则将结果存入 Redis
            **kwargs: 方法参数

        Returns:
            API 返回数据（已标准化为可序列化格式）

        Raises:
            RuntimeError: Actor 未登录或方法不存在

        Example:
            >>> # 在 Dask Worker 中使用
            >>> def remote_call(dask_worker):
            ...     actor = dask_worker.actors["amazingdata"]
            ...     return actor.call_sync("query_kline", code_list=["000001.SZ"])
        """
        import time as time_module

        start_time = time_module.time()
        logger.info(
            "[{}] call_sync 开始 | method={} | task_id={}",
            _ACTOR_ID,
            method,
            task_id,
        )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.call(method, **kwargs))
            elapsed = time_module.time() - start_time
            # 记录结果摘要（避免日志过大）
            result_summary = (
                f"len={len(result)}"
                if isinstance(result, (list, dict))
                else f"type={type(result).__name__}"
            )
            logger.info(
                "[{}] call_sync 完成 | method={} | 耗时={:.2f}s | result={}",
                _ACTOR_ID,
                method,
                elapsed,
                result_summary,
            )

            # 如果提供了 task_id，将结果存入 Redis（使用同步客户端）
            if task_id:
                self._store_result_to_redis_sync(task_id, result, method)

            return result
        except Exception as e:
            elapsed = time_module.time() - start_time
            logger.error(
                "[{}] call_sync 异常 | method={} | 耗时={:.2f}s | error={}",
                _ACTOR_ID,
                method,
                elapsed,
                str(e),
            )

            # 如果提供了 task_id，将错误存入 Redis（使用同步客户端）
            if task_id:
                self._store_error_to_redis_sync(task_id, str(e), method)

            raise
        finally:
            loop.close()

    async def _store_result_to_redis(
        self,
        task_id: str,
        result: Any,
        method: str,
    ) -> None:
        """将结果存入 Redis

        使用 JSON 序列化结果，存储到 Redis 中供 Client 轮询获取。
        这是绕过 Dask Future 返回机制的核心实现。

        Args:
            task_id: 任务唯一标识
            result: 调用结果
            method: 方法名（用于日志）
        """
        import json

        key = f"dask_result:{task_id}"
        data = {"status": "success", "result": result}

        try:
            # 使用 JSON 序列化，5分钟过期
            await self._redis.set(key, json.dumps(data), ex=300)  # type: ignore
            logger.info(
                "[{}] 结果已存入 Redis | task_id={} | method={}",
                _ACTOR_ID,
                task_id,
                method,
            )
        except Exception as e:
            logger.error(
                "[{}] 存储结果到 Redis 失败 | task_id={} | error={}",
                _ACTOR_ID,
                task_id,
                str(e),
            )

    async def _store_error_to_redis(
        self,
        task_id: str,
        error: str,
        method: str,
    ) -> None:
        """将错误存入 Redis

        Args:
            task_id: 任务唯一标识
            error: 错误信息
            method: 方法名（用于日志）
        """
        import json

        key = f"dask_result:{task_id}"
        data = {"status": "error", "error": error}

        try:
            await self._redis.set(key, json.dumps(data), ex=300)  # type: ignore
            logger.info(
                "[{}] 错误已存入 Redis | task_id={} | method={}",
                _ACTOR_ID,
                task_id,
                method,
            )
        except Exception as e:
            logger.error(
                "[{}] 存储错误到 Redis 失败 | task_id={} | error={}",
                _ACTOR_ID,
                task_id,
                str(e),
            )

    def _get_sync_redis(self, redis_url: str) -> Any:
        """获取同步 Redis 客户端（使用实例级别连接池）

        通过连接池复用连接，避免每次调用创建新连接导致的连接泄漏。
        连接池在实例级别管理，随实例 shutdown 时释放。

        Args:
            redis_url: Redis 连接 URL

        Returns:
            Redis 客户端实例（使用连接池）

        Raises:
            redis.ConnectionError: Redis 服务不可用时抛出
        """
        import redis

        # 如果 URL 变化或池未初始化，创建新池
        if self._sync_redis_pool is None or self._sync_redis_pool_url != redis_url:
            if self._sync_redis_pool is not None:
                try:
                    self._sync_redis_pool.disconnect()
                except Exception:
                    pass

            logger.info(
                "[{}] 创建 Redis 同步连接池 | url={}",
                _ACTOR_ID,
                redis_url,
            )

            try:
                self._sync_redis_pool = redis.ConnectionPool.from_url(  # type: ignore[attr-defined]
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=10,
                    socket_connect_timeout=5,  # 连接超时 5 秒
                )
                self._sync_redis_pool_url = redis_url

                # 立即测试连接，确保 Redis 服务可用
                test_client = redis.Redis(connection_pool=self._sync_redis_pool)
                test_client.ping()
                logger.info("[{}] Redis 连接测试成功", _ACTOR_ID)

            except redis.ConnectionError as e:  # type: ignore[attr-defined]
                logger.error(
                    "[{}] Redis 连接失败 | url={} | error={}",
                    _ACTOR_ID,
                    redis_url,
                    str(e),
                )
                # 清理失败的连接池
                self._sync_redis_pool = None
                self._sync_redis_pool_url = None
                raise

        return redis.Redis(connection_pool=self._sync_redis_pool)

    def _store_result_to_redis_sync(
        self,
        task_id: str,
        result: Any,
        method: str,
    ) -> None:
        """将结果存入 Redis（同步版本）

        使用类级别连接池复用 Redis 连接，避免连接泄漏。
        call_sync 创建临时事件循环，无法使用绑定到主循环的异步 Redis 客户端。

        Args:
            task_id: 任务唯一标识
            result: 调用结果
            method: 方法名（用于日志）
        """
        import json

        key = f"dask_result:{task_id}"
        data = {"status": "success", "result": result}

        logger.info(
            "[{}] 准备存储结果 | task_id={} | redis_url={} | key={}",
            _ACTOR_ID,
            task_id,
            self._redis_url,
            key,
        )

        try:
            # 使用连接池获取 Redis 客户端（连接自动归还池）
            sync_redis = self._get_sync_redis(self._redis_url)
            sync_redis.set(key, json.dumps(data), ex=300)
            # 注意：不调用 close()，连接由连接池管理
            logger.info(
                "[{}] 结果已存入 Redis (sync) | task_id={} | method={}",
                _ACTOR_ID,
                task_id,
                method,
            )
        except Exception as e:
            logger.error(
                "[{}] 存储结果到 Redis 失败 (sync) | task_id={} | error={}",
                _ACTOR_ID,
                task_id,
                str(e),
            )

    def _store_error_to_redis_sync(
        self,
        task_id: str,
        error: str,
        method: str,
    ) -> None:
        """将错误存入 Redis（同步版本）

        使用类级别连接池复用 Redis 连接，避免连接泄漏。

        Args:
            task_id: 任务唯一标识
            error: 错误信息
            method: 方法名（用于日志）
        """
        import json

        key = f"dask_result:{task_id}"
        data = {"status": "error", "error": error}

        try:
            # 使用连接池获取 Redis 客户端（连接自动归还池）
            sync_redis = self._get_sync_redis(self._redis_url)
            sync_redis.set(key, json.dumps(data), ex=300)
            # 注意：不调用 close()，连接由连接池管理
            logger.info(
                "[{}] 错误已存入 Redis (sync) | task_id={} | method={}",
                _ACTOR_ID,
                task_id,
                method,
            )
        except Exception as e:
            logger.error(
                "[{}] 存储错误到 Redis 失败 (sync) | task_id={} | error={}",
                _ACTOR_ID,
                task_id,
                str(e),
            )

    def _build_method_routes(self) -> None:
        """自动发现 SDK 对象的方法并建立路由映射

        扫描 BaseData、MarketData、InfoData 的所有公共方法，
        建立方法名到 SDK 对象类型的映射，避免硬编码维护。
        """
        if not self._logged_in:
            logger.warning("[{}] SDK 未登录，无法构建方法路由", _ACTOR_ID)
            return

        logger.info("[{}] 开始自动发现 SDK 方法路由...", _ACTOR_ID)

        # 扫描每个 SDK 对象的方法
        sdk_objects = [
            ("base_data", self._base_data),
            ("market_data", self._market_data),
            ("info_data", self._info_data),
        ]

        route_count = 0
        for obj_type, obj in sdk_objects:
            if obj is None:
                logger.debug("[{}] {} 对象未初始化，跳过", _ACTOR_ID, obj_type)
                continue

            # 获取对象的所有公共方法（不包括私有方法和魔术方法）
            methods = [
                name
                for name in dir(obj)
                if not name.startswith("_") and callable(getattr(obj, name, None))
            ]

            # 添加到路由映射
            for method in methods:
                # 如果方法已存在于其他对象中，跳过（优先级：base_data > market_data > info_data）
                if method not in self._method_routes:
                    self._method_routes[method] = obj_type
                    route_count += 1

        logger.info(
            "[{}] 方法路由构建完成 | 总计 {} 个方法 | base_data={} | market_data={} | info_data={}",
            _ACTOR_ID,
            route_count,
            len([v for v in self._method_routes.values() if v == "base_data"]),
            len([v for v in self._method_routes.values() if v == "market_data"]),
            len([v for v in self._method_routes.values() if v == "info_data"]),
        )

    def _route_method(self, method: str) -> Any | None:
        """路由方法到对应的 SDK 对象（使用自动发现的路由映射）

        Args:
            method: 方法名（已经过别名转换）

        Returns:
            对应的 SDK 对象，未找到返回 None
        """
        # 如果路由映射为空，说明是首次调用，需要构建路由
        if not self._method_routes:
            self._build_method_routes()

        # 从路由映射中查找
        obj_type = self._method_routes.get(method)

        if obj_type == "base_data":
            return self._base_data
        elif obj_type == "market_data":
            return self._market_data
        elif obj_type == "info_data":
            return self._info_data
        else:
            # 未找到路由，默认使用 InfoData（保持向后兼容）
            logger.warning(
                "[{}] 方法 '{}' 未在路由映射中找到，使用默认路由 (InfoData)",
                _ACTOR_ID,
                method,
            )
            return self._info_data

    async def _call_sdk_method(self, sdk_obj: Any, method: str, params: dict[str, Any]) -> Any:
        """调用 SDK 方法（带超时保护）

        Args:
            sdk_obj: SDK 对象
            method: 方法名
            params: 参数字典

        Returns:
            原始 SDK 结果
        """
        func = getattr(sdk_obj, method, None)
        if func is None:
            raise ValueError(f"Method '{method}' not found on SDK object")

        try:
            # 优先使用关键字参数调用（大多数 SDK 方法支持）
            return await self._run_sdk_with_timeout(
                lambda: func(**params), f"{sdk_obj.__class__.__name__}.{method}"
            )
        except TypeError as exc:
            # 某些 SDK 方法仅支持位置参数（不接受关键字参数），做一次兼容回退
            error_message = str(exc)
            if not params or len(params) != 1 or "unexpected keyword argument" not in error_message:
                raise

            param_keys = list(params.keys())
            positional_args = list(params.values())
            logger.warning(
                "[{}] SDK 方法关键字参数不兼容，回退为位置参数调用 | method={} | keys={}",
                _ACTOR_ID,
                method,
                param_keys,
            )
            return await self._run_sdk_with_timeout(
                lambda: func(*positional_args),
                f"{sdk_obj.__class__.__name__}.{method}(positional)",
            )

    async def _run_sdk_with_timeout(
        self,
        func: Callable[[], _T],
        method_name: str,
        timeout: float = _SDK_TIMEOUT_SECONDS,
    ) -> _T:
        """在线程池中执行阻塞式 SDK 调用，并应用超时保护

        SDK 方法可能阻塞，此方法通过 asyncio.to_thread 移至线程池，
        并用 wait_for 设置超时。

        Args:
            func: 零参数可调用对象，包装实际的 SDK 调用
            method_name: 方法名称（用于日志）
            timeout: 超时时间（秒）

        Returns:
            SDK 调用的返回值

        Raises:
            TimeoutError: 超时时抛出
        """
        import time

        start_time = time.time()
        logger.info(
            "[{}] 开始异步 SDK 调用 | method={} | timeout={}s",
            _ACTOR_ID,
            method_name,
            timeout,
        )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(func),
                timeout=timeout,
            )
            elapsed = time.time() - start_time
            logger.info(
                "[{}] SDK 调用成功 | method={} | 耗时={:.2f}s",
                _ACTOR_ID,
                method_name,
                elapsed,
            )
            return result
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(
                "[{}] SDK 调用超时 | method={} | 耗时={:.2f}s | timeout={}s",
                _ACTOR_ID,
                method_name,
                elapsed,
                timeout,
            )
            raise TimeoutError(f"SDK call '{method_name}' timed out after {timeout}s")
        except SystemExit as e:
            # AmazingData SDK 在登录失败时会调用 sys.exit()，这里捕获并转换为普通异常
            # 常见原因："Connections of this user exceed the max limitation"
            elapsed = time.time() - start_time
            logger.error(
                "[{}] SDK 调用触发 SystemExit（登录失败）| method={} | 耗时={:.2f}s | exit_code={}",
                _ACTOR_ID,
                method_name,
                elapsed,
                e.code,
            )
            raise RuntimeError(
                f"SDK call '{method_name}' failed with SystemExit({e.code}). "
                "This usually means login failed due to connection limit exceeded."
            ) from e
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "[{}] SDK 调用失败 | method={} | 耗时={:.2f}s | error={}",
                _ACTOR_ID,
                method_name,
                elapsed,
                str(e),
            )
            raise

    def _to_records(self, data: Any) -> Any:
        """将 DataFrame 或其他数据转为可序列化格式

        Args:
            data: SDK 返回的数据

        Returns:
            标准化后的数据（list[dict] 或原始数据）
        """
        if data is None:
            return []

        try:
            import pandas as pd

            # DataFrame -> list[dict]
            if isinstance(data, pd.DataFrame):
                return data.to_dict(orient="records")  # type: ignore[return-value]

            # dict[str, DataFrame] -> dict[str, list[dict]]
            if isinstance(data, dict):
                return {k: self._to_records(v) for k, v in data.items()}

            # list 直接返回
            if isinstance(data, list):
                return data

        except Exception as e:
            logger.warning("[{}] 数据转换异常: {}", _ACTOR_ID, e)

        # 其他类型原样返回
        return data

    # ==================== 状态和生命周期 ====================

    async def heartbeat(self) -> bool:
        """心跳检查

        Returns:
            是否健康
        """
        if not self._logged_in:
            return False

        await self._update_session_heartbeat()
        return True

    async def get_status(self) -> dict[str, Any]:
        """获取 Actor 状态

        Returns:
            状态字典
        """
        return {
            "name": self.name,
            "logged_in": self._logged_in,
            "worker_id": self._worker_id,
            "last_activity": self._last_activity,
            "redis_connected": self._redis is not None,
            "base_data_available": self._base_data is not None,
            "market_data_available": self._market_data is not None,
            "info_data_available": self._info_data is not None,
        }

    async def logout(self) -> None:
        """登出 AmazingData SDK"""
        if not self._logged_in:
            return

        try:
            if self._sdk:
                self._sdk.logout()
            self._logged_in = False
            self._sdk = None
            self._base_data = None
            self._market_data = None
            self._info_data = None
            self._tgw = None
            logger.info("[{}] 已登出", _ACTOR_ID)
        except Exception as e:
            logger.warning("[{}] 登出异常: {}", _ACTOR_ID, e)

    async def shutdown(self) -> None:
        """关闭 Actor - 清理资源"""
        logger.info("[{}] 正在关闭...", _ACTOR_ID)

        # 登出
        await self.logout()

        # 关闭异步 Redis 连接
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception as e:
                logger.warning("[{}] Redis 异步连接关闭异常: {}", _ACTOR_ID, e)
            self._redis = None

        # 关闭同步 Redis 连接池（实例级别）
        if self._sync_redis_pool is not None:
            try:
                self._sync_redis_pool.disconnect()
                logger.debug("[{}] Redis 同步连接池已关闭", _ACTOR_ID)
            except Exception as e:
                logger.warning("[{}] Redis 同步连接池关闭异常: {}", _ACTOR_ID, e)
            self._sync_redis_pool = None
            self._sync_redis_pool_url = None

        logger.info("[{}] 已关闭", _ACTOR_ID)

    # ==================== 向后兼容方法（待移除）====================

    @staticmethod
    def _convert_code_to_sdk_format(code: str) -> str:
        """代码格式转换 (向后兼容)

        将 SH.600000 格式转换为 600000.SH（SDK 格式）
        """
        if not code or "." not in code:
            return code

        parts = code.split(".")
        if len(parts) == 2:
            first, second = parts
            # 检查是否是前缀格式 (SH.600000)
            if first.upper() in ("SH", "SZ", "BJ"):
                return f"{second}.{first.upper()}"

        return code

    @staticmethod
    def _convert_codes_to_sdk_format(codes: list[str]) -> list[str]:
        """批量转换代码格式 (向后兼容)"""
        return [AmazingDataActor._convert_code_to_sdk_format(c) for c in codes]

    def normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码 (向后兼容，IDataFeed 接口)"""
        return self._convert_code_to_sdk_format(symbol)

    def standardize_symbol(self, symbol: str) -> str:
        """标准化股票代码 (向后兼容，IDataFeed 接口)"""
        return symbol
