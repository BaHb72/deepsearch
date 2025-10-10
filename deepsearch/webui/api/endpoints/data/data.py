"""数据管理 API 路由

提供数据查询、导入、导出等功能的 API 接口
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from deepsearch.core.managers.component_manager import ComponentManager
from deepsearch.data.cleaner import DataCleaner
from deepsearch.indicators.simple import SimpleIndicators
from deepsearch.infrastructure.persistence.analytics import AnalyticsDB
from deepsearch.infrastructure.persistence.database import DatabaseService
from deepsearch.observability.logger import logger

if TYPE_CHECKING:  # pragma: no cover
    from deepsearch.utils.data_sources import DataSourceManager

router = APIRouter()

# 全局变量
_db_service: Optional[DatabaseService] = None
_analytics_db: Optional[AnalyticsDB] = None


def get_db_service() -> DatabaseService:
    """获取数据库服务实例"""
    global _db_service
    if _db_service is None:
        # 从组件管理器获取数据库组件
        cm = ComponentManager()
        if "database" in cm._components:
            db_component = cm._components["database"]
            _db_service = DatabaseService(db_component)
        else:
            raise HTTPException(status_code=503, detail="数据库服务未初始化")
    return _db_service


def get_analytics_db() -> AnalyticsDB:
    """获取分析数据库实例"""
    global _analytics_db
    if _analytics_db is None:
        _analytics_db = AnalyticsDB()
        _analytics_db.connect()
    return _analytics_db


def get_data_service() -> "DataSourceManager":
    """获取数据服务实例（用于测试兼容）"""
    # 返回一个模拟服务对象
    from deepsearch.utils.data_sources import DataSourceManager

    return DataSourceManager.get_instance()


# ==================== 请求/响应模型 ====================


class MarketDataQuery(BaseModel):
    """市场数据查询参数"""

    symbols: List[str] = Field(..., description="股票代码列表")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    data_type: str = Field("daily", description="数据类型: daily, 1min, tick")
    limit: Optional[int] = Field(None, description="返回数量限制")


class MarketDataResponse(BaseModel):
    """市场数据响应"""

    count: int = Field(..., description="数据条数")
    data: List[Dict[str, Any]] = Field(..., description="数据列表")


class DataImportRequest(BaseModel):
    """数据导入请求"""

    data_type: str = Field(..., description="数据类型: daily, 1min, tick")
    source: str = Field("csv", description="数据源: csv, api")
    clean_data: bool = Field(True, description="是否清洗数据")


class DataStatsResponse(BaseModel):
    """数据统计响应"""

    total_symbols: int
    total_records: int
    date_range: Dict[str, str]
    data_types: Dict[str, int]
    last_update: Optional[datetime]


class IndicatorRequest(BaseModel):
    """技术指标计算请求"""

    symbol: str
    start_date: date
    end_date: date
    indicators: List[str] = Field(default=["SMA", "EMA", "RSI", "MACD"])


class IndicatorResponse(BaseModel):
    """技术指标响应"""

    symbol: str
    count: int
    data: List[Dict[str, Any]]


# ==================== API 路由 ====================


@router.get("/stats", response_model=DataStatsResponse)
async def get_data_statistics():
    """获取数据统计信息"""
    try:
        analytics_db = get_analytics_db()
        stats = analytics_db.get_statistics()

        # 获取更多统计信息
        response = DataStatsResponse(
            total_symbols=stats.get("symbol_count", 0),
            total_records=stats.get("market_daily_count", 0),
            date_range=stats.get("date_range", {"start": "", "end": ""}),
            data_types={
                "daily": stats.get("market_daily_count", 0),
                "factor": stats.get("factor_data_count", 0),
                "indicator": stats.get("indicator_data_count", 0),
            },
            last_update=datetime.now(),
        )

        return response

    except Exception as e:
        logger.error(f"获取数据统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=MarketDataResponse)
async def query_market_data(query: MarketDataQuery):
    """查询市场数据"""
    try:
        if query.data_type == "daily":
            # 从 DuckDB 查询日线数据
            analytics_db = get_analytics_db()
            df = analytics_db.query_daily_data(
                symbols=query.symbols, start_date=query.start_date, end_date=query.end_date
            )

            # 转换为字典列表
            data = df.to_dict("records")

            # 处理日期格式
            for item in data:
                if "date" in item and isinstance(item["date"], pd.Timestamp):
                    item["date"] = item["date"].strftime("%Y-%m-%d")

            return MarketDataResponse(count=len(data), data=data)

        else:
            # 从 PostgreSQL 查询分钟或 Tick 数据
            from sqlalchemy.orm import Session

            from deepsearch.infrastructure.persistence.sync_database import get_db
            from deepsearch.infrastructure.providers.entities.legacy_models import (
                MinuteKline,
                TickData,
            )

            db: Session = next(get_db())

            try:
                if query.data_type == "minute":
                    # 查询分钟线数据
                    q = db.query(MinuteKline)

                    if query.symbols:
                        q = q.filter(MinuteKline.symbol.in_(query.symbols))
                    if query.start_date:
                        q = q.filter(MinuteKline.datetime >= query.start_date)
                    if query.end_date:
                        q = q.filter(MinuteKline.datetime <= query.end_date)

                    q = q.order_by(MinuteKline.datetime.desc())
                    if query.limit:
                        q = q.limit(query.limit)

                    results = q.all()
                    data = [
                        {
                            "symbol": r.symbol,
                            "datetime": r.datetime.isoformat(),
                            "open": float(r.open),
                            "high": float(r.high),
                            "low": float(r.low),
                            "close": float(r.close),
                            "volume": r.volume,
                        }
                        for r in results
                    ]

                elif query.data_type == "tick":
                    # 查询 Tick 数据
                    q = db.query(TickData)

                    if query.symbols:
                        q = q.filter(TickData.symbol.in_(query.symbols))
                    if query.start_date:
                        q = q.filter(TickData.datetime >= query.start_date)
                    if query.end_date:
                        q = q.filter(TickData.datetime <= query.end_date)

                    q = q.order_by(TickData.datetime.desc())
                    if query.limit:
                        q = q.limit(query.limit)

                    results = q.all()
                    data = [
                        {
                            "symbol": r.symbol,
                            "datetime": r.datetime.isoformat(),
                            "price": float(r.price),
                            "volume": r.volume,
                            "bid_price": float(r.bid_price) if r.bid_price else None,
                            "ask_price": float(r.ask_price) if r.ask_price else None,
                            "bid_volume": r.bid_volume,
                            "ask_volume": r.ask_volume,
                        }
                        for r in results
                    ]

                else:
                    raise HTTPException(
                        status_code=400, detail=f"不支持的数据类型: {query.data_type}"
                    )

                return MarketDataResponse(count=len(data), data=data)

            finally:
                db.close()

    except Exception as e:
        logger.error(f"查询市场数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/csv")
async def import_csv_data(
    file: UploadFile = File(...),
    data_type: str = Query("daily", description="数据类型"),
    clean_data: bool = Query(True, description="是否清洗数据"),
):
    """从 CSV 文件导入数据"""
    try:
        # 读取 CSV 文件
        contents = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(contents))

        # 数据清洗
        if clean_data:
            cleaner = DataCleaner()
            if data_type == "daily":
                df = cleaner.clean_kline_data(df)
            elif data_type == "tick":
                df = cleaner.clean_tick_data(df)

            # 标准化股票代码
            df = cleaner.standardize_symbols(df)

        # 导入数据
        if data_type == "daily":
            analytics_db = get_analytics_db()
            count = analytics_db.insert_daily_data(df)

            return {"status": "success", "message": f"成功导入 {count} 条日线数据", "count": count}
        else:
            raise HTTPException(status_code=501, detail=f"暂不支持导入 {data_type} 数据")

    except Exception as e:
        logger.error(f"导入 CSV 数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{data_type}")
async def export_data(
    data_type: str,
    symbols: List[str] = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    format: str = Query("csv", description="导出格式: csv, parquet"),
):
    """导出数据"""
    try:
        if data_type == "daily":
            analytics_db = get_analytics_db()
            df = analytics_db.query_daily_data(
                symbols=symbols, start_date=start_date, end_date=end_date
            )

            if format == "csv":
                # 返回 CSV 数据
                import io

                from fastapi.responses import StreamingResponse

                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                binary_buffer = io.BytesIO(csv_buffer.getvalue().encode())

                return StreamingResponse(
                    binary_buffer,
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=market_daily_{datetime.now().strftime('%Y%m%d')}.csv"
                    },
                )

            elif format == "parquet":
                # 实现 Parquet 导出
                try:
                    import io

                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    from fastapi.responses import StreamingResponse

                    # 将 DataFrame 转换为 Parquet
                    table = pa.Table.from_pandas(df)
                    buffer = io.BytesIO()
                    pq.write_table(table, buffer)
                    buffer.seek(0)

                    return StreamingResponse(
                        buffer,
                        media_type="application/octet-stream",
                        headers={
                            "Content-Disposition": f"attachment; filename=market_daily_{datetime.now().strftime('%Y%m%d')}.parquet"
                        },
                    )
                except ImportError:
                    raise HTTPException(
                        status_code=501,
                        detail="Parquet 导出需要安装 pyarrow 库: pip install pyarrow",
                    )

        else:
            raise HTTPException(status_code=501, detail=f"暂不支持导出 {data_type} 数据")

    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators", response_model=IndicatorResponse)
async def calculate_indicators(request: IndicatorRequest):
    """计算技术指标"""
    try:
        # 查询基础数据
        analytics_db = get_analytics_db()
        df = analytics_db.query_daily_data(
            symbols=[request.symbol], start_date=request.start_date, end_date=request.end_date
        )

        if df.empty:
            raise HTTPException(status_code=404, detail="未找到数据")

        # 计算指标
        indicators = SimpleIndicators()
        result_df = indicators.calculate_all(df, indicators=request.indicators)

        # 转换结果
        data = result_df.to_dict("records")

        # 处理日期和 NaN 值
        for item in data:
            if "date" in item and isinstance(item["date"], pd.Timestamp):
                item["date"] = item["date"].strftime("%Y-%m-%d")

            # 将 NaN 转换为 None
            for key, value in item.items():
                if pd.isna(value):
                    item[key] = None

        return IndicatorResponse(symbol=request.symbol, count=len(data), data=data)

    except Exception as e:
        logger.error(f"计算技术指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clean")
async def clean_old_data(
    before_date: date = Query(..., description="删除此日期之前的数据"),
    data_type: str = Query("all", description="数据类型: all, daily, tick"),
):
    """清理旧数据"""
    try:
        from sqlalchemy.orm import Session

        from deepsearch.infrastructure.persistence.database import get_db
        from deepsearch.infrastructure.providers.entities.legacy_models import MinuteKline, TickData

        db: Session = next(get_db())
        deleted_count = {"daily": 0, "minute": 0, "tick": 0}

        try:
            # 清理日线数据
            if data_type in ["all", "daily"]:
                # 使用 DuckDB 清理日线数据
                analytics_db = get_analytics_db()
                conn = analytics_db.conn
                result = conn.execute(
                    "DELETE FROM daily_kline WHERE date < ?", [before_date]
                ).fetchone()
                deleted_count["daily"] = result[0] if result else 0

            # 清理分钟线数据
            if data_type in ["all", "minute"]:
                result = db.query(MinuteKline).filter(MinuteKline.datetime < before_date).delete()
                deleted_count["minute"] = result

            # 清理 Tick 数据
            if data_type in ["all", "tick"]:
                result = db.query(TickData).filter(TickData.datetime < before_date).delete()
                deleted_count["tick"] = result

            # 提交事务
            db.commit()

            total_deleted = sum(deleted_count.values())

            return {
                "status": "success",
                "message": f"成功删除 {total_deleted} 条数据",
                "details": deleted_count,
                "before_date": before_date.isoformat(),
            }

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks")
async def get_stocks(
    limit: int = Query(100, description="返回股票数量限制")
) -> List[Dict[str, Any]]:
    """
    获取股票列表

    Returns:
        股票列表
    """
    try:
        # 使用数据源管理器获取股票列表
        data_service = get_data_service()
        stocks = await data_service.get_stock_list(limit=limit)

        if not stocks:
            return []

        return cast(List[Dict[str, Any]], stocks)
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取股票列表失败: {str(e)}")


@router.get("/kline")
async def get_kline_data(
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("1d", description="周期"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(100, description="数据条数限制"),
) -> List[Dict[str, Any]]:
    """
    获取K线数据

    Returns:
        K线数据列表
    """
    try:
        # 使用数据源管理器获取K线数据
        data_service = get_data_service()
        kline_data = await data_service.get_kline_data(
            symbol=symbol, period=period, start_date=start_date, end_date=end_date, limit=limit
        )

        if not kline_data:
            return []

        return cast(List[Dict[str, Any]], kline_data)
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取K线数据失败: {str(e)}")


@router.get("/symbols")
async def get_symbols():
    """获取所有股票代码列表"""
    try:
        analytics_db = get_analytics_db()

        # 查询所有不同的股票代码
        result = analytics_db.conn.execute(
            """
                                           SELECT DISTINCT symbol
                                           FROM market_daily
                                           ORDER BY symbol
                                           """
        ).fetchall()

        symbols = [row[0] for row in result]

        return {"count": len(symbols), "symbols": symbols}

    except Exception as e:
        logger.error(f"获取股票代码列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
