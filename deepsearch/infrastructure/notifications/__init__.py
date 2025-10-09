"""通知推送基础设施模块。"""

from .client import XtuisClient
from .exceptions import (
    CategoryNotAllowedError,
    ChannelNotConfiguredError,
    NotificationDispatchError,
    NotificationError,
    NotificationValidationError,
    QuotaExceededContext,
    QuotaExceededError,
)
from .models import NotificationResult, QuotaDecision
from .quota import NotificationQuotaGuard
from .service import NotificationService

__all__ = [
    "NotificationService",
    "NotificationQuotaGuard",
    "XtuisClient",
    "NotificationResult",
    "QuotaDecision",
    "NotificationError",
    "ChannelNotConfiguredError",
    "CategoryNotAllowedError",
    "NotificationValidationError",
    "QuotaExceededError",
    "QuotaExceededContext",
    "NotificationDispatchError",
]
