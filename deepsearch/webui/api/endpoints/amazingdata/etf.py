"""
AmazingData ETF数据API模块
提供ETF申赎数据等接口

接口列表:
- 3.5.11.1 ETF每日最新申赎数据 (get_etf_pcf)
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .base import JSONDict, dataframe_to_dict, format_response, get_amazingdata_provider

router = APIRouter(tags=["AmazingData-ETF数据"])


# ================== 请求模型 ==================


class EtfPcfRequest(BaseModel):
    """ETF申赎数据请求"""

    code_list: List[str] = Field(
        ...,
        description="ETF代码列表，如 510300.SH, 159919.SZ 等",
        examples=[["510300.SH", "159919.SZ"]],
    )


# ================== API接口 ==================


@router.post("/pcf", summary="获取ETF每日申赎数据")
async def get_etf_pcf(request: EtfPcfRequest) -> JSONDict:
    """
    3.5.11.1 ETF每日最新申赎数据
    获取指定ETF的申赎和成分股数据（沪深交易所的ETF）

    返回数据结构：
    - etf_pcf_info: ETF申赎基本信息（DataFrame格式）
      - index为ETF代码
    - etf_pcf_constituent: ETF成分股数据（字典格式）
      - key: ETF代码
      - value: 成分股DataFrame
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_etf_pcf(code_list=request.code_list)

        # 处理返回结果
        if result is None:
            return format_response(
                success=True,
                data={"etf_pcf_info": None, "etf_pcf_constituent": {}},
                code_count=len(request.code_list),
            )

        # 如果返回的是元组 (etf_pcf_info, etf_pcf_constituent)
        if isinstance(result, tuple) and len(result) == 2:
            etf_pcf_info, etf_pcf_constituent = result

            # 转换成分股字典
            constituent_data: Dict[str, Any] = {}
            if isinstance(etf_pcf_constituent, dict):
                for etf_code, df in etf_pcf_constituent.items():
                    constituent_data[etf_code] = dataframe_to_dict(df)

            return format_response(
                success=True,
                data={
                    "etf_pcf_info": dataframe_to_dict(etf_pcf_info),
                    "etf_pcf_constituent": constituent_data,
                },
                code_count=len(request.code_list),
            )

        # 其他情况，直接返回转换后的数据
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
