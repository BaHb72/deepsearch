"""
AmazingData 股东股本数据接口
包含股东、股本结构、股权质押等数据
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from loguru import logger

from .base import get_provider, handle_amazingdata_error, create_response

router = APIRouter()


@router.post("/share-holder", summary="获取十大股东数据")
async def get_share_holder(
    code: str = Body(..., description="证券代码，如SH.600000"),
    report_date: Optional[str] = Body(None, description="报告期，格式：YYYY-MM-DD"),
    top_n: int = Body(10, description="返回前N大股东，默认10")
):
    """
    获取上市公司十大股东数据

    Parameters:
        code: 证券代码（必填）
        report_date: 报告期（可选，不填返回最新）
        top_n: 返回前N大股东

    Returns:
        十大股东数据，包含：
        - 报告期
        - 股东名称
        - 持股数量
        - 持股比例
        - 股份性质
        - 股东类型
        - 增减情况
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code, 'top_n': top_n}
        if report_date:
            params['report_date'] = report_date

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_share_holder(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}十大股东数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取十大股东数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/holder-num", summary="获取股东人数")
async def get_holder_num(
    code: str = Body(..., description="证券代码，如SH.600000"),
    start_date: Optional[str] = Body(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期，格式：YYYY-MM-DD")
):
    """
    获取股东人数变化数据

    Parameters:
        code: 证券代码（必填）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        股东人数数据，包含：
        - 公告日期
        - 股东人数
        - 较上期变化
        - 人均持股数
        - 人均流通股数
        - 前十大股东持股比例
        - 前十大流通股东持股比例
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_holder_num(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}股东人数数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股东人数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-structure", summary="获取股本结构")
async def get_equity_structure(
    code: str = Body(..., description="证券代码，如SH.600000"),
    report_date: Optional[str] = Body(None, description="报告期，格式：YYYY-MM-DD")
):
    """
    获取股本结构数据

    Parameters:
        code: 证券代码（必填）
        report_date: 报告期（可选）

    Returns:
        股本结构数据，包含：
        - 变动日期
        - 总股本
        - 流通A股
        - 限售A股
        - 流通B股
        - 限售B股
        - 流通H股
        - 国有股
        - 境内法人股
        - 境内自然人股
        - 其他
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if report_date:
            params['report_date'] = report_date

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_equity_structure(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}股本结构数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股本结构失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-pledge-freeze", summary="获取股权质押和冻结数据")
async def get_equity_pledge_freeze(
    code: str = Body(..., description="证券代码，如SH.600000"),
    holder_name: Optional[str] = Body(None, description="股东名称"),
    status: Optional[str] = Body(None, description="状态：质押/冻结/全部")
):
    """
    获取股权质押和冻结信息

    Parameters:
        code: 证券代码（必填）
        holder_name: 股东名称（可选）
        status: 状态过滤（可选）

    Returns:
        股权质押/冻结数据，包含：
        - 股东名称
        - 质押/冻结股数
        - 占持股比例
        - 占总股本比例
        - 质押/冻结日期
        - 质押方
        - 公告日期
        - 状态
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if holder_name:
            params['holder_name'] = holder_name
        if status:
            params['status'] = status

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_equity_pledge_freeze(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}股权质押/冻结数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股权质押/冻结数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-restricted", summary="获取限售股解禁数据")
async def get_equity_restricted(
    code: Optional[str] = Body(None, description="证券代码，如SH.600000"),
    start_date: Optional[str] = Body(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期，格式：YYYY-MM-DD")
):
    """
    获取限售股解禁计划数据

    Parameters:
        code: 证券代码（可选，不填返回全市场）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        限售股解禁数据，包含：
        - 解禁日期
        - 证券代码
        - 证券名称
        - 解禁数量
        - 解禁市值
        - 占总股本比例
        - 占流通股比例
        - 限售股类型
        - 股东名称
        - 实际解禁日期
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {}
        if code:
            params['code'] = code
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_equity_restricted(**params)
        )

        return create_response(
            data=result,
            message="获取限售股解禁数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取限售股解禁数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dividend", summary="获取分红数据")
async def get_dividend(
    code: str = Body(..., description="证券代码，如SH.600000"),
    year: Optional[int] = Body(None, description="年份"),
    report_type: Optional[str] = Body(None, description="报告类型：年报/中报/季报")
):
    """
    获取上市公司分红数据

    Parameters:
        code: 证券代码（必填）
        year: 年份（可选）
        report_type: 报告类型（可选）

    Returns:
        分红数据，包含：
        - 公告日期
        - 分红年度
        - 分红方案
        - 每股派息（税前）
        - 每股派息（税后）
        - 每股送股
        - 每股转增
        - 股权登记日
        - 除权除息日
        - 派息日
        - 分红对象
        - 分红进度
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if year:
            params['year'] = year
        if report_type:
            params['report_type'] = report_type

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_dividend(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}分红数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分红数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/right-issue", summary="获取配股数据")
async def get_right_issue(
    code: str = Body(..., description="证券代码，如SH.600000"),
    start_date: Optional[str] = Body(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期，格式：YYYY-MM-DD")
):
    """
    获取配股数据

    Parameters:
        code: 证券代码（必填）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        配股数据，包含：
        - 公告日期
        - 配股方案
        - 配股价格
        - 配股比例
        - 配股数量
        - 募集资金
        - 股权登记日
        - 缴款起始日
        - 缴款截止日
        - 上市日
        - 配股进度
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_right_issue(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}配股数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配股数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))