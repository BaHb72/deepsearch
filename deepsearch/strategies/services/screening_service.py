"""
Screening Service

Core screening logic for stock selection using registered strategies.
Integrates with DataAccessProxy for real market data.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd
from loguru import logger

from deepsearch.infrastructure.providers.unified_proxy import DataAccessProxy, get_data_proxy
from deepsearch.strategies.interfaces.models import (
    ScreeningRequest,
    ScreeningResponse,
    ScreeningResult,
    SignalDirection,
)
from deepsearch.strategies.services.registry_service import (
    StrategyRegistryService,
    get_registry_service,
)

# ============================================
# Stock Pool Definitions
# ============================================

STOCK_POOLS: Dict[str, List[str]] = {
    "demo": [
        "000001.SZ",
        "000002.SZ",
        "000858.SZ",
        "002415.SZ",
        "300750.SZ",
        "600000.SH",
        "600036.SH",
        "600519.SH",
        "601318.SH",
        "601606.SH",
    ],
    "hs300": [],  # Will be loaded dynamically
    "zz500": [],  # Will be loaded dynamically
}


class ScreeningService:
    """
    智能选股服务

    负责：
    1. 加载股票池
    2. 获取历史行情数据
    3. 对每只股票运行策略计算信号
    4. 聚合多策略信号并排序
    """

    def __init__(
        self,
        registry_service: Optional[StrategyRegistryService] = None,
        data_proxy: Optional[DataAccessProxy] = None,
    ):
        self._registry = registry_service
        self._data_proxy = data_proxy
        self._initialized = False

    async def initialize(self) -> None:
        """初始化服务"""
        if self._initialized:
            return

        if self._registry is None:
            self._registry = get_registry_service()

        if self._data_proxy is None:
            self._data_proxy = await get_data_proxy()

        self._initialized = True
        logger.info("ScreeningService 初始化完成")

    async def screen_stocks(
        self,
        request: ScreeningRequest,
        weights: Optional[Dict[str, float]] = None,
    ) -> ScreeningResponse:
        """
        执行选股

        Args:
            request: 选股请求
            weights: 策略权重 (strategy_id -> weight)

        Returns:
            选股结果
        """
        await self.initialize()

        start_time = time.time()
        request_id = str(uuid4())[:8]

        # 获取策略列表
        strategy_ids = request.strategy_ids
        if not strategy_ids:
            raise ValueError("No strategies specified")

        # 获取股票池
        stock_pool = await self._resolve_stock_pool(request.stock_pool)
        if not stock_pool:
            stock_pool = STOCK_POOLS["demo"]
            logger.info(f"Using demo stock pool: {len(stock_pool)} stocks")

        # 准备权重
        if weights is None:
            # 等权重
            weights = {sid: 1.0 / len(strategy_ids) for sid in strategy_ids}

        # 并行处理股票
        results: List[ScreeningResult] = []
        batch_size = 10  # 每批处理10只股票

        for i in range(0, len(stock_pool), batch_size):
            batch = stock_pool[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self._screen_single_stock(symbol, strategy_ids, weights) for symbol in batch],
                return_exceptions=True,
            )

            for result in batch_results:
                if isinstance(result, ScreeningResult):
                    # 只返回有信号的股票
                    if result.direction != SignalDirection.HOLD:
                        results.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Screening error: {result}")

        # 按评分排序
        results.sort(key=lambda x: abs(x.score), reverse=True)

        # 添加排名并限制数量
        for i, result in enumerate(results[: request.limit]):
            result.rank = i + 1

        results = results[: request.limit]

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"选股完成: 扫描 {len(stock_pool)} 只, 匹配 {len(results)} 只, " f"耗时 {duration_ms}ms"
        )

        return ScreeningResponse(
            request_id=request_id,
            composite_id=request.composite_id,
            strategy_ids=strategy_ids,
            results=results,
            total_scanned=len(stock_pool),
            total_matched=len(results),
            executed_at=datetime.now(),
            duration_ms=duration_ms,
        )

    async def _resolve_stock_pool(
        self,
        pool_spec: List[str],
    ) -> List[str]:
        """
        解析股票池

        Args:
            pool_spec: 股票池指定 (可以是代码列表或预定义池ID)

        Returns:
            股票代码列表
        """
        if not pool_spec:
            return []

        # 如果是单个预定义池ID
        if len(pool_spec) == 1 and pool_spec[0] in STOCK_POOLS:
            pool_id = pool_spec[0]
            if STOCK_POOLS[pool_id]:
                return STOCK_POOLS[pool_id]
            # 动态加载
            return await self._load_stock_pool(pool_id)

        # 否则视为股票代码列表
        return pool_spec

    async def _load_stock_pool(self, pool_id: str) -> List[str]:
        """动态加载股票池"""
        if self._data_proxy is None:
            return STOCK_POOLS.get("demo", [])

        try:
            result = await self._data_proxy.get_stock_list(module="screening")
            if result.records:
                codes = [r.symbol for r in result.records if r.symbol]
                # 缓存结果
                STOCK_POOLS[pool_id] = codes[:500]  # 限制数量
                return codes[:500]
        except Exception as e:
            logger.warning(f"加载股票池失败: {e}")

        return STOCK_POOLS.get("demo", [])

    async def _screen_single_stock(
        self,
        symbol: str,
        strategy_ids: List[str],
        weights: Dict[str, float],
    ) -> ScreeningResult:
        """
        对单只股票进行选股分析

        Args:
            symbol: 股票代码
            strategy_ids: 策略ID列表
            weights: 策略权重

        Returns:
            选股结果
        """
        # 获取历史数据
        kline_data = await self._get_stock_kline(symbol)
        if kline_data is None or kline_data.empty:
            return ScreeningResult(
                symbol=symbol,
                score=0.0,
                direction=SignalDirection.HOLD,
                component_signals={},
            )

        # 计算各策略信号
        signals: Dict[str, float] = {}

        for strategy_id in strategy_ids:
            try:
                signal = await self._calculate_strategy_signal(strategy_id, symbol, kline_data)
                signals[strategy_id] = signal
            except Exception as e:
                logger.debug(f"策略 {strategy_id} 计算失败: {e}")
                signals[strategy_id] = 0.0

        # 加权聚合
        total_weight = sum(weights.get(sid, 0) for sid in strategy_ids)
        if total_weight == 0:
            total_weight = 1.0

        score = sum(
            signals.get(sid, 0) * weights.get(sid, 0) / total_weight for sid in strategy_ids
        )

        # 确定方向
        threshold = 0.3
        if score > threshold:
            direction = SignalDirection.BUY
        elif score < -threshold:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        # 获取股票名称
        stock_name = await self._get_stock_name(symbol)

        return ScreeningResult(
            symbol=symbol,
            name=stock_name,
            score=round(score, 4),
            direction=direction,
            component_signals=signals,
        )

    async def _get_stock_kline(
        self,
        symbol: str,
        days: int = 60,
    ) -> Optional[pd.DataFrame]:
        """
        获取股票日K线数据

        Args:
            symbol: 股票代码
            days: 回溯天数

        Returns:
            DataFrame with OHLCV data
        """
        if self._data_proxy is None:
            return None

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = await self._data_proxy.get_historical_kline(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",  # 前复权
                module="screening",
            )

            if result and "data" in result:
                df = pd.DataFrame(result["data"])
                return df

        except Exception as e:
            logger.debug(f"获取 {symbol} K线失败: {e}")

        return None

    async def _calculate_strategy_signal(
        self,
        strategy_id: str,
        symbol: str,
        kline_data: pd.DataFrame,
    ) -> float:
        """
        计算策略信号

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            kline_data: K线数据

        Returns:
            信号强度 [-1, 1]
        """
        if self._registry is None:
            return 0.0

        # 获取策略类
        strategy_class = self._registry.get_strategy_class(strategy_id)
        if strategy_class is None:
            return 0.0

        try:
            # 创建策略实例
            strategy = strategy_class()

            # 检查策略是否有 generate_signal 方法
            if hasattr(strategy, "generate_signal"):
                signal = strategy.generate_signal(kline_data)
                if isinstance(signal, (int, float)):
                    return max(-1.0, min(1.0, float(signal)))

            # 如果没有，使用简化的技术分析
            return self._simple_technical_signal(kline_data)

        except Exception as e:
            logger.debug(f"策略 {strategy_id} 信号计算异常: {e}")
            return 0.0

    def _simple_technical_signal(self, df: pd.DataFrame) -> float:
        """
        简化技术分析信号

        基于均线和RSI的简单信号
        """
        if df is None or len(df) < 20:
            return 0.0

        try:
            # 确保有 close 列
            close_col = None
            for col in ["close", "Close", "收盘", "收盘价"]:
                if col in df.columns:
                    close_col = col
                    break

            if close_col is None:
                return 0.0

            closes = df[close_col].astype(float).values

            # 计算均线
            ma5 = closes[-5:].mean()
            ma20 = closes[-20:].mean()
            current = closes[-1]

            # 均线信号
            ma_signal = 0.0
            if current > ma5 > ma20:
                ma_signal = 0.5  # 多头排列
            elif current < ma5 < ma20:
                ma_signal = -0.5  # 空头排列

            # 价格偏离
            deviation = (current - ma20) / ma20
            dev_signal = max(-0.5, min(0.5, deviation * 5))

            # 综合信号
            return float((ma_signal + dev_signal) / 2)

        except Exception:
            return 0.0

    async def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        # TODO: 从缓存或数据库获取
        code = symbol.split(".")[0] if "." in symbol else symbol
        return f"股票{code}"


# ============================================
# Global Instance
# ============================================

_screening_service: Optional[ScreeningService] = None


async def get_screening_service() -> ScreeningService:
    """获取全局选股服务实例"""
    global _screening_service

    if _screening_service is None:
        _screening_service = ScreeningService()
        await _screening_service.initialize()

    return _screening_service
