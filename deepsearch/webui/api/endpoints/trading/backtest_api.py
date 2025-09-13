"""
Backtest API
回测相关的API端点
"""
import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from loguru import logger

# 在导入其他模块前抑制PIL日志
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

from deepsearch.backtest.engines.backtest_engine import get_backtest_engine
from deepsearch.backtest.utils.parameter_converter import ParameterConverter, DataValidator
from deepsearch.strategies.implementations import (
    SimpleMAStrategy,
    TurtleTradingStrategy,
    MeanReversionStrategy,
    MomentumStrategy
)
from deepsearch.webui.api.utils.json_utils import sanitize_data

# 创建API路由
router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# 策略映射
STRATEGY_MAP = {
    'simple_ma': SimpleMAStrategy,
    'turtle': TurtleTradingStrategy,
    'mean_reversion': MeanReversionStrategy,
    'momentum': MomentumStrategy
}

# 存储回测结果（实际应用中应使用数据库）
backtest_results = {}

# 图表缓存，避免重复生成
chart_cache = {}


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
    timeframe: str = Field('1d', description="数据周期")
    adjust: str = Field('qfq', description="复权方式")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")


class OptimizationConfig(BaseModel):
    """参数优化配置"""
    strategy: str = Field(..., description="策略类型")
    symbols: List[str] = Field(..., description="股票代码列表")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    param_grid: Dict[str, List[Any]] = Field(..., description="参数网格")
    metric: str = Field('sharpe_ratio', description="优化指标")
    initial_cash: float = Field(100000, description="初始资金")
    commission: float = Field(0.001, description="手续费率")


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


@router.get("/strategies")
async def get_strategies():
    """获取可用策略列表"""
    strategies = []
    
    for key, strategy_class in STRATEGY_MAP.items():
        # 获取策略参数
        params = {}
        if hasattr(strategy_class, 'params'):
            for param_name, param_value in strategy_class.params._getitems():
                if param_name != 'printlog':  # 排除日志参数
                    params[param_name] = {
                        'default': param_value,
                        'type': type(param_value).__name__
                    }
        
        # 添加参数类型信息
        param_types = ParameterConverter.get_strategy_param_info(key)
        
        strategies.append({
            'id': key,
            'name': strategy_class.__name__,
            'description': strategy_class.__doc__.strip() if strategy_class.__doc__ else '',
            'parameters': params,
            'parameter_types': param_types  # 添加类型信息供前端参考
        })
    
    return {'strategies': strategies}


@router.post("/run")
async def run_backtest(
    config: BacktestConfig,
    background_tasks: BackgroundTasks
):
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
        config.strategy_params = validated_config.get('strategy_params', {})
        
        logger.info(f"参数验证成功，策略参数: {config.strategy_params}")
        
    except ValueError as e:
        logger.error(f"参数验证失败: {e}")
        raise HTTPException(400, f"参数验证失败: {e}")
    
    # 生成回测ID
    backtest_id = str(uuid.uuid4())
    
    # 创建结果记录
    result = BacktestResult(
        id=backtest_id,
        status='running',
        strategy=config.strategy,
        symbols=config.symbols,
        start_date=config.start_date,
        end_date=config.end_date,
        created_at=datetime.now()
    )
    
    backtest_results[backtest_id] = result
    
    # 在后台运行回测
    background_tasks.add_task(
        execute_backtest,
        backtest_id,
        config
    )
    
    return {
        'id': backtest_id,
        'message': '回测任务已提交',
        'status': 'running'
    }


async def execute_backtest(backtest_id: str, config: BacktestConfig):
    """执行回测任务"""
    result = backtest_results[backtest_id]
    
    try:
        logger.info(f"开始执行回测 {backtest_id}")
        
        # 获取回测引擎
        engine = await get_backtest_engine()
        
        # 创建Cerebro
        engine.create_cerebro(
            initial_cash=config.initial_cash,
            commission=config.commission,
            slippage=config.slippage
        )
        
        # 添加数据
        await engine.add_data(
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            timeframe=config.timeframe,
            adjust=config.adjust
        )
        
        # 添加策略
        strategy_class = STRATEGY_MAP[config.strategy]
        engine.add_strategy(strategy_class, **config.strategy_params)
        
        # 运行回测
        engine.run()
        
        # 获取结果
        metrics = engine.get_performance_metrics()
        trades = engine.get_trade_list()
        
        # 获取权益曲线并清理NaN值
        equity_df = engine.get_equity_curve()
        # 填充NaN值为0或None
        equity_df = equity_df.fillna(0)  # 或使用 fillna(value={'returns': 0, 'cumulative_returns': 0, 'drawdown': 0})
        equity_curve = equity_df.to_dict(orient='records')
        
        # 进一步清理数据以确保没有NaN或Infinity
        equity_curve = sanitize_data(equity_curve)
        
        # 生成Backtrader原生图表（使用缓存避免重复生成）
        chart_key = f"{config.strategy}_{config.symbols}_{config.start_date}_{config.end_date}"
        
        # 检查缓存
        if chart_key in chart_cache:
            logger.info(f"使用缓存的图表: {chart_key}")
            chart = chart_cache[chart_key]
        else:
            logger.info(f"生成新图表: {chart_key}")
            try:
                # 调用plot_results，内部已经有超时保护
                chart = engine.plot_results(use_backtrader_plot=True)
                
                # 如果图表生成成功，缓存它
                if chart:
                    # 缓存图表（限制缓存大小）
                    if len(chart_cache) > 50:  # 最多缓存50个图表
                        # 删除最早的缓存项
                        oldest_key = next(iter(chart_cache))
                        del chart_cache[oldest_key]
                    chart_cache[chart_key] = chart
                else:
                    logger.warning("图表生成失败，使用空图表")
                    chart = None
            except Exception as e:
                logger.error(f"图表生成异常: {e}")
                chart = None  # 如果出错，不阻止回测结果返回
        
        # 更新结果
        result.status = 'completed'
        result.metrics = metrics
        result.trades = trades
        result.equity_curve = equity_curve
        result.chart = chart
        result.completed_at = datetime.now()
        
        logger.info(f"回测 {backtest_id} 完成")
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"回测 {backtest_id} 失败: {e}\n{error_trace}")
        result.status = 'failed'
        result.error = str(e)
        result.completed_at = datetime.now()


@router.get("/results/{backtest_id}")
async def get_backtest_result(backtest_id: str):
    """获取回测结果"""
    if backtest_id not in backtest_results:
        raise HTTPException(404, "回测结果不存在")
    
    result = backtest_results[backtest_id]
    
    return {
        'id': result.id,
        'status': result.status,
        'strategy': result.strategy,
        'symbols': result.symbols,
        'start_date': result.start_date,
        'end_date': result.end_date,
        'metrics': result.metrics,
        'trades': result.trades,
        'equity_curve': result.equity_curve,
        'chart': result.chart,
        'error': result.error,
        'created_at': result.created_at.isoformat(),
        'completed_at': result.completed_at.isoformat() if result.completed_at else None
    }


@router.get("/results")
async def list_backtest_results(
    limit: int = Query(10, description="返回数量"),
    offset: int = Query(0, description="偏移量")
):
    """列出回测结果"""
    # 按创建时间倒序排序
    sorted_results = sorted(
        backtest_results.values(),
        key=lambda x: x.created_at,
        reverse=True
    )
    
    # 分页
    paginated = sorted_results[offset:offset + limit]
    
    return {
        'total': len(backtest_results),
        'results': [
            {
                'id': r.id,
                'status': r.status,
                'strategy': r.strategy,
                'symbols': r.symbols,
                'start_date': r.start_date,
                'end_date': r.end_date,
                'created_at': r.created_at.isoformat(),
                'completed_at': r.completed_at.isoformat() if r.completed_at else None,
                'metrics': r.metrics if r.status == 'completed' else None
            }
            for r in paginated
        ]
    }


@router.post("/optimize")
async def optimize_parameters(
    config: OptimizationConfig,
    background_tasks: BackgroundTasks
):
    """参数优化"""
    # 验证策略
    if config.strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"未知策略: {config.strategy}")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 在后台运行优化
    background_tasks.add_task(
        execute_optimization,
        task_id,
        config
    )
    
    return {
        'id': task_id,
        'message': '参数优化任务已提交',
        'status': 'running'
    }


async def execute_optimization(task_id: str, config: OptimizationConfig):
    """执行参数优化"""
    try:
        logger.info(f"开始参数优化 {task_id}")
        
        # 获取回测引擎
        engine = await get_backtest_engine()
        
        # 运行优化
        strategy_class = STRATEGY_MAP[config.strategy]
        
        results = engine.optimize_parameters(
            strategy_class=strategy_class,
            param_grid=config.param_grid,
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            metric=config.metric,
            initial_cash=config.initial_cash,
            commission=config.commission
        )
        
        # 保存结果（这里简化处理，实际应保存到数据库）
        logger.info(f"优化完成: {results['best_params']}")
        
    except Exception as e:
        logger.error(f"参数优化 {task_id} 失败: {e}")


@router.delete("/results/{backtest_id}")
async def delete_backtest_result(backtest_id: str):
    """删除回测结果"""
    if backtest_id not in backtest_results:
        raise HTTPException(404, "回测结果不存在")
    
    del backtest_results[backtest_id]
    
    return {'message': '回测结果已删除'}


@router.get("/results/{backtest_id}/plot")
async def get_backtest_plot(
    backtest_id: str,
    use_native: bool = Query(True, description="使用Backtrader原生绘图")
):
    """
    获取回测结果的Backtrader原生图表
    
    Args:
        backtest_id: 回测ID
        use_native: 是否使用Backtrader原生绘图
    
    Returns:
        Base64编码的图表
    """
    if backtest_id not in backtest_results:
        raise HTTPException(404, "回测结果不存在")
    
    result = backtest_results[backtest_id]
    
    if result.status != 'completed':
        raise HTTPException(400, "回测尚未完成")
    
    try:
        # 重新创建引擎并加载结果以生成图表
        engine = await get_backtest_engine()
        
        # 如果有保存的cerebro对象，使用它来生成图表
        if hasattr(result, 'chart') and result.chart:
            return {
                'chart': result.chart,
                'type': 'backtrader' if use_native else 'custom'
            }
        
        # 否则返回已有的图表
        return {
            'chart': result.chart or None,
            'type': 'cached'
        }
        
    except Exception as e:
        logger.error(f"生成图表失败: {e}")
        raise HTTPException(500, f"生成图表失败: {str(e)}")


@router.get("/sample_config/{strategy}")
async def get_sample_config(strategy: str):
    """获取策略的示例配置"""
    if strategy not in STRATEGY_MAP:
        raise HTTPException(400, f"未知策略: {strategy}")
    
    # 返回示例配置
    configs = {
        'simple_ma': {
            'strategy': 'simple_ma',
            'symbols': ['000001', '000002'],
            'start_date': '2023-01-01',
            'end_date': '2024-01-01',
            'initial_cash': 100000,
            'commission': 0.001,
            'strategy_params': {
                'short_period': 10,
                'long_period': 30,
                'position_pct': 0.95,  # 使用95%的资金
                'stop_loss': 0.05,
                'take_profit': 0.15,
                'printlog': True  # 开启日志以便调试
            }
        },
        'turtle': {
            'strategy': 'turtle',
            'symbols': ['000001'],
            'start_date': '2023-01-01',
            'end_date': '2024-01-01',
            'initial_cash': 100000,
            'commission': 0.001,
            'strategy_params': {
                'entry_period_s1': 20,
                'exit_period_s1': 10,
                'atr_period': 20,
                'risk_percent': 0.02,
                'max_units': 4,
                'stop_n': 2,
                'use_system': 1
            }
        },
        'mean_reversion': {
            'strategy': 'mean_reversion',
            'symbols': ['000001', '000002'],
            'start_date': '2023-01-01',
            'end_date': '2024-01-01',
            'initial_cash': 100000,
            'commission': 0.001,
            'strategy_params': {
                'bb_period': 20,
                'bb_devfactor': 2.0,
                'rsi_period': 14,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'position_pct': 0.95,  # 使用95%的资金
                'stop_loss': 0.03
            }
        },
        'momentum': {
            'strategy': 'momentum',
            'symbols': ['000001'],
            'start_date': '2023-01-01',
            'end_date': '2024-01-01',
            'initial_cash': 100000,
            'commission': 0.001,
            'strategy_params': {
                'momentum_period': 20,
                'volume_period': 20,
                'breakout_period': 50,
                'atr_period': 14,
                'atr_multiplier': 2.0,
                'momentum_threshold': 0.05,
                'volume_multiplier': 1.5,
                'max_holding_period': 60,
                'position_pct': 0.95  # 使用95%的资金
            }
        }
    }
    
    return configs.get(strategy, {})