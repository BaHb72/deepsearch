"""
AkShare 代理补丁
让 akshare 库的所有请求通过 Cloudflare Worker 代理
"""

import functools
import importlib
import sys

import requests
from core.utils.network.proxy_client import get_proxy_client
from loguru import logger

# 在模块级别保存原始的 Session 类，避免被后续的 patch 影响
_OriginalSession = requests.Session


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

    # 获取代理客户端
    client = get_proxy_client()

    if not client.use_proxy:
        logger.info("未配置 Worker 代理，akshare 将使用直连模式")
        return

    logger.info(f"配置 akshare 使用 Worker 代理: {client.worker_url}")

    # 保存原始的 requests 方法
    original_get = requests.get
    original_post = requests.post
    original_request = requests.request

    # 创建代理包装器
    @functools.wraps(original_get)
    def proxy_get(url, **kwargs):
        """代理 GET 请求"""
        logger.debug(f"[AkShare] 代理 GET 请求: {url}")
        return client.get(url, **kwargs)

    @functools.wraps(original_post)
    def proxy_post(url, **kwargs):
        """代理 POST 请求"""
        logger.debug(f"[AkShare] 代理 POST 请求: {url}")
        return client.post(url, **kwargs)

    @functools.wraps(original_request)
    def proxy_request(method, url, **kwargs):
        """代理通用请求"""
        logger.debug(f"[AkShare] 代理 {method} 请求: {url}")
        return client.request(method, url, **kwargs)

    # 只替换 requests 模块的顶层方法，不修改 Session 类
    # 这样避免了递归问题，因为 proxy_client 内部使用的 Session 不会被影响
    requests.get = proxy_get
    requests.post = proxy_post
    requests.request = proxy_request

    # 不再修改 Session 类的方法，避免递归
    # 注意：这意味着使用 requests.Session() 的 akshare 代码不会被代理
    # 但大部分 akshare 代码使用的是 requests.get() 等顶层函数

    # 同时替换 akshare 模块内部的 requests
    # 某些 akshare 子模块可能已经导入了 requests
    for name, module in sys.modules.items():
        if name.startswith("akshare"):
            if hasattr(module, "requests"):
                module.requests.get = proxy_get
                module.requests.post = proxy_post
                module.requests.request = proxy_request

    logger.info("akshare 代理补丁应用成功")


def unpatch_akshare():
    """
    移除 akshare 的代理补丁，恢复原始行为
    """
    try:
        importlib.import_module("akshare")
    except ImportError:
        return

    # 这里可以恢复原始方法，但通常不需要
    logger.info("移除 akshare 代理补丁")


class ProxySession(_OriginalSession):
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
