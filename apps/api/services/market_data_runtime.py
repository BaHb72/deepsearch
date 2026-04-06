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
from time import perf_counter
from typing import TYPE_CHECKING, Any

from core.application.market_data.fallback_manager import ModuleFallbackManager
from core.config import Settings, get_config
from core.utils.timeout import DataSourceState, get_timeout_manager
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

    # 从配置读取预热参数（作为基础值，实际超时可能根据数据源状态动态调整）
    warmup_timeout = getattr(realtime_cfg, "warmup_timeout_seconds", 90.0)
    fetch_timeout = getattr(realtime_cfg, "warmup_fetch_timeout_seconds", 60.0)
    retry_count = getattr(realtime_cfg, "warmup_retry_count", 2)
    fallback_to_cache = getattr(realtime_cfg, "warmup_fallback_to_cache", True)

    # 记录预热前的缓存状态，用于回退
    cached_board_count = len(service.board_universe.boards())

    # 在后台任务中预热 board_universe，避免阻塞启动
    async def _warmup_board_universe():
        nonlocal cached_board_count
        warmup_start = perf_counter()
        last_error: Exception | None = None
        timeout_manager = get_timeout_manager()

        def _get_dynamic_timeout() -> float:
            """根据数据源状态动态获取超时时间"""
            # 检查 akshare 和 amazingdata 的状态
            akshare_state = timeout_manager.get_state("akshare")
            amazingdata_state = timeout_manager.get_state("amazingdata")

            # 如果任一数据源正在执行批量操作或连接中，使用更长的超时
            if akshare_state == DataSourceState.BATCH_FETCHING:
                dynamic_timeout = timeout_manager.get_timeout("akshare", "batch")
                logger.debug(
                    "AkShare 正在批量获取，使用动态超时: {:.1f}s",
                    dynamic_timeout,
                )
                return max(fetch_timeout, dynamic_timeout)

            if amazingdata_state == DataSourceState.CONNECTING:
                dynamic_timeout = timeout_manager.get_timeout("amazingdata", "connect")
                logger.debug(
                    "AmazingData 正在连接，使用动态超时: {:.1f}s",
                    dynamic_timeout,
                )
                return max(fetch_timeout, dynamic_timeout)

            # 使用配置的默认超时
            return fetch_timeout

        def _get_dynamic_warmup_timeout() -> float:
            """根据数据源状态动态计算总预热超时

            当数据源正在执行耗时操作（如 SDK 登录、批量获取）时，
            自动延长总超时以避免过早中断。

            超时配置从 settings 统一读取，避免硬编码:
            - AmazingData 首次调用: data_sources.providers.amazingdata.config.first_call_timeout
            - AkShare 批量获取: 使用固定 300s（无状态服务）
            """
            # 检查数据源状态
            amazingdata_state = timeout_manager.get_state("amazingdata")
            akshare_state = timeout_manager.get_state("akshare")

            # 如果正在连接，给 SDK 登录足够时间
            # 从统一超时配置读取（Settings.timeouts.amazingdata.first_call）
            if amazingdata_state == DataSourceState.CONNECTING:
                settings = get_config()
                timeouts_cfg = getattr(settings, "timeouts", None)
                amazingdata_first_call_timeout = (
                    timeouts_cfg.amazingdata.first_call if timeouts_cfg else 90.0
                )

                dynamic_timeout = max(warmup_timeout, amazingdata_first_call_timeout)
                logger.debug(
                    "AmazingData 正在连接，总预热超时延长至: {:.1f}s (配置: {:.1f}s)",
                    dynamic_timeout,
                    amazingdata_first_call_timeout,
                )
                return dynamic_timeout

            # 如果正在批量获取，需要更长的超时（AkShare 无状态服务，使用固定值）
            if akshare_state == DataSourceState.BATCH_FETCHING:
                dynamic_timeout = max(warmup_timeout, 300.0)
                logger.debug(
                    "AkShare 正在批量获取，总预热超时延长至: {:.1f}s",
                    dynamic_timeout,
                )
                return dynamic_timeout

            # 使用配置的默认超时
            return warmup_timeout

        async def _fetch_with_retry() -> bool:
            """执行带重试的数据获取，返回是否成功"""
            nonlocal last_error
            for attempt in range(retry_count + 1):
                attempt_start = perf_counter()
                # 每次重试时重新计算动态超时
                current_timeout = _get_dynamic_timeout()
                try:
                    await asyncio.wait_for(
                        service.refresh_board_universe(), timeout=current_timeout
                    )
                    elapsed = perf_counter() - attempt_start
                    logger.info(
                        "板块数据获取成功 (第{}次尝试, 耗时 {:.2f}s)",
                        attempt + 1,
                        elapsed,
                    )
                    return True
                except asyncio.TimeoutError:
                    elapsed = perf_counter() - attempt_start
                    last_error = asyncio.TimeoutError(f"fetch timeout after {elapsed:.2f}s")
                    if attempt < retry_count:
                        logger.warning(
                            "板块数据获取超时 (第{}次尝试, {:.2f}s), 准备重试...",
                            attempt + 1,
                            elapsed,
                        )
                    else:
                        logger.warning(
                            "板块数据获取超时 (第{}次尝试, {:.2f}s), 已达最大重试次数",
                            attempt + 1,
                            elapsed,
                        )
                except Exception as exc:
                    elapsed = perf_counter() - attempt_start
                    last_error = exc
                    if attempt < retry_count:
                        logger.warning(
                            "板块数据获取失败 (第{}次尝试, {:.2f}s): {}, 准备重试...",
                            attempt + 1,
                            elapsed,
                            exc,
                        )
                    else:
                        logger.warning(
                            "板块数据获取失败 (第{}次尝试, {:.2f}s): {}, 已达最大重试次数",
                            attempt + 1,
                            elapsed,
                            exc,
                        )
            return False

        try:
            # 获取动态超时值（根据数据源状态调整）
            initial_fetch_timeout = _get_dynamic_timeout()
            dynamic_warmup_timeout = _get_dynamic_warmup_timeout()
            logger.info(
                "开始预热板块数据 (总超时: {:.1f}s (动态), 单次超时: {:.1f}s (动态), 重试次数: {})",
                dynamic_warmup_timeout,
                initial_fetch_timeout,
                retry_count,
            )

            # 在动态总超时内执行带重试的获取
            success = await asyncio.wait_for(_fetch_with_retry(), timeout=dynamic_warmup_timeout)

            total_elapsed = perf_counter() - warmup_start
            current_board_count = len(service.board_universe.boards())

            if success:
                # 成功获取，写入缓存
                try:
                    await cache_writer.write_board_universe(service.board_universe.snapshot())
                    logger.info(
                        "板块数据预热完成 (来源: 网络, 板块数: {}, 总耗时: {:.2f}s)",
                        current_board_count,
                        total_elapsed,
                    )
                except Exception as cache_exc:
                    logger.debug("写入板块缓存失败: {}", cache_exc)
                    logger.info(
                        "板块数据预热完成 (来源: 网络, 板块数: {}, 总耗时: {:.2f}s, 缓存写入失败)",
                        current_board_count,
                        total_elapsed,
                    )
            else:
                # 获取失败，检查是否可以回退到缓存
                if fallback_to_cache and cached_board_count > 0:
                    logger.warning(
                        "板块数据预热失败，回退到已有缓存 (来源: 缓存, 板块数: {}, 总耗时: {:.2f}s)",
                        cached_board_count,
                        total_elapsed,
                    )
                else:
                    logger.warning(
                        "板块数据预热失败，无可用缓存 (总耗时: {:.2f}s), 将在首次请求时重试",
                        total_elapsed,
                    )

        except asyncio.TimeoutError:
            total_elapsed = perf_counter() - warmup_start
            current_board_count = len(service.board_universe.boards())
            # 记录超时时的数据源状态，便于诊断
            amazingdata_state = timeout_manager.get_state("amazingdata")
            akshare_state = timeout_manager.get_state("akshare")
            if fallback_to_cache and current_board_count > 0:
                logger.warning(
                    "板块数据预热总超时 ({:.1f}s), 回退到已有缓存 (板块数: {}, amazingdata={}, akshare={})",
                    dynamic_warmup_timeout,
                    current_board_count,
                    amazingdata_state.value if amazingdata_state else "unknown",
                    akshare_state.value if akshare_state else "unknown",
                )
            else:
                logger.warning(
                    "板块数据预热总超时 ({:.1f}s), 无可用缓存, 将在首次请求时重试 (amazingdata={}, akshare={})",
                    dynamic_warmup_timeout,
                    amazingdata_state.value if amazingdata_state else "unknown",
                    akshare_state.value if akshare_state else "unknown",
                )
        except Exception as exc:  # pragma: no cover - 初始化阶段容错
            total_elapsed = perf_counter() - warmup_start
            logger.warning("刷新板块列表失败 (耗时: {:.2f}s): {}", total_elapsed, exc)

    # 启动后台预热任务
    asyncio.create_task(_warmup_board_universe())

    # 在 Runner 启动前预加载交易日历，避免首次轮询时 calendar 为空
    if getattr(realtime_cfg, "enabled", False):
        session_guard = getattr(runner, "session_guard", None)
        if session_guard:
            try:
                from zoneinfo import ZoneInfo

                # 触发一次 evaluate 以缓存 calendar
                timeouts_cfg = getattr(get_config(), "timeouts", None)
                cal_timeout = timeouts_cfg.amazingdata.calendar_preload if timeouts_cfg else 30.0
                await asyncio.wait_for(
                    session_guard.evaluate(
                        default_interval=1.0,
                        default_timeout=5.0,
                        now=datetime.now(ZoneInfo("Asia/Shanghai")),
                    ),
                    timeout=cal_timeout,
                )
                logger.debug("交易日历预加载完成")
            except asyncio.TimeoutError:
                logger.warning("交易日历预加载超时，Runner 将使用 fallback 模式")
            except Exception as exc:
                logger.warning("交易日历预加载失败: {}，Runner 将使用 fallback 模式", exc)

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

            # 传入 provider_container 以便 orchestrator 复用已注册的 Provider
            provider_container = getattr(app_state, "provider_container", None)
            orchestrator = RealtimeDataOrchestrator(
                config_obj, provider_container=provider_container
            )
            app_state.market_data_orchestrator = orchestrator
            backend_runtime = getattr(app_state, "backend_runtime", None)
            if backend_runtime is not None:
                backend_runtime.market_data_orchestrator = orchestrator

        if getattr(app_state, "market_data_fallback_manager", None) is None:
            try:
                provider_container = getattr(app_state, "provider_container", None)
                app_state.market_data_fallback_manager = ModuleFallbackManager(
                    config_obj,
                    orchestrator=orchestrator,
                    provider_container=provider_container,
                )
                backend_runtime = getattr(app_state, "backend_runtime", None)
                if backend_runtime is not None:
                    backend_runtime.market_data_fallback_manager = (
                        app_state.market_data_fallback_manager
                    )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("初始化 fallback 管理器失败: {}", exc)

        # Dask/AmazingData 预热由 server.lifespan 启动期负责；
        # 此处仅负责确保实时运行态句柄已绑定。

        try:
            handle = await orchestrator.ensure_handle()
        except Exception as exc:
            logger.error("启动实时数据 orchestrator 失败: {}", exc)
            return

        await bind_market_data_handle(app_state, orchestrator, handle, realtime_cfg)
        backend_runtime = getattr(app_state, "backend_runtime", None)
        if backend_runtime is not None:
            backend_runtime.market_data_service = getattr(app_state, "market_data_service", None)

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

    # 从配置读取关闭超时
    try:
        from core.config import get_config

        _shutdown = getattr(get_config(), "timeouts", None)
        _shutdown = _shutdown.shutdown if _shutdown else None
    except Exception:
        _shutdown = None

    runner = getattr(app_state, "market_data_runner", None)
    if runner is not None:
        try:
            runner_timeout = _shutdown.runner_stop if _shutdown else 5.0
            runner_outer = _shutdown.runner_stop_outer if _shutdown else 8.0
            await asyncio.wait_for(runner.stop(timeout=runner_timeout), timeout=runner_outer)
        except asyncio.TimeoutError:
            logger.warning("停止市场数据实时轮询超时")
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.debug("停止市场数据实时轮询失败: {}", exc)

    writer = getattr(app_state, "market_data_cache_writer", None)
    if writer is not None:
        try:
            writer_timeout = _shutdown.cache_writer if _shutdown else 5.0
            await asyncio.wait_for(writer.close(), timeout=writer_timeout)
        except asyncio.TimeoutError:
            logger.warning("关闭市场数据缓存写入器超时")
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.debug("关闭市场数据缓存写入器失败: {}", exc)

    # 关闭底层数据源（如 AmazingData 的订阅线程），避免 SubscribeData.run 残留
    provider = getattr(app_state, "market_data_provider", None)
    if provider is not None:
        try:
            stop_coro = getattr(provider, "stop_async", None)
            if callable(stop_coro):
                provider_timeout = _shutdown.provider_stop if _shutdown else 5.0
                await asyncio.wait_for(stop_coro(), timeout=provider_timeout)
        except asyncio.TimeoutError:
            logger.warning("停止数据源提供器超时")
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
    fallback_manager = getattr(app_state, "market_data_fallback_manager", None)
    if fallback_manager is not None:
        try:
            fallback_timeout = _shutdown.provider_stop if _shutdown else 5.0
            await asyncio.wait_for(fallback_manager.shutdown(), timeout=fallback_timeout)
        except asyncio.TimeoutError:
            logger.warning("关闭 fallback 管理器超时")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("关闭 fallback 管理器失败: {}", exc)
    app_state.market_data_fallback_manager = None
    backend_runtime = getattr(app_state, "backend_runtime", None)
    if backend_runtime is not None:
        backend_runtime.market_data_fallback_manager = None

    orchestrator = getattr(app_state, "market_data_orchestrator", None)
    if orchestrator is not None:
        try:
            await orchestrator.shutdown()
        except Exception as exc:  # pragma: no cover
            logger.debug("Shutdown orchestrator failed: {}", exc)
    app_state.market_data_orchestrator = None
