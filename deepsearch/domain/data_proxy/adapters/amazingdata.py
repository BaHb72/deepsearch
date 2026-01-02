"""
AmazingData Data Source Adapter

基于 AmazingData SDK 的数据源适配器。
通过 Dask Actor 在 Windows Worker 上保持 SDK 登录状态。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Sequence

from loguru import logger

from deepsearch.compute import get_dask_client

from ..interfaces import (
    CAPABILITY_CALENDAR,
    CAPABILITY_KLINE,
    CAPABILITY_REALTIME,
    CAPABILITY_STOCK_LIST,
    CAPABILITY_SUBSCRIPTION,
)

if TYPE_CHECKING:
    import pandas as pd

    from deepsearch.ports.market_data import MarketSnapshot


class AmazingDataAdapter:
    """AmazingData 数据源适配器

    通过 Dask Actor 在 Windows Worker 上执行 SDK 调用。
    Actor 保持登录状态，支持实时订阅和历史数据查询。
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """初始化适配器

        Args:
            config: 配置字典，包含登录信息
        """
        self._config = config or {}
        self._latencies: deque[float] = deque(maxlen=10)
        self._actor: Any = None
        self._actor_initialized = False

    @property
    def name(self) -> str:
        return "amazingdata"

    @property
    def capabilities(self) -> set[str]:
        return {
            CAPABILITY_KLINE,
            CAPABILITY_REALTIME,
            CAPABILITY_CALENDAR,
            CAPABILITY_STOCK_LIST,
            CAPABILITY_SUBSCRIPTION,
        }

    async def is_available(self) -> bool:
        """检查 AmazingData 是否可用"""
        if not self._actor_initialized:
            return False
        try:
            if self._actor:
                status = await self._actor.is_logged_in()
                return status
        except Exception:
            pass
        return False

    async def get_latency(self) -> float:
        """获取平均延迟"""
        if not self._latencies:
            return 999.0
        return sum(self._latencies) / len(self._latencies)

    async def initialize_actor(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> bool:
        """初始化 Dask Actor 并登录

        Args:
            username: 用户名（或使用配置中的值）
            password: 密码（或使用配置中的值）

        Returns:
            初始化是否成功
        """
        if self._actor_initialized and self._actor:
            logger.info("AmazingData Actor 已初始化")
            return True

        username = username or self._config.get("username")
        password = password or self._config.get("password")

        if not username or not password:
            logger.error("初始化失败：缺少用户名或密码")
            return False

        try:
            from deepsearch.compute.actors import AmazingDataActor

            # 获取 Dask Client
            client = await get_dask_client()

            logger.info("正在创建 AmazingData Actor...")

            # 创建 Actor (在 Windows Worker 上)
            actor_future = client.submit(
                AmazingDataActor,
                self._config,
                actor=True,
                resources={"WIN": 1},
            )
            self._actor = await asyncio.wait_for(
                asyncio.wrap_future(actor_future), timeout=60.0
            )

            # 登录
            logger.info("正在登录 AmazingData...")
            login_result = await self._actor.login(username, password)

            if not login_result:
                logger.error("AmazingData 登录失败")
                return False

            self._actor_initialized = True
            logger.info("AmazingData Actor 初始化成功")
            return True

        except Exception as e:
            logger.error("AmazingData Actor 初始化失败: {}", e)
            self._actor = None
            return False

    async def shutdown_actor(self) -> None:
        """关闭 Dask Actor"""
        if self._actor:
            try:
                await self._actor.shutdown()
                logger.info("AmazingData Actor 已关闭")
            except Exception as e:
                logger.warning("关闭 Actor 时出错: {}", e)
            finally:
                self._actor = None
                self._actor_initialized = False

    async def _ensure_actor(self) -> Any:
        """确保 Actor 已初始化"""
        if not self._actor_initialized or not self._actor:
            raise RuntimeError(
                "AmazingData Actor 未初始化，请先调用 initialize_actor()"
            )
        return self._actor

    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> "pd.DataFrame":
        """获取 K 线数据"""
        import pandas as pd

        actor = await self._ensure_actor()

        start_time = time.perf_counter()
        try:
            result = await actor.get_kline(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            latency = (time.perf_counter() - start_time) * 1000
            self._latencies.append(latency)

            if not result:
                return pd.DataFrame()

            return pd.DataFrame(result)

        except Exception as e:
            logger.error("AmazingData K 线获取失败: {}", e)
            raise

    async def get_realtime_quotes(
        self,
        symbols: Sequence[str],
    ) -> Sequence["MarketSnapshot"]:
        """获取实时行情"""
        from datetime import datetime, timezone
        from decimal import Decimal

        from deepsearch.ports.market_data import MarketSnapshot

        actor = await self._ensure_actor()

        start_time = time.perf_counter()
        try:
            result = await actor.get_realtime_quotes(list(symbols))
            latency = (time.perf_counter() - start_time) * 1000
            self._latencies.append(latency)

            if not result:
                return []

            # 转换为 MarketSnapshot
            snapshots = []
            for data in result:
                snapshots.append(
                    MarketSnapshot(
                        code=data.get("code", ""),
                        name=data.get("code", ""),
                        exchange="SH",  # TODO: 从代码推断
                        ts=datetime.now(timezone.utc),
                        last=Decimal(str(data.get("last_price", 0))),
                        open=Decimal(str(data.get("open", 0))),
                        high=Decimal(str(data.get("high", 0))),
                        low=Decimal(str(data.get("low", 0))),
                        prev_close=Decimal("0"),
                        amount=Decimal(str(data.get("amount", 0))),
                        volume=int(data.get("volume", 0)),
                    )
                )
            return snapshots

        except Exception as e:
            logger.error("AmazingData 实时行情获取失败: {}", e)
            raise

    async def get_calendar(
        self,
        market: str = "SH",
    ) -> list[int]:
        """获取交易日历"""
        actor = await self._ensure_actor()

        start_time = time.perf_counter()
        try:
            result = await actor.get_calendar(market)
            latency = (time.perf_counter() - start_time) * 1000
            self._latencies.append(latency)
            return result or []

        except Exception as e:
            logger.error("AmazingData 日历获取失败: {}", e)
            raise

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """获取股票列表

        注: AmazingData 可能不直接支持此接口，可能需要其他方式实现
        """
        logger.warning("AmazingData 股票列表接口暂不支持")
        return []

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback_topic: str,
    ) -> None:
        """订阅实时行情

        行情数据将通过消息总线推送到指定主题。
        """
        actor = await self._ensure_actor()
        await actor.subscribe(list(symbols), callback_topic)

    async def unsubscribe(
        self,
        symbols: Sequence[str],
    ) -> None:
        """取消订阅"""
        actor = await self._ensure_actor()
        await actor.unsubscribe(list(symbols))

    async def get_actor_status(self) -> dict[str, Any]:
        """获取 Actor 状态"""
        if not self._actor_initialized or not self._actor:
            return {"initialized": False}

        try:
            status = await self._actor.get_status()
            status["initialized"] = True
            return status
        except Exception as e:
            return {"initialized": False, "error": str(e)}
