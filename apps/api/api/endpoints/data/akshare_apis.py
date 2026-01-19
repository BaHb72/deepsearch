"""
AkShare API端点模块

提供查看系统已接入的所有AkShare API的功能，以及通用API调用接口
"""

from typing import Any, Dict, Optional

from core.infrastructure.providers.implementations.akshare.akshare_api_mapping import (
    AkShareAPIMapping,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.provider_deps import get_akshare_provider
from apps.api.api.providers import DataProviderFactory, DataSourceType

router = APIRouter(prefix="/api/akshare", tags=["akshare"])


# ================== 请求模型 ==================


class CallApiRequest(BaseModel):
    """通用API调用请求"""

    api_name: str = Field(
        ...,
        description="AkShare API名称，如 stock_zh_a_spot_em",
        examples=["stock_zh_a_spot_em"],
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="API参数，根据不同API有不同参数",
        examples=[{"symbol": "000001", "period": "daily"}],
    )
    use_cache: bool = Field(
        default=True,
        description="是否使用缓存",
    )


# ================== 通用API调用 ==================


@router.post("/call", summary="通用AkShare API调用")
async def call_akshare_api(request: CallApiRequest):
    """
    通用AkShare API调用接口

    允许调用任意已注册的AkShare API函数。
    可通过 /apis/list 查看所有可用的API。

    Args:
        request: 调用请求，包含API名称和参数

    Returns:
        API返回的数据

    Examples:
        - 获取实时行情: {"api_name": "stock_zh_a_spot_em", "params": {}}
        - 获取历史K线: {"api_name": "stock_zh_a_hist", "params": {"symbol": "000001", "period": "daily"}}
        - 获取涨停池: {"api_name": "stock_zt_pool_em", "params": {"date": "20240101"}}
    """
    try:
        # 验证API是否存在
        api_info = AkShareAPIMapping.get_api_info(request.api_name)
        if not api_info:
            # 尝试直接调用，可能是未注册但有效的API
            logger.warning(f"API '{request.api_name}' 未在映射表中注册，尝试直接调用")

        # 获取AkShare provider
        provider = await DataProviderFactory.get_provider_async(DataSourceType.AKSHARE)

        if provider is None:
            raise HTTPException(status_code=503, detail="AkShare provider 不可用")

        # 调用API
        result = await provider.call_api(
            api_name=request.api_name,
            params=request.params or {},
            use_cache=request.use_cache,
        )

        # 统计信息
        record_count = len(result) if isinstance(result, list) else 1

        return {
            "success": True,
            "api_name": request.api_name,
            "params": request.params,
            "cached": request.use_cache,
            "record_count": record_count,
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"调用AkShare API '{request.api_name}' 失败: {e}")
        raise HTTPException(status_code=500, detail=f"API调用失败: {str(e)}")


# ================== API元数据查询 ==================


@router.get("/apis/list")
async def list_all_apis(
    category: Optional[str] = Query(None, description="按类别筛选"),
    search: Optional[str] = Query(None, description="搜索API名称或描述"),
):
    """
    列出所有已接入的AkShare API

    Args:
        category: 可选的类别筛选 (realtime, historical, minute, anomaly, sector, hsgt等)
        search: 可选的搜索关键词

    Returns:
        API列表及统计信息
    """
    try:
        AkShareAPIMapping._ensure_catalog_loaded()
        apis = []

        for name, info in AkShareAPIMapping.API_FUNCTIONS.items():
            # 类别筛选
            if category and info.get("category") != category:
                continue

            # 搜索筛选
            if search:
                search_lower = search.lower()
                if (
                    search_lower not in name.lower()
                    and search_lower not in info.get("description", "").lower()
                ):
                    continue

            api_info = {
                "name": name,
                "description": info.get("description", ""),
                "category": info.get("category", "unknown"),
                "cache_ttl": info.get("cache_ttl", 300),
                "params": info.get("params", []),
                "param_defaults": info.get("param_defaults", {}),
                "param_transform": list(info.get("param_transform", {}).keys()),
            }
            apis.append(api_info)

        # 按类别和名称排序
        apis.sort(key=lambda x: (x["category"], x["name"]))

        # 统计信息
        categories_count: dict[str, int] = {}
        for api in apis:
            cat = api["category"]
            categories_count[cat] = categories_count.get(cat, 0) + 1

        return {
            "success": True,
            "total": len(apis),
            "filtered": len(apis),
            "categories": categories_count,
            "apis": apis,
        }

    except Exception as e:
        logger.error(f"获取API列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apis/by-category")
async def list_apis_by_category():
    """
    按类别分组列出所有API

    Returns:
        按类别分组的API字典
    """
    try:
        AkShareAPIMapping._ensure_catalog_loaded()
        categories = {}

        # 类别中文名称映射
        category_names = {
            "realtime": "实时数据",
            "historical": "历史数据",
            "minute": "分钟数据",
            "intraday": "分时数据",
            "orderbook": "盘口数据",
            "technical": "技术指标",
            "market": "市场统计",
            "anomaly": "异动数据",
            "sector": "板块数据",
            "hsgt": "沪深港通",
            "info": "基础信息",
            "restriction": "限售解禁",
            "holder": "股东信息",
            "stock": "股票数据",
            "fund": "基金数据",
            "bond": "债券数据",
            "futures": "期货数据",
            "options": "期权数据",
            "forex": "外汇数据",
            "crypto": "加密货币",
            "fundamental": "基本面信息",
            "macro": "宏观经济",
            "article": "新闻资讯",
            "index": "指数数据",
            "misc": "其他数据",
            "unknown": "未知",
        }
        # 初始化所有类别
        for cat_key, cat_name in category_names.items():
            categories[cat_key] = {"name": cat_name, "count": 0, "apis": []}

        # 分组API
        for name, info in AkShareAPIMapping.API_FUNCTIONS.items():
            cat = info.get("category", "unknown")

            # 确保类别存在
            if cat not in categories:
                categories[cat] = {"name": cat, "count": 0, "apis": []}

            api_info = {
                "name": name,
                "description": info.get("description", ""),
                "cache_ttl": info.get("cache_ttl", 300),
                "params": info.get("params", []),
            }

            categories[cat]["apis"].append(api_info)
            categories[cat]["count"] += 1

        # 移除空类别
        categories = {k: v for k, v in categories.items() if v["count"] > 0}

        # 对每个类别内的API排序
        for cat in categories.values():
            cat["apis"].sort(key=lambda x: x["name"])

        return {
            "success": True,
            "total_apis": len(AkShareAPIMapping.API_FUNCTIONS),
            "total_categories": len(categories),
            "categories": categories,
        }

    except Exception as e:
        logger.error(f"按类别获取API失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apis/{api_name}")
async def get_api_detail(api_name: str):
    """
    获取特定API的详细信息

    Args:
        api_name: API名称

    Returns:
        API的详细信息
    """
    try:
        api_info = AkShareAPIMapping.get_api_info(api_name)

        if not api_info:
            raise HTTPException(status_code=404, detail=f"API '{api_name}' 不存在")

        # 构建详细信息
        detail = {
            "name": api_name,
            "description": api_info.get("description", ""),
            "category": api_info.get("category", "unknown"),
            "cache_ttl": api_info.get("cache_ttl", 300),
            "params": api_info.get("params", []),
            "param_defaults": api_info.get("param_defaults", {}),
            "param_transform": api_info.get("param_transform", {}),
            "usage_example": f"await provider.call_api('{api_name}', params)",
        }

        # 添加参数说明
        param_descriptions = {
            "symbol": "股票代码 (如: 000001)",
            "period": "周期 (daily/weekly/monthly)",
            "start_date": "开始日期 (格式: YYYY-MM-DD)",
            "end_date": "结束日期 (格式: YYYY-MM-DD)",
            "adjust": "复权类型 (空字符串:不复权, qfq:前复权, hfq:后复权)",
            "date": "日期 (格式: YYYY-MM-DD)",
            "indicator": "指标类型",
            "market": "市场类型",
            "timeout": "超时时间(秒)",
        }

        detail["param_descriptions"] = {
            param: param_descriptions.get(param, "") for param in detail["params"]
        }

        return {"success": True, "data": detail}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取API详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 板块数据 API ==================


async def _get_akshare_provider():
    """获取AkShare provider实例"""
    provider = await DataProviderFactory.get_provider_async(DataSourceType.AKSHARE)
    if provider is None:
        raise HTTPException(status_code=503, detail="AkShare provider 不可用")
    return provider


@router.get("/boards/industry", summary="获取行业板块列表")
async def get_industry_boards():
    """
    获取行业板块列表

    Returns:
        行业板块列表，包含板块名称、涨跌幅、成交量等信息
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_industry_boards()
        return {
            "success": True,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取行业板块失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/concept", summary="获取概念板块列表")
async def get_concept_boards():
    """
    获取概念板块列表

    Returns:
        概念板块列表，包含板块名称、涨跌幅、成交量等信息
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_concept_boards()
        return {
            "success": True,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取概念板块失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/{board_name}/stocks", summary="获取板块成分股")
async def get_board_constituents(
    board_name: str,
    board_type: str = Query("industry", description="板块类型: industry(行业)/concept(概念)"),
):
    """
    获取板块成分股列表

    Args:
        board_name: 板块名称
        board_type: 板块类型 (industry/concept)

    Returns:
        板块成分股列表
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_board_constituents(board_name, board_type)
        return {
            "success": True,
            "board_name": board_name,
            "board_type": board_type,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 北向资金 API ==================


@router.get("/hsgt/flow", summary="获取北向资金流向")
async def get_north_flow(
    indicator: str = Query("北向资金", description="指标类型: 沪股通/深股通/北向资金"),
):
    """
    获取北向资金流向历史数据

    Args:
        indicator: 指标类型 (沪股通/深股通/北向资金)

    Returns:
        资金流向历史数据
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_north_flow(indicator)
        return {
            "success": True,
            "indicator": indicator,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取北向资金流向失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hsgt/hold", summary="获取北向资金持股排行")
async def get_north_hold_stock(
    market: str = Query("北向", description="市场: 北向/沪股通/深股通"),
    indicator: str = Query(
        "今日排行", description="排行类型: 今日排行/5日排行/10日排行/月排行/季排行/年排行"
    ),
):
    """
    获取北向资金持股排行

    Args:
        market: 市场 (北向/沪股通/深股通)
        indicator: 排行类型 (今日排行/5日排行/10日排行/月排行/季排行/年排行)

    Returns:
        持股排行数据
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_north_hold_stock(market, indicator)
        return {
            "success": True,
            "market": market,
            "indicator": indicator,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取北向资金持股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 异动数据 API ==================


@router.get("/anomaly/limit-up", summary="获取涨停池数据")
async def get_limit_up_pool(
    date: Optional[str] = Query(None, description="日期，格式YYYYMMDD，默认最新"),
):
    """
    获取涨停池数据

    Args:
        date: 日期 YYYYMMDD，默认最新

    Returns:
        涨停股票列表
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_limit_up_pool(date)
        return {
            "success": True,
            "date": date or "latest",
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取涨停池失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly/limit-down", summary="获取跌停池数据")
async def get_limit_down_pool(
    date: Optional[str] = Query(None, description="日期，格式YYYYMMDD，默认最新"),
):
    """
    获取跌停池数据

    Args:
        date: 日期 YYYYMMDD，默认最新

    Returns:
        跌停股票列表
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_limit_down_pool(date)
        return {
            "success": True,
            "date": date or "latest",
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取跌停池失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly/dragon-tiger", summary="获取龙虎榜数据")
async def get_dragon_tiger(
    date: Optional[str] = Query(None, description="日期，格式YYYYMMDD，默认最新"),
):
    """
    获取龙虎榜数据

    Args:
        date: 日期 YYYYMMDD，默认最新

    Returns:
        龙虎榜数据
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_dragon_tiger(date)
        return {
            "success": True,
            "date": date or "latest",
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 融资融券 API ==================


@router.get("/margin/{market}", summary="获取融资融券数据")
async def get_margin_trading(
    market: str,
):
    """
    获取融资融券数据

    Args:
        market: 市场代码 (sh/sz)

    Returns:
        融资融券数据
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_margin_trading(market)
        return {
            "success": True,
            "market": market,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取融资融券数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 个股数据 API ==================


@router.get("/stock/{symbol}/info", summary="获取个股详细信息")
async def get_stock_info(symbol: str):
    """
    获取个股详细信息

    Args:
        symbol: 股票代码

    Returns:
        个股详细信息
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_stock_info(symbol)
        return {
            "success": True,
            "symbol": symbol,
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取个股信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{symbol}/kline", summary="获取日线K线数据")
async def get_stock_kline(
    symbol: str,
    period: str = Query("daily", description="周期: daily/weekly/monthly"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("", description="复权类型: 空字符串(不复权)/qfq(前复权)/hfq(后复权)"),
):
    """
    获取日线K线数据

    Args:
        symbol: 股票代码
        period: 周期 (daily/weekly/monthly)
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        adjust: 复权类型

    Returns:
        K线数据列表
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_kline(symbol, period, start_date, end_date, adjust)
        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "adjust": adjust or "none",
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{symbol}/minute", summary="获取分钟K线数据")
async def get_minute_kline(
    symbol: str,
    period: str = Query("1", description="周期: 1/5/15/30/60 分钟"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD HH:MM:SS"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD HH:MM:SS"),
    adjust: str = Query("", description="复权类型: qfq/hfq"),
):
    """
    获取分钟K线数据

    Args:
        symbol: 股票代码
        period: 周期 (1/5/15/30/60 分钟)
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权类型

    Returns:
        分钟K线数据
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_minute_kline(symbol, period, start_date, end_date, adjust)
        return {
            "success": True,
            "symbol": symbol,
            "period": f"{period}min",
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分钟K线失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== API统计 ==================


@router.get("/apis/statistics")
async def get_api_statistics():
    """
    获取API统计信息

    Returns:
        API的统计摘要
    """
    try:
        AkShareAPIMapping._ensure_catalog_loaded()
        total = len(AkShareAPIMapping.API_FUNCTIONS)

        # 按类别统计
        by_category = {}
        # 按缓存时间统计
        by_cache_ttl = {}
        # 需要参数的API
        with_params = 0
        # 有默认值的API
        with_defaults = 0

        for name, info in AkShareAPIMapping.API_FUNCTIONS.items():
            # 类别统计
            cat = info.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

            # 缓存时间统计
            ttl = info.get("cache_ttl", 300)
            ttl_group = f"{ttl}秒"
            by_cache_ttl[ttl_group] = by_cache_ttl.get(ttl_group, 0) + 1

            # 参数统计
            if info.get("params"):
                with_params += 1
            if info.get("param_defaults"):
                with_defaults += 1

        return {
            "success": True,
            "statistics": {
                "total_apis": total,
                "by_category": by_category,
                "by_cache_ttl": by_cache_ttl,
                "with_params": with_params,
                "with_defaults": with_defaults,
                "no_params": total - with_params,
            },
        }

    except Exception as e:
        logger.error(f"获取API统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 实时行情 API ==================


@router.get("/realtime/quotes", summary="获取实时行情")
async def get_realtime_quotes(
    symbols: str = Query(..., description="股票代码列表，逗号分隔，如: 000001,600000,300750"),
):
    """
    获取多只股票的实时行情数据

    Args:
        symbols: 股票代码列表，逗号分隔

    Returns:
        实时行情数据字典，key为股票代码
    """
    try:
        provider = await _get_akshare_provider()
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供至少一个股票代码")

        result = await provider.get_realtime_quotes(symbol_list)
        return {
            "success": True,
            "symbols": symbol_list,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 股票列表 API ==================


@router.get("/stock/list", summary="获取股票列表")
async def get_stock_list(
    provider=Depends(get_akshare_provider),  # 使用新的依赖注入
):
    """
    获取A股股票列表

    Returns:
        股票列表，包含股票代码和名称

    Note:
        此端点已迁移到新 Provider 架构 (Phase 4)
    """
    try:
        result = await provider.get_stock_list()
        return {
            "success": True,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 交易日历 API ==================


@router.get("/calendar", summary="获取交易日历")
async def get_calendar(
    market: str = Query("SH", description="市场代码: SH(上海)/SZ(深圳)"),
):
    """
    获取交易日历

    Args:
        market: 市场代码 (SH/SZ)

    Returns:
        交易日列表 (YYYYMMDD 格式)
    """
    try:
        provider = await _get_akshare_provider()
        result = await provider.get_calendar(market)
        return {
            "success": True,
            "market": market,
            "count": len(result),
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
