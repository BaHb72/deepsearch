"""
市场数据运行时服务模块

提供市场数据实时运行态的管理函数，包括：
- bind_market_data_handle: 绑定 orchestrator handle 到应用状态
- ensure_market_data_runtime: 确保市场数据运行态已初始化
- refresh_market_data_once: 执行一次实时刷新
- shutdown_market_data_runtime: 关闭市场数据运行态

此模块从 server.py 提取，用于解决循环导入问题。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from core.application.market_data.fallback_manager import ModuleFallbackManager
from core.config import Settings, get_config
from loguru import logger

if TYPE_CHECKING:
    from core.application.market_data.orchestrator import (
        RealtimeDataOrchestrator,
        RealtimeRuntimeHandle,
    )

    from apps.api.server import AppState

__all__ = [
    "bind_market_data_handle",
    "ensure_market_data_runtime",
    "refresh_market_data_once",
    "shutdown_market_data_runtime",
]


async def bind_market_data_handle(
    app_state: "AppState",
    orchestrator: "RealtimeDataOrchestrator",
    handle: "RealtimeRuntimeHandle",
    realtime_cfg: Any | None,
) -> None:
    """把 orchestrator handle 绑定到 app_state 并启动实时流水线。"""

    if realtime_cfg is None:
        raise RuntimeError("realtime config missing, cannot bind market data handle")

    service = handle.service
    cache_writer = handle.cache_writer
    pipeline = handle.pipeline
    runner = handle.runner
    reader = handle.cache_reader
    provider = handle.provider or getattr(handle, "adapter", None)

    app_state.market_data_service = service
    app_state.market_data_cache_writer = cache_writer
    app_state.market_data_pipeline = pipeline
    app_state.market_data_runner = runner
    app_state.market_data_reader = reader
    app_state.market_data_provider = provider
    app_state.market_data_handle = handle
    app_state.market_data_active_source = handle.adapter_name
    app_state.market_data_health = orchestrator.get_status_snapshot()

    try:
        cached_boards, _ = await reader.fetch_board_universe()
        if cached_boards:
            service.board_universe.load_snapshot(cached_boards)
            logger.debug("预热板块映射: {} 个记录", len(cached_boards))
    except Exception as exc:  # pragma: no cover - cache hydration best-effort
        logger.debug("加载缓存板块映射失败: {}", exc)

    # 在后台任务中预热 board_universe，避免阻塞启动
    async def _warmup_board_universe():
        try:
            logger.info("开始预热板块数据...")
            await asyncio.wait_for(service.refresh_board_universe(), timeout=30.0)
            try:
                await cache_writer.write_board_universe(service.board_universe.snapshot())
                logger.info(
                    "板块数据预热完成，已缓存 {} 个板块", len(service.board_universe.boards())
                )
            except Exception as cache_exc:
                logger.debug("写入板块缓存失败: {}", cache_exc)
        except asyncio.TimeoutError:
            logger.warning("板块数据预热超时（30秒），将在首次请求时重试")
        except Exception as exc:  # pragma: no cover - 初始化阶段容错
            logger.warning("刷新板块列表失败: {}", exc)

    # 启动后台预热任务
    asyncio.create_task(_warmup_board_universe())

    if getattr(realtime_cfg, "enabled", False):
        try:
            await runner.start()
            logger.info(
                "市场数据实时组件已启动，订阅板块: {}",
                ", ".join(str(board) for board in pipeline.boards),
            )
        except Exception as exc:
            logger.error("启动市场数据实时轮询失败: {}", exc)
    else:
        logger.info("市场数据实时组件已初始化，当前配置为后台轮询模式")


async def ensure_market_data_runtime(
    app_state: "AppState", settings: Settings | None = None
) -> None:
    """确保市场数据实时运行态已初始化。"""

    if getattr(app_state, "market_data_service", None) is not None:
        return
    if getattr(app_state, "market_data_initializing", False):
        return

    app_state.market_data_initializing = True
    try:
        config_obj = settings or get_config()
        market_cfg = getattr(config_obj, "market_data", None)
        if market_cfg is None:
            return

        realtime_cfg = getattr(market_cfg, "realtime", None)
        if realtime_cfg is None:
            return

        orchestrator = getattr(app_state, "market_data_orchestrator", None)
        if orchestrator is None or orchestrator.settings is not config_obj:
            from core.application.market_data.orchestrator import RealtimeDataOrchestrator

            orchestrator = RealtimeDataOrchestrator(config_obj)
            app_state.market_data_orchestrator = orchestrator

        if getattr(app_state, "market_data_fallback_manager", None) is None:
            try:
                app_state.market_data_fallback_manager = ModuleFallbackManager(config_obj)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("初始化 fallback 管理器失败: {}", exc)

        try:
            handle = await orchestrator.ensure_handle()
        except Exception as exc:
            logger.error("启动实时数据 orchestrator 失败: {}", exc)
            return

        await bind_market_data_handle(app_state, orchestrator, handle, realtime_cfg)

    finally:
        app_state.market_data_initializing = False


async def refresh_market_data_once(app_state: "AppState") -> None:
    """在后台任务停摆时执行一次实时刷新。"""
    from datetime import time as time_type
    from zoneinfo import ZoneInfo

    from core.application.market_data.trading_guard import PhaseState

    pipeline = getattr(app_state, "market_data_pipeline", None)
    if pipeline is None:
        return

    runner = getattr(app_state, "market_data_runner", None)
    runner_active = bool(
        runner and getattr(runner, "_task", None) is not None and not runner._task.done()
    )
    if runner_active:
        return

    lock = getattr(app_state, "market_data_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        app_state.market_data_lock = lock

    # 判断当前交易阶段
    def _detect_phase() -> PhaseState:
        try:
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
        except Exception:
            now = datetime.now()
        current_time = now.time()
        # A股交易时段: 9:30-11:30, 13:00-15:00
        morning_session = time_type(9, 30) <= current_time <= time_type(11, 30)
        afternoon_session = time_type(13, 0) <= current_time <= time_type(15, 0)
        if morning_session or afternoon_session:
            return PhaseState.CONTINUOUS  # 交易时段：实时模式
        return PhaseState.NO_TRADE  # 收盘后：汇总模式

    phase_state = _detect_phase()

    async with lock:
        try:
            runner_timeout = 3.0
            if runner is not None:
                runner_timeout = getattr(runner, "step_timeout_seconds", runner_timeout)
            timeout_budget = max(5.0, runner_timeout)
            await asyncio.wait_for(pipeline.run_once(phase_state), timeout=timeout_budget)
        except asyncio.TimeoutError:
            provider = getattr(app_state, "market_data_provider", None)
            branch = getattr(provider, "last_code_list_branch", None)
            security_type = getattr(provider, "last_code_list_security_type", None)
            logger.warning(
                "market data refresh timed out; serving stale cache (branch={}, security_type={})",
                branch or "unknown",
                security_type or "unknown",
            )
        except Exception as exc:
            logger.error("市场数据实时刷新失败: {}", exc)


async def shutdown_market_data_runtime(app_state: "AppState") -> None:
    """关闭市场数据实时运行态，释放资源。"""

    runner = getattr(app_state, "market_data_runner", None)
    if runner is not None:
        try:
            await runner.stop()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.debug("停止市场数据实时轮询失败: {}", exc)

    writer = getattr(app_state, "market_data_cache_writer", None)
    if writer is not None:
        try:
            await writer.close()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.debug("关闭市场数据缓存写入器失败: {}", exc)

    # 关闭底层数据源（如 AmazingData 的订阅线程），避免 SubscribeData.run 残留
    provider = getattr(app_state, "market_data_provider", None)
    if provider is not None:
        try:
            stop_coro = getattr(provider, "stop_async", None)
            if callable(stop_coro):
                await stop_coro()
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.debug("停止数据库提供器进程失败: {}", exc)

    app_state.market_data_service = None
    app_state.market_data_cache_writer = None
    app_state.market_data_pipeline = None
    app_state.market_data_runner = None
    app_state.market_data_reader = None
    app_state.market_data_provider = None
    app_state.market_data_handle = None
    app_state.market_data_active_source = None
    app_state.market_data_health = {}
    orchestrator = getattr(app_state, "market_data_orchestrator", None)
    if orchestrator is not None:
        try:
            await orchestrator.shutdown()
        except Exception as exc:  # pragma: no cover
            logger.debug("Shutdown orchestrator failed: {}", exc)
    app_state.market_data_orchestrator = None
