"""
分析 API

提供基于 DuckDB 的高性能数据分析接口
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from fastapi import APIRouter, Query, HTTPException, Body, Depends
from loguru import logger

from deepsearch.infrastructure.providers.managers.data_sync_service import get_sync_service
from deepsearch.infrastructure.persistence.duckdb_analytics import get_analytics_db
from deepsearch.webui.api.utils import sanitize_for_json
from deepsearch.webui.auth import optional_auth

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/indicators/{symbol}")
async def calculate_indicators(
        symbol: str,
        indicators: str = Query(..., description="指标列表，逗号分隔，如: MA_20,RSI_14,MACD"),
        start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
        end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
        period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 1h, 1d")
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
        df = await analytics_db.calculate_indicators(
            symbol, start_date, end_date, indicator_list
        )

        if df.empty:
            raise HTTPException(status_code=404, detail=f"没有找到 {symbol} 的数据")

        # 转换为响应格式
        return sanitize_for_json({
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "indicators": indicator_list,
            "data": df.to_dict(orient="records")
        })

    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregates/{symbol}")
async def get_aggregates(
        symbol: str,
        source_period: str = Query("1m", description="源周期"),
        target_period: str = Query("1d", description="目标周期"),
        start_date: str = Query(None, description="开始日期"),
        end_date: str = Query(None, description="结束日期")
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

        return sanitize_for_json({
            "symbol": symbol,
            "source_period": source_period,
            "target_period": target_period,
            "data": df.to_dict(orient="records")
        })

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
        parameters: Dict[str, Any] = Body({}, description="策略参数")
):
    """
    运行回测
    
    基于历史数据运行策略回测
    """
    try:
        analytics_db = get_analytics_db()

        # 获取历史数据
        sql = """
              SELECT *
              FROM kline_history
              WHERE symbol = ? AND time BETWEEN ? AND ?
              ORDER BY time \
              """

        df = await analytics_db.query(sql, (symbol, start_date, end_date))

        if df.empty:
            raise HTTPException(status_code=404, detail="没有历史数据")

        # 实现简单的均线交叉策略回测
        import numpy as np

        # 计算均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()

        # 生成交易信号
        df['signal'] = 0
        df.loc[(df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1)), 'signal'] = 1  # 买入信号
        df.loc[(df['ma5'] < df['ma20']) & (df['ma5'].shift(1) >= df['ma20'].shift(1)), 'signal'] = -1  # 卖出信号

        # 计算持仓
        df['position'] = df['signal'].cumsum().clip(0, 1)

        # 计算收益
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['position'].shift(1) * df['returns']
        df['cumulative_returns'] = (1 + df['strategy_returns']).cumprod()

        # 去除NaN值
        df = df.dropna()

        if len(df) == 0:
            raise HTTPException(status_code=400, detail="数据不足以进行回测")

        # 计算回测指标
        total_return = float((df['cumulative_returns'].iloc[-1] - 1) * 100)  # 转换为百分比

        # 计算夏普比率 (假设无风险利率为3%)
        risk_free_rate = 0.03 / 252  # 日化无风险利率
        excess_returns = df['strategy_returns'] - risk_free_rate
        if excess_returns.std() > 0:
            sharpe_ratio = float(np.sqrt(252) * excess_returns.mean() / excess_returns.std())
        else:
            sharpe_ratio = 0.0

        # 计算最大回撤
        cumulative = df['cumulative_returns']
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = float(drawdown.min() * 100)  # 转换为百分比

        # 计算胜率
        trades = df[df['signal'] != 0].copy()
        if len(trades) > 0:
            trades['trade_return'] = trades['close'].pct_change()
            winning_trades = len(trades[trades['trade_return'] > 0])
            total_trades = len(trades)
            win_rate = float(winning_trades / total_trades) if total_trades > 0 else 0.0
        else:
            win_rate = 0.0
            total_trades = 0

        # 生成交易记录
        trade_records = []
        position = 0
        entry_price = 0

        for idx, row in df.iterrows():
            if row['signal'] == 1 and position == 0:  # 买入
                position = 1
                entry_price = row['close']
                trade_records.append({
                    'date': row['time'].strftime('%Y-%m-%d') if hasattr(row['time'], 'strftime') else str(row['time']),
                    'action': 'BUY',
                    'price': float(entry_price),
                    'volume': 100  # 假设每次买入100股
                })
            elif row['signal'] == -1 and position == 1:  # 卖出
                position = 0
                exit_price = row['close']
                profit = (exit_price - entry_price) / entry_price * 100
                trade_records.append({
                    'date': row['time'].strftime('%Y-%m-%d') if hasattr(row['time'], 'strftime') else str(row['time']),
                    'action': 'SELL',
                    'price': float(exit_price),
                    'volume': 100,
                    'profit': float(profit)
                })

        # 保存回测结果
        result_df = pd.DataFrame([{
            'strategy_id': strategy_id,
            'run_time': datetime.now(),
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trades': '[]',  # JSON string
            'metrics': '{}'  # JSON string
        }])

        await analytics_db.import_from_dataframe(
            result_df, "backtest_results", if_exists="append"
        )

        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "period": f"{start_date} to {end_date}",
            "results": {
                "total_return": total_return,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate
            }
        }

    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def custom_query(
        sql: str = Body(..., description="SQL 查询语句"),
        params: Optional[List[Any]] = Body(None, description="查询参数"),
        current_user: Optional[Dict[str, Any]] = Depends(optional_auth)
):
    """
    执行自定义 SQL 查询
    
    警告：仅供管理员使用，需要谨慎处理 SQL 注入风险
    """
    try:
        # 添加权限检查
        from deepsearch.config import get_config
        config = get_config()

        # 检查是否启用了认证
        auth_enabled = getattr(config.webui, "auth_enabled", False)

        if auth_enabled:
            # 如果启用了认证，检查用户权限
            if not current_user:
                raise HTTPException(
                    status_code=401,
                    detail="需要登录才能执行SQL查询"
                )

            # 检查是否是管理员
            is_admin = current_user.get("role") == "admin" or current_user.get("is_admin", False)
            if not is_admin:
                raise HTTPException(
                    status_code=403,
                    detail="需要管理员权限才能执行SQL查询"
                )

        # SQL注入防护：限制只能执行 SELECT 查询
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise HTTPException(status_code=400, detail="只允许 SELECT 查询")

        # 进一步的SQL注入防护：禁止危险关键字
        dangerous_keywords = [
            "DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER",
            "EXEC", "EXECUTE", "GRANT", "REVOKE", "UNION", "INTO"
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                raise HTTPException(
                    status_code=400,
                    detail=f"SQL查询包含禁止的关键字: {keyword}"
                )

        analytics_db = get_analytics_db()

        df = await analytics_db.query(sql, tuple(params) if params else None)

        return sanitize_for_json({
            "query": sql,
            "rows": len(df),
            "data": df.to_dict(orient="records")
        })

    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """获取数据库统计信息"""
    try:
        analytics_db = get_analytics_db()
        stats = await analytics_db.get_statistics()

        return {
            "status": "healthy",
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/trigger")
async def trigger_sync(
        table: str = Body("kline_history", description="表名"),
        start_date: Optional[str] = Body(None, description="开始日期"),
        end_date: Optional[str] = Body(None, description="结束日期"),
        symbols: Optional[List[str]] = Body(None, description="股票列表")
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

        return {
            "status": "success",
            "message": f"同步 {table} 已触发"
        }

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
        table: str = Body(..., description="表名"),
        output_path: str = Body(..., description="输出路径")
):
    """
    导出表到 Parquet 文件
    
    用于数据归档和备份
    """
    try:
        analytics_db = get_analytics_db()
        await analytics_db.export_to_parquet(table, output_path)

        return {
            "status": "success",
            "table": table,
            "output": output_path
        }

    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/parquet")
async def import_from_parquet(
        parquet_path: str = Body(..., description="Parquet 文件路径"),
        table: str = Body(..., description="目标表名")
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

        return {
            "status": "success",
            "table": table,
            "records": count
        }

    except Exception as e:
        logger.error(f"导入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
