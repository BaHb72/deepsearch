"""Login workflow helpers for process-isolated AmazingData provider."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from deepsearch.infrastructure.providers.interfaces.base import DataProviderError
from deepsearch.ports.amazingdata_process import AmazingDataLoginRequest

from ..logging_utils import ProcessLoggerAdapter
from .alert_utils import trigger_alert

logger = ProcessLoggerAdapter(action="process")

if TYPE_CHECKING:
    from ..amazingdata_process_adapter import AmazingDataProcessAdapter  # noqa: F401
    from .runtime import ProcessIsolatedAmazingDataProvider  # noqa: F401


async def perform_login(
    provider: "ProcessIsolatedAmazingDataProvider",
    adapter: "AmazingDataProcessAdapter",
) -> None:
    """Execute login flow with reuse, throttling and alert handling."""
    pool = provider._pool
    login_success = False
    error_message: str | None = None
    last_exception: Exception | None = None
    performed_login = False
    lock: asyncio.Lock | None = None

    try:
        lock = await provider._acquire_global_login_lock(provider._datasource_id)
        if provider._should_reuse_recent_login():
            login_success = True
            provider._mark_connected(True)
            logger.info(
                "AmazingData login reuse datasource={} window={:.0f}s",
                provider._datasource_id,
                provider._LOGIN_DEDUP_WINDOW_SECONDS,
            )
            return

        if pool:
            await asyncio.to_thread(pool.wait_for_login_slot, provider._datasource_id)

        username = str(getattr(provider.config, "username", "") or "").strip()
        password = str(getattr(provider.config, "password", "") or "")
        if not username or username.replace("*", "").strip() == "":
            raise DataProviderError("AmazingData process requires a valid username")
        if not password:
            raise DataProviderError("AmazingData process requires a valid password")

        try:
            timeout_value = float(getattr(provider.config, "timeout", 30.0))
        except (TypeError, ValueError):
            timeout_value = 10.0

        max_attempts = 2
        api_mode_switched = False
        for attempt in range(max_attempts):
            login_request = AmazingDataLoginRequest(
                username=username,
                password=password,
                host=getattr(provider.config, "host", ""),
                port=getattr(provider.config, "port", 0),
                timeout=max(timeout_value, 5.0),
                api_mode=provider._login_api_mode,  # type: ignore[has-type]
            )
            # [TGW参数检查] 使用INFO级别确保始终可见
            tgw_params_msg = (
                f"[TGW登录参数] datasource={provider._datasource_id} "
                f"username={login_request.username!r} host={login_request.host!r} "
                f"port={login_request.port} timeout={login_request.timeout:.2f}s "
                f"api_mode={provider._login_api_mode or 'default'} "  # type: ignore[has-type]
                f"password={'***' if login_request.password else '(空)'}"
            )
            logger.info(tgw_params_msg)
            # 同时写入文件日志，避免被TUI覆盖
            try:
                from pathlib import Path

                log_dir = Path("data/logs/datasource")
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "tgw_login.log", "a", encoding="utf-8") as f:
                    from datetime import datetime

                    f.write(f"{datetime.now().isoformat()} {tgw_params_msg}\n")
            except Exception:
                pass  # 文件日志失败不影响主流程
            login_start = perf_counter()
            response = await adapter.login(login_request)
            performed_login = True
            latency = perf_counter() - login_start
            metadata_dict = dict(provider._extract_response_metadata(response) or {})
            logger.debug(
                "AmazingData login response success={} error={} error_type={} metadata={} latency={:.3f}s",
                response.success,
                response.error,
                response.error_type,
                metadata_dict,
                latency,
            )

            if response.success:
                login_success = True
                error_message = None
                provider._mark_connected(True)
                logger.info(
                    "AmazingData login succeeded datasource={} host={} port={} duration={:.3f}s api_mode={}",
                    provider._datasource_id,
                    login_request.host,
                    login_request.port,
                    latency,
                    provider._login_api_mode or "default",  # type: ignore[has-type]
                )
                break

            error_message = response.error or response.error_type or "login_failed"
            logger.warning(
                "AmazingData login failed datasource={} host={} port={} error={} error_type={} metadata={}",
                provider._datasource_id,
                login_request.host,
                login_request.port,
                error_message,
                response.error_type,
                metadata_dict,
            )

            alert_type: str | None = None
            if response.error_type == "SystemExit":
                alert_type = "SDK_EXIT"
            elif response.error_type == "ProcessCrash":
                alert_type = "PROCESS_CRASH"
            if alert_type:
                await trigger_alert(provider, alert_type, error_message or "login_failed")

            if not api_mode_switched and provider._should_switch_to_api_mode(response):
                provider._set_login_api_mode("api")
                api_mode_switched = True
                error_message = None
                logger.warning(
                    "Detected TGW push init failure, switching to api_mode=api attempt={}",
                    attempt + 1,
                )
                continue

            raise DataProviderError(f"AmazingData login failed: {error_message}")
    except Exception as exc:
        if error_message is None:
            error_message = str(exc)
        provider._mark_connected(False, error=error_message)
        last_exception = exc
    finally:
        if pool and performed_login:
            await asyncio.to_thread(
                pool.record_login_result,
                provider._datasource_id,
                login_success,
                error_message,
            )
        provider._record_login_state(provider._datasource_id, success=login_success)
        if lock is not None and lock.locked():
            lock.release()

    if not login_success:
        if last_exception is not None:
            raise last_exception
        raise DataProviderError(f"AmazingData login failed: {error_message}")


__all__ = ["perform_login"]
