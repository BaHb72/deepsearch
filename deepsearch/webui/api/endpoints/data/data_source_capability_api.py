"""
数据源能力对比API

提供数据源能力查询、对比和推荐功能
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from deepsearch.data_providers.interfaces.capabilities import (
    DataCapability,
    DATA_SOURCE_CAPABILITIES,
    get_capable_providers,
    check_provider_capability
)

router = APIRouter(prefix="/api/datasource", tags=["datasource_capability"])


# 数据源元数据
DATA_SOURCE_METADATA = {
    "amazingdata": {
        "name": "AmazingData",
        "label": "企业级数据",
        "description": "最全面的企业级金融数据服务",
        "badge": "专业版",
        "color": "gold",
        "priority": 1,
        "unique_features": [
            "融资融券数据",
            "北向资金流",
            "完整财务指标",
            "股东变动追踪",
            "Level2深度数据"
        ],
        "connection_type": "remote",
        "requires_auth": True,
        "cost": "paid"
    },
    "qmt": {
        "name": "QMT",
        "label": "量化终端",
        "description": "本地量化交易终端",
        "badge": "Level2",
        "color": "blue",
        "priority": 2,
        "unique_features": [
            "Level2逐笔数据",
            "实时盘口",
            "逐笔成交明细",
            "完整筹码分布"
        ],
        "connection_type": "local",
        "requires_auth": True,
        "cost": "paid"
    },
    "miniqmt": {
        "name": "MiniQMT",
        "label": "轻量终端",
        "description": "轻量级量化终端",
        "badge": "基础版",
        "color": "green",
        "priority": 3,
        "unique_features": [
            "实时行情",
            "盘口数据",
            "筹码分布",
            "异动监控"
        ],
        "connection_type": "local",
        "requires_auth": True,
        "cost": "free"
    },
    "akshare": {
        "name": "AKShare",
        "label": "开源数据",
        "description": "免费开源金融数据接口",
        "badge": "免费版",
        "color": "gray",
        "priority": 4,
        "unique_features": [
            "历史数据",
            "基础行情",
            "财务数据",
            "北向资金"
        ],
        "connection_type": "remote",
        "requires_auth": False,
        "cost": "free"
    }
}

# 能力分类元数据
CAPABILITY_CATEGORIES = {
    "market": {
        "name": "市场数据",
        "capabilities": [
            DataCapability.MARKET_OVERVIEW,
            DataCapability.MARKET_BREADTH,
            DataCapability.CAPITAL_FLOW,
            DataCapability.SECTOR_DATA,
            DataCapability.ANOMALY_DETECTION
        ]
    },
    "quote": {
        "name": "行情数据",
        "capabilities": [
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA
        ]
    },
    "depth": {
        "name": "深度数据",
        "capabilities": [
            DataCapability.ORDER_BOOK,
            DataCapability.LEVEL2_DATA,
            DataCapability.TRANSACTION_DATA
        ]
    },
    "special": {
        "name": "特色数据",
        "capabilities": [
            DataCapability.CHIP_DISTRIBUTION,
            DataCapability.DRAGON_TIGER,
            DataCapability.BLOCK_TRADE,
            DataCapability.MARGIN_TRADING,
            DataCapability.NORTH_FLOW
        ]
    },
    "fundamental": {
        "name": "基础信息",
        "capabilities": [
            DataCapability.STOCK_INFO,
            DataCapability.FINANCIAL_DATA,
            DataCapability.ANNOUNCEMENT,
            DataCapability.KEY_INDICATORS,
            DataCapability.SHAREHOLDER_INFO
        ]
    },
    "utility": {
        "name": "工具数据",
        "capabilities": [
            DataCapability.TRADING_CALENDAR,
            DataCapability.ADJUSTMENT_FACTOR
        ]
    }
}

# 能力中文名称映射
CAPABILITY_NAMES = {
    DataCapability.MARKET_OVERVIEW: "市场概览",
    DataCapability.MARKET_BREADTH: "市场宽度",
    DataCapability.CAPITAL_FLOW: "资金流向",
    DataCapability.SECTOR_DATA: "板块数据",
    DataCapability.ANOMALY_DETECTION: "异动监控",
    DataCapability.REALTIME_QUOTES: "实时行情",
    DataCapability.KLINE_DATA: "K线数据",
    DataCapability.TICK_DATA: "逐笔数据",
    DataCapability.MINUTE_DATA: "分钟数据",
    DataCapability.ORDER_BOOK: "盘口数据",
    DataCapability.LEVEL2_DATA: "Level2数据",
    DataCapability.TRANSACTION_DATA: "成交明细",
    DataCapability.CHIP_DISTRIBUTION: "筹码分布",
    DataCapability.DRAGON_TIGER: "龙虎榜",
    DataCapability.BLOCK_TRADE: "大宗交易",
    DataCapability.STOCK_INFO: "股票信息",
    DataCapability.FINANCIAL_DATA: "财务数据",
    DataCapability.ANNOUNCEMENT: "公告数据",
    DataCapability.MARGIN_TRADING: "融资融券",
    DataCapability.NORTH_FLOW: "北向资金",
    DataCapability.KEY_INDICATORS: "关键指标",
    DataCapability.SHAREHOLDER_INFO: "股东信息",
    DataCapability.TRADING_CALENDAR: "交易日历",
    DataCapability.ADJUSTMENT_FACTOR: "复权因子"
}


@router.get("/capabilities/matrix")
async def get_capability_matrix():
    """
    获取完整的数据源能力矩阵
    
    Returns:
        包含所有数据源能力对比的矩阵
    """
    try:
        # 构建能力矩阵
        matrix = {}
        
        for source_id, metadata in DATA_SOURCE_METADATA.items():
            capabilities = DATA_SOURCE_CAPABILITIES.get(source_id, {})
            
            # 统计能力数量
            supported_count = sum(1 for v in capabilities.values() if v)
            total_count = len(DataCapability)
            
            matrix[source_id] = {
                **metadata,
                "supported_count": supported_count,
                "total_count": total_count,
                "coverage_rate": f"{(supported_count/total_count)*100:.1f}%",
                "capabilities": {
                    cap.value: {
                        "supported": capabilities.get(cap, False),
                        "name": CAPABILITY_NAMES.get(cap, cap.value)
                    }
                    for cap in DataCapability
                }
            }
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                "sources": matrix,
                "categories": {
                    cat_id: {
                        "name": cat_info["name"],
                        "capabilities": [
                            {
                                "id": cap.value,
                                "name": CAPABILITY_NAMES.get(cap, cap.value)
                            }
                            for cap in cat_info["capabilities"]
                        ]
                    }
                    for cat_id, cat_info in CAPABILITY_CATEGORIES.items()
                }
            }
        })
    except Exception as e:
        logger.error(f"获取能力矩阵失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/{source}")
async def get_source_capabilities(source: str):
    """
    获取特定数据源的能力
    
    Args:
        source: 数据源ID
        
    Returns:
        数据源的详细能力信息
    """
    try:
        if source not in DATA_SOURCE_CAPABILITIES:
            raise HTTPException(status_code=404, detail=f"数据源 {source} 不存在")
        
        capabilities = DATA_SOURCE_CAPABILITIES[source]
        metadata = DATA_SOURCE_METADATA.get(source, {})
        
        # 按类别组织能力
        categorized = {}
        for cat_id, cat_info in CAPABILITY_CATEGORIES.items():
            cat_capabilities = []
            for cap in cat_info["capabilities"]:
                if cap in capabilities:
                    cat_capabilities.append({
                        "id": cap.value,
                        "name": CAPABILITY_NAMES.get(cap, cap.value),
                        "supported": capabilities[cap]
                    })
            
            if cat_capabilities:
                categorized[cat_id] = {
                    "name": cat_info["name"],
                    "capabilities": cat_capabilities,
                    "support_rate": f"{sum(1 for c in cat_capabilities if c['supported'])/len(cat_capabilities)*100:.0f}%"
                }
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                **metadata,
                "categorized_capabilities": categorized,
                "summary": {
                    "total": len(capabilities),
                    "supported": sum(1 for v in capabilities.values() if v),
                    "unsupported": sum(1 for v in capabilities.values() if not v)
                }
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据源能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/compare")
async def compare_capabilities(
    sources: str = Query(..., description="逗号分隔的数据源ID列表，如: amazingdata,qmt,akshare")
):
    """
    对比多个数据源的能力差异
    
    Args:
        sources: 逗号分隔的数据源ID列表
        
    Returns:
        数据源能力对比结果
    """
    try:
        source_list = [s.strip() for s in sources.split(",")]
        
        # 验证数据源
        for source in source_list:
            if source not in DATA_SOURCE_CAPABILITIES:
                raise HTTPException(status_code=400, detail=f"数据源 {source} 不存在")
        
        # 构建对比结果
        comparison = {}
        
        # 按能力对比
        for cap in DataCapability:
            cap_comparison = {
                "name": CAPABILITY_NAMES.get(cap, cap.value),
                "sources": {}
            }
            
            for source in source_list:
                capabilities = DATA_SOURCE_CAPABILITIES[source]
                cap_comparison["sources"][source] = capabilities.get(cap, False)
            
            # 判断差异类型
            support_count = sum(1 for v in cap_comparison["sources"].values() if v)
            if support_count == len(source_list):
                cap_comparison["diff_type"] = "all_support"
            elif support_count == 0:
                cap_comparison["diff_type"] = "none_support"
            else:
                cap_comparison["diff_type"] = "partial_support"
            
            comparison[cap.value] = cap_comparison
        
        # 计算差异统计
        diff_stats = {
            "all_support": [],
            "partial_support": [],
            "none_support": [],
            "unique_features": {}
        }
        
        for cap_id, cap_comp in comparison.items():
            diff_type = cap_comp["diff_type"]
            diff_stats[diff_type].append(cap_id)
            
            # 找出独有功能
            if diff_type == "partial_support":
                for source in source_list:
                    if cap_comp["sources"][source]:
                        # 检查是否只有这个数据源支持
                        others_support = any(
                            cap_comp["sources"][s] for s in source_list if s != source
                        )
                        if not others_support:
                            if source not in diff_stats["unique_features"]:
                                diff_stats["unique_features"][source] = []
                            diff_stats["unique_features"][source].append(cap_id)
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                "sources": {
                    source: DATA_SOURCE_METADATA.get(source, {"name": source})
                    for source in source_list
                },
                "comparison": comparison,
                "statistics": diff_stats
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对比能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/recommend")
async def recommend_source(
    capability: str,
    prefer_free: bool = Query(False, description="优先推荐免费数据源")
):
    """
    根据能力需求推荐数据源
    
    Args:
        capability: 能力ID
        prefer_free: 是否优先推荐免费数据源
        
    Returns:
        推荐的数据源列表
    """
    try:
        # 验证能力
        try:
            cap = DataCapability(capability)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的能力ID: {capability}")
        
        # 获取支持该能力的数据源
        capable_sources = get_capable_providers(cap)
        
        if not capable_sources:
            return JSONResponse(content={
                "status": "success",
                "data": {
                    "capability": {
                        "id": capability,
                        "name": CAPABILITY_NAMES.get(cap, capability)
                    },
                    "recommendations": [],
                    "message": "没有数据源支持此功能"
                }
            })
        
        # 构建推荐列表
        recommendations = []
        for source in capable_sources:
            metadata = DATA_SOURCE_METADATA.get(source, {})
            
            # 计算推荐分数
            score = 100
            
            # 优先级影响分数
            priority = metadata.get("priority", 99)
            score -= priority * 10
            
            # 免费偏好
            if prefer_free:
                if metadata.get("cost") == "free":
                    score += 50
                else:
                    score -= 20
            
            recommendations.append({
                "source": source,
                "name": metadata.get("name", source),
                "label": metadata.get("label", ""),
                "cost": metadata.get("cost", "unknown"),
                "score": score,
                "reason": self._get_recommendation_reason(source, cap, metadata)
            })
        
        # 按分数排序
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                "capability": {
                    "id": capability,
                    "name": CAPABILITY_NAMES.get(cap, capability)
                },
                "recommendations": recommendations,
                "best_choice": recommendations[0] if recommendations else None
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"推荐数据源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/check")
async def check_feature_availability(
    source: str,
    feature: str
):
    """
    检查特定功能在数据源上的可用性
    
    Args:
        source: 数据源ID
        feature: 功能/能力ID
        
    Returns:
        功能可用性信息
    """
    try:
        # 验证数据源
        if source not in DATA_SOURCE_CAPABILITIES:
            raise HTTPException(status_code=404, detail=f"数据源 {source} 不存在")
        
        # 验证能力
        try:
            cap = DataCapability(feature)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的功能ID: {feature}")
        
        # 检查可用性
        available = check_provider_capability(source, cap)
        
        # 如果不可用，提供替代方案
        alternatives = []
        if not available:
            capable_sources = get_capable_providers(cap)
            alternatives = [
                {
                    "source": s,
                    "name": DATA_SOURCE_METADATA.get(s, {}).get("name", s),
                    "cost": DATA_SOURCE_METADATA.get(s, {}).get("cost", "unknown")
                }
                for s in capable_sources if s != source
            ]
        
        return JSONResponse(content={
            "status": "success",
            "data": {
                "source": {
                    "id": source,
                    "name": DATA_SOURCE_METADATA.get(source, {}).get("name", source)
                },
                "feature": {
                    "id": feature,
                    "name": CAPABILITY_NAMES.get(cap, feature)
                },
                "available": available,
                "alternatives": alternatives,
                "message": f"{'功能可用' if available else '功能不可用，请切换到支持的数据源'}"
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查功能可用性失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_recommendation_reason(source: str, capability: DataCapability, metadata: Dict) -> str:
    """生成推荐理由"""
    reasons = []
    
    # 根据数据源特点生成理由
    if source == "amazingdata":
        reasons.append("最全面的数据覆盖")
        if capability in [DataCapability.MARGIN_TRADING, DataCapability.KEY_INDICATORS]:
            reasons.append("独家提供此功能")
    elif source == "qmt":
        if capability in [DataCapability.LEVEL2_DATA, DataCapability.TICK_DATA]:
            reasons.append("支持Level2深度数据")
        reasons.append("本地部署，延迟最低")
    elif source == "miniqmt":
        reasons.append("轻量级，资源占用少")
        if metadata.get("cost") == "free":
            reasons.append("免费使用")
    elif source == "akshare":
        reasons.append("开源免费")
        reasons.append("易于集成")
    
    return "，".join(reasons) if reasons else "支持此功能"