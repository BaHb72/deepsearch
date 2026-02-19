"""
HTTP 代理客户端
通过 Cloudflare Worker 代理请求，保护服务器 IP
"""

import json
import os
import re
import socket
import subprocess
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
        # 获取配置对象（用于读取 worker URL 与网络选项）
        config = get_config()
        workers_cfg = (
            getattr(config, "cloudflare_workers", None) if config and hasattr(config, "cloudflare_workers") else None
        )

        # 获取 Worker URL
        self.worker_url: Optional[str]
        if worker_url:
            self.worker_url = worker_url
        else:
            # 从配置读取
            if workers_cfg:
                if workers_cfg.is_configured():
                    self.worker_url = workers_cfg.get_full_url()
                else:
                    self.worker_url = None
            else:
                self.worker_url = None

        # 网络选项（默认：使用系统代理 + 超时时执行 IPv4 回退）
        self.use_system_proxy = bool(getattr(workers_cfg, "use_system_proxy", True))
        self.prefer_ipv4_fallback = bool(getattr(workers_cfg, "prefer_ipv4_fallback", True))

        # 如果没有 Worker，使用直连
        self.use_proxy = bool(self.worker_url)

        if self.use_proxy:
            logger.info(f"使用 Worker 代理: {self.worker_url}")
        else:
            logger.info("未配置 Worker，使用直连模式")

        # 创建 session，使用原始的 Session 类避免递归
        self.session = _OriginalSession()

        self._apply_proxy_policy()

        # 设置默认超时时间（秒）
        # 增加超时时间以适应东方财富等 API 的响应延迟
        self.default_timeout = 30

        # 请求间隔配置（秒）- 防止触发 Cloudflare/东方财富速率限制
        # 测试表明 1s 间隔可稳定成功，0.5s 作为速度与稳定性的折中
        self.request_interval = 0.5
        self._last_request_time = 0.0

        # 配置重试策略
        # 添加 520-530 Cloudflare 错误码到重试列表
        retry_strategy = Retry(
            total=5,  # 增加重试次数
            backoff_factor=1.5,  # 增加退避因子，等待更长时间
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],  # 允许 POST 重试
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

    @staticmethod
    def _normalize_proxy_url(proxy: str) -> str:
        """规范化代理 URL，补全缺失协议。"""
        proxy = proxy.strip()
        if not proxy:
            return proxy
        if "://" not in proxy:
            return f"http://{proxy}"
        return proxy

    def _load_system_proxies(self) -> dict[str, str]:
        """
        读取系统代理配置。
        优先级：
        1. 显式环境变量（requests/trust_env 已处理）
        2. Windows Internet Settings（当环境变量缺失时）
        3. WinHTTP 代理（当 Internet Settings 不可用时）
        """
        # 若用户已通过环境变量提供代理，不做覆盖
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if os.getenv(key):
                return {}

        if os.name != "nt":
            return {}

        proxies = self._load_windows_internet_settings_proxies()
        if proxies:
            return proxies

        return self._load_winhttp_proxies()

    def _apply_proxy_policy(self) -> None:
        """应用代理策略到 requests Session。"""
        # 系统代理策略：
        # - use_system_proxy=True: 使用环境变量代理，且在 Windows 下尝试读取系统代理
        # - use_system_proxy=False: 强制忽略环境代理，保持完全直连
        if self.use_system_proxy:
            self.session.trust_env = True  # type: ignore[attr-defined]
            system_proxies = self._load_system_proxies()
            if system_proxies:
                self.session.proxies.update(system_proxies)  # type: ignore[attr-defined]
                logger.info(f"ProxyClient 已加载系统代理: {system_proxies}")
            else:
                logger.info("ProxyClient 启用系统代理环境变量(trust_env=True)")
            return

        # 设置空字典会让 requests 忽略环境变量中的代理设置
        self.session.proxies = {"http": None, "https": None}  # type: ignore[attr-defined]
        self.session.trust_env = False  # type: ignore[attr-defined]
        logger.info("ProxyClient 已禁用系统代理环境变量(trust_env=False)")

    def _load_windows_internet_settings_proxies(self) -> dict[str, str]:
        """读取 Windows Internet Settings 代理。"""
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                proxy_enabled = int(winreg.QueryValueEx(key, "ProxyEnable")[0])
                if proxy_enabled != 1:
                    return {}
                proxy_server = str(winreg.QueryValueEx(key, "ProxyServer")[0]).strip()
                if not proxy_server:
                    return {}
                try:
                    proxy_override = str(winreg.QueryValueEx(key, "ProxyOverride")[0]).strip()
                except Exception:
                    proxy_override = ""
        except Exception as error:
            logger.debug(f"读取 Windows 系统代理失败: {error}")
            return {}

        proxies = self._parse_proxy_server(proxy_server)
        no_proxy = self._parse_no_proxy(proxy_override)
        if no_proxy:
            proxies["no_proxy"] = no_proxy

        return proxies

    def _load_winhttp_proxies(self) -> dict[str, str]:
        """读取 WinHTTP 代理配置（作为系统代理兜底）。"""
        try:
            result = subprocess.run(
                ["netsh", "winhttp", "show", "proxy"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except Exception as error:
            logger.debug(f"读取 WinHTTP 代理失败: {error}")
            return {}

        if result.returncode != 0:
            logger.debug(f"读取 WinHTTP 代理失败，退出码: {result.returncode}")
            return {}

        output = result.stdout
        if "Direct access (no proxy server)" in output:
            return {}

        proxy_server = ""
        bypass = ""
        for line in output.splitlines():
            clean_line = line.strip()
            if "Proxy Server(s)" in clean_line and ":" in clean_line:
                proxy_server = clean_line.split(":", 1)[1].strip()
            elif "Bypass List" in clean_line and ":" in clean_line:
                bypass = clean_line.split(":", 1)[1].strip()

        if not proxy_server:
            return {}

        proxies = self._parse_proxy_server(proxy_server)
        no_proxy = self._parse_no_proxy(bypass)
        if no_proxy:
            proxies["no_proxy"] = no_proxy
        return proxies

    def _parse_proxy_server(self, proxy_server: str) -> dict[str, str]:
        """
        解析 Windows 代理字符串。
        支持：
        - 127.0.0.1:10808
        - http=127.0.0.1:10808;https=127.0.0.1:10808
        """
        proxies: dict[str, str] = {}
        entries = [entry.strip() for entry in proxy_server.split(";") if entry.strip()]
        for entry in entries:
            if "=" in entry:
                scheme, value = entry.split("=", 1)
                scheme = scheme.strip().lower()
                value = self._normalize_proxy_url(value)
                if scheme in {"http", "https"} and value:
                    proxies[scheme] = value
            else:
                value = self._normalize_proxy_url(entry)
                if value:
                    proxies.setdefault("http", value)
                    proxies.setdefault("https", value)
        return proxies

    @staticmethod
    def _parse_no_proxy(no_proxy_raw: str) -> str:
        """解析 bypass 列表为 requests 可识别的 no_proxy 字符串。"""
        if not no_proxy_raw:
            return ""
        if no_proxy_raw.lower() in {"(none)", "none"}:
            return ""
        tokens = [tok.strip() for tok in re.split(r"[;,\s]+", no_proxy_raw) if tok.strip()]
        normalized = [tok for tok in tokens if tok.lower() != "<local>"]
        return ",".join(normalized)

    def _session_request(self, method: str, request_url: str, **kwargs) -> requests.Response:
        """
        统一封装 session 请求，并在 Worker 连接超时时执行 IPv4 一次性回退。
        """
        try:
            return self.session.request(method, request_url, **kwargs)
        except requests.exceptions.ConnectTimeout as exc:
            if not self.prefer_ipv4_fallback:
                raise
            if not self.worker_url or ".workers.dev" not in self.worker_url:
                raise

            logger.warning(f"Worker 连接超时，尝试 IPv4 回退重试: {exc}")
            try:
                from urllib3.util import connection as urllib3_connection

                original_allowed_gai_family = urllib3_connection.allowed_gai_family
                urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
                try:
                    return self.session.request(method, request_url, **kwargs)
                finally:
                    urllib3_connection.allowed_gai_family = original_allowed_gai_family
            except Exception as fallback_error:
                logger.warning(f"IPv4 回退重试失败: {fallback_error}")
                raise

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
        # 请求间隔控制 - 防止触发速率限制
        if self.request_interval > 0:
            elapsed_since_last = time.time() - self._last_request_time
            if elapsed_since_last < self.request_interval:
                sleep_time = self.request_interval - elapsed_since_last
                time.sleep(sleep_time)

        start_time = time.time()
        self._last_request_time = start_time
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
        # 注意：必须完全编码，否则嵌套 URL 中的 ? 和 = 会被误解析为外层参数
        encoded_url = quote(url, safe="")
        proxy_url = f"{self.worker_url}/proxy?url={encoded_url}"

        if method == "GET":
            # 发送 GET 请求到 Worker（不使用 params，URL 已完全编码）
            response = self._session_request("GET", proxy_url, **kwargs)

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
            response = self._session_request("POST", proxy_url, **kwargs)

        else:
            # 其他方法
            response = self._session_request(method, proxy_url, **kwargs)

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

    if _proxy_client is None or force_refresh:
        target_url = worker_url
        if target_url is None and _proxy_client is not None:
            target_url = _proxy_client.worker_url
        _proxy_client = ProxyClient(worker_url=target_url)
        return _proxy_client

    if worker_url is not None and _proxy_client.worker_url != worker_url:
        _proxy_client.update_worker_url(worker_url)

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
