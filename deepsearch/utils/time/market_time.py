"""
市场时间工具模块

提供A股市场交易时间判断和缓存策略
"""

from datetime import datetime, time
from enum import Enum
from typing import Optional


class MarketSession(Enum):
    """市场交易时段"""

    PRE_MARKET = "pre_market"  # 盘前（9:00-9:30）
    MORNING = "morning"  # 上午交易（9:30-11:30）
    LUNCH_BREAK = "lunch_break"  # 午休（11:30-13:00）
    AFTERNOON = "afternoon"  # 下午交易（13:00-15:00）
    AFTER_HOURS = "after_hours"  # 盘后（15:00-15:30）
    CLOSED = "closed"  # 收盘（其他时间）


class MarketTimeUtil:
    """市场时间工具类"""

    # A股交易时间定义
    PRE_MARKET_START = time(9, 0)
    MORNING_START = time(9, 30)
    MORNING_END = time(11, 30)
    AFTERNOON_START = time(13, 0)
    AFTERNOON_END = time(15, 0)
    AFTER_HOURS_END = time(15, 30)

    @classmethod
    def get_current_session(cls, dt: Optional[datetime] = None) -> MarketSession:
        """
        获取当前市场交易时段

        Args:
            dt: 指定时间，默认为当前时间

        Returns:
            当前市场时段
        """
        if dt is None:
            dt = datetime.now()

        # 检查是否为周末
        if dt.weekday() >= 5:  # 周六或周日
            return MarketSession.CLOSED

        current_time = dt.time()

        # 判断时段
        if current_time < cls.PRE_MARKET_START:
            return MarketSession.CLOSED
        elif current_time < cls.MORNING_START:
            return MarketSession.PRE_MARKET
        elif current_time < cls.MORNING_END:
            return MarketSession.MORNING
        elif current_time < cls.AFTERNOON_START:
            return MarketSession.LUNCH_BREAK
        elif current_time < cls.AFTERNOON_END:
            return MarketSession.AFTERNOON
        elif current_time < cls.AFTER_HOURS_END:
            return MarketSession.AFTER_HOURS
        else:
            return MarketSession.CLOSED

    @classmethod
    def is_trading_time(cls, dt: Optional[datetime] = None) -> bool:
        """
        判断是否为交易时间

        Args:
            dt: 指定时间，默认为当前时间

        Returns:
            是否为交易时间
        """
        session = cls.get_current_session(dt)
        return session in [MarketSession.MORNING, MarketSession.AFTERNOON]

    @classmethod
    def is_market_open(cls, dt: Optional[datetime] = None) -> bool:
        """
        判断市场是否开放（包括盘前盘后）

        Args:
            dt: 指定时间，默认为当前时间

        Returns:
            市场是否开放
        """
        session = cls.get_current_session(dt)
        return session != MarketSession.CLOSED

    @classmethod
    def get_cache_ttl(cls, data_type: str, dt: Optional[datetime] = None) -> int:
        """
        根据数据类型和市场状态获取缓存TTL

        Args:
            data_type: 数据类型（realtime/minute/daily/info）
            dt: 指定时间，默认为当前时间

        Returns:
            缓存TTL（秒）
        """
        session = cls.get_current_session(dt)

        # 定义不同时段的缓存策略
        cache_config = {
            MarketSession.PRE_MARKET: {
                "realtime": 5,  # 盘前实时数据缓存短
                "minute": 60,  # 分钟数据
                "daily": 300,  # 日线数据
                "info": 3600,  # 基础信息
            },
            MarketSession.MORNING: {
                "realtime": 3,  # 交易时段实时数据缓存最短
                "minute": 30,  # 分钟数据缓存短
                "daily": 180,  # 日线数据
                "info": 3600,  # 基础信息不变
            },
            MarketSession.LUNCH_BREAK: {
                "realtime": 30,  # 午休期间实时数据缓存稍长
                "minute": 120,  # 分钟数据
                "daily": 600,  # 日线数据
                "info": 3600,  # 基础信息
            },
            MarketSession.AFTERNOON: {
                "realtime": 3,  # 下午交易时段同上午
                "minute": 30,
                "daily": 180,
                "info": 3600,
            },
            MarketSession.AFTER_HOURS: {
                "realtime": 10,  # 盘后数据缓存稍长
                "minute": 60,
                "daily": 300,
                "info": 3600,
            },
            MarketSession.CLOSED: {
                "realtime": 60,  # 收盘后实时数据缓存长
                "minute": 300,  # 分钟数据缓存长
                "daily": 3600,  # 日线数据缓存很长
                "info": 7200,  # 基础信息缓存更长
            },
        }

        # 获取对应时段的缓存配置
        session_config = cache_config.get(session, cache_config[MarketSession.CLOSED])

        # 返回对应数据类型的TTL，默认60秒
        return session_config.get(data_type, 60)

    @classmethod
    def get_request_priority(cls, data_type: str, dt: Optional[datetime] = None) -> int:
        """
        根据数据类型和市场状态获取请求优先级

        Args:
            data_type: 数据类型
            dt: 指定时间

        Returns:
            优先级（1-10，数字越小优先级越高）
        """
        session = cls.get_current_session(dt)

        # 交易时段优先级配置
        if session in [MarketSession.MORNING, MarketSession.AFTERNOON]:
            priority_map = {
                "realtime": 1,  # 实时数据最高优先级
                "orderbook": 1,  # 盘口数据同样高优先级
                "minute": 3,
                "daily": 5,
                "info": 8,
            }
        elif session == MarketSession.PRE_MARKET:
            priority_map = {
                "realtime": 2,
                "orderbook": 2,
                "minute": 4,
                "daily": 4,  # 盘前日线数据也重要
                "info": 6,
            }
        else:
            # 非交易时段
            priority_map = {
                "realtime": 5,
                "orderbook": 5,
                "minute": 6,
                "daily": 3,  # 非交易时段日线数据优先级反而高
                "info": 4,
            }

        return priority_map.get(data_type, 5)

    @classmethod
    def should_prefetch(cls, dt: Optional[datetime] = None) -> bool:
        """
        判断是否应该进行数据预取

        Args:
            dt: 指定时间

        Returns:
            是否应该预取
        """
        if dt is None:
            dt = datetime.now()

        # 在以下时间段进行预取：
        # 1. 早上8:30-9:00（盘前准备）
        # 2. 中午12:30-13:00（午休准备）
        # 3. 凌晨2:00-3:00（夜间维护）

        current_time = dt.time()

        prefetch_windows = [
            (time(8, 30), time(9, 0)),
            (time(12, 30), time(13, 0)),
            (time(2, 0), time(3, 0)),
        ]

        for start, end in prefetch_windows:
            if start <= current_time <= end:
                return True

        return False

    @classmethod
    def get_rate_limit(cls, data_type: str, dt: Optional[datetime] = None) -> float:
        """
        根据数据类型和市场状态获取速率限制

        Args:
            data_type: 数据类型
            dt: 指定时间

        Returns:
            每秒允许的请求数
        """
        session = cls.get_current_session(dt)

        # 交易时段允许更高的请求频率
        if session in [MarketSession.MORNING, MarketSession.AFTERNOON]:
            rate_limits = {
                "realtime": 30.0,  # 实时数据允许高频请求
                "orderbook": 20.0,  # 盘口数据
                "minute": 10.0,  # 分钟数据
                "daily": 5.0,  # 日线数据
                "info": 2.0,  # 基础信息
            }
        elif session in [MarketSession.PRE_MARKET, MarketSession.AFTER_HOURS]:
            rate_limits = {
                "realtime": 15.0,
                "orderbook": 10.0,
                "minute": 5.0,
                "daily": 3.0,
                "info": 2.0,
            }
        else:
            # 非交易时段限制更严格
            rate_limits = {
                "realtime": 5.0,
                "orderbook": 3.0,
                "minute": 2.0,
                "daily": 2.0,
                "info": 1.0,
            }

        return rate_limits.get(data_type, 5.0)
