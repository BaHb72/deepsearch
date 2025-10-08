"""
通知推送相关的配置模型。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class NotificationBaseUrls(BaseModel):
    """虾推啥推送渠道的基础 URL 配置。"""

    wechat: str = Field(default="https://wx.xtuis.cn", description="微信推送基础地址")
    bark: str = Field(default="https://bark.xtuis.cn", description="Bark 推送基础地址")

    def get(self, channel: str) -> str:
        """按渠道获取基础地址。"""
        channel = channel.lower()
        if channel == "wechat":
            return self.wechat
        if channel == "bark":
            return self.bark
        raise ValueError(f"未知的推送渠道: {channel}")


class NotificationCategoryConfig(BaseModel):
    """单个通知类别的额度限制配置。"""

    enabled: bool = Field(default=True, description="是否启用该类别的额度限制")
    max_per_window: int = Field(
        default=10, ge=0, description="单个时间窗口内允许的最大推送条数，0 表示不限"
    )
    window_seconds: int = Field(default=300, gt=0, description="额度统计窗口的长度（秒）")
    channels: List[str] = Field(
        default_factory=list, description="允许使用的渠道列表，空列表表示继承全局默认"
    )

    @field_validator("channels", mode="after")
    @classmethod
    def _normalize_channels(cls, value: List[str]) -> List[str]:
        """标准化渠道名称为小写并移除空项。"""
        normalized = [item.strip().lower() for item in value if item and item.strip()]
        # 去重同时保持原有顺序
        seen = set()
        result: List[str] = []
        for channel in normalized:
            if channel not in seen:
                seen.add(channel)
                result.append(channel)
        return result


class NotificationsConfig(BaseModel):
    """通知推送顶层配置。"""

    enabled: bool = Field(default=False, description="是否启用通知推送功能")
    wechat_token: Optional[str] = Field(default=None, description="虾推啥微信渠道的 token")
    bark_token: Optional[str] = Field(default=None, description="虾推啥 Bark 渠道的 token")
    base_urls: NotificationBaseUrls = Field(
        default_factory=NotificationBaseUrls, description="推送渠道的基础 URL 配置"
    )
    default_channel: str = Field(default="wechat", description="默认推送渠道")
    categories: Dict[str, NotificationCategoryConfig] = Field(
        default_factory=dict, description="按类别定义的额度限制配置"
    )
    request_timeout: float = Field(default=5.0, gt=0, description="HTTP 请求超时时间（秒）")
    retry_attempts: int = Field(default=2, ge=0, description="发送失败后的重试次数")
    retry_delay: float = Field(default=1.0, ge=0, description="重试之间的等待时间（秒）")
    title_template: str = Field(
        default="DeepSearch 通知提醒: {title}", description="通知标题模板，支持占位符"
    )
    body_template: str = Field(default="{content}", description="通知正文模板，支持占位符")

    @field_validator("default_channel")
    @classmethod
    def _normalize_default_channel(cls, value: str) -> str:
        """标准化默认渠道名称。"""
        if not value:
            return "wechat"
        return value.strip().lower()

    @model_validator(mode="after")
    def _apply_defaults(self) -> "NotificationsConfig":
        """在模型校验后补全缺省渠道配置。"""
        default_channel = self.default_channel
        for name, category in self.categories.items():
            if not category.channels:
                # 直接修改实例副本
                self.categories[name] = category.model_copy(update={"channels": [default_channel]})
        return self

    def get_token(self, channel: str) -> Optional[str]:
        """按渠道获取推送 token。"""
        channel = channel.lower()
        if channel == "wechat":
            return self.wechat_token
        if channel == "bark":
            return self.bark_token
        return None

    def supports_channel(self, channel: str) -> bool:
        """判断指定渠道是否配置了 token。"""
        return bool(self.get_token(channel))

    def get_category(self, category: str) -> Optional[NotificationCategoryConfig]:
        """获取指定类别的额度配置。"""
        return self.categories.get(category)

    def list_channels(self) -> List[str]:
        """列出启用的渠道。"""
        channels = []
        if self.wechat_token:
            channels.append("wechat")
        if self.bark_token:
            channels.append("bark")
        return channels
