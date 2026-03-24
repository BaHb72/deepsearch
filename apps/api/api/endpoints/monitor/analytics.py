"""
分析 API

提供基于 DuckDB 的高性能数据分析接口
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from core.infrastructure.persistence.duckdb_analytics import get_analytics_db
from core.infrastructure.providers.managers.data_sync_service import get_sync_service
from core.strategies.implementations import MeanReversionStrategy, MomentumStrategy
from core.strategies.implementations.moving_average import MovingAverageStrategy
from core.strategies.implementations.turtle_trading import TurtleTradingStrategy
from core.strategies.interfaces.models import TradingCostConfig
from core.strategies.services.backtest_service import get_backtest_service
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.params import Body as BodyParam
from loguru import logger

from apps.api.api.utils import sanitize_for_json
from apps.api.auth import optional_auth

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ANALYTICS_BACKTEST_STRATEGY_MAP: dict[str, type] = {
    "simple_ma": MovingAverageStrategy,
    "ma": MovingAverageStrategy,
    "movingaverage": MovingAverageStrategy,
    "moving_average": MovingAverageStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
    "turtle": TurtleTradingStrategy,
}


def _resolve_body_value(value: Any, default: Any) -> Any:
    """兼容直接函数调用场景，避免默认 Body 对象泄漏到业务逻辑。"""

    if isinstance(value, BodyParam):
        return default
    return value


@router.get("/indicators/{symbol}")
async def calculate_indicators(
    symbol: str,
    indicators: str = Query(..., description="指标列表，逗号分隔，如: MA_20,RSI_14,MACD"),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 1h, 1d"),
):
    """
    计算技术指标

    支持的指标：
    - MA_N: N日移动平均线
    - RSI_N: N日RSI
    - MACD: MACD指标
    - BOLL: 布林带
    - KDJ: KDJ指标
    """
    try:
        # 默认时间范围
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        # 解析指标列表
        indicator_list = [i.strip() for i in indicators.split(",")]

        # 获取分析数据库
        analytics_db = get_analytics_db()

        # 计算指标
        df = await analytics_db.calculate_indicators(symbol, start_date, end_date, indicator_list)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"没有找到 {symbol} 的数据")

        # 转换为响应格式
        return sanitize_for_json(
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "indicators": indicator_list,
                "data": df.to_dict(orient="records"),
            }
        )

    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregates/{symbol}")
async def get_aggregates(
    symbol: str,
    source_period: str = Query("1m", description="源周期"),
    target_period: str = Query("1d", description="目标周期"),
    start_date: str = Query(None, description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
):
    """
    获取聚合K线数据

    将细粒度K线聚合为粗粒度K线
    """
    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        analytics_db = get_analytics_db()

        df = await analytics_db.aggregate_klines(
            symbol, source_period, target_period, start_date, end_date
        )

        return sanitize_for_json(
            {
                "symbol": symbol,
                "source_period": source_period,
                "target_period": target_period,
                "data": df.to_dict(orient="records"),
            }
        )

    except Exception as e:
        logger.error(f"聚合数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest")
async def run_backtest(
    strategy_id: str = Body(..., description="策略ID"),
    symbol: Optional[str] = Body(None, description="股票代码"),
    start_date: str = Body(..., description="开始日期"),
    end_date: str = Body(..., description="结束日期"),
    initial_capital: float = Body(100000, description="初始资金"),
    parameters: Dict[str, Any] = Body({}, description="策略参数"),
    timeframe: str = Body("1d", description="周期: 1d / 1m / 1w"),
    adjust: str = Body("qfq", description="复权方式: qfq / hfq / none"),
    slippage: float = Body(0.0, description="滑点比例"),
    enforce_a_share_rules: bool = Body(True, description="是否启用A股交易规则"),
    plot: bool = Body(False, description="是否生成图表"),
    commission: float = Body(0.0002, description="手续费率"),
    min_commission: float = Body(5.0, description="最低佣金"),
    commission_exempt_min: bool = Body(False, description="是否免最低佣金"),
    stamp_tax_rate: float = Body(0.001, description="印花税率"),
    transfer_fee_rate: float = Body(0.00001, description="过户费率"),
):
    """
    运行回测

    基于历史数据运行策略回测
    """
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol 不能为空")

        strategy_key = str(strategy_id).strip().lower()
        strategy_class = ANALYTICS_BACKTEST_STRATEGY_MAP.get(strategy_key)
        if strategy_class is None:
            raise HTTPException(status_code=400, detail=f"不支持的策略ID: {strategy_id}")

        service = get_backtest_service()
        timeframe_value = str(_resolve_body_value(timeframe, "1d"))
        adjust_value = str(_resolve_body_value(adjust, "qfq"))
        slippage_value = float(_resolve_body_value(slippage, 0.0))
        enforce_a_share_rules_value = bool(_resolve_body_value(enforce_a_share_rules, True))
        plot_value = bool(_resolve_body_value(plot, False))
        commission_value = float(_resolve_body_value(commission, 0.0002))
        min_commission_value = float(_resolve_body_value(min_commission, 5.0))
        commission_exempt_min_value = bool(_resolve_body_value(commission_exempt_min, False))
        stamp_tax_rate_value = float(_resolve_body_value(stamp_tax_rate, 0.001))
        transfer_fee_rate_value = float(_resolve_body_value(transfer_fee_rate, 0.00001))

        cost_config = TradingCostConfig(
            commission_rate=commission_value,
            min_commission=min_commission_value,
            commission_exempt_min=commission_exempt_min_value,
            stamp_tax_rate=stamp_tax_rate_value,
            transfer_fee_rate=transfer_fee_rate_value,
            slippage=slippage_value,
        )
        strategy_params = parameters if isinstance(parameters, dict) else {}

        result = await service.run_backtest(
            strategy_class=strategy_class,
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            strategy_params=strategy_params,
            cost_config=cost_config,
            timeframe=timeframe_value,
            adjust=adjust_value,
            enforce_a_share_rules=enforce_a_share_rules_value,
            plot=plot_value,
        )

        analytics_db = get_analytics_db()
        result_df = pd.DataFrame(
            [
                {
                    "strategy_id": strategy_key,
                    "run_time": datetime.now(),
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_return": float(result.total_return * 100),
                    "sharpe_ratio": float(result.sharpe_ratio),
                    "max_drawdown": float(result.max_drawdown * 100),
                    "win_rate": float(result.win_rate),
                    "trades": "[]",
                    "metrics": "{}",
                }
            ]
        )
        await analytics_db.import_from_dataframe(result_df, "backtest_results", if_exists="append")

        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            response_payload = to_dict()
            return sanitize_for_json(response_payload)

        # 兼容旧结果对象（例如测试桩或历史调用）
        return sanitize_for_json(
            {
                "strategy_id": strategy_key,
                "symbol": symbol,
                "period": f"{start_date} to {end_date}",
                "results": {
                    "total_return": float(result.total_return * 100),
                    "sharpe_ratio": float(result.sharpe_ratio),
                    "max_drawdown": float(result.max_drawdown * 100),
                    "win_rate": float(result.win_rate),
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def custom_query(
    sql: str = Body(..., description="SQL 查询语句"),
    params: Optional[List[Any]] = Body(None, description="查询参数"),
    current_user: Optional[Dict[str, Any]] = Depends(optional_auth),
):
    """
    执行自定义 SQL 查询

    警告：仅供管理员使用，需要谨慎处理 SQL 注入风险
    """
    try:
        # 添加权限检查
        from core.config import get_config

        config = get_config()

        # 检查是否启用了认证
        auth_enabled = getattr(config.webui, "auth_enabled", False)

        if auth_enabled:
            # 如果启用了认证，检查用户权限
            if not current_user:
                raise HTTPException(status_code=401, detail="需要登录才能执行SQL查询")

            # 检查是否是管理员
            is_admin = current_user.get("role") == "admin" or current_user.get("is_admin", False)
            if not is_admin:
                raise HTTPException(status_code=403, detail="需要管理员权限才能执行SQL查询")

        # SQL注入防护：限制只能执行 SELECT 查询
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise HTTPException(status_code=400, detail="只允许 SELECT 查询")

        # 进一步的SQL注入防护：禁止危险关键字
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "CREATE",
            "ALTER",
            "EXEC",
            "EXECUTE",
            "GRANT",
            "REVOKE",
            "UNION",
            "INTO",
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                raise HTTPException(status_code=400, detail=f"SQL查询包含禁止的关键字: {keyword}")

        analytics_db = get_analytics_db()

        df = await analytics_db.query(sql, tuple(params) if params else None)

        return sanitize_for_json(
            {"query": sql, "rows": len(df), "data": df.to_dict(orient="records")}
        )

    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """获取数据库统计信息"""
    try:
        analytics_db = get_analytics_db()
        stats = await analytics_db.get_statistics()

        return {"status": "healthy", "statistics": stats}

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/trigger")
async def trigger_sync(
    table: str = Body("kline_history", description="表名"),
    start_date: Optional[str] = Body(None, description="开始日期"),
    end_date: Optional[str] = Body(None, description="结束日期"),
    symbols: Optional[List[str]] = Body(None, description="股票列表"),
):
    """
    手动触发数据同步

    从 PostgreSQL 同步数据到 DuckDB
    """
    try:
        sync_service = get_sync_service()

        if table == "kline_history":
            await sync_service.sync_historical_data(start_date, end_date, symbols)
        else:
            await sync_service.sync_incremental(table)

        return {"status": "success", "message": f"同步 {table} 已触发"}

    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/status")
async def get_sync_status():
    """获取同步状态"""
    try:
        sync_service = get_sync_service()
        status = await sync_service.get_sync_status()

        return status

    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/parquet")
async def export_to_parquet(
    table: str = Body(..., description="表名"), output_path: str = Body(..., description="输出路径")
):
    """
    导出表到 Parquet 文件

    用于数据归档和备份
    """
    try:
        analytics_db = get_analytics_db()
        await analytics_db.export_to_parquet(table, output_path)

        return {"status": "success", "table": table, "output": output_path}

    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/parquet")
async def import_from_parquet(
    parquet_path: str = Body(..., description="Parquet 文件路径"),
    table: str = Body(..., description="目标表名"),
):
    """
    从 Parquet 文件导入数据

    用于数据恢复和迁移
    """
    try:
        analytics_db = get_analytics_db()

        # 读取 Parquet 文件
        import pyarrow.parquet as pq

        df = pq.read_table(parquet_path).to_pandas()

        # 导入到表
        count = await analytics_db.import_from_dataframe(df, table, if_exists="append")

        return {"status": "success", "table": table, "records": count}

    except Exception as e:
        logger.error(f"导入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
