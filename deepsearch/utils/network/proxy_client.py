"""
HTTP 代理客户端
通过 Cloudflare Worker 代理请求，保护服务器 IP
"""
import json
import time
from typing import Optional, Dict, Any

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from deepsearch.config import get_config

# 保存原始的 Session 类，确保不受任何 monkey patch 影响
_OriginalSession = requests.Session


class ProxyClient:
    """通过 Cloudflare Worker 代理的 HTTP 客户端"""

    def __init__(self, worker_url: Optional[str] = None):
        """
        初始化代理客户端
        
        Args:
            worker_url: Worker URL，如果不提供则从配置读取
        """
        # 获取 Worker URL
        if worker_url:
            self.worker_url = worker_url
        else:
            # 从配置读取
            config = get_config()
            if config and hasattr(config, 'cloudflare_workers') and config.cloudflare_workers:
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
        self.stats = {
            "total_requests": 0,
            "proxy_requests": 0,
            "direct_requests": 0,
            "failed_requests": 0,
            "total_time": 0
        }

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        发送 GET 请求
        
        Args:
            url: 目标 URL
            **kwargs: 其他请求参数
            
        Returns:
            Response 对象
        """
        return self.request('GET', url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """
        发送 POST 请求
        
        Args:
            url: 目标 URL
            **kwargs: 其他请求参数
            
        Returns:
            Response 对象
        """
        return self.request('POST', url, **kwargs)

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
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.default_timeout

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
        # 构建代理 URL
        proxy_url = f"{self.worker_url}/proxy"

        # 准备参数
        proxy_params = {
            "url": url
        }

        # 处理原始请求参数
        if method == 'GET':
            # GET 请求，参数已经在 URL 中
            if 'params' in kwargs:
                # 如果有额外参数，添加到 URL
                from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                query_params.update(kwargs.pop('params'))
                new_query = urlencode(query_params, doseq=True)
                url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                proxy_params["url"] = url

            # 发送 GET 请求到 Worker
            response = self.session.get(proxy_url, params=proxy_params, **kwargs)

        elif method == 'POST':
            # POST 请求，需要转发请求体
            # Worker 会转发请求体到目标服务器
            headers = kwargs.get('headers', {})

            # 如果有 JSON 数据
            if 'json' in kwargs:
                headers['Content-Type'] = 'application/json'
                kwargs['data'] = json.dumps(kwargs.pop('json'))

            kwargs['headers'] = headers

            # 发送 POST 请求到 Worker
            # 注意：这里仍然是 GET 到 Worker，因为 Worker 会根据参数转发
            response = self.session.post(proxy_url, params=proxy_params, **kwargs)

        else:
            # 其他方法
            response = self.session.request(method, proxy_url, params=proxy_params, **kwargs)

        return response

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.stats.copy()

        # 计算成功率
        if stats["total_requests"] > 0:
            stats["success_rate"] = 1 - (stats["failed_requests"] / stats["total_requests"])
            stats["avg_time"] = stats["total_time"] / stats["total_requests"]
        else:
            stats["success_rate"] = 0
            stats["avg_time"] = 0

        # 添加模式信息
        stats["mode"] = "proxy" if self.use_proxy else "direct"
        stats["worker_url"] = self.worker_url if self.use_proxy else None

        return stats


# 全局代理客户端实例
_proxy_client = None


def get_proxy_client() -> ProxyClient:
    """
    获取全局代理客户端实例
    
    Returns:
        ProxyClient 实例
    """
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = ProxyClient()
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
