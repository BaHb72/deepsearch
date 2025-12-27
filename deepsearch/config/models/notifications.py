"""
通知推送相关的配置模型。
"""

from __future__ import annotations

from typing import Dict, List, Optional, cast

from pydantic import BaseModel, Field, field_validator, model_validator


class NotificationBaseUrls(BaseModel):
    """虾推啥推送渠道的基础 URL 配置。"""

    wechat: str = Field(default="https://wx.xtuis.cn", description="微信推送基础地址")
    bark: str = Field(
        default="https://bark.xtuis.cn",
        description="Bark 推送基础地址（已弃用，使用 bark_servers）",
    )

    def get(self, channel: str) -> str:
        """按渠道获取基础地址。"""
        channel = channel.lower()
        if channel == "wechat":
            return self.wechat
        if channel == "bark":
            return self.bark
        raise ValueError(f"未知的推送渠道: {channel}")


# ==================== 消息模板模型 ====================


class MessageTemplateBase(BaseModel):
    """消息模板基类。"""

    name: str = Field(..., min_length=1, description="模板名称")
    title_template: str = Field(
        default="{title}", description="标题模板，支持 {title}, {timestamp}, {category} 等占位符"
    )
    body_template: str = Field(
        default="{content}", description="正文模板，支持 {content}, {title}, {timestamp} 等占位符"
    )


class WechatMessageTemplate(MessageTemplateBase):
    """微信消息模板。"""

    pass


class BarkMessageTemplate(MessageTemplateBase):
    """Bark 消息模板，支持丰富的推送样式。"""

    subtitle_template: Optional[str] = Field(default=None, description="副标题模板")
    use_markdown: bool = Field(default=False, description="是否使用 Markdown 格式")
    level: Optional[str] = Field(
        default=None,
        description="中断级别: active(默认)/timeSensitive(时效性)/passive(静默)/critical(紧急)",
    )
    sound: Optional[str] = Field(default=None, description="通知声音，如 minuet.caf, birdsong.caf")
    icon: Optional[str] = Field(default=None, description="自定义图标 URL")
    image: Optional[str] = Field(default=None, description="通知配图 URL")
    group: Optional[str] = Field(default=None, description="通知分组名称")
    url: Optional[str] = Field(default=None, description="点击跳转 URL")
    copy: Optional[str] = Field(default=None, description="复制内容模板")
    auto_copy: bool = Field(default=False, description="是否自动复制内容到剪贴板")
    is_archive: Optional[bool] = Field(default=None, description="是否归档到历史记录")
    call: bool = Field(default=False, description="是否持续响铃直到用户操作")
    badge: Optional[int] = Field(default=None, ge=0, description="App 角标数字")

    @field_validator("level", mode="after")
    @classmethod
    def _validate_level(cls, value: Optional[str]) -> Optional[str]:
        """验证通知级别。"""
        if value is None:
            return None
        valid_levels = {"active", "timesensitive", "passive", "critical"}
        normalized = value.lower()
        if normalized not in valid_levels:
            raise ValueError(
                f"无效的通知级别: {value}，可选: active/timeSensitive/passive/critical"
            )
        return normalized


class MessageTemplates(BaseModel):
    """消息模板配置。"""

    wechat: List[WechatMessageTemplate] = Field(
        default_factory=list, description="微信消息模板列表"
    )
    bark: List[BarkMessageTemplate] = Field(default_factory=list, description="Bark 消息模板列表")
    default_wechat: Optional[str] = Field(default=None, description="微信默认模板名称")
    default_bark: Optional[str] = Field(default=None, description="Bark 默认模板名称")

    def get_wechat_template(self, name: Optional[str] = None) -> Optional[WechatMessageTemplate]:
        """获取微信模板。"""
        target = name or self.default_wechat
        if not target:
            return self.wechat[0] if self.wechat else None
        for t in self.wechat:
            if t.name == target:
                return t
        return None

    def get_bark_template(self, name: Optional[str] = None) -> Optional[BarkMessageTemplate]:
        """获取 Bark 模板。"""
        target = name or self.default_bark
        if not target:
            return self.bark[0] if self.bark else None
        for t in self.bark:
            if t.name == target:
                return t
        return None


class BarkServerConfig(BaseModel):
    """单个 Bark 服务器配置。"""

    name: str = Field(..., min_length=1, description="服务器显示名称")
    base_url: str = Field(
        ...,
        min_length=1,
        description="服务器地址，如 https://api.day.app 或 https://api.day.app/YOUR_KEY",
    )
    token: str = Field(default="", description="设备 Key（官方 Bark 可留空，key 已在 URL 中）")
    enabled: bool = Field(default=True, description="是否启用此服务器")
    # 默认参数
    group: Optional[str] = Field(default=None, description="默认通知分组")
    icon: Optional[str] = Field(default=None, description="默认图标 URL（iOS 15+）")
    sound: Optional[str] = Field(default=None, description="默认通知声音")
    level: Optional[str] = Field(
        default=None, description="默认通知级别: active/timeSensitive/passive/critical"
    )

    @field_validator("base_url", mode="after")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        """移除末尾斜杠。"""
        return value.rstrip("/")

    @field_validator("level", mode="after")
    @classmethod
    def _validate_level(cls, value: Optional[str]) -> Optional[str]:
        """验证通知级别。"""
        if value is None:
            return None
        valid_levels = {"active", "timesensitive", "passive", "critical"}
        normalized = value.lower()
        if normalized not in valid_levels:
            raise ValueError(
                f"无效的通知级别: {value}，可选: active/timeSensitive/passive/critical"
            )
        return normalized


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
    bark_token: Optional[str] = Field(
        default=None, description="虾推啥 Bark 渠道的 token（已弃用，使用 bark_servers）"
    )
    bark_servers: List[BarkServerConfig] = Field(
        default_factory=list, description="Bark 服务器列表，支持多服务器推送"
    )
    base_urls: NotificationBaseUrls = Field(
        default_factory=NotificationBaseUrls, description="推送渠道的基础 URL 配置"
    )
    default_channel: List[str] = Field(
        default_factory=lambda: ["wechat"], description="默认推送渠道列表"
    )
    categories: Dict[str, NotificationCategoryConfig] = Field(
        default_factory=dict, description="按类别定义的额度限制配置"
    )
    request_timeout: float = Field(default=5.0, gt=0, description="HTTP 请求超时时间（秒）")
    retry_attempts: int = Field(default=2, ge=0, description="发送失败后的重试次数")
    retry_delay: float = Field(default=1.0, ge=0, description="重试之间的等待时间（秒）")
    title_template: str = Field(
        default="DeepSearch 通知提醒: {title}", description="通知标题模板，支持占位符（向后兼容）"
    )
    body_template: str = Field(
        default="{content}", description="通知正文模板，支持占位符（向后兼容）"
    )
    templates: MessageTemplates = Field(
        default_factory=MessageTemplates, description="消息模板配置，支持分渠道自定义模板"
    )

    @field_validator("default_channel")
    @classmethod
    def _normalize_default_channel(cls, value: List[str]) -> List[str]:
        """标准化默认渠道名称列表。"""
        if not value:
            return ["wechat"]
        return [ch.strip().lower() for ch in value if ch and ch.strip()]

    @model_validator(mode="after")
    def _apply_defaults(self) -> "NotificationsConfig":
        """在模型校验后补全缺省渠道配置，并迁移旧版 bark_token 到 bark_servers。"""
        default_channels = self.default_channel or ["wechat"]
        for name, category in self.categories.items():
            if not category.channels:
                updated = cast(
                    NotificationCategoryConfig,
                    category.model_copy(update={"channels": default_channels}),
                )
                self.categories[name] = updated

        # 向后兼容：如果有旧版 bark_token 但没有 bark_servers，自动迁移
        if self.bark_token and not self.bark_servers:
            legacy_server = BarkServerConfig(
                name="默认 Bark 服务器",
                base_url=self.base_urls.bark,
                token=self.bark_token,
                enabled=True,
            )
            self.bark_servers = [legacy_server]

        return self

    def get_token(self, channel: str) -> Optional[str]:
        """按渠道获取推送 token。"""
        channel = channel.lower()
        if channel == "wechat":
            return self.wechat_token
        if channel == "bark":
            # 返回第一个启用的 Bark 服务器的 token（向后兼容）
            for server in self.bark_servers:
                if server.enabled:
                    return server.token
            return self.bark_token
        return None

    def get_enabled_bark_servers(self) -> List[BarkServerConfig]:
        """获取所有启用的 Bark 服务器。"""
        return [s for s in self.bark_servers if s.enabled]

    def supports_channel(self, channel: str) -> bool:
        """判断指定渠道是否配置了 token。"""
        channel = channel.lower()
        if channel == "bark":
            return bool(self.get_enabled_bark_servers()) or bool(self.bark_token)
        return bool(self.get_token(channel))

    def get_category(self, category: str) -> Optional[NotificationCategoryConfig]:
        """获取指定类别的额度配置。"""
        return self.categories.get(category)

    def list_channels(self) -> List[str]:
        """列出启用的渠道。"""
        channels = []
        if self.wechat_token:
            channels.append("wechat")
        if self.get_enabled_bark_servers() or self.bark_token:
            channels.append("bark")
        return channels
