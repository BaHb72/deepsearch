"""
Provider 异常定义
"""



class ProviderError(Exception):
    """Provider 基础异常"""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ConfigValidationError(ProviderError):
    """配置验证失败"""

    pass


class ProviderCreationError(ProviderError):
    """Provider 创建失败"""

    pass


class ProviderInitializationError(ProviderError):
    """Provider 初始化失败"""

    pass


class ProviderStateError(ProviderError):
    """Provider 状态错误"""

    pass


class ProviderNotFoundError(ProviderError):
    """Provider 不存在"""

    def __init__(self, provider: str, message: str = "Provider 不存在"):
        super().__init__(provider, message)


class UnknownProviderError(ProviderError):
    """未知的 Provider 类型"""

    def __init__(self, provider: str, available: list[str]):
        self.available = available
        message = f"未知的 Provider 类型，可用的类型: {', '.join(available)}"
        super().__init__(provider, message)


class ProviderDataError(ProviderError):
    """数据查询失败"""

    pass


class ProviderTimeoutError(ProviderError):
    """查询超时"""

    pass
