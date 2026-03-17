"""
AkShare 代理补丁
让 akshare 库的所有请求通过 Cloudflare Worker 代理
"""

import functools
import importlib
import sys
from contextlib import contextmanager
from threading import RLock
from typing import Any, cast

import requests as requests_module
from core.utils.network.proxy_client import get_proxy_client
from loguru import logger

requests = cast(Any, requests_module)

_ORIGINAL_GET = requests.get
_ORIGINAL_POST = requests.post
_ORIGINAL_REQUEST = requests.request
_PATCH_LOCK = RLock()
_PATCHED = False


def patch_akshare():
    """
    Monkey patch akshare 库，让它使用我们的代理客户端
    这样所有 akshare 的请求都会通过 Cloudflare Worker
    """
    try:
        importlib.import_module("akshare")
    except ImportError:
        logger.warning("akshare 未安装，跳过代理补丁")
        return

    global _PATCHED
    with _PATCH_LOCK:
        # 获取代理客户端
        client = get_proxy_client()

        if not client.use_proxy:
            logger.info("未配置 Worker 代理，akshare 将使用直连模式")
            return

        if _PATCHED:
            logger.debug("akshare 代理补丁已存在，跳过重复 patch")
            return

        logger.info(f"配置 akshare 使用 Worker 代理: {client.worker_url}")

        # 创建代理包装器
        @functools.wraps(_ORIGINAL_GET)
        def proxy_get(url, **kwargs):
            """代理 GET 请求"""
            logger.debug(f"[AkShare] 代理 GET 请求: {url}")
            return client.get(url, **kwargs)

        @functools.wraps(_ORIGINAL_POST)
        def proxy_post(url, **kwargs):
            """代理 POST 请求"""
            logger.debug(f"[AkShare] 代理 POST 请求: {url}")
            return client.post(url, **kwargs)

        @functools.wraps(_ORIGINAL_REQUEST)
        def proxy_request(method, url, **kwargs):
            """代理通用请求"""
            logger.debug(f"[AkShare] 代理 {method} 请求: {url}")
            return client.request(method, url, **kwargs)

        # 只替换 requests 模块的顶层方法，不修改 Session 类
        requests.get = proxy_get
        requests.post = proxy_post
        requests.request = proxy_request

        # 同时替换 akshare 模块内部的 requests
        for name, module in sys.modules.items():
            if name.startswith("akshare") and hasattr(module, "requests"):
                module.requests.get = proxy_get
                module.requests.post = proxy_post
                module.requests.request = proxy_request

        _PATCHED = True
        logger.info("akshare 代理补丁应用成功")


def unpatch_akshare():
    """
    移除 akshare 的代理补丁，恢复原始行为
    """
    try:
        importlib.import_module("akshare")
    except ImportError:
        return

    global _PATCHED
    with _PATCH_LOCK:
        if not _PATCHED:
            return

        requests.get = _ORIGINAL_GET
        requests.post = _ORIGINAL_POST
        requests.request = _ORIGINAL_REQUEST

        for name, module in sys.modules.items():
            if name.startswith("akshare") and hasattr(module, "requests"):
                module.requests.get = _ORIGINAL_GET
                module.requests.post = _ORIGINAL_POST
                module.requests.request = _ORIGINAL_REQUEST

        _PATCHED = False
        logger.info("移除 akshare 代理补丁")


@contextmanager
def temporarily_unpatch_akshare_requests():
    """在上下文中临时恢复 requests 原始行为，退出后恢复补丁状态。"""
    with _PATCH_LOCK:
        was_patched = _PATCHED
        if was_patched:
            unpatch_akshare()
        try:
            yield
        finally:
            if was_patched:
                patch_akshare()


class ProxySession(requests_module.Session):
    """
    代理 Session 类，所有请求都通过 Cloudflare Worker
    专门为 akshare 设计，不会造成递归
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_client = get_proxy_client()

    def request(self, method, url, **kwargs):
        """重写 request 方法，通过代理发送"""
        if self.proxy_client and self.proxy_client.use_proxy:
            logger.debug(f"[ProxySession] 代理 {method} 请求: {url}")
            # 使用代理客户端，但注意这里调用的是 proxy_client 的方法
            # 而 proxy_client 内部使用的是原始的 Session，不会递归
            return self.proxy_client.request(method, url, **kwargs)
        else:
            # 如果没有配置代理，使用原始方法
            return super().request(method, url, **kwargs)


def create_akshare_session():
    """
    创建一个专门为 akshare 使用的代理 Session

    Returns:
        ProxySession 实例
    """
    return ProxySession()


class AkShareProxyContext:
    """
    上下文管理器，在上下文中使用代理的 akshare

    Example:
        with AkShareProxyContext():
            df = ak.stock_zh_a_spot_em()
    """

    def __enter__(self):
        patch_akshare()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 可以选择是否恢复
        pass
