"""交易时段配置加载器

独立的配置模块，从 trading_schedule.yaml 加载交易时段相关配置。
支持多市场（A股/港股/美股）不同交易时间的配置。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time as time_type
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


@dataclass(slots=True, frozen=True)
class TimeWindow:
    """时间窗口"""

    start: time_type
    end: time_type

    def contains(self, t: time_type) -> bool:
        """检查时间是否在窗口内"""
        if self.start <= self.end:
            return self.start <= t <= self.end
        # 处理跨午夜的情况（如美股）
        return t >= self.start or t <= self.end


@dataclass(slots=True)
class PhaseBehavior:
    """阶段行为配置"""

    interval_seconds: float = 1.0
    timeout_seconds: float = 3.0
    skip_polling: bool = False
    skip_windows: list[TimeWindow] = field(default_factory=list)

    def should_skip_at(self, t: time_type) -> bool:
        """检查指定时间是否应该跳过轮询"""
        if self.skip_polling:
            return True
        return any(window.contains(t) for window in self.skip_windows)


@dataclass(slots=True)
class SessionConfig:
    """交易时段配置"""

    auction_windows: list[TimeWindow] = field(default_factory=list)
    continuous_windows: list[TimeWindow] = field(default_factory=list)


@dataclass(slots=True)
class MarketConfig:
    """市场配置"""

    name: str
    enabled: bool = True
    aliases: list[str] = field(default_factory=list)
    timezone: str = "Asia/Shanghai"
    sessions: SessionConfig = field(default_factory=SessionConfig)
    phase_behavior: dict[str, PhaseBehavior] = field(default_factory=dict)


@dataclass(slots=True)
class TradingScheduleConfig:
    """交易时段总配置"""

    calendar_ttl_minutes: int = 10
    defaults: dict[str, PhaseBehavior] = field(default_factory=dict)
    markets: dict[str, MarketConfig] = field(default_factory=dict)
    _alias_map: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """构建别名映射"""
        for market_name, market_config in self.markets.items():
            self._alias_map[market_name.upper()] = market_name
            for alias in market_config.aliases:
                self._alias_map[alias.upper()] = market_name

    def get_market(self, market_or_alias: str) -> MarketConfig | None:
        """通过市场名或别名获取市场配置"""
        normalized = market_or_alias.upper()
        market_name = self._alias_map.get(normalized)
        if market_name:
            return self.markets.get(market_name)
        return None

    def get_enabled_markets(self) -> list[MarketConfig]:
        """获取所有启用的市场"""
        return [m for m in self.markets.values() if m.enabled]

    def get_phase_behavior(self, phase: str, market_or_alias: str | None = None) -> PhaseBehavior:
        """获取阶段行为配置，优先使用市场特定配置，回退到默认配置"""
        if market_or_alias:
            market = self.get_market(market_or_alias)
            if market and phase in market.phase_behavior:
                return market.phase_behavior[phase]
        return self.defaults.get(phase, PhaseBehavior())


def _parse_time(value: str) -> time_type:
    """解析时间字符串"""
    parts = value.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    return time_type(hour, minute, second)


def _parse_time_windows(raw: list[dict[str, str]] | None) -> list[TimeWindow]:
    """解析时间窗口列表"""
    if not raw:
        return []
    windows = []
    for item in raw:
        start = _parse_time(item.get("start", "00:00"))
        end = _parse_time(item.get("end", "23:59"))
        windows.append(TimeWindow(start=start, end=end))
    return windows


def _parse_phase_behavior(raw: dict[str, Any] | None) -> PhaseBehavior:
    """解析阶段行为配置"""
    if not raw:
        return PhaseBehavior()
    return PhaseBehavior(
        interval_seconds=float(raw.get("interval_seconds", 1.0)),
        timeout_seconds=float(raw.get("timeout_seconds", 3.0)),
        skip_polling=bool(raw.get("skip_polling", False)),
        skip_windows=_parse_time_windows(raw.get("skip_windows")),
    )


def _parse_session_config(raw: dict[str, Any] | None) -> SessionConfig:
    """解析交易时段配置"""
    if not raw:
        return SessionConfig()
    return SessionConfig(
        auction_windows=_parse_time_windows(raw.get("auction", {}).get("windows")),
        continuous_windows=_parse_time_windows(raw.get("continuous", {}).get("windows")),
    )


def _parse_market_config(name: str, raw: dict[str, Any]) -> MarketConfig:
    """解析市场配置"""
    phase_behavior = {}
    raw_behavior = raw.get("phase_behavior", {})
    for phase_name, phase_data in raw_behavior.items():
        phase_behavior[phase_name] = _parse_phase_behavior(phase_data)

    return MarketConfig(
        name=name,
        enabled=bool(raw.get("enabled", True)),
        aliases=list(raw.get("aliases", [])),
        timezone=str(raw.get("timezone", "Asia/Shanghai")),
        sessions=_parse_session_config(raw.get("sessions")),
        phase_behavior=phase_behavior,
    )


def load_trading_schedule_config(
    path: Path | str | None = None,
) -> TradingScheduleConfig:
    """从 YAML 文件加载交易时段配置

    Args:
        path: 配置文件路径，默认为 config/trading_schedule.yaml

    Returns:
        TradingScheduleConfig 实例
    """
    if path is None:
        path = Path(__file__).parent / "trading_schedule.yaml"
    else:
        path = Path(path)

    if not path.exists():
        logger.warning("交易时段配置文件不存在: {}, 使用默认配置", path)
        return TradingScheduleConfig()

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("加载交易时段配置失败: {} error={}", path, exc)
        return TradingScheduleConfig()

    # 解析默认行为
    defaults = {}
    raw_defaults = raw.get("defaults", {})
    for phase_name, phase_data in raw_defaults.items():
        defaults[phase_name] = _parse_phase_behavior(phase_data)

    # 解析市场配置
    markets = {}
    raw_markets = raw.get("markets", {})
    for market_name, market_data in raw_markets.items():
        markets[market_name] = _parse_market_config(market_name, market_data)

    config = TradingScheduleConfig(
        calendar_ttl_minutes=int(raw.get("calendar_ttl_minutes", 10)),
        defaults=defaults,
        markets=markets,
    )

    logger.info(
        "交易时段配置加载完成: {} 个市场, {} 个启用",
        len(markets),
        len(config.get_enabled_markets()),
    )
    return config


# 全局配置实例
_config: TradingScheduleConfig | None = None


def get_trading_schedule_config() -> TradingScheduleConfig:
    """获取全局交易时段配置实例"""
    global _config
    if _config is None:
        _config = load_trading_schedule_config()
    return _config


def reload_trading_schedule_config(
    path: Path | str | None = None,
) -> TradingScheduleConfig:
    """重新加载交易时段配置"""
    global _config
    _config = load_trading_schedule_config(path)
    return _config
