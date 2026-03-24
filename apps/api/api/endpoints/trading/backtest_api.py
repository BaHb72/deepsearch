"""
Backtest API
回测相关的API端点
"""

import logging
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from core.backtest.utils.parameter_converter import DataValidator, ParameterConverter
from core.observability import get_logger
from core.strategies.implementations.mean_reversion import MeanReversionStrategy
from core.strategies.implementations.momentum import MomentumStrategy
from core.strategies.implementations.moving_average import MovingAverageStrategy
from core.strategies.implementations.turtle_trading import TurtleTradingStrategy
from core.strategies.interfaces.models import TradingCostConfig
from core.strategies.services.backtest_service import get_backtest_service
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.utils.json_utils import sanitize_data

# 在导入其他模块前抑制PIL日志


# 在导入完成后降低 PIL 日志噪声
get_logger("PIL").setLevel(logging.WARNING)
get_logger("PIL.PngImagePlugin").setLevel(logging.WARNING)


# 创建API路由
router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# 策略映射
STRATEGY_MAP = {
    "simple_ma": MovingAverageStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
    "turtle": TurtleTradingStrategy,
}


class TTLCache:
    """带 TTL（过期时间）和 LRU（最近最少使用）的缓存"""

    def __init__(self, maxsize: int = 100, ttl_seconds: float = 3600):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，如果过期则删除并返回 None"""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            # 过期，删除并返回 None
            del self._cache[key]
            return None

        # 更新访问顺序（LRU）
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        # 如果已存在，先删除（为了更新顺序）
        if key in self._cache:
            del self._cache[key]

        # 如果超过最大大小，删除最旧的
        if len(self._cache) >= self.maxsize:
            self._cache.popitem(last=False)  # FIFO: 删除最早加入的

        # 添加新值
        self._cache[key] = (value, time.time())

    def __contains__(self, key: str) -> bool:
        """检查 key 是否存在且未过期"""
        return self.get(key) is not None

    def __len__(self) -> int:
        """返回当前缓存大小"""
        return len(self._cache)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def delete(self, key: str) -> None:
        """删除指定key的缓存"""
        if key in self._cache:
            del self._cache[key]

    def values(self) -> list[Any]:
        """返回所有有效的缓存值（自动清理过期项）"""
        current_time = time.time()
        valid_values = []
        expired_keys = []

        for key, (value, timestamp) in self._cache.items():
            if current_time - timestamp > self.ttl_seconds:
                expired_keys.append(key)
            else:
                valid_values.append(value)

        # 清理过期项
        for key in expired_keys:
            del self._cache[key]

        return valid_values


# 存储回测结果（带 TTL 防止内存泄漏）
# 回测结果保留 1 小时，最多 100 个
backtest_results = TTLCache(maxsize=100, ttl_seconds=3600)

# 图表缓存，避免重复生成
# 图表缓存保留 30 分钟，最多 50 个
chart_cache = TTLCache(maxsize=50, ttl_seconds=1800)

# 参数优化结果缓存
# 优化结果保留 1 小时，最多 100 个
optimization_results = TTLCache(maxsize=100, ttl_seconds=3600)


# 请求/响应模型
class BacktestConfig(BaseModel):
    """回测配置"""

    strategy: str = Field(..., description="策略类型")
    symbols: List[str] = Field(..., description="股票代码列表")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_cash: float = Field(100000, description="初始资金")
    commission: float = Field(0.001, description="手续费率")
    slippage: float = Field(0.0, description="滑点")
    timeframe: str = Field("1d", description="数据周期")
    adjust: str = Field("qfq", description="复权方式")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")


class OptimizationConfig(BaseModel):
    """参数优化配置"""

    strategy: str = Field(..., description="策略类型")
    symbols: List[str] = Field(..., description="股票代码列表")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    param_grid: Dict[str, List[Any]] = Field(..., description="参数网格")
    metric: str = Field("sharpe_ratio", description="优化指标")
    initial_cash: float = Field(100000, description="初始资金")
    timeframe: str = Field("1d", description="数据周期")
    adjust: str = Field("qfq", description="复权方式")
    enforce_a_share_rules: bool = Field(True, description="是否启用 A 股约束")
    top_n: int = Field(20, ge=1, le=200, description="返回前 N 个参数组合")
    max_combinations: int = Field(256, ge=1, le=2048, description="参数组合数量上限")
    commission: float = Field(0.0002, description="手续费率")
    min_commission: float = Field(5.0, description="最低佣金")
    commission_exempt_min: bool = Field(False, description="是否免最低佣金")
    stamp_tax_rate: float = Field(0.001, description="印花税率")
    transfer_fee_rate: float = Field(0.00001, description="过户费率")
    slippage: float = Field(0.0, description="滑点")


class BacktestResult(BaseModel):
    """回测结果"""

    id: str
    status: str  # running, completed, failed
    strategy: str
    symbols: List[str]
    start_date: str
    end_date: str
    metrics: Optional[Dict[str, Any]] = None
    trades: Optional[List[Dict[str, Any]]] = None
    equity_curve: Optional[List[Dict[str, Any]]] = None
    chart: Optional[str] = None  # Base64编码的图表
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class OptimizationResult(BaseModel):
    """参数优化结果"""

    id: str
    status: str  # running, completed, failed
    strategy: str
    symbols: List[str]
    start_date: str
    end_date: str
    metric: str
    best_params: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None
    best_result: Optional[Dict[str, Any]] = None
    ranked_results: Optional[List[Dict[str, Any]]] = None
    combination_count: Optional[int] = None
    evaluated_count: Optional[int] = None
    failed_count: Optional[int] = None
    failed_cases: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


@router.get("/strategies")
async def get_strategies():
    """获取可用策略列表"""
    defaults_by_strategy: Dict[str, Dict[str, Any]] = {
        "simple_ma": {
            "short_period": 10,
            "long_period": 30,
            "position_size": 100,
            "max_positions": 5,
        },
        "mean_reversion": {
            "lookback_period": 20,
            "entry_threshold": 2.0,
            "exit_threshold": 0.35,
            "stop_loss": 0.03,
            "position_size": 100,
        },
        "momentum": {
            "momentum_period": 20,
            "volume_period": 20,
            "breakout_period": 50,
            "momentum_threshold": 0.05,
            "position_size": 100,
        },
        "turtle": {
            "entry_period_s1": 20,
            "exit_period_s1": 10,
            "atr_period": 20,
            "risk_percent": 0.02,
            "max_units": 4,
        },
    }

    strategies: List[Dict[str, Any]] = []
    for strategy_key, strategy_cls in STRATEGY_MAP.items():
        defaults = defaults_by_strategy.get(strategy_key, {})
        params = {
            key: {"default": value, "type": type(value).__name__} for key, value in defaults.items()
        }
        strategies.append(
            {
                "id": strategy_key,
                "name": strategy_cls.__name__,
                "description": f"统一 Backtrader 主线策略（{strategy_key}）",
                "parameters": params,
                "parameter_types": ParameterConverter.get_strategy_param_info(strategy_key),
                "engine": "backtrader-mainline",
            }
        )

    return {"strategies": strategies}


@router.post("/run")
async def run_backtest(config: BacktestConfig, background_tasks: BackgroundTasks):
    """运行回测"""
    # 验证策略
    if config.strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"未知策略: {config.strategy}")

    # 验证和转换配置参数
    try:
        # 将Pydantic模型转换为字典
        config_dict = config.dict()

        # 验证配置
        validated_config = DataValidator.validate_backtest_config(config_dict)

        # 更新config对象的strategy_params
        config.strategy_params = validated_config.get("strategy_params", {})

        logger.info(f"参数验证成功，策略参数: {config.strategy_params}")

    except ValueError as e:
        logger.error(f"参数验证失败: {e}")
        raise HTTPException(400, f"参数验证失败: {e}")

    # 生成回测ID
    backtest_id = str(uuid.uuid4())

    # 创建结果记录
    result = BacktestResult(
        id=backtest_id,
        status="running",
        strategy=config.strategy,
        symbols=config.symbols,
        start_date=config.start_date,
        end_date=config.end_date,
        created_at=datetime.now(),
    )

    backtest_results.set(backtest_id, result)

    # 在后台运行回测
    background_tasks.add_task(execute_backtest, backtest_id, config)

    return {"id": backtest_id, "message": "回测任务已提交", "status": "running"}


async def execute_backtest(backtest_id: str, config: BacktestConfig):
    """执行回测任务"""
    result = backtest_results.get(backtest_id)
    if result is None:
        logger.error(f"回测 {backtest_id} 结果对象不存在（可能已过期）")
        return

    try:
        logger.info(f"开始执行回测 {backtest_id}")
        service = get_backtest_service()
        strategy_class = STRATEGY_MAP[config.strategy]

        cost_config = TradingCostConfig(
            commission_rate=config.commission,
            slippage=config.slippage,
        )

        unified_result = await service.run_backtest(
            strategy_class=strategy_class,
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_cash,
            strategy_params=config.strategy_params,
            cost_config=cost_config,
            timeframe=config.timeframe,
            adjust=config.adjust,
            enforce_a_share_rules=True,
            plot=True,
        )
        dto = unified_result.to_dict()

        # 更新结果
        result.status = "completed"
        result.metrics = cast(Optional[Dict[str, Any]], dto.get("metrics"))
        result.trades = cast(Optional[List[Dict[str, Any]]], dto.get("trades"))
        result.equity_curve = cast(
            Optional[List[Dict[str, Any]]],
            sanitize_data(dto.get("equity_curve", [])),
        )
        result.chart = cast(Optional[str], dto.get("plot_base64"))
        result.completed_at = datetime.now()

        logger.info(f"回测 {backtest_id} 完成")

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"回测 {backtest_id} 失败: {e}\n{error_trace}")
        result.status = "failed"
        result.error = str(e)
        result.completed_at = datetime.now()


@router.get("/results/{backtest_id}")
async def get_backtest_result(backtest_id: str):
    """获取回测结果"""
    result = backtest_results.get(backtest_id)
    if result is None:
        raise HTTPException(404, "回测结果不存在或已过期")

    return {
        "id": result.id,
        "status": result.status,
        "strategy": result.strategy,
        "symbols": result.symbols,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "metrics": result.metrics,
        "trades": result.trades,
        "equity_curve": result.equity_curve,
        "chart": result.chart,
        "error": result.error,
        "created_at": result.created_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
    }


@router.get("/results")
async def list_backtest_results(
    limit: int = Query(10, description="返回数量"), offset: int = Query(0, description="偏移量")
):
    """列出回测结果"""
    # 按创建时间倒序排序
    sorted_results = sorted(backtest_results.values(), key=lambda x: x.created_at, reverse=True)

    # 分页
    paginated = sorted_results[offset : offset + limit]

    return {
        "total": len(backtest_results),
        "results": [
            {
                "id": r.id,
                "status": r.status,
                "strategy": r.strategy,
                "symbols": r.symbols,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "metrics": r.metrics if r.status == "completed" else None,
            }
            for r in paginated
        ],
    }


@router.post("/optimize")
async def optimize_parameters(config: OptimizationConfig, background_tasks: BackgroundTasks):
    """参数优化"""
    if config.strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"未知策略: {config.strategy}")
    if not config.param_grid:
        raise HTTPException(400, "param_grid 不能为空")

    task_id = str(uuid.uuid4())
    result = OptimizationResult(
        id=task_id,
        status="running",
        strategy=config.strategy,
        symbols=config.symbols,
        start_date=config.start_date,
        end_date=config.end_date,
        metric=config.metric,
        created_at=datetime.now(),
    )
    optimization_results.set(task_id, result)

    background_tasks.add_task(execute_optimization, task_id, config)
    return {"id": task_id, "message": "参数优化任务已提交", "status": "running"}


async def execute_optimization(task_id: str, config: OptimizationConfig):
    """执行参数优化"""
    result = optimization_results.get(task_id)
    if result is None:
        logger.error(f"参数优化任务 {task_id} 结果对象不存在（可能已过期）")
        return

    try:
        logger.info(f"开始执行参数优化 {task_id}")
        service = get_backtest_service()
        strategy_class = STRATEGY_MAP[config.strategy]

        cost_config = TradingCostConfig(
            commission_rate=config.commission,
            min_commission=config.min_commission,
            commission_exempt_min=config.commission_exempt_min,
            stamp_tax_rate=config.stamp_tax_rate,
            transfer_fee_rate=config.transfer_fee_rate,
            slippage=config.slippage,
        )

        optimize_result = await service.optimize_parameters(
            strategy_class=strategy_class,
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            param_grid=config.param_grid,
            metric=config.metric,
            initial_capital=config.initial_cash,
            cost_config=cost_config,
            timeframe=config.timeframe,
            adjust=config.adjust,
            enforce_a_share_rules=config.enforce_a_share_rules,
            top_n=config.top_n,
            max_combinations=config.max_combinations,
        )

        result.status = "completed"
        result.best_params = cast(Optional[Dict[str, Any]], optimize_result.get("best_params"))
        result.best_score = cast(Optional[float], optimize_result.get("best_score"))
        result.best_result = cast(
            Optional[Dict[str, Any]],
            sanitize_data(cast(Dict[str, Any], optimize_result.get("best_result", {}))),
        )
        result.ranked_results = cast(
            Optional[List[Dict[str, Any]]],
            sanitize_data(cast(List[Dict[str, Any]], optimize_result.get("ranked_results", []))),
        )
        result.combination_count = cast(Optional[int], optimize_result.get("combination_count"))
        result.evaluated_count = cast(Optional[int], optimize_result.get("evaluated_count"))
        result.failed_count = cast(Optional[int], optimize_result.get("failed_count"))
        result.failed_cases = cast(
            Optional[List[Dict[str, Any]]],
            sanitize_data(cast(List[Dict[str, Any]], optimize_result.get("failed_cases", []))),
        )
        result.completed_at = datetime.now()
        logger.info(f"参数优化 {task_id} 完成")

    except Exception as exc:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"参数优化 {task_id} 失败: {exc}\n{error_trace}")
        result.status = "failed"
        result.error = str(exc)
        result.completed_at = datetime.now()


@router.get("/optimize/results/{task_id}")
async def get_optimization_result(task_id: str):
    """获取参数优化结果"""
    result = optimization_results.get(task_id)
    if result is None:
        raise HTTPException(404, "参数优化结果不存在或已过期")

    return {
        "id": result.id,
        "status": result.status,
        "strategy": result.strategy,
        "symbols": result.symbols,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "metric": result.metric,
        "best_params": result.best_params,
        "best_score": result.best_score,
        "best_result": result.best_result,
        "ranked_results": result.ranked_results,
        "combination_count": result.combination_count,
        "evaluated_count": result.evaluated_count,
        "failed_count": result.failed_count,
        "failed_cases": result.failed_cases,
        "error": result.error,
        "created_at": result.created_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
    }


@router.delete("/results/{backtest_id}")
async def delete_backtest_result(backtest_id: str):
    """删除回测结果"""
    if backtest_id not in backtest_results:
        raise HTTPException(404, "回测结果不存在或已过期")

    backtest_results.delete(backtest_id)

    return {"message": "回测结果已删除"}


@router.get("/results/{backtest_id}/plot")
async def get_backtest_plot(
    backtest_id: str, use_native: bool = Query(True, description="使用Backtrader原生绘图")
):
    """
    获取回测结果的Backtrader原生图表

    Args:
        backtest_id: 回测ID
        use_native: 是否使用Backtrader原生绘图

    Returns:
        Base64编码的图表
    """
    result = backtest_results.get(backtest_id)
    if result is None:
        raise HTTPException(404, "回测结果不存在或已过期")

    if result.status != "completed":
        raise HTTPException(400, "回测尚未完成")
    if hasattr(result, "chart") and result.chart:
        return {"chart": result.chart, "type": "backtrader" if use_native else "custom"}
    return {"chart": None, "type": "none"}


@router.get("/sample_config/{strategy}")
async def get_sample_config(strategy: str):
    """获取策略的示例配置"""
    if strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"未知策略: {strategy}")

    # 返回示例配置
    configs = {
        "simple_ma": {
            "strategy": "simple_ma",
            "symbols": ["000001", "000002"],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_cash": 100000,
            "commission": 0.0002,
            "strategy_params": {
                "short_period": 10,
                "long_period": 30,
                "position_size": 100,
                "max_positions": 5,
            },
        },
        "mean_reversion": {
            "strategy": "mean_reversion",
            "symbols": ["000001", "000002"],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_cash": 100000,
            "commission": 0.0002,
            "strategy_params": {
                "lookback_period": 20,
                "entry_threshold": 2.0,
                "exit_threshold": 0.35,
                "stop_loss": 0.03,
                "position_size": 100,
            },
        },
        "momentum": {
            "strategy": "momentum",
            "symbols": ["000001"],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_cash": 100000,
            "commission": 0.0002,
            "strategy_params": {
                "momentum_period": 20,
                "volume_period": 20,
                "breakout_period": 50,
                "momentum_threshold": 0.05,
                "position_size": 100,
            },
        },
        "turtle": {
            "strategy": "turtle",
            "symbols": ["000001"],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_cash": 100000,
            "commission": 0.0002,
            "strategy_params": {
                "entry_period_s1": 20,
                "exit_period_s1": 10,
                "atr_period": 20,
                "risk_percent": 0.02,
                "max_units": 4,
                "stop_n": 2.0,
            },
        },
    }

    return configs.get(strategy, {})
