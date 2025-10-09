"""通知推送模块自定义异常。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class NotificationError(Exception):
    """通知推送基础异常。"""


class ChannelNotConfiguredError(NotificationError):
    """指定渠道未配置 token。"""

    def __init__(self, channel: str):
        super().__init__(f"通知渠道未配置: {channel}")
        self.channel = channel


class CategoryNotAllowedError(NotificationError):
    """指定类别不允许使用目标渠道。"""

    def __init__(self, category: str, channel: str):
        super().__init__(f"类别 {category} 不允许使用渠道 {channel}")
        self.category = category
        self.channel = channel


@dataclass(slots=True)
class QuotaExceededContext:
    """保存额度超限时的上下文信息。"""

    channel: str
    category: str
    max_per_window: Optional[int]
    current_count: int
    window_seconds: int
    reset_seconds: int


class QuotaExceededError(NotificationError):
    """额度超限异常。"""

    def __init__(self, context: QuotaExceededContext):
        super().__init__(
            f"通知额度已用尽: {context.category}@{context.channel}, "
            f"当前 {context.current_count}/{context.max_per_window}"
        )
        self.context = context


class NotificationValidationError(NotificationError):
    """请求参数未通过校验。"""

    def __init__(self, message: str):
        super().__init__(message)


class NotificationDispatchError(NotificationError):
    """发送通知时出现错误。"""

    def __init__(self, channel: str, detail: str):
        super().__init__(f"渠道 {channel} 推送失败: {detail}")
        self.channel = channel
        self.detail = detail
