"""
千股千评相关API接口
使用AKShare获取东方财富网千股千评数据
"""

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, TypedDict, cast

import akshare as ak
import numpy as np
import pandas as pd
from core.observability import get_logger
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = get_logger(__name__)

router = APIRouter(prefix="/api/stock-comment", tags=["stock_comment"])

# 线程池执行器用于运行同步的akshare函数
executor = ThreadPoolExecutor(max_workers=4)


class CacheEntry(TypedDict):
    data: pd.DataFrame | None
    time: datetime | None


# 缓存数据
cache: dict[str, CacheEntry] = {
    "stock_comment": {"data": None, "time": None},
    "fund_flow": {"data": None, "time": None},
}
CACHE_DURATION = 300  # 缓存5分钟


class StockCommentQuery(BaseModel):
    """查询参数"""

    page: int = 1
    size: int = 50
    search: Optional[str] = None
    score_filter: Optional[str] = None  # excellent/good/average/poor
    institution_filter: Optional[str] = None  # high/medium/low
    sort: str = "score"
    order: str = "desc"


class StockDetailQuery(BaseModel):
    """股票详情查询参数"""

    symbol: str
    period: int = 30  # 查询天数


def run_in_executor(func, *args):
    """在线程池中运行同步函数"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(executor, func, *args)


def is_cache_valid(cache_item, duration=CACHE_DURATION):
    """检查缓存是否有效"""
    if cache_item["data"] is None or cache_item["time"] is None:
        return False
    return (datetime.now() - cache_item["time"]).seconds < duration


@router.get("/list")
async def get_stock_comment_list(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    score_filter: Optional[str] = Query(None),
    institution_filter: Optional[str] = Query(None),
    sort: str = Query("score"),
    order: str = Query("desc"),
):
    """
    获取千股千评列表数据
    """
    try:
        # 检查缓存
        if is_cache_valid(cache["stock_comment"]):
            cached_df = cast(pd.DataFrame, cache["stock_comment"]["data"])
            df = cached_df.copy()
        else:
            # 获取千股千评数据
            df = await run_in_executor(ak.stock_comment_em)

            # 重命名列
            df = df.rename(
                columns={
                    "序号": "index",
                    "代码": "code",
                    "名称": "name",
                    "最新价": "price",
                    "涨跌幅": "change_pct",
                    "换手率": "turnover_rate",
                    "市盈率": "pe_ratio",
                    "主力成本": "main_cost",
                    "机构参与度": "institution_rate",
                    "综合得分": "score",
                    "上升": "rank_change",
                    "目前排名": "current_rank",
                    "关注指数": "focus_index",
                    "交易日": "trade_date",
                }
            )

            # 计算星级（1-5星）
            df["focus_stars"] = pd.cut(
                df["focus_index"], bins=[0, 20, 40, 60, 80, 100], labels=[1, 2, 3, 4, 5]
            ).astype(float)

            # 缓存数据
            cache["stock_comment"]["data"] = df
            cache["stock_comment"]["time"] = datetime.now()

        # 搜索过滤
        if search:
            mask = df["code"].str.contains(search, na=False) | df["name"].str.contains(
                search, na=False
            )
            df = df[mask]

        # 评分过滤
        if score_filter:
            if score_filter == "excellent":
                df = df[df["score"] >= 80]
            elif score_filter == "good":
                df = df[(df["score"] >= 60) & (df["score"] < 80)]
            elif score_filter == "average":
                df = df[(df["score"] >= 40) & (df["score"] < 60)]
            elif score_filter == "poor":
                df = df[df["score"] < 40]

        # 机构参与度过滤
        if institution_filter:
            if institution_filter == "high":
                df = df[df["institution_rate"] > 50]
            elif institution_filter == "medium":
                df = df[(df["institution_rate"] >= 30) & (df["institution_rate"] <= 50)]
            elif institution_filter == "low":
                df = df[df["institution_rate"] < 30]

        # 排序
        if sort in df.columns:
            df = df.sort_values(sort, ascending=(order == "asc"))

        # 获取总数
        total = len(df)

        # 分页
        start = (page - 1) * size
        end = start + size
        df_page = df.iloc[start:end]

        # 获取统计数据
        top_focus = df.nlargest(5, "focus_index")[["code", "name", "focus_index"]].to_dict(
            "records"
        )
        top_score = df.nlargest(5, "score")[["code", "name", "score"]].to_dict("records")
        top_institution = df.nlargest(5, "institution_rate")[
            ["code", "name", "institution_rate"]
        ].to_dict("records")

        # 处理NaN值
        df_page = df_page.replace({np.nan: None})

        return {
            "success": True,
            "data": {
                "list": df_page.to_dict("records"),
                "total": total,
                "page": page,
                "size": size,
                "topFocus": top_focus,
                "topScore": top_score,
                "topInstitution": top_institution,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取千股千评数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/detail/{symbol}")
async def get_stock_detail(symbol: str, period: int = Query(30, ge=7, le=90)):
    """
    获取个股详细数据
    包括机构参与度、历史评分、用户关注指数、市场参与意愿
    """
    try:
        result = {}

        # 获取机构参与度
        try:
            df_jgcyd = await run_in_executor(ak.stock_comment_detail_zlkp_jgcyd_em, symbol)
            df_jgcyd = df_jgcyd.rename(columns={"交易日": "date", "机构参与度": "value"})
            # 只取最近period天的数据
            df_jgcyd = df_jgcyd.tail(period)
            result["institution"] = df_jgcyd.to_dict("records")
        except Exception as e:
            logger.warning(f"获取机构参与度失败: {e}")
            result["institution"] = []

        # 获取历史评分
        try:
            df_score = await run_in_executor(ak.stock_comment_detail_zhpj_lspf_em, symbol)
            df_score = df_score.rename(columns={"交易日": "date", "评分": "value"})
            df_score = df_score.tail(period)
            result["score"] = df_score.to_dict("records")
        except Exception as e:
            logger.warning(f"获取历史评分失败: {e}")
            result["score"] = []

        # 获取用户关注指数
        try:
            df_focus = await run_in_executor(ak.stock_comment_detail_scrd_focus_em, symbol)
            df_focus = df_focus.rename(columns={"交易日": "date", "用户关注指数": "value"})
            df_focus = df_focus.tail(period)
            result["focus"] = df_focus.to_dict("records")
        except Exception as e:
            logger.warning(f"获取用户关注指数失败: {e}")
            result["focus"] = []

        # 获取市场参与意愿（日度）
        try:
            df_desire = await run_in_executor(ak.stock_comment_detail_scrd_desire_daily_em, symbol)
            df_desire = df_desire.rename(
                columns={
                    "交易日": "date",
                    "当日意愿上升": "daily_rise",
                    "5日平均参与意愿变化": "avg_5d_change",
                }
            )
            df_desire = df_desire.tail(period)
            result["desire"] = df_desire.to_dict("records")
        except Exception as e:
            logger.warning(f"获取市场参与意愿失败: {e}")
            result["desire"] = []

        return {
            "success": True,
            "data": result,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取股票详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.get("/fund-flow")
async def get_fund_flow():
    """
    获取沪深港通资金流向数据
    """
    try:
        # 检查缓存
        if is_cache_valid(cache["fund_flow"], duration=60):  # 资金流向缓存1分钟
            return cache["fund_flow"]["data"]

        # 获取资金流向数据
        df = await run_in_executor(ak.stock_hsgt_fund_flow_summary_em)

        # 处理数据
        result = {
            "northFlow": 0,  # 北向资金净流入
            "southFlow": 0,  # 南向资金净流入
            "shBalance": 520,  # 沪股通余额
            "szBalance": 520,  # 深股通余额
            "details": [],
        }

        if not df.empty:
            # 计算北向资金（沪股通 + 深股通）
            sh_data = df[df["板块"] == "沪股通"]
            sz_data = df[df["板块"] == "深股通"]

            if not sh_data.empty:
                result["northFlow"] += (
                    sh_data.iloc[0]["资金净流入"] if "资金净流入" in sh_data.columns else 0
                )
                result["shBalance"] = (
                    sh_data.iloc[0]["当日资金余额"] if "当日资金余额" in sh_data.columns else 520
                )

            if not sz_data.empty:
                result["northFlow"] += (
                    sz_data.iloc[0]["资金净流入"] if "资金净流入" in sz_data.columns else 0
                )
                result["szBalance"] = (
                    sz_data.iloc[0]["当日资金余额"] if "当日资金余额" in sz_data.columns else 520
                )

            # 计算南向资金（港股通）
            hk_sh_data = df[df["板块"] == "港股通(沪)"]
            hk_sz_data = df[df["板块"] == "港股通(深)"]

            if not hk_sh_data.empty:
                result["southFlow"] += (
                    hk_sh_data.iloc[0]["资金净流入"] if "资金净流入" in hk_sh_data.columns else 0
                )

            if not hk_sz_data.empty:
                result["southFlow"] += (
                    hk_sz_data.iloc[0]["资金净流入"] if "资金净流入" in hk_sz_data.columns else 0
                )

            # 详细数据
            df_dict = df.to_dict("records")
            result["details"] = df_dict

        # 缓存结果
        response = {"success": True, "data": result, "timestamp": datetime.now().isoformat()}

        cache["fund_flow"]["data"] = response
        cache["fund_flow"]["time"] = datetime.now()

        return response

    except Exception as e:
        logger.error(f"获取资金流向失败: {str(e)}")
        # 返回默认值而不是抛出异常
        return {
            "success": False,
            "data": {
                "northFlow": 0,
                "southFlow": 0,
                "shBalance": 520,
                "szBalance": 520,
                "details": [],
            },
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/intraday-desire/{symbol}")
async def get_intraday_desire(symbol: str):
    """
    获取盘中市场参与意愿数据（分时）
    """
    try:
        # 获取分时参与意愿
        df = await run_in_executor(ak.stock_comment_detail_scrd_desire_em, symbol)

        # 处理数据
        df = df.rename(
            columns={"日期时间": "datetime", "大户": "big", "全部": "all", "散户": "retail"}
        )

        # 转换时间格式
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "success": True,
            "data": df.to_dict("records"),
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取分时参与意愿失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/export")
async def export_stock_comment(format: str = Query("excel", regex="^(excel|csv)$")):
    """
    导出千股千评数据
    """
    try:
        # 获取全部数据
        if not is_cache_valid(cache["stock_comment"]):
            df = await run_in_executor(ak.stock_comment_em)
            cache["stock_comment"]["data"] = df
            cache["stock_comment"]["time"] = datetime.now()
        else:
            df = cast(pd.DataFrame, cache["stock_comment"]["data"]).copy()

        # 生成文件名
        filename = f"stock_comment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format == "excel":
            # 导出为Excel
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="千股千评", index=False)
            excel_buffer.seek(0)

            return StreamingResponse(
                excel_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
            )

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode("utf-8-sig")

        return StreamingResponse(
            io.BytesIO(csv_data),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    except Exception as e:
        logger.error(f"导出数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
