"""
代理管理器

整合代理池、验证器，提供完整的代理管理功能。
"""
import asyncio
from datetime import datetime
from typing import Optional, List, Dict

import aiohttp
from loguru import logger

from .pool import ProxyPool
from .validator import ProxyValidator
from ..base import ProxyConfig


class ProxyManager:
    """
    代理管理器
    
    统一管理代理的获取、验证、轮换和健康检查。
    """

    def __init__(self, config: ProxyConfig):
        """
        初始化代理管理器
        
        Args:
            config: 代理配置
        """
        self.config = config
        self._pool = ProxyPool(rotation_strategy=config.rotation_strategy)
        self._validator = ProxyValidator(timeout=config.timeout)
        self._health_check_task: Optional[asyncio.Task] = None
        self._dynamic_fetch_task: Optional[asyncio.Task] = None
        self._running = False

        # 统计信息
        self._total_requests = 0
        self._total_success = 0
        self._last_health_check = None
        self._last_dynamic_fetch = None

    async def initialize(self) -> None:
        """初始化代理管理器"""
        logger.info("初始化代理管理器...")

        # 添加静态代理
        if self.config.proxy_list:
            await self._add_static_proxies()

        # 获取动态代理
        if self.config.proxy_api_url:
            await self._fetch_dynamic_proxies()

        # 验证所有代理
        await self._validate_all_proxies()

        logger.info(f"代理管理器初始化完成，可用代理数: {len(await self._get_available_proxies())}")

    async def start(self) -> None:
        """启动代理管理器"""
        if self._running:
            return

        self._running = True

        # 启动健康检查任务
        if self.config.health_check_interval > 0:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        # 启动动态代理获取任务
        if self.config.proxy_api_url:
            self._dynamic_fetch_task = asyncio.create_task(self._dynamic_fetch_loop())

        logger.info("代理管理器已启动")

    async def stop(self) -> None:
        """停止代理管理器"""
        self._running = False

        # 取消后台任务
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._dynamic_fetch_task:
            self._dynamic_fetch_task.cancel()
            try:
                await self._dynamic_fetch_task
            except asyncio.CancelledError:
                pass

        logger.info("代理管理器已停止")

    async def get_proxy(self) -> Optional[str]:
        """
        获取一个可用代理
        
        Returns:
            代理URL，如果没有可用代理返回None
        """
        self._total_requests += 1

        # 先清理黑名单
        await self._pool.cleanup_blacklist()

        # 获取代理
        proxy = await self._pool.get_proxy()

        if not proxy:
            # 尝试获取新的动态代理
            if self.config.proxy_api_url:
                await self._fetch_dynamic_proxies()
                proxy = await self._pool.get_proxy()

        if proxy:
            logger.debug(f"分配代理: {proxy}")
        else:
            logger.warning("无可用代理")

        return proxy

    async def mark_success(self, proxy_url: str, response_time: float = 0) -> None:
        """
        标记代理成功
        
        Args:
            proxy_url: 代理URL
            response_time: 响应时间（秒）
        """
        self._total_success += 1
        await self._pool.mark_success(proxy_url, response_time)
        await self._pool.release_proxy(proxy_url)

    async def mark_failure(self, proxy_url: str) -> None:
        """
        标记代理失败
        
        Args:
            proxy_url: 代理URL
        """
        await self._pool.mark_failure(
            proxy_url,
            self.config.blacklist_threshold,
            self.config.blacklist_duration
        )
        await self._pool.release_proxy(proxy_url)

    async def _add_static_proxies(self) -> None:
        """添加静态代理"""
        for proxy_url in self.config.proxy_list:
            await self._pool.add_proxy(proxy_url, {"source": "static"})
        logger.info(f"添加了 {len(self.config.proxy_list)} 个静态代理")

    async def _fetch_dynamic_proxies(self) -> None:
        """获取动态代理"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if self.config.proxy_api_key:
                    headers["Authorization"] = f"Bearer {self.config.proxy_api_key}"

                async with session.get(
                        self.config.proxy_api_url,
                        headers=headers,
                        timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # 解析代理列表（根据实际API格式调整）
                        proxies = []
                        if isinstance(data, list):
                            proxies = data
                        elif isinstance(data, dict):
                            proxies = data.get("proxies", data.get("data", []))

                        # 添加到代理池
                        new_count = 0
                        for proxy in proxies:
                            if isinstance(proxy, str):
                                proxy_url = proxy
                            elif isinstance(proxy, dict):
                                # 尝试不同的字段名
                                proxy_url = proxy.get("proxy") or proxy.get("url") or \
                                            f"{proxy.get('protocol', 'http')}://{proxy.get('ip')}:{proxy.get('port')}"
                            else:
                                continue

                            await self._pool.add_proxy(proxy_url, {"source": "dynamic"})
                            new_count += 1

                        self._last_dynamic_fetch = datetime.now()
                        logger.info(f"获取了 {new_count} 个动态代理")
                    else:
                        logger.error(f"获取动态代理失败: HTTP {response.status}")

        except Exception as e:
            logger.error(f"获取动态代理异常: {e}")

    async def _validate_all_proxies(self) -> None:
        """验证所有代理"""
        proxies = list(self._pool._proxies.keys())

        if not proxies:
            return

        logger.info(f"开始验证 {len(proxies)} 个代理...")

        async with ProxyValidator(timeout=self.config.timeout) as validator:
            results = await validator.batch_validate(proxies, max_concurrent=10)

        # 更新代理状态
        for proxy_url, result in results.items():
            if result["valid"]:
                await self._pool.mark_success(proxy_url, result.get("response_time", 0))
            else:
                await self._pool.mark_failure(
                    proxy_url,
                    self.config.blacklist_threshold,
                    self.config.blacklist_duration
                )

    async def _get_available_proxies(self) -> List[str]:
        """获取所有可用代理"""
        return [
            url for url, info in self._pool._proxies.items()
            if info.is_available
        ]

    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                # 获取需要检查的代理
                proxies_to_check = []
                now = datetime.now()

                for url, info in self._pool._proxies.items():
                    # 检查失败的代理
                    if info.status.value == "failed":
                        proxies_to_check.append(url)
                    # 检查长时间未使用的代理
                    elif info.last_used and (now - info.last_used).seconds > 300:
                        proxies_to_check.append(url)

                if proxies_to_check:
                    logger.debug(f"健康检查 {len(proxies_to_check)} 个代理")

                    async with ProxyValidator(timeout=self.config.timeout) as validator:
                        for proxy_url in proxies_to_check[:5]:  # 每次最多检查5个
                            valid, result = await validator.validate_proxy(proxy_url)
                            if valid:
                                await self._pool.mark_success(
                                    proxy_url,
                                    result.get("response_time", 0)
                                )
                            else:
                                await self._pool.mark_failure(
                                    proxy_url,
                                    self.config.blacklist_threshold,
                                    self.config.blacklist_duration
                                )

                # 清理黑名单
                await self._pool.cleanup_blacklist()

                self._last_health_check = datetime.now()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查异常: {e}")

    async def _dynamic_fetch_loop(self) -> None:
        """动态代理获取循环"""
        while self._running:
            try:
                # 每5分钟获取一次新代理
                await asyncio.sleep(300)

                # 检查是否需要更多代理
                available_count = len(await self._get_available_proxies())
                if available_count < self.config.pool_size:
                    logger.info(f"可用代理数不足 ({available_count}/{self.config.pool_size})，获取新代理")
                    await self._fetch_dynamic_proxies()
                    await self._validate_all_proxies()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"动态代理获取异常: {e}")

    def get_statistics(self) -> Dict[str, any]:
        """获取统计信息"""
        pool_stats = self._pool.get_statistics()

        return {
            "enabled": self.config.enabled,
            "total_requests": self._total_requests,
            "total_success": self._total_success,
            "success_rate": self._total_success / self._total_requests if self._total_requests > 0 else 0,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "last_dynamic_fetch": self._last_dynamic_fetch.isoformat() if self._last_dynamic_fetch else None,
            "pool": pool_stats,
            "config": {
                "rotation_strategy": self.config.rotation_strategy,
                "pool_size": self.config.pool_size,
                "blacklist_threshold": self.config.blacklist_threshold,
                "blacklist_duration": self.config.blacklist_duration
            }
        }

    def get_proxy_list(self) -> List[Dict]:
        """获取代理列表详情"""
        return self._pool.get_proxy_details()
