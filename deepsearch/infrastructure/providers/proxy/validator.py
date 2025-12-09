"""
代理验证器

提供对代理的可用性、匿名性和性能验证。
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, TypedDict, Literal

import aiohttp
from loguru import logger

AnonymityLevel = Literal["transparent", "anonymous", "elite", "unknown"]


class ProxyValidationResult(TypedDict, total=False):
    proxy: str
    valid: bool
    response_time: Optional[float]
    anonymity_level: Optional[AnonymityLevel]
    error: Optional[str]
    ip: Optional[str]


class SpeedTestResult(TypedDict):
    avg_time: float
    min_time: float
    max_time: float
    success_rate: float


class ProxyValidator:
    """代理验证器

    支持验证代理可用性、匿名性以及测速
    """

    TEST_URLS = [
        "http://httpbin.org/ip",
        "http://ip.jsontest.com/",
        "http://api.ipify.org?format=json",
    ]
    ANONYMITY_CHECK_URL = "http://httpbin.org/headers"

    def __init__(self, timeout: float = 10) -> None:
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "ProxyValidator":
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def validate_proxy(
        self, proxy_url: str, test_url: Optional[str] = None
    ) -> Tuple[bool, ProxyValidationResult]:
        session = self._ensure_session()
        resolved_url = test_url or self.TEST_URLS[0]
        result: ProxyValidationResult = {
            "proxy": proxy_url,
            "valid": False,
            "response_time": None,
            "anonymity_level": None,
            "error": None,
            "ip": None,
        }

        start_time = time.time()

        try:
            async with session.get(resolved_url, proxy=proxy_url, ssl=False) as response:
                response_time = time.time() - start_time

                if response.status == 200:
                    data = await response.json()

                    result["valid"] = True
                    result["response_time"] = response_time
                    result["ip"] = data.get("origin") or data.get("ip")

                    anonymity = await self._check_anonymity(proxy_url)
                    result["anonymity_level"] = anonymity

                    logger.debug(
                        "代理验证成功: {}, 响应时间: {:.2f}s, 匿名级别: {}",
                        proxy_url,
                        response_time,
                        anonymity,
                    )
                else:
                    result["error"] = f"HTTP {response.status}"
                    logger.debug("代理验证失败: {}, 状态码: {}", proxy_url, response.status)

        except asyncio.TimeoutError:
            result["error"] = "Timeout"
            logger.debug("代理验证超时: {}", proxy_url)
        except aiohttp.ClientError as exc:
            result["error"] = str(exc)
            logger.debug("代理验证请求失败: {}, {}", proxy_url, exc)
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("代理验证异常: {}, {}", proxy_url, exc)

        return result["valid"], result

    async def _check_anonymity(self, proxy_url: str) -> AnonymityLevel:
        session = self._ensure_session()
        try:
            async with session.get(self.ANONYMITY_CHECK_URL) as response:
                await response.json()

            async with session.get(self.ANONYMITY_CHECK_URL, proxy=proxy_url, ssl=False) as response:
                proxy_headers = await response.json()

            headers = proxy_headers.get("headers", {})
            indicators = {
                "X-Forwarded-For",
                "X-Real-Ip",
                "X-Originating-Ip",
                "X-Forwarded",
                "Forwarded-For",
                "Forwarded",
                "Client-Ip",
                "Via",
                "Proxy-Connection",
            }
            found = [header for header in indicators if header in headers]

            if not found:
                return "elite"
            if "Via" in found or "Proxy-Connection" in found:
                return "transparent"
            return "anonymous"

        except Exception as exc:
            logger.debug("匿名性检测失败: {}", exc)
            return "unknown"

    async def batch_validate(
        self, proxy_urls: List[str], max_concurrent: int = 10
    ) -> Dict[str, ProxyValidationResult]:
        results: Dict[str, ProxyValidationResult] = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_limit(proxy_url: str) -> Tuple[str, ProxyValidationResult]:
            async with semaphore:
                _, result = await self.validate_proxy(proxy_url)
                return proxy_url, result

        tasks = [validate_with_limit(url) for url in proxy_urls]

        for future in asyncio.as_completed(tasks):
            proxy_url, result = await future
            results[proxy_url] = result

        valid_count = sum(1 for item in results.values() if item.get("valid"))
        logger.info(
            "代理批量验证: 总数={}, 有效={}, 无效={}",
            len(proxy_urls),
            valid_count,
            len(proxy_urls) - valid_count,
        )
        return results

    async def test_proxy_speed(
        self, proxy_url: str, test_urls: Optional[List[str]] = None, iterations: int = 3
    ) -> Dict[str, SpeedTestResult]:
        session = self._ensure_session()
        resolved_urls = test_urls or self.TEST_URLS
        results: Dict[str, SpeedTestResult] = {}

        for url in resolved_urls:
            timings: List[float] = []

            for _ in range(iterations):
                start = time.time()
                try:
                    async with session.get(url, proxy=proxy_url, ssl=False) as response:
                        if response.status == 200:
                            timings.append(time.time() - start)
                except Exception as exc:
                    logger.debug("代理测速请求失败: {}", exc)

            if timings:
                results[url] = SpeedTestResult(
                    avg_time=sum(timings) / len(timings),
                    min_time=min(timings),
                    max_time=max(timings),
                    success_rate=len(timings) / iterations,
                )

        return results
