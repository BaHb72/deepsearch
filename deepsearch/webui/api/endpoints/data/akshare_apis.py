"""
AkShare API列表查看端点

提供查看系统已接入的所有AkShare API的功能
"""
from typing import Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
from loguru import logger

from deepsearch.data_providers.implementations.akshare.akshare_api_mapping import AkShareAPIMapping

router = APIRouter(prefix="/api/akshare", tags=["akshare"])


@router.get("/apis/list")
async def list_all_apis(
    category: Optional[str] = Query(None, description="按类别筛选"),
    search: Optional[str] = Query(None, description="搜索API名称或描述")
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
        apis = []
        
        for name, info in AkShareAPIMapping.API_FUNCTIONS.items():
            # 类别筛选
            if category and info.get("category") != category:
                continue
                
            # 搜索筛选
            if search:
                search_lower = search.lower()
                if (search_lower not in name.lower() and 
                    search_lower not in info.get("description", "").lower()):
                    continue
            
            api_info = {
                "name": name,
                "description": info.get("description", ""),
                "category": info.get("category", "unknown"),
                "cache_ttl": info.get("cache_ttl", 300),
                "params": info.get("params", []),
                "param_defaults": info.get("param_defaults", {}),
                "param_transform": list(info.get("param_transform", {}).keys())
            }
            apis.append(api_info)
        
        # 按类别和名称排序
        apis.sort(key=lambda x: (x["category"], x["name"]))
        
        # 统计信息
        categories_count = {}
        for api in apis:
            cat = api["category"]
            categories_count[cat] = categories_count.get(cat, 0) + 1
        
        return {
            "success": True,
            "total": len(apis),
            "filtered": len(apis),
            "categories": categories_count,
            "apis": apis
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
        categories = {}
        
        # 类别中文名称映射
        category_names = {
            "realtime": "实时行情",
            "historical": "历史数据",
            "minute": "分钟数据",
            "intraday": "分时数据",
            "orderbook": "盘口数据",
            "technical": "技术指标",
            "market": "市场统计",
            "anomaly": "异动监控",
            "sector": "板块数据",
            "hsgt": "沪深港通",
            "info": "个股信息",
            "restriction": "限售解禁",
            "holder": "股东信息",
            "unknown": "其他"
        }
        
        # 初始化所有类别
        for cat_key, cat_name in category_names.items():
            categories[cat_key] = {
                "name": cat_name,
                "count": 0,
                "apis": []
            }
        
        # 分组API
        for name, info in AkShareAPIMapping.API_FUNCTIONS.items():
            cat = info.get("category", "unknown")
            
            # 确保类别存在
            if cat not in categories:
                categories[cat] = {
                    "name": cat,
                    "count": 0,
                    "apis": []
                }
            
            api_info = {
                "name": name,
                "description": info.get("description", ""),
                "cache_ttl": info.get("cache_ttl", 300),
                "params": info.get("params", [])
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
            "categories": categories
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
            "usage_example": f"await provider.call_api('{api_name}', params)"
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
            "timeout": "超时时间(秒)"
        }
        
        detail["param_descriptions"] = {
            param: param_descriptions.get(param, "")
            for param in detail["params"]
        }
        
        return {
            "success": True,
            "data": detail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取API详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apis/statistics")
async def get_api_statistics():
    """
    获取API统计信息
    
    Returns:
        API的统计摘要
    """
    try:
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
                "no_params": total - with_params
            }
        }
        
    except Exception as e:
        logger.error(f"获取API统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))