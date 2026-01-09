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
class SessionGuardConfig:
    """交易阶段判断配置"""

    enabled: bool = True
    calendar_source: str = "amazingdata"  # amazingdata, miniqmt, auto
    market: str = "SH"


@dataclass(slots=True)
class TradingScheduleConfig:
    """交易时段总配置"""

    calendar_ttl_minutes: int = 10
    session_guard: SessionGuardConfig = field(default_factory=SessionGuardConfig)
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

    # 解析 session_guard 配置
    raw_guard = raw.get("session_guard", {})
    session_guard = SessionGuardConfig(
        enabled=bool(raw_guard.get("enabled", True)),
        calendar_source=str(raw_guard.get("calendar_source", "amazingdata")).lower(),
        market=str(raw_guard.get("market", "SH")).upper(),
    )

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
        session_guard=session_guard,
        defaults=defaults,
        markets=markets,
    )

    logger.info(
        "交易时段配置加载完成: {} 个市场, {} 个启用, session_guard={}",
        len(markets),
        len(config.get_enabled_markets()),
        session_guard.enabled,
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


# ---------------------------------------------------------------------------
# 配置序列化与保存
# ---------------------------------------------------------------------------


def _time_to_str(t: time_type) -> str:
    """将 time 对象转换为字符串"""
    return t.strftime("%H:%M")


def _time_window_to_dict(window: TimeWindow) -> dict[str, str]:
    """将 TimeWindow 转换为字典"""
    return {"start": _time_to_str(window.start), "end": _time_to_str(window.end)}


def _phase_behavior_to_dict(behavior: PhaseBehavior) -> dict[str, Any]:
    """将 PhaseBehavior 转换为字典"""
    result: dict[str, Any] = {
        "interval_seconds": behavior.interval_seconds,
        "timeout_seconds": behavior.timeout_seconds,
    }
    if behavior.skip_polling:
        result["skip_polling"] = True
    if behavior.skip_windows:
        result["skip_windows"] = [_time_window_to_dict(w) for w in behavior.skip_windows]
    return result


def _session_config_to_dict(sessions: SessionConfig) -> dict[str, Any]:
    """将 SessionConfig 转换为字典"""
    result: dict[str, Any] = {}
    if sessions.auction_windows:
        result["auction"] = {"windows": [_time_window_to_dict(w) for w in sessions.auction_windows]}
    if sessions.continuous_windows:
        result["continuous"] = {
            "windows": [_time_window_to_dict(w) for w in sessions.continuous_windows]
        }
    return result


def _market_config_to_dict(market: MarketConfig) -> dict[str, Any]:
    """将 MarketConfig 转换为字典"""
    result: dict[str, Any] = {
        "enabled": market.enabled,
        "timezone": market.timezone,
    }
    if market.aliases:
        result["aliases"] = market.aliases
    sessions_dict = _session_config_to_dict(market.sessions)
    if sessions_dict:
        result["sessions"] = sessions_dict
    if market.phase_behavior:
        result["phase_behavior"] = {
            name: _phase_behavior_to_dict(behavior)
            for name, behavior in market.phase_behavior.items()
        }
    return result


def config_to_dict(config: TradingScheduleConfig) -> dict[str, Any]:
    """将 TradingScheduleConfig 转换为可序列化的字典"""
    result: dict[str, Any] = {
        "calendar_ttl_minutes": config.calendar_ttl_minutes,
        "session_guard": {
            "enabled": config.session_guard.enabled,
            "calendar_source": config.session_guard.calendar_source,
            "market": config.session_guard.market,
        },
    }
    if config.defaults:
        result["defaults"] = {
            name: _phase_behavior_to_dict(behavior) for name, behavior in config.defaults.items()
        }
    if config.markets:
        result["markets"] = {
            name: _market_config_to_dict(market) for name, market in config.markets.items()
        }
    return result


def save_trading_schedule_config(
    config: TradingScheduleConfig,
    path: Path | str | None = None,
) -> None:
    """将配置保存回 YAML 文件

    Args:
        config: 要保存的配置对象
        path: 配置文件路径，默认为 config/trading_schedule.yaml
    """
    if path is None:
        path = Path(__file__).parent / "trading_schedule.yaml"
    else:
        path = Path(path)

    config_dict = config_to_dict(config)

    # 添加文件头注释
    header = """# 交易时段配置
# 独立配置文件，管理各市场交易时段参数
#
# 设计原则：只记录交易时段，非交易时段自动跳过轮询

"""

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.dump(
                config_dict,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.info("交易时段配置已保存: {}", path)
    except Exception as exc:
        logger.error("保存交易时段配置失败: {} error={}", path, exc)
        raise


def update_phase_behavior(
    phase: str,
    interval_seconds: float | None = None,
    timeout_seconds: float | None = None,
    skip_polling: bool | None = None,
) -> TradingScheduleConfig:
    """更新指定阶段的行为配置并热重载

    Args:
        phase: 阶段名称 (continuous, auction, no_trade, off_day)
        interval_seconds: 轮询间隔（秒）
        timeout_seconds: 超时时间（秒）
        skip_polling: 是否跳过轮询

    Returns:
        更新后的配置
    """
    config = get_trading_schedule_config()

    # 获取或创建阶段配置
    current = config.defaults.get(phase, PhaseBehavior())

    # 更新字段
    new_interval = interval_seconds if interval_seconds is not None else current.interval_seconds
    new_timeout = timeout_seconds if timeout_seconds is not None else current.timeout_seconds
    new_skip = skip_polling if skip_polling is not None else current.skip_polling

    # 创建新的 PhaseBehavior
    config.defaults[phase] = PhaseBehavior(
        interval_seconds=new_interval,
        timeout_seconds=new_timeout,
        skip_polling=new_skip,
        skip_windows=current.skip_windows,
    )

    # 保存并重载
    save_trading_schedule_config(config)
    return reload_trading_schedule_config()
