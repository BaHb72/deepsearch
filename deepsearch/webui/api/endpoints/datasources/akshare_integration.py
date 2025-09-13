"""
AKShare数据源API集成

提供AKShare数据源的市场总貌、股票数据等API接口
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, date
from loguru import logger
import asyncio

from deepsearch.webui.api.common.response_format import APIResponse, APIException, ErrorCodes

# 尝试导入akshare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("AKShare未安装，部分功能将不可用")


# 创建路由
router = APIRouter(prefix="/api/market/akshare", tags=["AKShare Integration"])


# 数据模型
class MarketOverviewResponse(BaseModel):
    """市场总貌响应"""
    exchange: str = Field(..., description="交易所: sse|szse")
    data: Dict[str, Any] = Field(..., description="市场数据")
    update_time: datetime = Field(..., description="更新时间")


class StockListRequest(BaseModel):
    """股票列表请求"""
    market: Optional[str] = Field("all", description="市场: all|sh|sz|bj|hk")
    sector: Optional[str] = Field(None, description="板块筛选")
    page: Optional[int] = Field(1, description="页码")
    page_size: Optional[int] = Field(50, description="每页大小")


def check_akshare():
    """检查AKShare是否可用"""
    if not AKSHARE_AVAILABLE:
        raise APIException(
            code="AKSHARE_NOT_AVAILABLE",
            message="AKShare数据源未安装或不可用",
            status_code=503
        )


@router.get("/status")
async def get_akshare_status():
    """
    获取AKShare数据源状态
    
    Returns:
        AKShare状态信息
    """
    try:
        status = {
            "available": AKSHARE_AVAILABLE,
            "version": None,
            "apis_count": 0,
            "last_check": datetime.now()
        }
        
        if AKSHARE_AVAILABLE:
            # 获取版本信息
            import akshare
            status["version"] = getattr(akshare, "__version__", "unknown")
            
            # 统计可用API数量（简化计算）
            status["apis_count"] = len([attr for attr in dir(akshare) if attr.startswith("stock_")])
            
        return APIResponse.success(
            data=status,
            message="AKShare状态获取成功"
        )
    except Exception as e:
        logger.error(f"获取AKShare状态失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取状态失败: {str(e)}",
            status_code=500
        )


@router.get("/sse/summary")
async def get_sse_summary():
    """
    获取上海证券交易所市场总貌
    
    对应AKShare接口: stock_sse_summary
    
    Returns:
        上交所市场总貌数据
    """
    try:
        check_akshare()
        
        # 获取数据
        df = ak.stock_sse_summary()
        
        # 转换为字典格式
        data = {
            "market_data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "row_count": len(df),
            "update_time": datetime.now()
        }
        
        return APIResponse.success(
            data=data,
            message="上交所市场总貌获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取上交所市场总貌失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取数据失败: {str(e)}",
            status_code=500
        )


@router.get("/szse/summary")
async def get_szse_summary(
    date: Optional[str] = Query(None, description="日期，格式：20240110")
):
    """
    获取深圳证券交易所市场总貌
    
    对应AKShare接口: stock_szse_summary
    
    Args:
        date: 查询日期，默认为最新
        
    Returns:
        深交所市场总貌数据
    """
    try:
        check_akshare()
        
        # 如果没有指定日期，使用今天
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        
        # 获取数据
        df = ak.stock_szse_summary(date=date)
        
        # 转换为字典格式
        data = {
            "market_data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "row_count": len(df),
            "query_date": date,
            "update_time": datetime.now()
        }
        
        return APIResponse.success(
            data=data,
            message="深交所市场总貌获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取深交所市场总貌失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取数据失败: {str(e)}",
            status_code=500
        )


@router.get("/overview")
async def get_market_overview(
    source: str = Query("akshare", description="数据源"),
    exchange: str = Query("all", description="交易所: all|sse|szse")
):
    """
    统一的市场总貌接口
    
    Args:
        source: 数据源（当前仅支持akshare）
        exchange: 交易所选择
        
    Returns:
        市场总貌数据
    """
    try:
        if source != "akshare":
            return APIResponse.error(
                code="INVALID_SOURCE",
                message=f"不支持的数据源: {source}"
            )
        
        check_akshare()
        
        result = {
            "source": source,
            "exchange": exchange,
            "data": {},
            "update_time": datetime.now()
        }
        
        # 获取不同交易所的数据
        if exchange in ["all", "sse"]:
            try:
                sse_df = ak.stock_sse_summary()
                result["data"]["sse"] = {
                    "summary": sse_df.to_dict(orient="records"),
                    "total_market_value": float(sse_df[sse_df["项目"] == "总市值"]["股票"].values[0]) if len(sse_df) > 0 else 0,
                    "listed_companies": int(sse_df[sse_df["项目"] == "上市公司"]["股票"].values[0]) if len(sse_df) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"获取上交所数据失败: {e}")
                result["data"]["sse"] = {"error": str(e)}
        
        if exchange in ["all", "szse"]:
            try:
                szse_date = datetime.now().strftime("%Y%m%d")
                szse_df = ak.stock_szse_summary(date=szse_date)
                result["data"]["szse"] = {
                    "summary": szse_df.to_dict(orient="records"),
                    "stock_count": int(szse_df[szse_df["证券类别"] == "股票"]["数量"].values[0]) if len(szse_df) > 0 else 0,
                    "total_market_value": float(szse_df[szse_df["证券类别"] == "股票"]["总市值"].values[0]) if len(szse_df) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"获取深交所数据失败: {e}")
                result["data"]["szse"] = {"error": str(e)}
        
        return APIResponse.success(
            data=result,
            message="市场总貌获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取市场总貌失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取数据失败: {str(e)}",
            status_code=500
        )


@router.get("/stock/list")
async def get_stock_list(
    market: str = Query("all", description="市场: all|sh|sz"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页大小")
):
    """
    获取股票列表
    
    Args:
        market: 市场选择
        page: 页码
        page_size: 每页大小
        
    Returns:
        分页的股票列表
    """
    try:
        check_akshare()
        
        # 获取A股票列表
        if market == "sh":
            df = ak.stock_info_sh_name_code()
            market_name = "上海"
        elif market == "sz":
            df = ak.stock_info_sz_name_code()
            market_name = "深圳"
        else:
            # 获取所有A股
            df = ak.stock_info_a_code_name()
            market_name = "全部"
        
        # 计算分页
        total = len(df)
        start = (page - 1) * page_size
        end = start + page_size
        
        # 获取分页数据
        page_data = df.iloc[start:end].to_dict(orient="records")
        
        return APIResponse.paginated(
            data=page_data,
            total=total,
            page=page,
            page_size=page_size,
            message=f"{market_name}市场股票列表获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取股票列表失败: {str(e)}",
            status_code=500
        )


@router.get("/stock/{symbol}/kline")
async def get_stock_kline(
    symbol: str,
    period: str = Query("daily", description="周期: daily|weekly|monthly"),
    start_date: Optional[str] = Query(None, description="开始日期: 20240101"),
    end_date: Optional[str] = Query(None, description="结束日期: 20240110"),
    adjust: str = Query("qfq", description="复权: qfq(前复权)|hfq(后复权)|空(不复权)")
):
    """
    获取股票K线数据
    
    Args:
        symbol: 股票代码
        period: K线周期
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权类型
        
    Returns:
        K线数据
    """
    try:
        check_akshare()
        
        # 获取K线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date or "20240101",
            end_date=end_date or datetime.now().strftime("%Y%m%d"),
            adjust=adjust
        )
        
        # 转换为标准格式
        data = {
            "symbol": symbol,
            "period": period,
            "adjust": adjust,
            "kline_data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "count": len(df),
            "start_date": df.iloc[0]["日期"] if len(df) > 0 else None,
            "end_date": df.iloc[-1]["日期"] if len(df) > 0 else None
        }
        
        return APIResponse.success(
            data=data,
            message=f"股票{symbol} K线数据获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取K线数据失败: {str(e)}",
            status_code=500
        )


@router.get("/realtime/quote")
async def get_realtime_quote(
    symbols: str = Query(..., description="股票代码，多个用逗号分隔")
):
    """
    获取实时行情
    
    Args:
        symbols: 股票代码列表
        
    Returns:
        实时行情数据
    """
    try:
        check_akshare()
        
        symbol_list = symbols.split(",")
        quotes = []
        
        for symbol in symbol_list:
            try:
                # 获取实时数据
                df = ak.stock_zh_a_spot_em()
                stock_data = df[df["代码"] == symbol]
                
                if not stock_data.empty:
                    quotes.append(stock_data.iloc[0].to_dict())
                else:
                    quotes.append({
                        "symbol": symbol,
                        "error": "未找到该股票"
                    })
            except Exception as e:
                quotes.append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return APIResponse.success(
            data={
                "quotes": quotes,
                "count": len(quotes),
                "update_time": datetime.now()
            },
            message="实时行情获取成功"
        )
        
    except APIException as e:
        return e.to_response()
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return APIResponse.error(
            code="AKSHARE_API_ERROR",
            message=f"获取实时行情失败: {str(e)}",
            status_code=500
        )