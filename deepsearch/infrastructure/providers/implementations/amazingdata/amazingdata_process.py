# encoding:utf-8
"""
AmazingData Provider - 子进程隔离实现。

通过 multiprocessing 子进程托管 AmazingData SDK，防止 SDK 异常影响主进程。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, Dict, Optional, TypeVar

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderError,
)
from deepsearch.ports.amazingdata_process import (
    AmazingDataLoginRequest,
    AmazingDataLogoutRequest,
    ProcessCommand,
)
from .amazingdata import (
    AmazingDataConfig,
    ProviderConfigLike,
    ensure_amazingdata_provider_config,
)
from .amazingdata_process_adapter import AmazingDataProcessAdapter
from .amazingdata_process_pool import AmazingDataProcessPool, get_global_pool

TResult = TypeVar("TResult")


class ProcessIsolatedAmazingDataProvider(DataProvider):
    """基于子进程代理的 AmazingData 数据提供者。"""

    def __init__(self, config: ProviderConfigLike) -> None:
        provider_config = ensure_amazingdata_provider_config(config)
        super().__init__(provider_config)
        self.config: AmazingDataConfig = provider_config
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._pool: AmazingDataProcessPool | None = None
        self._adapter: AmazingDataProcessAdapter | None = None
        self._datasource_id = self._build_datasource_id()
        self._proxy_config = self._build_proxy_config()

    def _build_datasource_id(self) -> str:
        username = getattr(self.config, "username", "") or "anonymous"
        host = getattr(self.config, "host", "") or "unknown"
        port = getattr(self.config, "port", 0)
        return f"amazingdata::{username}@{host}:{port}"

    def _build_proxy_config(self) -> Dict[str, Any]:
        proxy_config: Dict[str, Any] = {}
        python_candidate = (
            getattr(self.config, "python_interpreter_path", "")
            or self.config.config.get("python_interpreter_path")
        )
        python_path = str(python_candidate or "").strip()
        if python_path:
            proxy_config["python_executable"] = python_path
        worker_env = getattr(self.config, "worker_env", None)
        if worker_env:
            proxy_config["worker_env"] = dict(worker_env)
        try:
            timeout_value = float(getattr(self.config, "timeout", 30.0))
        except (TypeError, ValueError):
            timeout_value = 10.0
        proxy_config["startup_timeout"] = max(timeout_value, 5.0)
        return proxy_config

    async def _ensure_adapter(self) -> AmazingDataProcessAdapter:
        if self._adapter is not None:
            return self._adapter

        pool = get_global_pool()
        try:
            proxy = await asyncio.to_thread(
                pool.get_or_create,
                self._datasource_id,
                False,
                300.0,
                dict(self._proxy_config),
            )
        except Exception as exc:  # pragma: no cover - 极端异常用于日志观测
            logger.error(f"AmazingData 子进程获取失败: {exc}")
            raise DataProviderError(f"AmazingData 子进程获取失败: {exc}") from exc

        self._pool = pool
        self._adapter = AmazingDataProcessAdapter(proxy)
        return self._adapter

    async def _perform_login(self, adapter: AmazingDataProcessAdapter) -> None:
        pool = self._pool
        login_success = False
        error_message: str | None = None
        if pool:
            await asyncio.to_thread(pool.wait_for_login_slot, self._datasource_id)
        try:
            username = str(getattr(self.config, "username", "") or "").strip()
            password = str(getattr(self.config, "password", "") or "")
            if not username or username.replace("*", "").strip() == "":
                raise DataProviderError("AmazingData 进程模式缺少有效的用户名配置")
            if not password:
                raise DataProviderError("AmazingData 进程模式缺少有效的密码配置")
            try:
                timeout_value = float(getattr(self.config, "timeout", 30.0))
            except (TypeError, ValueError):
                timeout_value = 10.0
            login_request = AmazingDataLoginRequest(
                username=username,
                password=password,
                host=getattr(self.config, "host", ""),
                port=getattr(self.config, "port", 0),
                timeout=max(timeout_value, 5.0),
            )
            response = await adapter.login(login_request)
            login_success = response.success
            if not response.success:
                error_message = response.error or response.error_type or "login_failed"
                raise DataProviderError(f"AmazingData 登录失败: {error_message}")
        except Exception as exc:
            if error_message is None:
                error_message = str(exc)
            raise
        finally:
            if pool:
                await asyncio.to_thread(
                    pool.record_login_result,
                    self._datasource_id,
                    login_success,
                    error_message,
                )
    async def _ensure_ready(self) -> AmazingDataProcessAdapter:
        adapter = await self._ensure_adapter()
        if self._initialized:
            return adapter

        async with self._init_lock:
            if self._initialized:
                return adapter

            started = await adapter.ensure_started()
            if not started:
                raise DataProviderError("AmazingData 子进程启动失败")

            await self._perform_login(adapter)
            self._initialized = True

        return adapter

    async def _execute(self, command: ProcessCommand[TResult]) -> Optional[TResult]:
        adapter = await self._ensure_ready()
        result = await adapter.execute(command)
        if not result.success:
            message = result.error or result.error_type or "子进程执行失败"
            raise DataProviderError(message)
        return result.result

    async def initialize(self) -> bool:
        await self._ensure_ready()
        return True

    async def get_stock_list(
        self,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        command = ProcessCommand[list[Dict[str, Any]]](
            method="query_api.get_stock_list",
        )
        raw_result = await self._execute(command)
        if not raw_result:
            return None

        items: list[Dict[str, Any]] = []
        for entry in raw_result:
            if isinstance(entry, Mapping):
                items.append(dict(entry))

        if limit and limit > 0:
            items = items[:limit]
        return items

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        args = (
            symbol,
            start_date or "",
            end_date or "",
            period,
        )
        payload_kwargs: Dict[str, object] = {}
        adjust = kwargs.get("adjust")
        if adjust is not None:
            payload_kwargs["adjust"] = adjust

        command = ProcessCommand[list[Dict[str, Any]]](
            method="query_api.get_kline_data",
            args=args,
            kwargs=payload_kwargs,
        )

        raw_result = await self._execute(command)
        if not raw_result:
            return None

        records: list[Dict[str, Any]] = []
        for entry in raw_result:
            if isinstance(entry, Mapping):
                records.append(dict(entry))

        if limit and limit > 0:
            records = records[:limit]
        return records

    async def get_realtime_quote(
        self,
        symbol: str,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        command = ProcessCommand[list[Dict[str, Any]]](
            method="query_api.get_realtime_quotes",
            args=([symbol],),
        )
        raw_result = await self._execute(command)
        if not raw_result:
            return None

        if isinstance(raw_result, Sequence):
            for entry in raw_result:
                if isinstance(entry, Mapping):
                    return dict(entry)
        return None

    async def subscribe(
        self,
        symbols: list[str],
        callback: Any,
        data_type: str = "realtime",
        **kwargs: Any,
    ) -> bool:
        raise DataProviderError("AmazingData process 模式暂未开放 subscribe 功能")

    async def unsubscribe(
        self,
        symbols: list[str],
        data_type: str = "realtime",
        **kwargs: Any,
    ) -> bool:
        raise DataProviderError("AmazingData process 模式暂未开放 unsubscribe 功能")

    async def close(self) -> None:
        adapter = self._adapter
        if adapter:
            try:
                await adapter.logout(
                    AmazingDataLogoutRequest(username=getattr(self.config, "username", None))
                )
            except Exception as exc:  # pragma: no cover - 仅记录日志
                logger.warning(f"AmazingData 子进程注销异常: {exc}")

        if self._pool:
            try:
                await asyncio.to_thread(
                    self._pool.stop,
                    self._datasource_id,
                    False,
                    False,
                )
            except Exception as exc:  # pragma: no cover - 仅记录日志
                logger.warning(f"AmazingData 子进程停止异常: {exc}")

        self._adapter = None
        self._pool = None
        self._initialized = False
