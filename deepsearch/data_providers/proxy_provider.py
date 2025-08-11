"""
通用代理数据提供者
使用Cloudflare Worker代理获取真实股票数据
"""
import json
import time
from typing import Dict, Any, Optional

import aiohttp
from loguru import logger

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class ProxyDataProvider:
    """通过代理获取真实股票数据"""

    def __init__(self, worker_url: str = "https://wandering-sea-d394.934073514.workers.dev"):
        self.worker_url = worker_url.rstrip('/')
        self.session = None
        self._cache = {}
        self._cache_ttl = {
            'realtime': 5,
            'minute': 60,
            'daily': 300,
            'info': 3600
        }

    async def initialize(self):
        """初始化"""
        logger.info(f"初始化代理数据提供者: {self.worker_url}")

        # 测试连接
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.worker_url}/health", timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Worker健康检查成功: v{data.get('version', 'unknown')}")
                        return True
        except Exception as e:
            logger.error(f"Worker健康检查失败: {e}")
            return False

    async def get_stock_hist(
            self,
            symbol: str,
            period: str = "daily",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            adjust: str = ""
    ) -> Dict[str, Any]:
        """
        获取股票历史数据
        
        通过东方财富API获取K线数据
        """
        try:
            # 转换period到东方财富的klt参数
            period_map = {
                "daily": "101",  # 日K
                "weekly": "102",  # 周K
                "monthly": "103",  # 月K
                "5": "5",  # 5分钟
                "15": "15",  # 15分钟
                "30": "30",  # 30分钟
                "60": "60",  # 60分钟
            }

            klt = period_map.get(period, "101")

            # 构建secid (东方财富的股票ID格式)
            if symbol.startswith('6'):
                secid = f"1.{symbol}"  # 上海
            elif symbol.startswith('0') or symbol.startswith('3'):
                secid = f"0.{symbol}"  # 深圳
            else:
                secid = symbol

            # 使用代理获取东方财富K线数据
            url = f"{self.worker_url}/proxy"
            target = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"

            params = {
                "url": target,
                "secid": secid,
                "klt": klt,
                "fqt": "1" if not adjust else ("2" if adjust == "qfq" else "0"),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "beg": start_date.replace("-", "") if start_date else "0",
                "end": end_date.replace("-", "") if end_date else "20500101",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "_": str(int(time.time() * 1000))
            }

            # 构建完整的目标URL
            target_with_params = target + "?" + "&".join([f"{k}={v}" for k, v in params.items() if k != "url"])

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url,
                        params={"url": target_with_params},
                        timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        try:
                            data = json.loads(text)
                        except:
                            # 东方财富返回的可能不是标准JSON，需要解析
                            return await self._parse_eastmoney_response(text, symbol)

                        if isinstance(data, dict) and data.get("data"):
                            return self._format_eastmoney_kline(data["data"], symbol)

                    logger.warning(f"代理请求失败: {response.status}")
                    return {"data": [], "error": f"HTTP {response.status}"}

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return {"data": [], "error": str(e)}

    def _format_eastmoney_kline(self, data: Dict, symbol: str) -> Dict[str, Any]:
        """格式化东方财富K线数据"""
        try:
            if not data or "klines" not in data:
                return {"data": []}

            klines = data.get("klines", [])
            if not klines:
                return {"data": []}

            result = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 7:
                    result.append({
                        "日期": parts[0],
                        "开盘": float(parts[1]),
                        "收盘": float(parts[2]),
                        "最高": float(parts[3]),
                        "最低": float(parts[4]),
                        "成交量": float(parts[5]),
                        "成交额": float(parts[6]),
                        "振幅": float(parts[7]) if len(parts) > 7 else 0,
                        "涨跌幅": float(parts[8]) if len(parts) > 8 else 0,
                        "涨跌额": float(parts[9]) if len(parts) > 9 else 0,
                        "换手率": float(parts[10]) if len(parts) > 10 else 0
                    })

            logger.info(f"成功获取{symbol}的{len(result)}条K线数据")
            return {"data": result, "source": "eastmoney"}

        except Exception as e:
            logger.error(f"格式化K线数据失败: {e}")
            return {"data": []}

    async def _parse_eastmoney_response(self, text: str, symbol: str) -> Dict[str, Any]:
        """解析东方财富的响应文本"""
        try:
            # 东方财富的响应可能包含回调函数包装
            import re

            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                if isinstance(data, dict) and data.get("data"):
                    return self._format_eastmoney_kline(data["data"], symbol)

            return {"data": [], "error": "无法解析响应"}

        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return {"data": [], "error": str(e)}

    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        try:
            # 使用新浪接口获取实时行情
            if symbol.startswith('6'):
                sina_symbol = f"sh{symbol}"
            elif symbol.startswith('0') or symbol.startswith('3'):
                sina_symbol = f"sz{symbol}"
            else:
                sina_symbol = symbol

            url = f"{self.worker_url}/proxy"
            target = f"https://hq.sinajs.cn/list={sina_symbol}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url,
                        params={"url": target},
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        return self._parse_sina_quote(text, symbol)

                    return {"error": f"HTTP {response.status}"}

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {"error": str(e)}

    def _parse_sina_quote(self, text: str, symbol: str) -> Dict[str, Any]:
        """解析新浪行情数据"""
        try:
            import re
            match = re.search(r'="(.+)"', text)
            if not match:
                return {"error": "无法解析行情"}

            parts = match.group(1).split(',')
            if len(parts) < 32:
                return {"error": "数据格式错误"}

            return {
                "symbol": symbol,
                "name": parts[0],
                "open": float(parts[1]),
                "prev_close": float(parts[2]),
                "current": float(parts[3]),
                "high": float(parts[4]),
                "low": float(parts[5]),
                "volume": float(parts[8]),
                "amount": float(parts[9]),
                "time": parts[30] + " " + parts[31] if len(parts) > 31 else "",
                "source": "sina"
            }

        except Exception as e:
            logger.error(f"解析新浪行情失败: {e}")
            return {"error": str(e)}

    async def _fetch_with_fallback(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """兼容原有接口"""
        # 判断请求类型
        if path == "stock_zh_a_hist":
            return await self.get_stock_hist(
                params.get("symbol"),
                params.get("period", "daily"),
                params.get("start_date"),
                params.get("end_date"),
                params.get("adjust", "")
            )
        elif path == "stock_zh_a_spot_em":
            return await self.get_realtime_quote(params.get("symbol", "000001"))
        else:
            logger.warning(f"未支持的API: {path}")
            return {"data": [], "error": f"Unsupported API: {path}"}
