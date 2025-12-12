"""
通用代理数据提供者
使用Cloudflare Worker代理获取真实股票数据
"""

import json
import time
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataSourceType,
)


# from deepsearch.application.services.cache.stock_info_cache import get_stock_info_cache


# 临时的缓存实现
class StockInfoCache:
    def __init__(self) -> None:
        self._cache: dict[str, Dict[str, Any]] = {}

    def get(self, symbol: str) -> Dict[str, Any] | None:
        return self._cache.get(symbol)

    def set(self, symbol: str, data: Dict[str, Any]) -> None:
        self._cache[symbol] = data


_stock_info_cache = StockInfoCache()


def get_stock_info_cache():
    return _stock_info_cache


try:
    import pandas as pd
except ImportError:  # pragma: no cover - 可选依赖
    pd = None  # type: ignore[assignment]

HAS_PANDAS = pd is not None


class ProxyDataProvider:
    """通过代理获取真实股票数据"""

    _MARKET_FILTERS: Dict[str, str] = {
        "all": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "sh": "m:1+t:2",
        "sz": "m:0+t:6",
        "bj": "m:0+t:81+s:2048",
        "cy": "m:0+t:80",
        "kc": "m:1+t:23",
        "new": "m:0+t:6+f:8,m:1+t:2+f:8",
    }
    _SPOT_FIELDS = (
        "f12,f13,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,"
        "f15,f16,f17,f18,f20,f21,f23,f62,f84,f128,f136,f140,f141,f152"
    )

    def __init__(
        self,
        worker_url: str = "https://akshare-proxy.934073514.workers.dev",
        timeout: float | int | None = None,
        retry_count: int | None = None,
        connection: Optional[Dict[str, Any]] | None = None,
        cache: Optional[Dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        """初始化代理数据提供者。

        兼容配置文件中的扩展字段，确保 registry 传入的参数不会导致初始化失败。
        """

        base_url = worker_url or "https://akshare-proxy.934073514.workers.dev"
        self.worker_url = base_url.rstrip("/")

        connection = connection or {}
        if connection.get("worker_url"):
            self.worker_url = str(connection["worker_url"]).rstrip("/")

        configured_timeout = timeout if timeout is not None else connection.get("timeout")
        self._timeout_seconds = float(configured_timeout) if configured_timeout is not None else 30.0
        self._healthcheck_timeout = min(max(self._timeout_seconds, 0.5), 5.0)

        configured_retry = retry_count if retry_count is not None else connection.get("retry_count")
        self._retry_count = int(configured_retry) if configured_retry is not None else 3

        self.session: aiohttp.ClientSession | None = None
        self._cache: dict[str, tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl = {"realtime": 5, "minute": 60, "daily": 300, "info": 3600}
        self._cache_config = cache or {}
        self._extra_options = kwargs
        self._using_placeholder_worker = self._is_placeholder_worker(self.worker_url)

        # 添加 config 属性以兼容 DataProviderManager
        self.config = DataProviderConfig(
            name="cloudflare",
            source_type=DataSourceType.CLOUDFLARE,
            enabled=True,
            priority=10,
            timeout=self._timeout_seconds,
            retry_count=self._retry_count,
        )
        self.status = "running"

    @staticmethod
    def _is_placeholder_worker(worker_url: str) -> bool:
        """
        判断 worker_url 是否仍为占位值，避免默认配置导致的长时间等待。
        """

        try:
            hostname = (urlparse(worker_url).hostname or "").lower()
        except Exception:
            hostname = (worker_url or "").lower()

        if not hostname:
            return True
        if "your-cloudflare-worker" in hostname:
            return True
        if hostname.endswith("example.com"):
            return True
        return False

    def _make_timeout(self, override: Optional[float] = None) -> aiohttp.ClientTimeout:
        """构造统一的超时配置。"""

        total = self._timeout_seconds if override is None else float(override)
        return aiohttp.ClientTimeout(total=total)

    async def initialize(self):
        """初始化"""
        if self._using_placeholder_worker:
            logger.warning(
                "Cloudflare worker URL is placeholder ({}); skip health check and mark as unavailable",
                self.worker_url,
            )
            return False

        logger.info(f"初始化代理数据提供者: {self.worker_url}")

        # 测试连接
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.worker_url}/health", timeout=self._healthcheck_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Worker健康检查成功: v{data.get('version', 'unknown')}")
                        return True
        except Exception as e:
            logger.error(f"Worker健康检查失败: {e}")
            return False

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[list]:
        """
        获取K线数据 - DataSourceManager接口方法

        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            **kwargs: 其他参数

        Returns:
            K线数据列表
        """
        try:
            # 转换周期格式
            period_map = {
                "1d": "daily",
                "d": "daily",
                "daily": "daily",
                "1w": "weekly",
                "w": "weekly",
                "weekly": "weekly",
                "1M": "monthly",
                "M": "monthly",
                "monthly": "monthly",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "60m": "60",
            }

            period_str = period_map.get(period, "daily")
            adjust = kwargs.get("adjust", "")

            # 调用已有的get_stock_hist方法
            hist_data = await self.get_stock_hist(
                symbol=symbol,
                period=period_str,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

            # 检查返回数据
            if not hist_data or "error" in hist_data:
                logger.error(
                    f"获取K线数据失败: {hist_data.get('error', 'Unknown error') if hist_data else 'No data'}"
                )
                return None

            # 获取data字段
            data_raw = hist_data.get("data", [])
            if not isinstance(data_raw, list):
                return None

            data = data_raw[-limit:] if limit and limit > 0 else data_raw

            logger.info(f"CloudFlare返回{len(data)}条K线数据")
            return data

        except Exception as e:
            logger.error(f"CloudFlare get_kline_data失败: {e}")
            return None

    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
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
            if symbol.startswith("6"):
                secid = f"1.{symbol}"  # 上海
            elif symbol.startswith("0") or symbol.startswith("3"):
                secid = f"0.{symbol}"  # 深圳
            else:
                secid = symbol

            # 使用代理获取东方财富K线数据
            url = f"{self.worker_url}/proxy"
            target = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

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
                "_": str(int(time.time() * 1000)),
            }

            # 构建完整的目标URL
            target_with_params = (
                target + "?" + "&".join([f"{k}={v}" for k, v in params.items() if k != "url"])
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={"url": target_with_params},
                    timeout=self._make_timeout(),
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        try:
                            data = json.loads(text)
                        except Exception:
                            # 东方财富返回的可能不是标准JSON，需要解析
                            return await self._parse_eastmoney_response(text, symbol)

                        if data is not None and "data" in data:
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
                    result.append(
                        {
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
                            "换手率": float(parts[10]) if len(parts) > 10 else 0,
                        }
                    )

            logger.info(f"成功获取 {symbol} 的 {len(result)} 条K线数据")
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
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                if data is not None and "data" in data:
                    return self._format_eastmoney_kline(data["data"], symbol)

            return {"data": [], "error": "无法解析响应"}

        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return {"data": [], "error": str(e)}

    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        try:
            # 使用新浪接口获取实时行情
            if symbol.startswith("6"):
                sina_symbol = f"sh{symbol}"
            elif symbol.startswith("0") or symbol.startswith("3"):
                sina_symbol = f"sz{symbol}"
            else:
                sina_symbol = symbol

            url = f"{self.worker_url}/proxy"
            target = f"https://hq.sinajs.cn/list={sina_symbol}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={"url": target},
                    timeout=self._make_timeout(10),
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

            parts = match.group(1).split(",")
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
                "source": "sina",
            }

        except Exception as e:
            logger.error(f"解析新浪行情失败: {e}")
            return {"error": str(e)}

    async def fetch_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基础信息

        Args:
            symbol: 股票代码

        Returns:
            股票基础信息字典
        """
        try:
            # 首先尝试从本地缓存获取
            stock_cache = get_stock_info_cache()
            cached_info = stock_cache.get(symbol)
            if cached_info:
                # 如果本地缓存有数据，直接返回
                return {
                    "symbol": symbol,
                    "name": cached_info.get("name", f"股票{symbol}"),
                    "industry": cached_info.get("industry", ""),
                    "sector": cached_info.get("sector", ""),
                    "market": cached_info.get("market", ""),
                    "listed_date": cached_info.get("listed_date", ""),
                    **cached_info,
                }

            # 检查内存缓存
            cache_key = f"stock_info_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("info", 3600):
                    return cached_data

            # 从东方财富获取股票基础信息
            if symbol.startswith("6"):
                secid = f"1.{symbol}"  # 上海
            elif symbol.startswith("0") or symbol.startswith("3"):
                secid = f"0.{symbol}"  # 深圳
            else:
                secid = symbol

            url = f"{self.worker_url}/proxy"
            target = "https://push2.eastmoney.com/api/qt/stock/get"

            params = {
                "url": target,
                "secid": secid,
                "fields": "f57,f58,f43,f44,f45,f46,f60,f169,f170,f171,f172,f173,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197",
                "_": str(int(time.time() * 1000)),
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=self._make_timeout(10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data is not None and "data" in data:
                            stock_data = data["data"]
                            result = {
                                "symbol": symbol,
                                "name": stock_data.get("f58", f"股票{symbol}"),
                                "full_name": stock_data.get("f57", ""),
                                "price": (
                                    stock_data.get("f43", 0) / 100 if stock_data.get("f43") else 0
                                ),
                                "change": (
                                    stock_data.get("f169", 0) / 100 if stock_data.get("f169") else 0
                                ),
                                "change_pct": (
                                    stock_data.get("f170", 0) / 100 if stock_data.get("f170") else 0
                                ),
                                "volume": stock_data.get("f45", 0),
                                "amount": stock_data.get("f46", 0),
                                "amplitude": (
                                    stock_data.get("f171", 0) / 100 if stock_data.get("f171") else 0
                                ),
                                "high": (
                                    stock_data.get("f44", 0) / 100 if stock_data.get("f44") else 0
                                ),
                                "low": (
                                    stock_data.get("f45", 0) / 100 if stock_data.get("f45") else 0
                                ),
                                "open": (
                                    stock_data.get("f46", 0) / 100 if stock_data.get("f46") else 0
                                ),
                                "prev_close": (
                                    stock_data.get("f60", 0) / 100 if stock_data.get("f60") else 0
                                ),
                                "volume_ratio": (
                                    stock_data.get("f172", 0) / 100 if stock_data.get("f172") else 0
                                ),
                                "turnover": (
                                    stock_data.get("f173", 0) / 100 if stock_data.get("f173") else 0
                                ),
                                "pe_ratio": (
                                    stock_data.get("f174", 0) / 100 if stock_data.get("f174") else 0
                                ),
                                "pb_ratio": (
                                    stock_data.get("f175", 0) / 100 if stock_data.get("f175") else 0
                                ),
                                "total_shares": stock_data.get("f176", 0),
                                "float_shares": stock_data.get("f177", 0),
                                "market_cap": stock_data.get("f178", 0),
                                "float_market_cap": stock_data.get("f179", 0),
                                "industry": stock_data.get("f180", ""),
                                "update_time": stock_data.get("f181", ""),
                            }

                            # 缓存结果
                            self._cache[cache_key] = (time.time(), result)

                            # 更新本地缓存
                            stock_cache.set(
                                symbol,
                                {
                                    "name": result.get("name"),
                                    "industry": result.get("industry", ""),
                                    "sector": result.get("sector", ""),
                                    "market": result.get("market", ""),
                                },
                            )

                            return result

            # 如果从API获取失败，返回基础信息
            logger.warning(f"从API获取股票 {symbol} 信息失败，返回基础信息")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": "无法获取股票信息"}

        except Exception as e:
            logger.error(f"获取股票信息失败 {symbol}: {e}")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": str(e)}

    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[list]:
        """
        获取股票列表 - DataSourceManager接口方法

        Args:
            limit: 限制返回数量
            **kwargs: 其他参数

        Returns:
            股票列表
        """
        try:
            # 调用已有的fetch_stock_list方法
            stocks = await self.fetch_stock_list()

            if not stocks:
                return None

            # 转换格式以匹配DataSourceManager的期望格式
            result = []
            for stock in stocks:
                result.append(
                    {
                        "symbol": stock.get("代码", ""),
                        "name": stock.get("名称", ""),
                        "code": stock.get("代码", ""),
                        "source": "cloudflare",
                    }
                )

            # 应用限制
            if limit and limit > 0:
                result = result[:limit]

            logger.info(f"CloudFlare返回{len(result)}只股票")
            return result

        except Exception as e:
            logger.error(f"CloudFlare get_stock_list失败: {e}")
            return None

    async def fetch_market_spot(
        self,
        *,
        market: str = "all",
        limit: int = 100,
        sort_field: str = "f3",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """通过 Cloudflare Worker 获取市场行情快照。"""

        cache_key = f"spot:{market}:{limit}:{sort_field}:{sort_order}"
        ttl = self._cache_ttl.get("realtime", 5)
        cached = self._cache.get(cache_key)
        if cached:
            cached_time, cached_payload = cached
            if time.time() - cached_time < ttl:
                return cached_payload

        fs = self._MARKET_FILTERS.get(market.lower(), self._MARKET_FILTERS["all"])
        sort_flag = "1" if sort_order.lower() != "asc" else "0"
        limit = max(1, min(limit, 400))
        page_size = min(limit, 200)
        url = f"{self.worker_url}/proxy"
        target = "https://82.push2.eastmoney.com/api/qt/clist/get"

        aggregated: List[Dict[str, Any]] = []
        total_records: Optional[int] = None
        page = 1

        while len(aggregated) < limit:
            current_page_size = min(page_size, limit - len(aggregated))
            params = {
                "pn": str(page),
                "pz": str(current_page_size),
                "po": sort_flag,
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fid": sort_field,
                "fs": fs,
                "fields": self._SPOT_FIELDS,
                "_": str(int(time.time() * 1000)),
            }
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            target_with_params = f"{target}?{query_string}"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        params={"url": target_with_params},
                        timeout=self._make_timeout(),
                    ) as response:
                        if response.status != 200:
                            logger.warning("行情接口返回非200: status={}", response.status)
                            break
                        payload = await response.json()
            except Exception as exc:
                logger.error("调用 Cloudflare Worker 获取行情失败: {}", exc)
                break

            data_section = (payload or {}).get("data") or {}
            if total_records is None:
                total_records = data_section.get("total")
            diff = data_section.get("diff") or []
            if not diff:
                break

            for raw in diff:
                normalized = self._normalize_spot_item(raw, market)
                if normalized:
                    aggregated.append(normalized)
                    if len(aggregated) >= limit:
                        break

            if len(diff) < current_page_size:
                break
            page += 1

        result = {
            "items": aggregated,
            "total": total_records if total_records is not None else len(aggregated),
            "source": "cloudflare",
        }
        self._cache[cache_key] = (time.time(), result)
        return result

    @staticmethod
    def _safe_number(value: Any) -> float | None:
        if value in (None, "", "-", "--"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _map_exchange(value: Any) -> Optional[str]:
        mapping = {"1": "SH", "0": "SZ", "3": "BJ"}
        if value is None:
            return None
        return mapping.get(str(value))

    def _normalize_spot_item(
        self,
        payload: Mapping[str, Any],
        market: str,
    ) -> Optional[Dict[str, Any]]:
        code = str(payload.get("f12") or "").strip()
        if not code:
            return None

        entry = {
            "symbol": code,
            "name": payload.get("f14") or "",
            "代码": code,
            "名称": payload.get("f14") or "",
            "最新价": self._safe_number(payload.get("f2")),
            "涨跌幅": self._safe_number(payload.get("f3")),
            "涨跌额": self._safe_number(payload.get("f4")),
            "成交量": self._safe_number(payload.get("f5")),
            "成交额": self._safe_number(payload.get("f6")),
            "振幅": self._safe_number(payload.get("f7")),
            "换手率": self._safe_number(payload.get("f8")),
            "市盈率": self._safe_number(payload.get("f9")),
            "量比": self._safe_number(payload.get("f10")),
            "最高": self._safe_number(payload.get("f15")),
            "最低": self._safe_number(payload.get("f16")),
            "今开": self._safe_number(payload.get("f17")),
            "昨收": self._safe_number(payload.get("f18")),
            "总市值": self._safe_number(payload.get("f20")),
            "流通市值": self._safe_number(payload.get("f21")),
            "市净率": self._safe_number(payload.get("f23")),
            "净流入": self._safe_number(payload.get("f62")),
            "更新时间": payload.get("f84") or "",
            "data_source": "cloudflare",
            "market": market,
            "exchange": self._map_exchange(payload.get("f13")),
        }
        return entry



    async def fetch_stock_list(self) -> list:
        """
        获取股票列表

        Returns:
            股票列表数据
        """
        try:
            # 从东方财富获取A股列表
            url = f"{self.worker_url}/proxy"
            target = "https://82.push2.eastmoney.com/api/qt/clist/get"

            params = {
                "pn": "1",  # 页码
                "pz": "5000",  # 每页数量
                "po": "1",  # 排序方式
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",  # 排序字段
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",  # A股市场
                "fields": "f12,f14",  # f12:代码, f14:名称
                "_": str(int(time.time() * 1000)),
            }

            # 构建完整URL
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            target_with_params = f"{target}?{query_string}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={"url": target_with_params},
                    timeout=self._make_timeout(),
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data and "data" in data and "diff" in data["data"]:
                            stocks = []
                            for stock_data in data["data"]["diff"]:
                                if isinstance(stock_data, dict):
                                    stocks.append(
                                        {
                                            "代码": stock_data.get("f12", ""),
                                            "名称": stock_data.get("f14", ""),
                                        }
                                    )

                            logger.info(f"成功获取 {len(stocks)} 条股票数据")

                            # 更新本地缓存
                            if stocks:
                                stock_cache = get_stock_info_cache()
                                for stock in stocks[:100]:  # 先更新前100条
                                    if stock["代码"] and stock["名称"]:
                                        stock_cache.set(
                                            stock["代码"],
                                            {"name": stock["名称"], "code": stock["代码"]},
                                        )

                            return stocks

            logger.warning("无法从东方财富获取股票列表")
            return []

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    async def _fetch_with_fallback(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """兼容原有接口"""
        # 判断请求类型
        if path == "stock_zh_a_hist":
            symbol_value = params.get("symbol")
            if not isinstance(symbol_value, str):
                return {"error": "symbol 参数缺失"}
            period_value = params.get("period", "daily")
            period = str(period_value) if isinstance(period_value, str) else "daily"
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            adjust_value = params.get("adjust", "")
            adjust = str(adjust_value) if isinstance(adjust_value, str) else ""
            return await self.get_stock_hist(
                symbol=symbol_value,
                period=period,
                start_date=start_date if isinstance(start_date, str) else None,
                end_date=end_date if isinstance(end_date, str) else None,
                adjust=adjust,
            )
        elif path == "stock_zh_a_spot_em":
            symbol_raw = params.get("symbol", "000001")
            symbol = str(symbol_raw)
            return await self.get_realtime_quote(symbol)
        else:
            logger.warning(f"未支持的API: {path}")
            return {"data": [], "error": f"Unsupported API: {path}"}

    def get_statistics(self) -> Dict[str, Any]:
        """返回提供者统计信息，满足 DataProviderManager 接口要求。"""
        return {
            "worker_url": self.worker_url,
            "timeout": self._timeout_seconds,
            "retry_count": self._retry_count,
            "cache_size": len(self._cache),
            "using_placeholder": self._using_placeholder_worker,
        }
