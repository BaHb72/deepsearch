"""
HTTP 代理客户端
通过 Cloudflare Worker 代理请求，保护服务器 IP
"""

import json
import time
from typing import Optional, TypedDict
from urllib.parse import quote

import requests
from core.config import get_config
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 保存原始的 Session 类，确保不受任何 monkey patch 影响
_OriginalSession = requests.Session


class ProxyClientStats(TypedDict):
    """基础统计结构。"""

    total_requests: int
    proxy_requests: int
    direct_requests: int
    failed_requests: int
    total_time: float


class ProxyClientStatsReport(ProxyClientStats, total=False):
    """带派生指标的统计报表。"""

    success_rate: float
    avg_time: float
    mode: str
    worker_url: Optional[str]


class ProxyClient:
    """通过 Cloudflare Worker 代理的 HTTP 客户端"""

    def __init__(self, worker_url: Optional[str] = None):
        """
        初始化代理客户端

        Args:
            worker_url: Worker URL，如果不提供则从配置读取
        """
        # 获取 Worker URL
        self.worker_url: Optional[str]
        if worker_url:
            self.worker_url = worker_url
        else:
            # 从配置读取
            config = get_config()
            if config and hasattr(config, "cloudflare_workers") and config.cloudflare_workers:
                # 现在 cloudflare_workers 是 CloudflareWorkersConfig 对象
                if config.cloudflare_workers.is_configured():
                    self.worker_url = config.cloudflare_workers.get_full_url()
                else:
                    self.worker_url = None
            else:
                self.worker_url = None

        # 如果没有 Worker，使用直连
        self.use_proxy = bool(self.worker_url)

        if self.use_proxy:
            logger.info(f"使用 Worker 代理: {self.worker_url}")
        else:
            logger.info("未配置 Worker，使用直连模式")

        # 创建 session，使用原始的 Session 类避免递归
        self.session = _OriginalSession()

        # 设置默认超时时间（秒）
        self.default_timeout = 10  # 默认10秒超时

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 统计信息
        self.stats: ProxyClientStats = {
            "total_requests": 0,
            "proxy_requests": 0,
            "direct_requests": 0,
            "failed_requests": 0,
            "total_time": 0.0,
        }

    def update_worker_url(self, worker_url: Optional[str]) -> None:
        """动态更新 Worker URL，并切换代理模式"""
        if worker_url == self.worker_url:
            return

        self.worker_url = worker_url
        self.use_proxy = bool(worker_url)

        if self.use_proxy:
            logger.info(f"更新 Worker 代理: {self.worker_url}")
        else:
            logger.info("关闭 Worker 代理，切换为直连模式")

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        发送 GET 请求

        Args:
            url: 目标 URL
            **kwargs: 其他请求参数

        Returns:
            Response 对象
        """
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """
        发送 POST 请求

        Args:
            url: 目标 URL
            **kwargs: 其他请求参数

        Returns:
            Response 对象
        """
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        发送 HTTP 请求

        Args:
            method: 请求方法
            url: 目标 URL
            **kwargs: 其他请求参数

        Returns:
            Response 对象
        """
        start_time = time.time()
        self.stats["total_requests"] += 1

        # 设置默认超时（如果用户没有提供）
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.default_timeout

        try:
            if self.use_proxy and self.worker_url:
                # 通过 Worker 代理
                response = self._proxy_request(method, url, **kwargs)
                self.stats["proxy_requests"] += 1
                logger.debug(f"通过 Worker 代理请求: {url}")
            else:
                # 直连
                response = self.session.request(method, url, **kwargs)
                self.stats["direct_requests"] += 1
                logger.debug(f"直连请求: {url}")

            # 记录耗时
            elapsed = time.time() - start_time
            self.stats["total_time"] += elapsed

            return response

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"请求失败 {url}: {e}")
            raise

    def _proxy_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        通过 Worker 代理发送请求

        Args:
            method: 请求方法
            url: 目标 URL
            **kwargs: 其他请求参数

        Returns:
            Response 对象
        """
        # 处理原始请求参数
        if method == "GET":
            # GET 请求，如果有 params 参数，需要先合并到 URL
            if "params" in kwargs:
                # 如果有额外参数，需要合并到目标 URL
                # 注意：不使用 urlencode，因为某些服务器（如东方财富）不接受 URL 编码的逗号
                # 我们直接拼接参数，保持原始格式
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(url)
                # 获取额外的 params 参数
                extra_params = kwargs.pop("params")

                # 手动构建查询字符串，不编码特殊字符（如逗号）
                # 只需要确保 key=value 格式正确
                param_parts = []
                for key, value in extra_params.items():
                    # 将值转换为字符串
                    param_parts.append(f"{key}={value}")
                new_params_str = "&".join(param_parts)

                # 合并现有查询字符串和新参数
                if parsed.query:
                    new_query = f"{parsed.query}&{new_params_str}"
                else:
                    new_query = new_params_str

                # 重新构建完整 URL
                url = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        new_query,
                        parsed.fragment,
                    )
                )

        # 构建代理 URL
        # 使用完全编码 (safe="") 确保目标 URL 正确作为 Worker 的查询参数传递
        # Worker 的 decodeURIComponent 会正确解码所有编码字符
        # 注意：由于不使用 urlencode 构建参数，逗号等字符保持原始格式
        encoded_url = quote(url, safe="")
        proxy_url = f"{self.worker_url}/proxy?url={encoded_url}"

        if method == "GET":
            # 发送 GET 请求到 Worker（不使用 params，URL 已完全编码）
            response = self.session.get(proxy_url, **kwargs)

        elif method == "POST":
            # POST 请求，需要转发请求体
            # Worker 会转发请求体到目标服务器
            headers = kwargs.get("headers", {})

            # 如果有 JSON 数据
            if "json" in kwargs:
                headers["Content-Type"] = "application/json"
                kwargs["data"] = json.dumps(kwargs.pop("json"))

            kwargs["headers"] = headers

            # 发送 POST 请求到 Worker
            response = self.session.post(proxy_url, **kwargs)

        else:
            # 其他方法
            response = self.session.request(method, proxy_url, **kwargs)

        return response

    def get_stats(self) -> ProxyClientStatsReport:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        total_requests = self.stats["total_requests"]
        failed_requests = self.stats["failed_requests"]
        total_time = self.stats["total_time"]

        if total_requests > 0:
            success_rate = 1 - (failed_requests / total_requests)
            avg_time = total_time / total_requests
        else:
            success_rate = 0.0
            avg_time = 0.0

        report: ProxyClientStatsReport = {
            "total_requests": total_requests,
            "proxy_requests": self.stats["proxy_requests"],
            "direct_requests": self.stats["direct_requests"],
            "failed_requests": failed_requests,
            "total_time": total_time,
            "success_rate": success_rate,
            "avg_time": avg_time,
            "mode": "proxy" if self.use_proxy else "direct",
            "worker_url": self.worker_url if self.use_proxy else None,
        }

        return report


# 全局代理客户端实例
_proxy_client: Optional[ProxyClient] = None


def get_proxy_client(worker_url: Optional[str] = None, force_refresh: bool = False) -> ProxyClient:
    """
    获取全局代理客户端实例，并支持动态更新 Worker URL

    Args:
        worker_url: 指定新的 Worker URL
        force_refresh: 是否强制刷新现有客户端配置

    Returns:
        ProxyClient 实例
    """
    global _proxy_client

    if _proxy_client is None:
        _proxy_client = ProxyClient(worker_url=worker_url)
        return _proxy_client

    if worker_url is not None:
        if force_refresh or _proxy_client.worker_url != worker_url:
            _proxy_client.update_worker_url(worker_url)
    elif force_refresh:
        _proxy_client.update_worker_url(None)

    return _proxy_client


def create_proxy_session() -> requests.Session:
    """
    创建一个配置了代理的 requests.Session
    这个 session 的所有请求都会通过 Worker 代理

    Returns:
        配置好的 Session 对象
    """
    client = get_proxy_client()

    if not client.use_proxy:
        # 如果没有配置代理，返回原始 session
        return _OriginalSession()

    # 创建一个自定义的 Session，继承自原始 Session 类
    class ProxySession(_OriginalSession):
        def request(self, method, url, **kwargs):
            # 拦截所有请求，通过代理客户端发送
            return client.request(method, url, **kwargs)

    return ProxySession()
