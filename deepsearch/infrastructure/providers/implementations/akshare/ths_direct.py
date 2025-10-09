"""
同花顺概念板块数据直接访问模块
绕过CloudFlare代理，直接使用AkShare访问
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from ._deps import AkshareModule, PandasModule, load_akshare, load_pandas

ak: Optional[AkshareModule] = load_akshare()
HAS_AKSHARE = ak is not None

pd: Optional[PandasModule] = load_pandas()
HAS_PANDAS = pd is not None


class ThsDirectProvider:
    """同花顺数据直接提供者"""

    def __init__(
        self,
        akshare_module: Optional[AkshareModule] = None,
        pandas_module: Optional[PandasModule] = None,
    ):
        self.name = "ths_direct"
        self.display_name = "同花顺直连"
        self._akshare: Optional[AkshareModule] = akshare_module if akshare_module is not None else ak
        self._pandas: Optional[PandasModule] = pandas_module if pandas_module is not None else pd

        if self._akshare is None:
            raise ImportError("AkShare 未安装或未注入")

        if self._pandas is None:
            raise ImportError("Pandas 未安装或未注入")

    def _akshare_module(self) -> AkshareModule:
        """返回已注入的 AkShare 模块"""

        if self._akshare is None:
            raise RuntimeError("AkShare 未正确注入")
        return self._akshare

    def _pandas_module(self) -> PandasModule:
        """返回已注入的 pandas 模块"""

        if self._pandas is None:
            raise RuntimeError("pandas 未正确注入")
        return self._pandas

    async def get_concept_list(self) -> Dict[str, Any]:
        """获取同花顺概念板块列表"""
        akshare = self._akshare_module()
        try:
            logger.info("获取同花顺概念板块列表...")
            df = await asyncio.get_event_loop().run_in_executor(
                None, akshare.stock_board_concept_name_ths
            )

            if df is not None and not df.empty:
                # 转换为标准格式
                result = df.to_dict("records")
                logger.info(f"成功获取 {len(result)} 个概念板块")
                return {"success": True, "data": result, "source": "ths_direct"}
            else:
                return {
                    "success": False,
                    "data": [],
                    "error": "No data returned",
                    "source": "ths_direct",
                }
        except Exception as e:
            logger.error(f"获取概念列表失败: {e}")
            return {"success": False, "data": [], "error": str(e), "source": "ths_direct"}

    async def get_concept_index(
        self, symbol: str, start_date: str = "20230101", end_date: str = "20250131"
    ) -> Dict[str, Any]:
        """获取概念板块指数数据"""
        akshare = self._akshare_module()
        try:
            logger.info(f"获取概念板块指数: {symbol}")
            df = await asyncio.get_event_loop().run_in_executor(
                None, akshare.stock_board_concept_index_ths, symbol, start_date, end_date
            )

            if df is not None and not df.empty:
                result = df.to_dict("records")
                logger.info(f"成功获取 {len(result)} 条指数数据")
                return {"success": True, "data": result, "source": "ths_direct"}
            else:
                return {
                    "success": False,
                    "data": [],
                    "error": "No data returned",
                    "source": "ths_direct",
                }
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return {"success": False, "data": [], "error": str(e), "source": "ths_direct"}

    async def get_concept_info(self, symbol: str) -> Dict[str, Any]:
        """获取概念板块简介"""
        akshare = self._akshare_module()
        try:
            logger.info(f"获取概念板块简介: {symbol}")
            df = await asyncio.get_event_loop().run_in_executor(
                None, akshare.stock_board_concept_info_ths, symbol
            )

            if df is not None:
                # 根据返回数据类型处理
                if hasattr(df, "to_dict"):
                    if not df.empty:
                        result = df.to_dict("records")
                    else:
                        result = {}
                else:
                    result = df

                logger.info("成功获取概念板块简介")
                return {"success": True, "data": result, "source": "ths_direct"}
            else:
                return {
                    "success": False,
                    "data": {},
                    "error": "No data returned",
                    "source": "ths_direct",
                }
        except Exception as e:
            logger.error(f"获取板块简介失败: {e}")
            return {"success": False, "data": {}, "error": str(e), "source": "ths_direct"}

    async def get_concept_constituents(self, symbol: str) -> Dict[str, Any]:
        """获取概念板块成份股

        注意：AkShare暂不支持获取同花顺概念板块成份股
        此方法返回概念板块汇总信息
        """
        akshare = self._akshare_module()
        try:
            logger.info("获取概念板块汇总信息（成份股功能暂不可用）")
            df = await asyncio.get_event_loop().run_in_executor(
                None, akshare.stock_board_concept_summary_ths
            )

            if df is not None and not df.empty:
                # 筛选包含指定概念的记录
                if "板块名称" in df.columns:
                    filtered = df[df["板块名称"].str.contains(symbol, na=False)]
                    if not filtered.empty:
                        result = filtered.to_dict("records")
                    else:
                        result = df.head(10).to_dict("records")  # 返回前10条作为示例
                else:
                    result = df.head(10).to_dict("records")

                logger.info(f"返回 {len(result)} 条概念板块汇总信息")
                return {
                    "success": True,
                    "data": result,
                    "source": "ths_direct",
                    "note": "成份股详情暂不可用，显示概念板块汇总信息",
                }
            else:
                return {
                    "success": False,
                    "data": [],
                    "error": "No data returned",
                    "source": "ths_direct",
                }
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return {"success": False, "data": [], "error": str(e), "source": "ths_direct"}


# 全局实例
_ths_provider = None


def get_ths_provider() -> ThsDirectProvider:
    """获取同花顺数据提供者单例"""
    global _ths_provider
    if _ths_provider is None:
        _ths_provider = ThsDirectProvider()
    return _ths_provider
