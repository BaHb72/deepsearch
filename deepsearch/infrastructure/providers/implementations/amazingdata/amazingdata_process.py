# encoding:utf-8
"""
AmazingData Provider - 子进程隔离实现。

通过 multiprocessing 子进程托管 AmazingData SDK，防止 SDK 异常影响主进程。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar

import pandas as pd
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
    normalize_stock_records,
    _normalize_date_to_int,
    _coalesce,
    _ensure_float,
    _ensure_int,
)
from .amazingdata_process_adapter import AmazingDataProcessAdapter
from .amazingdata_process_pool import AmazingDataProcessPool, get_global_pool
from .amazingdata_types import AmazingDataSecurityType

TResult = TypeVar("TResult")

DEFAULT_HIST_CODE_LIST_START = 20130101
DEFAULT_LOCAL_DATA_PATH = "D://AmazingData_local_data//"

_SECURITY_VALUE_LOOKUP: Dict[str, str] = {
    item.value.lower(): item.value for item in AmazingDataSecurityType
}
_SECURITY_NAME_LOOKUP: Dict[str, str] = {
    item.name.lower(): item.value for item in AmazingDataSecurityType
}
_SECURITY_ALIAS: Dict[str, str] = {
    "EXTRA__FUTURE": AmazingDataSecurityType.FUTURE.value,
    "EXTRA__STOCK_A": AmazingDataSecurityType.STOCK_A.value,
    "STOCK_A_SHSZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
    "STOCK_A_SH_SZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
    "A_SH_SZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
}


def _normalize_security_type_value(value: object | None) -> str:
    """��Ϊ AmazingData SDK ������֤ȯ���͡�"""
    default_value = AmazingDataSecurityType.STOCK_A_SH_SZ.value
    if value is None:
        return default_value

    text = str(value).strip()
    if not text:
        return default_value

    normalized = text.upper().replace("-", "_").replace(" ", "")
    alias = _SECURITY_ALIAS.get(normalized)
    if alias:
        return alias

    lowered = normalized.lower()
    if lowered in _SECURITY_VALUE_LOOKUP:
        return _SECURITY_VALUE_LOOKUP[lowered]
    if lowered in _SECURITY_NAME_LOOKUP:
        return _SECURITY_NAME_LOOKUP[lowered]
    if text in _SECURITY_VALUE_LOOKUP.values():
        return text

    logger.debug("AmazingData security_type %s 未命中映射，保持原值", text)
    return text


def _resolve_local_cache_path(config: AmazingDataConfig, candidate: object | None) -> str:
    """����ʹ�õı��ر켣·����Ҫʱʹ��Ĭ��·����"""
    for item in (
            candidate,
            getattr(config, "local_path", None),
            config.config.get("local_path"),
            config.config.get("local_cache_path"),
    ):
        if not item:
            continue
        text = str(item).strip()
        if text:
            return text
    return DEFAULT_LOCAL_DATA_PATH


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
        self._connected: bool = False
        self._connected_since: datetime | None = None
        self._last_disconnect_at: datetime | None = None
        self._last_error: str | None = None
        self._last_health_status: Dict[str, Any] | None = None

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

    def _mark_connected(self, value: bool, *, error: str | None = None) -> None:
        previous_state = self._connected
        self._connected = value
        now = datetime.now(timezone.utc)
        if value:
            if not previous_state:
                self._connected_since = now
            if error:
                self._last_error = error
            else:
                self._last_error = None
        else:
            if previous_state:
                self._last_disconnect_at = now
            if error:
                self._last_error = error

    def update_health_status(self, payload: Dict[str, Any] | None) -> None:
        self._last_health_status = dict(payload) if payload else None

    def connection_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "connected_since": self._format_dt(self._connected_since),
            "last_disconnect_at": self._format_dt(self._last_disconnect_at),
            "last_error": self._last_error,
            "health": self._last_health_status or {},
        }

    @staticmethod
    def _format_dt(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

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
            self._mark_connected(True)
        except Exception as exc:
            if error_message is None:
                error_message = str(exc)
            self._mark_connected(False, error=error_message)
            raise
        finally:
            if pool:
                await asyncio.to_thread(
                    pool.record_login_result,
                    self._datasource_id,
                    login_success,
                    error_message,
                )

    def _reset_connection_state(self, *, drop_adapter: bool = False, reason: str | None = None) -> None:
        if reason:
            logger.warning(f"AmazingData process provider will reset connection due to: {reason}")
        self._initialized = False
        self._mark_connected(False, error=reason)
        if drop_adapter:
            self._adapter = None

    @staticmethod
    def _classify_recoverable_error(message: str) -> tuple[bool, bool]:
        lowered = message.lower()
        drop_adapter_tokens = (
            "worker process crashed",
            "process died",
            "broken pipe",
            "connection reset",
            "eoferror",
        )
        retry_tokens = drop_adapter_tokens + (
            "nonetype object is not subscriptable",
            "session expired",
            "channel closed",
        )

        for token in drop_adapter_tokens:
            if token in lowered:
                return True, True
        for token in retry_tokens:
            if token in lowered:
                return True, False
        return False, False
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
        last_error: DataProviderError | None = None
        for attempt in range(2):
            adapter = await self._ensure_ready()
            result = await adapter.execute(command)
            if result.success:
                return result.result

            message = result.error or result.error_type or "�ӽ���ִ��ʧ��"
            error = DataProviderError(message)
            recoverable, drop_adapter = self._classify_recoverable_error(message)
            if recoverable and attempt == 0:
                self._reset_connection_state(drop_adapter=drop_adapter, reason=message)
                last_error = error
                continue
            self._mark_connected(False, error=message)
            raise error

        assert last_error is not None
        self._mark_connected(False, error=str(last_error))
        raise last_error

    async def initialize(self) -> bool:
        await self._ensure_ready()
        return True

    def is_connected(self) -> bool:
        return self._connected and self._initialized

    async def get_stock_list(
        self,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        config_section = self.config.config if isinstance(self.config.config, Mapping) else {}
        requested_security_type = (
                kwargs.get("security_type")
                or getattr(self.config, "security_type", None)
                or config_section.get("security_type")
        )
        normalized_security_type = _normalize_security_type_value(requested_security_type)

        security_type_candidates: list[str] = []
        for candidate in (
                normalized_security_type,
                AmazingDataSecurityType.STOCK_A_SH_SZ.value,
                AmazingDataSecurityType.STOCK_A.value,
        ):
            if candidate and candidate not in security_type_candidates:
                security_type_candidates.append(candidate)

        raw_result: Any | None = None
        last_error: DataProviderError | None = None
        for candidate in security_type_candidates:
            command = ProcessCommand[Any](
                method="BaseData.get_code_list",
                kwargs={"security_type": candidate},
                alt_methods=("BaseData.get_code_info", "BaseData.get_stock_list"),
                kwargs_patches=(
                    {},
                    {"__remove__": ("security_type",)},
                ),
            )
            try:
                raw_result = await self._execute(command)
                break
            except DataProviderError as exc:
                last_error = exc
                logger.warning(f"BaseData.get_code_list({candidate}) 调用失败: {exc}")
        else:
            raw_result = None

        if raw_result is None:
            hist_security_type = security_type_candidates[0] if security_type_candidates else normalized_security_type
            fallback_start = _normalize_date_to_int(kwargs.get("start_date")) or DEFAULT_HIST_CODE_LIST_START
            fallback_end = _normalize_date_to_int(kwargs.get("end_date"))
            if fallback_end is None:
                fallback_end = int(datetime.now().strftime("%Y%m%d"))
            if fallback_end < fallback_start:
                fallback_start, fallback_end = fallback_end, fallback_start

            local_path = _resolve_local_cache_path(self.config, kwargs.get("local_path"))
            try:
                Path(local_path).mkdir(parents=True, exist_ok=True)
            except Exception as path_exc:  # pragma: no cover - 环境依赖
                logger.debug(f"创建本地缓存目录 {local_path} 失败: {path_exc}")

            fallback_params: Dict[str, object] = {
                "security_type": hist_security_type,
                "start_date": fallback_start,
                "end_date": fallback_end,
                "local_path": local_path,
                "is_local": False,
            }

            fallback_command = ProcessCommand[Any](
                method="BaseData.get_hist_code_list",
                kwargs=fallback_params,
            )
            logger.info(
                (
                    f"回退调用 BaseData.get_hist_code_list，参数 "
                    f"security_type={hist_security_type} start={fallback_start} "
                    f"end={fallback_end} local_path={local_path} is_local=False"
                )
            )
            try:
                raw_result = await self._execute(fallback_command)
            except DataProviderError as fallback_exc:
                fallback_message = str(fallback_exc)
                if "unexpected keyword argument 'is_local'" in fallback_message:
                    logger.info("BaseData.get_hist_code_list 不支持 is_local 参数，使用兼容模式调用")
                    compat_params = dict(fallback_params)
                    compat_params.pop("is_local", None)
                    compat_command = ProcessCommand[Any](
                        method="BaseData.get_hist_code_list",
                        kwargs=compat_params,
                    )
                    try:
                        raw_result = await self._execute(compat_command)
                    except DataProviderError as compat_exc:
                        if last_error is not None:
                            combined = f"{last_error}; BaseData.get_hist_code_list fallback failed: {compat_exc}"
                            raise DataProviderError(combined) from compat_exc
                        raise
                else:
                    if last_error is not None:
                        combined = f"{last_error}; BaseData.get_hist_code_list fallback failed: {fallback_exc}"
                        raise DataProviderError(combined) from fallback_exc
                    raise

        records = normalize_stock_records(raw_result)
        if not records:
            return None

        if limit and limit > 0:
            records = records[:limit]
        return records

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        begin_date_value = _normalize_date_to_int(start_date)
        end_date_value = _normalize_date_to_int(end_date)
        adjust_value = kwargs.get("adjust", "none")

        base_kwargs: Dict[str, object] = {}
        if begin_date_value is not None:
            base_kwargs["begin_date"] = begin_date_value
        if end_date_value is not None:
            base_kwargs["end_date"] = end_date_value
        if period:
            base_kwargs["period"] = period
        if adjust_value is not None:
            base_kwargs["adjust"] = adjust_value
        legacy_arg_tuple = ([symbol], period, start_date or "", end_date or "", limit, adjust_value, True)

        command = ProcessCommand[Any](
            method="MarketData.query_kline",
            args=([symbol],),
            kwargs=base_kwargs,
            alt_methods=("MarketData.get_kline_data",),
            alt_args=(legacy_arg_tuple,),
            kwargs_patches=(
                {"__remove__": tuple(base_kwargs.keys())},
            ),
        )

        raw_result = await self._execute(command)
        if not raw_result:
            return None

        records: list[Dict[str, Any]] = []
        if isinstance(raw_result, Mapping):
            payload = raw_result.get(symbol) or raw_result.get(symbol.upper())
            if isinstance(payload, pd.DataFrame):
                df_payload = payload.copy()
                if df_payload.index.name and df_payload.index.name not in df_payload.columns:
                    df_payload = df_payload.reset_index()
                else:
                    df_payload = df_payload.reset_index(drop=True)
                records = [dict(row) for row in df_payload.to_dict("records")]
            elif isinstance(payload, Sequence):
                for entry in payload:
                    if isinstance(entry, Mapping):
                        records.append(dict(entry))
        elif isinstance(raw_result, Sequence):
            for entry in raw_result:
                if isinstance(entry, Mapping):
                    records.append(dict(entry))

        if not records:
            return None

        if limit and limit > 0:
            records = records[:limit]
        return records

    async def get_realtime_quote(
        self,
        symbol: str,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        today = int(datetime.now().strftime("%Y%m%d"))
        command = ProcessCommand[Any](
            method="MarketData.query_snapshot",
            args=([symbol],),
            kwargs={"begin_date": today, "end_date": today},
            alt_methods=("MarketData.get_snapshot",),
            alt_args=(([symbol],),),
            kwargs_patches=({"__remove__": ("begin_date", "end_date")},),
        )
        raw_result = await self._execute(command)
        if not raw_result:
            return None

        def _extract_row(payload: Any) -> Dict[str, Any] | None:
            if isinstance(payload, pd.DataFrame):
                if payload.empty:
                    return None
                frame = payload.copy()
                if frame.index.name and frame.index.name not in frame.columns:
                    frame = frame.reset_index()
                else:
                    frame = frame.reset_index(drop=True)
                return dict(frame.iloc[-1])
            if isinstance(payload, Mapping):
                return dict(payload)
            if isinstance(payload, Sequence) and payload and isinstance(payload[-1], Mapping):
                return dict(payload[-1])
            return None

        payload = None
        if isinstance(raw_result, Mapping):
            payload = raw_result.get(symbol) or raw_result.get(symbol.upper())
        elif isinstance(raw_result, Sequence):
            for entry in raw_result:
                if isinstance(entry, Mapping):
                    code = entry.get("code") or entry.get("symbol")
                    if code and code == symbol:
                        payload = entry
                        break
            if payload is None and raw_result:
                payload = raw_result[0]

        row = _extract_row(payload)
        if row is None:
            return None

        name = _coalesce(row.get("name"), row.get("SECURITY_NAME"), row.get("security_name"), "")
        last_value = _coalesce(row.get("last"), row.get("close"), row.get("last_price"), row.get("price"))
        open_value = _coalesce(row.get("open"), row.get("open_price"))
        high_value = row.get("high")
        low_value = row.get("low")
        prev_close = _coalesce(row.get("prev_close"), row.get("pre_close"))
        volume_value = row.get("volume")
        amount_value = row.get("amount")
        bid_price = _coalesce(row.get("bid_price1"), row.get("bid1"))
        ask_price = _coalesce(row.get("ask_price1"), row.get("ask1"))
        bid_volume = _coalesce(row.get("bid_volume1"), row.get("bid1_volume"))
        ask_volume = _coalesce(row.get("ask_volume1"), row.get("ask1_volume"))
        change_value = _coalesce(row.get("change"), row.get("price_change"))
        change_percent = _coalesce(row.get("change_percent"), row.get("chg"))
        trade_time_raw = _coalesce(row.get("trade_time"), row.get("time"))
        if isinstance(trade_time_raw, datetime):
            trade_time = trade_time_raw.isoformat()
        else:
            trade_time = str(trade_time_raw or "")
        status_value = _coalesce(row.get("status"), row.get("trading_phase_code"), "")

        return {
            "code": symbol,
            "symbol": symbol,
            "name": str(name),
            "last": _ensure_float(last_value),
            "open": _ensure_float(open_value),
            "high": _ensure_float(high_value),
            "low": _ensure_float(low_value),
            "close": _ensure_float(prev_close),
            "volume": _ensure_float(volume_value),
            "amount": _ensure_float(amount_value),
            "bid1": _ensure_float(bid_price),
            "ask1": _ensure_float(ask_price),
            "bid1_volume": _ensure_int(bid_volume),
            "ask1_volume": _ensure_int(ask_volume),
            "change": _ensure_float(change_value),
            "change_percent": _ensure_float(change_percent),
            "time": trade_time,
            "status": str(status_value or ""),
        }

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
        self._mark_connected(False)
