"""
MiniQMT Dask Actor

简化版 Actor - 只作为状态容器，不包含业务逻辑。
在 Windows Worker 上保持 xtquant SDK 连接状态。

架构设计:
- Actor 只持有 xtdata SDK 连接状态
- 提供简单的 call() 方法代理，不包含缓存/熔断逻辑
- 业务逻辑、缓存、熔断器都在 Adapter/Provider 层

Usage:
    # 由 Plugin 自动创建和管理
    actor = MiniQMTActor(config)
    await actor.initialize()
    data = await actor.call("get_calendar", market="SH")
    await actor.shutdown()
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    pass

# xtdata SDK 导入
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    xtdata = None  # type: ignore
    XTDATA_AVAILABLE = False


class MiniQMTActor:
    """MiniQMT Dask Actor - 状态容器

    简化的 Actor 实现，只负责:
    1. 持有 xtdata SDK 引用
    2. 管理连接状态
    3. 提供方法调用代理
    4. 管理资源生命周期

    不包含:
    - ❌ 缓存逻辑 (由 Adapter 层负责)
    - ❌ 熔断器逻辑 (由 Provider 层负责)
    - ❌ 业务方法 (由 Adapter 层通过 call() 访问)

    Example:
        >>> actor = MiniQMTActor(config)
        >>> await actor.initialize()
        >>> data = await actor.call("get_calendar", market="SH")
        >>> await actor.shutdown()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化 MiniQMT Actor

        Args:
            config: 配置字典（保留用于未来扩展）
        """
        self._config = config or {}

        # 核心状态
        self._initialized = False
        self._connected = False
        self._last_activity = time.time()

        logger.info("[MiniQMTActor] 实例已创建")

    # ==================== 基础属性 ====================

    @property
    def name(self) -> str:
        """数据源名称"""
        return "MiniQMT"

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected and XTDATA_AVAILABLE

    # ==================== 初始化 ====================

    async def initialize(self) -> bool:
        """初始化 MiniQMT Actor"""
        if self._initialized:
            logger.debug("[MiniQMTActor] 已初始化，跳过")
            return True

        if not XTDATA_AVAILABLE:
            logger.error("[MiniQMTActor] xtquant SDK 不可用")
            return False

        try:
            logger.info("[MiniQMTActor] 开始初始化...")

            # 测试 xtdata SDK 连接（异步化）
            calendar = await asyncio.to_thread(
                xtdata.get_trading_calendar, "SH", "20250101", "20250110"  # type: ignore[attr-defined]
            )

            if calendar:
                logger.info(f"[MiniQMTActor] xtdata 连接成功，测试日历: {len(calendar)} 天")
                self._connected = True
            else:
                logger.warning("[MiniQMTActor] xtdata 连接但日历为空")
                self._connected = True  # SDK 可用但可能没数据

            self._initialized = True
            self._last_activity = time.time()

            logger.info("[MiniQMTActor] 初始化完成")
            return True

        except Exception as e:
            logger.error(f"[MiniQMTActor] 初始化失败: {e}")
            return False

    # ==================== 核心方法代理 ====================

    async def call(self, method: str, **kwargs: Any) -> Any:
        """通用方法调用 - 简单代理，不包含缓存/熔断逻辑

        供 RPC Client 通过 worker.actors["miniqmt"].call() 调用。

        Args:
            method: xtdata 方法名 (如 "get_calendar", "get_kline")
            **kwargs: 方法参数

        Returns:
            API 返回数据（已标准化为可序列化格式）

        Raises:
            RuntimeError: Actor 未初始化或 SDK 不可用
        """
        if not self._initialized:
            raise RuntimeError("Actor not initialized")

        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK not available")

        self._last_activity = time.time()

        # 调用 xtdata SDK 方法
        result = await self._call_xtdata(method, kwargs)
        return self._normalize_result(result)

    async def _call_xtdata(self, method: str, params: dict[str, Any]) -> Any:
        """调用 xtdata SDK 方法

        Args:
            method: 方法名
            params: 参数字典

        Returns:
            原始 SDK 结果
        """
        # 获取 xtdata 方法
        func = getattr(xtdata, method, None)
        if func is None:
            raise ValueError(f"xtdata method '{method}' not found")

        # 异步调用 SDK（在线程池中执行）
        return await asyncio.to_thread(lambda: func(**params))

    def _normalize_result(self, result: Any) -> Any:
        """标准化结果为可序列化格式

        将 pandas DataFrame 转换为 list[dict]。

        Args:
            result: 原始 SDK 结果

        Returns:
            标准化后的结果
        """
        if result is None:
            return None

        try:
            import pandas as pd

            # DataFrame -> list[dict]
            if isinstance(result, pd.DataFrame):
                return result.reset_index().to_dict("records")  # type: ignore[return-value]

            # dict[str, DataFrame] -> dict[str, list[dict]]
            if isinstance(result, dict):
                normalized = {}
                for key, val in result.items():
                    if isinstance(val, pd.DataFrame):
                        normalized[key] = val.reset_index().to_dict("records")
                    else:
                        normalized[key] = val
                return normalized

            # list 直接返回
            if isinstance(result, list):
                return result

        except Exception as e:
            logger.warning("[MiniQMTActor] 数据转换异常: {}", e)

        # 其他类型原样返回
        return result

    # ==================== 状态和生命周期 ====================

    async def heartbeat(self) -> bool:
        """心跳检测，验证 SDK 连接

        Returns:
            连接是否正常
        """
        if not XTDATA_AVAILABLE:
            return False

        try:
            # 轻量级检测：获取当天交易日历
            await asyncio.to_thread(
                xtdata.get_trading_calendar, "SH", "20250101", "20250102"  # type: ignore[attr-defined]
            )
            self._last_activity = time.time()
            self._connected = True
            return True
        except Exception as e:
            logger.warning("[MiniQMTActor] 心跳检测失败: {}", e)
            self._connected = False
            return False

    async def get_status(self) -> dict[str, Any]:
        """获取 Actor 状态

        Returns:
            状态信息字典
        """
        return {
            "name": self.name,
            "initialized": self._initialized,
            "connected": self._connected,
            "sdk_available": XTDATA_AVAILABLE,
            "last_activity": self._last_activity,
        }

    async def shutdown(self) -> None:
        """优雅关闭 Actor"""
        logger.info("[MiniQMTActor] 正在关闭...")

        self._initialized = False
        self._connected = False

        logger.info("[MiniQMTActor] 已关闭")
