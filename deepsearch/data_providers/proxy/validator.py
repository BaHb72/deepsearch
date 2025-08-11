"""
代理验证器

验证代理的可用性和性能。
"""
import asyncio
import time
from typing import Optional, Dict, List, Tuple

import aiohttp
from loguru import logger


class ProxyValidator:
    """
    代理验证器
    
    用于验证代理的可用性、匿名性和性能。
    """

    # 用于测试的URL列表
    TEST_URLS = [
        "http://httpbin.org/ip",
        "http://ip.jsontest.com/",
        "http://api.ipify.org?format=json"
    ]

    # 用于检测匿名性的URL
    ANONYMITY_CHECK_URL = "http://httpbin.org/headers"

    def __init__(self, timeout: int = 10):
        """
        初始化验证器
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._session:
            await self._session.close()

    async def validate_proxy(
            self,
            proxy_url: str,
            test_url: Optional[str] = None
    ) -> Tuple[bool, Dict[str, any]]:
        """
        验证单个代理
        
        Args:
            proxy_url: 代理URL (如 http://127.0.0.1:8080)
            test_url: 测试URL，默认使用内置测试URL
            
        Returns:
            (是否可用, 验证结果详情)
        """
        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

        test_url = test_url or self.TEST_URLS[0]
        result = {
            "proxy": proxy_url,
            "valid": False,
            "response_time": None,
            "anonymity_level": None,
            "error": None,
            "ip": None
        }

        start_time = time.time()

        try:
            # 测试代理连接
            async with self._session.get(
                    test_url,
                    proxy=proxy_url,
                    ssl=False
            ) as response:
                response_time = time.time() - start_time

                if response.status == 200:
                    data = await response.json()

                    result["valid"] = True
                    result["response_time"] = response_time
                    result["ip"] = data.get("origin") or data.get("ip")

                    # 检查匿名性
                    anonymity = await self._check_anonymity(proxy_url)
                    result["anonymity_level"] = anonymity

                    logger.debug(
                        f"代理验证成功: {proxy_url}, "
                        f"响应时间: {response_time:.2f}s, "
                        f"匿名级别: {anonymity}"
                    )
                else:
                    result["error"] = f"HTTP {response.status}"
                    logger.debug(f"代理验证失败: {proxy_url}, 状态码: {response.status}")

        except asyncio.TimeoutError:
            result["error"] = "Timeout"
            logger.debug(f"代理验证超时: {proxy_url}")
        except aiohttp.ClientError as e:
            result["error"] = str(e)
            logger.debug(f"代理验证错误: {proxy_url}, {e}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"代理验证异常: {proxy_url}, {e}")

        return result["valid"], result

    async def _check_anonymity(self, proxy_url: str) -> str:
        """
        检查代理匿名性
        
        Args:
            proxy_url: 代理URL
            
        Returns:
            匿名级别: transparent(透明), anonymous(匿名), elite(高匿)
        """
        try:
            # 先获取真实IP的请求头
            async with self._session.get(self.ANONYMITY_CHECK_URL) as response:
                real_headers = await response.json()

            # 通过代理获取请求头
            async with self._session.get(
                    self.ANONYMITY_CHECK_URL,
                    proxy=proxy_url,
                    ssl=False
            ) as response:
                proxy_headers = await response.json()

            headers = proxy_headers.get("headers", {})

            # 检查是否包含真实IP相关的头
            proxy_indicators = [
                "X-Forwarded-For",
                "X-Real-Ip",
                "X-Originating-Ip",
                "X-Forwarded",
                "Forwarded-For",
                "Forwarded",
                "Client-Ip",
                "Via",
                "Proxy-Connection"
            ]

            found_indicators = [
                header for header in proxy_indicators
                if header in headers
            ]

            if not found_indicators:
                return "elite"  # 高匿代理
            elif "Via" in found_indicators or "Proxy-Connection" in found_indicators:
                return "transparent"  # 透明代理
            else:
                return "anonymous"  # 匿名代理

        except Exception as e:
            logger.debug(f"匿名性检查失败: {e}")
            return "unknown"

    async def batch_validate(
            self,
            proxy_urls: List[str],
            max_concurrent: int = 10
    ) -> Dict[str, Dict]:
        """
        批量验证代理
        
        Args:
            proxy_urls: 代理URL列表
            max_concurrent: 最大并发数
            
        Returns:
            验证结果字典
        """
        results = {}

        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_limit(proxy_url):
            async with semaphore:
                valid, result = await self.validate_proxy(proxy_url)
                return proxy_url, result

        # 并发验证所有代理
        tasks = [validate_with_limit(url) for url in proxy_urls]

        for future in asyncio.as_completed(tasks):
            proxy_url, result = await future
            results[proxy_url] = result

        # 统计结果
        valid_count = sum(1 for r in results.values() if r["valid"])
        logger.info(
            f"批量验证完成: 总数={len(proxy_urls)}, "
            f"有效={valid_count}, "
            f"无效={len(proxy_urls) - valid_count}"
        )

        return results

    async def test_proxy_speed(
            self,
            proxy_url: str,
            test_urls: Optional[List[str]] = None,
            iterations: int = 3
    ) -> Dict[str, float]:
        """
        测试代理速度
        
        Args:
            proxy_url: 代理URL
            test_urls: 测试URL列表
            iterations: 每个URL测试次数
            
        Returns:
            速度测试结果
        """
        test_urls = test_urls or self.TEST_URLS
        results = {}

        for url in test_urls:
            times = []

            for _ in range(iterations):
                start = time.time()
                try:
                    async with self._session.get(
                            url,
                            proxy=proxy_url,
                            ssl=False
                    ) as response:
                        if response.status == 200:
                            times.append(time.time() - start)
                except Exception as e:
                    # Connection failed, skip this attempt
                    logger.debug(f"Proxy validation request failed: {e}")
                    pass

            if times:
                results[url] = {
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "success_rate": len(times) / iterations
                }

        return results
