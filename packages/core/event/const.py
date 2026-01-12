"""
Event type constants for the DeepSearch event system.
"""

from __future__ import annotations

# ==============================================================================
# System Internal Event Types
# ==============================================================================

EVENT_SYSTEM_EXIT: str = "_SYSTEM_EXIT_"  # 系统退出事件
EVENT_SYSTEM_READY: str = "_SYSTEM_READY_"  # 系统准备就绪事件

# ==============================================================================
# Trading Event Types
# ==============================================================================

# Market Data Events
EVENT_TICK: str = "TICK"  # 行情 Tick

# Trading Events
EVENT_ORDER: str = "ORDER"  # 订单状态
EVENT_TRADE: str = "TRADE"  # 成交回报

# System Events
EVENT_TIMER: str = "TIMER"  # 系统计时器
EVENT_ERROR: str = "ERROR"  # 错误信息
EVENT_LOG: str = "LOG"  # 日志事件

# ==============================================================================
# Strategy Event Types
# ==============================================================================

# Strategy lifecycle events
EVENT_STRATEGY_STARTED: str = "STRATEGY_STARTED"  # 策略启动
EVENT_STRATEGY_STOPPED: str = "STRATEGY_STOPPED"  # 策略停止
EVENT_STRATEGY_PAUSED: str = "STRATEGY_PAUSED"  # 策略暂停
EVENT_STRATEGY_RESUMED: str = "STRATEGY_RESUMED"  # 策略恢复

# Strategy signal events
EVENT_STRATEGY_SIGNAL: str = "STRATEGY_SIGNAL"  # 策略信号
EVENT_STRATEGY_ORDER_SUBMIT: str = "STRATEGY_ORDER_SUBMIT"  # 策略提交订单
EVENT_STRATEGY_ORDER_CANCEL: str = "STRATEGY_ORDER_CANCEL"  # 策略取消订单

# Strategy performance events
EVENT_STRATEGY_PERFORMANCE: str = "STRATEGY_PERFORMANCE"  # 策略性能更新

# ==============================================================================
# Reserved Event Types (Not Yet Implemented)
# ==============================================================================

EVENT_ACCOUNT: str = "ACCOUNT"  # 账户信息
EVENT_POSITION: str = "POSITION"  # 持仓信息

# ==============================================================================
# Module Summary
# ==============================================================================
"""
This module defines all event type constants used in the DeepSearch event system.

Event Categories:
1. System Internal Events:
   - EVENT_SYSTEM_EXIT: Used for graceful system shutdown

2. Trading Events:
   - EVENT_TICK: Market tick data
   - EVENT_ORDER: Order status updates
   - EVENT_TRADE: Trade execution reports

3. System Events:
   - EVENT_TIMER: Timer events for scheduled tasks
   - EVENT_ERROR: Error notifications
   - EVENT_LOG: Log events for system monitoring

Usage:
    from core.event.const import EVENT_TICK, EVENT_ORDER

    # Publish a tick event
    event = Event(EVENT_TICK, tick_data)
    message_bus.publish(EVENT_TICK, event)
"""
