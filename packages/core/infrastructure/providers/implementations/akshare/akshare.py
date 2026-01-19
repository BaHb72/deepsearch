"""
AkShare 数据提供者

主 Provider 实现：AkShareProvider
支持两种模式：
- worker: 通过 Cloudflare Worker 代理访问
- direct: 直接调用 akshare 库

命名历史：
- AkShareProxyProvider: 已废弃，使用 request_handler.py（与 worker.js 不兼容）
- AKShareDirectProvider: 已重命名为 AkShareProvider
- AkShareProvider: 当前主实现，使用 proxy_client.py（正确兼容 worker.js）
"""

import warnings

# 导入主实现
from .akshare_direct import AkShareProvider

# 向后兼容别名
# AKShareDirectProvider 已重命名为 AkShareProvider
AKShareDirectProvider = AkShareProvider


# AkShareProxyProvider 已废弃，但保留别名以兼容现有代码
# 实际上指向新的 AkShareProvider（功能相同，协议兼容）
class AkShareProxyProvider(AkShareProvider):
    """
    [DEPRECATED] 已废弃，请使用 AkShareProvider

    此类保留仅为向后兼容。它现在是 AkShareProvider 的子类，
    不再使用有问题的 request_handler.py。

    废弃原因：
    - 原 AkShareProxyProvider 使用 request_handler.py
    - request_handler.py 发送 /api/* 格式请求
    - 但 worker.js 只处理 /proxy?url=* 格式
    - 协议不兼容导致 404 错误

    迁移指南：
        # 旧代码
        from ...akshare import AkShareProxyProvider
        provider = AkShareProxyProvider()

        # 新代码
        from ...akshare import AkShareProvider
        provider = AkShareProvider()
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "AkShareProxyProvider 已废弃，请使用 AkShareProvider。" "详见 akshare.py 模块文档。",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


# 导出
__all__ = ["AkShareProvider", "AKShareDirectProvider", "AkShareProxyProvider"]
