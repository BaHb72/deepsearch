"""
数据源能力对比API

提供数据源能力查询、对比和推荐功能
"""

from __future__ import annotations

from typing import Final, Mapping, cast

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.webui.api.models import (
    CAPABILITY_STATUS_SUCCESS,
    CapabilityAlternative,
    CapabilityAvailabilityData,
    CapabilityAvailabilityResponse,
    CapabilityCategoryMeta,
    CapabilityCategorySummary,
    CapabilityComparisonEntry,
    CapabilityComparisonResponse,
    CapabilityDescriptor,
    CapabilityDiffStats,
    CapabilityInfo,
    CapabilityItem,
    CapabilityMatrix,
    CapabilityMatrixResponse,
    CapabilityRecommendation,
    CapabilityRecommendationResponse,
    CapabilitySourceInfo,
    CapabilitySummary,
    CapabilitySummaryData,
    CapabilitySummaryResponse,
    DataSourceSlug,
    SourceMetadata,
    SourceOverview,
)

router = APIRouter(prefix="/api/datasource", tags=["datasource_capability"])

# 数据源能力映射
DATA_SOURCE_CAPABILITIES: Final[dict[DataSourceSlug, frozenset[DataCapability]]] = {
    "amazingdata": frozenset(
        {
            DataCapability.STOCK_LIST,
            DataCapability.REALTIME_QUOTE,
            DataCapability.KLINE_DATA,
            DataCapability.STOCK_INFO,
            DataCapability.ORDER_BOOK,
            DataCapability.TRADE_DETAIL,
            DataCapability.FINANCIAL_DATA,
            DataCapability.NEWS,
            DataCapability.ANNOUNCEMENT,
            DataCapability.MARGIN_TRADING,
            DataCapability.NORTH_FLOW,
            DataCapability.KEY_INDICATORS,
            DataCapability.SHAREHOLDER_INFO,
            DataCapability.TRADING_CALENDAR,
            DataCapability.ADJUSTMENT_FACTOR,
        }
    ),
    "akshare": frozenset(
        {
            DataCapability.STOCK_LIST,
            DataCapability.KLINE_DATA,
            DataCapability.STOCK_INFO,
            DataCapability.FINANCIAL_DATA,
            DataCapability.TRADING_CALENDAR,
            DataCapability.ADJUSTMENT_FACTOR,
        }
    ),
    "qmt": frozenset(
        {
            DataCapability.REALTIME_QUOTE,
            DataCapability.ORDER_BOOK,
            DataCapability.TRADE_DETAIL,
            DataCapability.KLINE_DATA,
            DataCapability.LEVEL2_DATA,
            DataCapability.TICK_DATA,
        }
    ),
    "miniqmt": frozenset(
        {
            DataCapability.REALTIME_QUOTE,
            DataCapability.ORDER_BOOK,
            DataCapability.KLINE_DATA,
        }
    ),
    "cloudflare": frozenset(
        {
            DataCapability.STOCK_LIST,
            DataCapability.KLINE_DATA,
            DataCapability.STOCK_INFO,
            DataCapability.TRADING_CALENDAR,
        }
    ),
}

EMPTY_CAPABILITIES: Final[frozenset[DataCapability]] = frozenset()

# 数据源元数据
DATA_SOURCE_METADATA: Final[dict[DataSourceSlug, SourceMetadata]] = {
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
            "Level2深度数据",
        ],
        "connection_type": "remote",
        "requires_auth": True,
        "cost": "paid",
    },
    "qmt": {
        "name": "QMT",
        "label": "量化终端",
        "description": "本地量化交易终端",
        "badge": "Level2",
        "color": "blue",
        "priority": 2,
        "unique_features": ["Level2逐笔数据", "实时盘口", "逐笔成交明细", "完整筹码分布"],
        "connection_type": "local",
        "requires_auth": True,
        "cost": "paid",
    },
    "miniqmt": {
        "name": "MiniQMT",
        "label": "轻量终端",
        "description": "轻量级量化终端",
        "badge": "基础版",
        "color": "green",
        "priority": 3,
        "unique_features": ["实时行情", "盘口数据", "筹码分布", "异动监控"],
        "connection_type": "local",
        "requires_auth": True,
        "cost": "free",
    },
    "akshare": {
        "name": "AKShare",
        "label": "开源数据",
        "description": "免费开源金融数据接口",
        "badge": "免费版",
        "color": "gray",
        "priority": 4,
        "unique_features": ["历史数据", "基础行情", "财务数据", "北向资金"],
        "connection_type": "remote",
        "requires_auth": False,
        "cost": "free",
    },
    "cloudflare": {
        "name": "Cloudflare Workers",
        "label": "边缘代理",
        "description": "Cloudflare 边缘节点提供的缓存与代理能力",
        "badge": "辅助源",
        "color": "orange",
        "priority": 5,
        "unique_features": ["边缘加速", "代理转发", "灾备兜底"],
        "connection_type": "remote",
        "requires_auth": False,
        "cost": "free",
    },
}

DEFAULT_METADATA: Final[SourceMetadata] = {
    "name": "未知数据源",
    "label": "未登记",
    "description": "当前未在能力矩阵中登记的数据源",
    "badge": "未知",
    "color": "silver",
    "priority": 999,
    "unique_features": [],
    "connection_type": "remote",
    "requires_auth": False,
    "cost": "free",
}


def _normalize_source_slug(source: str) -> str:
    """将用户输入的来源规范化为内部使用的 key。"""
    normalized = source.strip().lower()
    return normalized


def _iter_capable_sources(capability: DataCapability) -> list[DataSourceSlug]:
    """根据能力返回所有支持的数据源 ID。"""
    return [
        source_id
        for source_id, capability_set in DATA_SOURCE_CAPABILITIES.items()
        if capability in capability_set
    ]


def _is_capability_supported(source: str, capability: DataCapability) -> bool:
    """判断指定来源是否支持某项能力。"""
    normalized = _normalize_source_slug(source)
    if normalized not in DATA_SOURCE_CAPABILITIES:
        return False
    capability_set = DATA_SOURCE_CAPABILITIES[cast(DataSourceSlug, normalized)]
    return capability in capability_set

# 能力分类元数据
CAPABILITY_CATEGORIES: Final[dict[str, CapabilityCategoryMeta]] = {
    "market": {
        "name": "市场数据",
        "capabilities": [
            DataCapability.MARKET_OVERVIEW,
            DataCapability.MARKET_BREADTH,
            DataCapability.CAPITAL_FLOW,
            DataCapability.SECTOR_DATA,
            DataCapability.ANOMALY_DETECTION,
        ],
    },
    "quote": {
        "name": "行情数据",
        "capabilities": [
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA,
        ],
    },
    "depth": {
        "name": "深度数据",
        "capabilities": [
            DataCapability.ORDER_BOOK,
            DataCapability.LEVEL2_DATA,
            DataCapability.TRANSACTION_DATA,
        ],
    },
    "special": {
        "name": "特色数据",
        "capabilities": [
            DataCapability.CHIP_DISTRIBUTION,
            DataCapability.DRAGON_TIGER,
            DataCapability.BLOCK_TRADE,
            DataCapability.MARGIN_TRADING,
            DataCapability.NORTH_FLOW,
        ],
    },
    "fundamental": {
        "name": "基础信息",
        "capabilities": [
            DataCapability.STOCK_INFO,
            DataCapability.FINANCIAL_DATA,
            DataCapability.ANNOUNCEMENT,
            DataCapability.KEY_INDICATORS,
            DataCapability.SHAREHOLDER_INFO,
        ],
    },
    "utility": {
        "name": "工具数据",
        "capabilities": [DataCapability.TRADING_CALENDAR, DataCapability.ADJUSTMENT_FACTOR],
    },
}

# 能力中文名称映射
CAPABILITY_NAMES: Final[dict[DataCapability, str]] = {
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
    DataCapability.ADJUSTMENT_FACTOR: "复权因子",
}


@router.get("/capabilities/matrix")
async def get_capability_matrix():
    """
    获取全量数据源能力矩阵

    Returns:
        各数据源能力对比矩阵
    """
    try:
        matrix: CapabilityMatrix = {"sources": {}, "categories": {}}
        sources = matrix["sources"]

        for source_id, metadata in DATA_SOURCE_METADATA.items():
            capabilities = DATA_SOURCE_CAPABILITIES.get(source_id, EMPTY_CAPABILITIES)

            supported_count = len(capabilities)
            total_count = len(DataCapability)

            capability_details: dict[str, CapabilityInfo] = {
                cap.value: {
                    "supported": cap in capabilities,
                    "name": CAPABILITY_NAMES.get(cap, cap.value),
                }
                for cap in DataCapability
            }

            sources[source_id] = {
                **metadata,
                "supported_count": supported_count,
                "total_count": total_count,
                "coverage_rate": f"{(supported_count / total_count) * 100:.1f}%",
                "capabilities": capability_details,
            }

        matrix["categories"] = {
            cat_id: {
                "name": cat_info["name"],
                "capabilities": [
                    {"id": cap.value, "name": CAPABILITY_NAMES.get(cap, cap.value)}
                    for cap in cat_info["capabilities"]
                ],
            }
            for cat_id, cat_info in CAPABILITY_CATEGORIES.items()
        }

        payload: CapabilityMatrixResponse = {
            "status": CAPABILITY_STATUS_SUCCESS,
            "data": matrix,
        }

        return JSONResponse(content=payload)
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
        normalized_source = _normalize_source_slug(source)

        if normalized_source not in DATA_SOURCE_CAPABILITIES:
            raise HTTPException(status_code=404, detail=f"数据源 {source} 不存在")

        source_slug = cast(DataSourceSlug, normalized_source)

        capabilities = DATA_SOURCE_CAPABILITIES[source_slug]
        metadata = DATA_SOURCE_METADATA.get(source_slug, DEFAULT_METADATA)

        # 按类别组织能力
        categorized: dict[str, CapabilityCategorySummary] = {}
        for cat_id, cat_info in CAPABILITY_CATEGORIES.items():
            cat_capabilities: list[CapabilityItem] = []
            for cap in cat_info["capabilities"]:
                supported = cap in capabilities
                cat_capabilities.append(
                    {
                        "id": cap.value,
                        "name": CAPABILITY_NAMES.get(cap, cap.value),
                        "supported": supported,
                    }
                )

            if cat_capabilities:
                support_count = sum(1 for item in cat_capabilities if item["supported"])
                support_rate = (
                    f"{(support_count / len(cat_capabilities)) * 100:.0f}%"
                    if cat_capabilities
                    else "0%"
                )
                categorized[cat_id] = {
                    "name": cat_info["name"],
                    "capabilities": cat_capabilities,
                    "support_rate": support_rate,
                }

        total_count = len(DataCapability)
        supported_count = len(capabilities)

        summary: CapabilitySummary = {
            "total": total_count,
            "supported": supported_count,
            "unsupported": max(total_count - supported_count, 0),
        }
        response_data: CapabilitySummaryData = {
            **metadata,
            "categorized_capabilities": categorized,
            "summary": summary,
        }
        payload: CapabilitySummaryResponse = {
            "status": CAPABILITY_STATUS_SUCCESS,
            "data": response_data,
        }

        return JSONResponse(content=payload)
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
        raw_sources = [s.strip() for s in sources.split(",") if s.strip()]
        source_slugs: list[DataSourceSlug] = []

        # 验证数据源
        for raw_source in raw_sources:
            normalized = _normalize_source_slug(raw_source)
            if normalized not in DATA_SOURCE_CAPABILITIES:
                raise HTTPException(status_code=400, detail=f"数据源 {normalized} 不存在")
            source_slugs.append(cast(DataSourceSlug, normalized))

        # 构建对比结果
        comparison: dict[str, CapabilityComparisonEntry] = {}

        # 按能力对比
        for cap in DataCapability:
            cap_comparison: CapabilityComparisonEntry = {
                "name": CAPABILITY_NAMES.get(cap, cap.value),
                "sources": {},
                "diff_type": "none_support",
            }

            for source in source_slugs:
                capabilities = DATA_SOURCE_CAPABILITIES[source]
                cap_comparison["sources"][source] = cap in capabilities

            # 判断差异类型
            support_count = sum(1 for v in cap_comparison["sources"].values() if v)
            if support_count == len(source_slugs):
                cap_comparison["diff_type"] = "all_support"
            elif support_count == 0:
                cap_comparison["diff_type"] = "none_support"
            else:
                cap_comparison["diff_type"] = "partial_support"

            comparison[cap.value] = cap_comparison

        # 计算差异统计
        diff_stats: CapabilityDiffStats = {
            "all_support": [],
            "partial_support": [],
            "none_support": [],
            "unique_features": {},
        }

        for cap_id, cap_comp in comparison.items():
            diff_type = cap_comp["diff_type"]
            diff_stats[diff_type].append(cap_id)

            # 找出独有功能
            if diff_type == "partial_support":
                for source in source_slugs:
                    if cap_comp["sources"][source]:
                        # 检查是否只有这个数据源支持
                        others_support = any(
                            cap_comp["sources"][s] for s in source_slugs if s != source
                        )
                        if not others_support:
                            features = diff_stats["unique_features"].setdefault(source, [])
                            features.append(cap_id)

        sources_info: dict[DataSourceSlug, SourceOverview] = {}
        for source in source_slugs:
            metadata = DATA_SOURCE_METADATA.get(source, DEFAULT_METADATA)
            source_overview: SourceOverview = {**metadata, "id": source}
            sources_info[source] = source_overview

        payload: CapabilityComparisonResponse = {
            "status": CAPABILITY_STATUS_SUCCESS,
            "data": {
                "sources": sources_info,
                "comparison": comparison,
                "statistics": diff_stats,
            },
        }

        return JSONResponse(content=payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对比能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/recommend")
async def recommend_source(
    capability: str, prefer_free: bool = Query(False, description="优先推荐免费数据源")
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
        capability_descriptor: CapabilityDescriptor = {
            "id": capability,
            "name": CAPABILITY_NAMES.get(cap, capability),
        }

        # ��ȡ֧�ָ�����������Դ
        capable_sources = _iter_capable_sources(cap)

        if not capable_sources:
            payload: CapabilityRecommendationResponse = {
                "status": CAPABILITY_STATUS_SUCCESS,
                "data": {
                    "capability": capability_descriptor,
                    "recommendations": [],
                    "best_choice": None,
                    "message": "û������Դ֧�ִ˹���",
                },
            }
            return JSONResponse(content=payload)

        # 构建推荐列表
        recommendations: list[CapabilityRecommendation] = []
        for source in capable_sources:
            metadata = DATA_SOURCE_METADATA.get(source, DEFAULT_METADATA)

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

            recommendations.append(
                {
                    "source": source,
                    "name": metadata.get("name", source),
                    "label": metadata.get("label", ""),
                    "cost": metadata.get("cost", "unknown"),
                    "score": score,
                    "reason": _get_recommendation_reason(source, cap, metadata),
                }
            )

        # 按分数排序
        recommendations.sort(key=lambda item: item["score"], reverse=True)

        return JSONResponse(
            content={
                "status": CAPABILITY_STATUS_SUCCESS,
                "data": {
                    "capability": {"id": capability, "name": CAPABILITY_NAMES.get(cap, capability)},
                    "recommendations": recommendations,
                    "best_choice": recommendations[0] if recommendations else None,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"推荐数据源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/check")
async def check_feature_availability(source: str, feature: str):
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
        normalized_source = _normalize_source_slug(source)

        if normalized_source not in DATA_SOURCE_CAPABILITIES:
            raise HTTPException(status_code=404, detail=f"数据源 {source} 不存在")

        source_slug = cast(DataSourceSlug, normalized_source)

        # 验证能力
        try:
            cap = DataCapability(feature)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的功能ID: {feature}")

        # 检查可用性
        available = _is_capability_supported(source_slug, cap)

        # 如果不可用，提供替代方案
        alternatives: list[CapabilityAlternative] = []
        if not available:
            capable_sources = _iter_capable_sources(cap)
            alternatives = [
                {
                    "source": slug,
                    "name": DATA_SOURCE_METADATA.get(slug, DEFAULT_METADATA).get("name", slug),
                    "cost": DATA_SOURCE_METADATA.get(slug, DEFAULT_METADATA).get("cost", "unknown"),
                }
                for slug in capable_sources
                if slug != source_slug
            ]

        source_info: CapabilitySourceInfo = {
            "id": source_slug,
            "name": DATA_SOURCE_METADATA.get(source_slug, DEFAULT_METADATA).get("name", source_slug),
        }
        feature_descriptor: CapabilityDescriptor = {
            "id": feature,
            "name": CAPABILITY_NAMES.get(cap, feature),
        }
        availability_message = (
            "功能可用" if available else "功能不可用，请切换到支持的数据源"
        )

        data: CapabilityAvailabilityData = {
            "source": source_info,
            "feature": feature_descriptor,
            "available": available,
            "alternatives": alternatives,
            "message": availability_message,
        }
        payload: CapabilityAvailabilityResponse = {
            "status": CAPABILITY_STATUS_SUCCESS,
            "data": data,
        }

        return JSONResponse(content=payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查功能可用性失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_recommendation_reason(
    source: str, capability: DataCapability, metadata: Mapping[str, object]
) -> str:
    """生成推荐理由"""
    reasons = []

    normalized_source = _normalize_source_slug(source)

    # 根据数据源特点生成理由
    if normalized_source == "amazingdata":
        reasons.append("最全面的数据覆盖")
        if capability in [DataCapability.MARGIN_TRADING, DataCapability.KEY_INDICATORS]:
            reasons.append("独家提供此功能")
    elif normalized_source == "qmt":
        if capability in [DataCapability.LEVEL2_DATA, DataCapability.TICK_DATA]:
            reasons.append("支持Level2深度数据")
        reasons.append("本地部署，延迟最低")
    elif normalized_source == "miniqmt":
        reasons.append("轻量级，资源占用少")
        if metadata.get("cost") == "free":
            reasons.append("免费使用")
    elif normalized_source == "akshare":
        reasons.append("开源免费")
        reasons.append("易于集成")
    elif normalized_source == "cloudflare":
        reasons.append("边缘加速")
        reasons.append("减少源站压力")

    return "，".join(reasons) if reasons else "支持此功能"
