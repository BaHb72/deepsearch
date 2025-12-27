"""Low-level utilities shared by AmazingData provider implementations."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, ParamSpec, Sequence, TypeVar

import pandas as pd

from deepsearch.infrastructure.providers.interfaces.base import DataProviderError

from .common import (
    BOARD_FIELD_CANDIDATES,
    DEFAULT_HIST_CODE_LIST_START,
    get_default_local_data_path,
)
from .logging_utils import log_debug, log_error, log_info, log_warning
from .param_guards import CacheParamMode, CachePolicy
from .types import AmazingDataSDKProtocol


class _RetryStrategy:
    """Simple exponential-backoff retry strategy."""

    def __init__(
        self, max_attempts: int, backoff_base: float, max_delay: float, jitter: bool
    ) -> None:
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.max_delay = max_delay
        self.jitter = jitter

    def delays(self) -> list[float]:
        delays: list[float] = []
        for attempt in range(self.max_attempts - 1):
            delay = min(self.backoff_base**attempt, self.max_delay)
            if self.jitter:
                delay += random.uniform(0, 1)
            delays.append(delay)
        return delays


def build_retry_strategy(
    *,
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> _RetryStrategy:
    """Factory for retry animations used in async_retry and future backoff logic."""
    return _RetryStrategy(max_attempts, backoff_base, max_delay, jitter)


def _coalesce(*values: object | None) -> object | None:
    """��˳�򷵻��׸���Чֵ�����⽫��ֵ�򲼶���ֵ��Ϊȱʧ."""

    if not values:
        return None

    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value

    return None


def _ensure_float(value: object | None, default: float = 0.0) -> float:
    """���������ת��Ϊ float��ʧ��ʱ����Ĭ��ֵ."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return float(stripped)
        except ValueError:
            return default
    return default


def _resolve_constant_variant(
    namespace: object | None,
    names: Sequence[str],
    fallback: Any | None = None,
) -> Any | None:
    """�Ը����кܶ�ֶε����������ƣ����빹��ʵ��ֵ."""
    if namespace is None:
        return fallback
    for name in names:
        candidate = getattr(namespace, name, None)
        if candidate is None:
            continue
        return getattr(candidate, "value", candidate)
    return fallback


def _normalize_date_to_int(value: object | None) -> Optional[int]:
    """������ʽ����ת���� YYYYMMDD ���͵�������."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        digits = f"{int(value):08d}"
    else:
        digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 8 or not digits.isdigit():
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _create_market_data_instance(sdk: Any) -> Any:
    """创建 MarketData 实例，必须传入交易日历。

    根据SDK文档，query_kline内部会遍历calendar筛选交易日，
    因此calendar参数是必需的，不能为None。
    详见：docs/datasources/amazingdata/query_kline_calendar_requirement.md
    """
    market_cls = getattr(sdk, "MarketData", None)
    if market_cls is None:
        raise DataProviderError("AmazingData SDK 缺少 MarketData 类，无法查询行情数据")

    # 获取交易日历（必需）
    calendar = None
    base_cls = getattr(sdk, "BaseData", None)
    if base_cls is not None:
        try:
            base_instance = base_cls()
            calendar = base_instance.get_calendar()
            log_debug("获取交易日历成功，长度: {}", len(calendar) if calendar else 0)
        except Exception as exc:  # noqa: BLE001
            log_warning(
                "BaseData.get_calendar 调用失败",
                action="market_data_init",
                metadata={"error": str(exc)},
            )

    # 使用calendar创建MarketData
    try:
        if calendar is not None:
            return market_cls(calendar)
        # calendar为None时尝试无参创建（可能会在query_kline时报错）
        log_warning(
            "未能获取交易日历，MarketData可能无法正常调用query_kline",
            action="market_data_init",
        )
        return market_cls()
    except TypeError as exc:
        raise DataProviderError(f"AmazingData MarketData 初始化失败: {exc}") from exc


def _ensure_int(value: object | None, default: int = 0) -> int:
    """תΪ intʧʱĬֵ."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except ValueError:
            return default
    return default


def _format_date(value: object) -> str:
    """��ԭʼ������ʽ��Ϊ YYYY-MM-DD �ַ���."""
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        value_str = str(int(value))
    else:
        value_str = str(value)
    value_str = value_str.strip()
    if len(value_str) == 8 and value_str.isdigit():
        return value_str[:4] + "-" + value_str[4:6] + "-" + value_str[6:]
    return value_str


def fetch_stock_dataset_blocking(
    sdk: AmazingDataSDKProtocol,
    *,
    security_type: str = "EXTRA_STOCK_A",
    start_date: object | None = None,
    end_date: object | None = None,
    local_path: object | None = None,
) -> Any:
    """��ͬ���߳��е��� AmazingData SDK����ȡ��Ʊ�б����ڱ��."""

    errors: list[str] = []
    security_type_value = security_type or "EXTRA_STOCK_A"
    cache_policy = CachePolicy.from_params(
        context="BaseData.get_hist_code_list",
        local_path=local_path,
        is_local=None,
        begin_date=start_date,
        end_date=end_date,
    )
    if cache_policy.mode is CacheParamMode.LOCAL_CACHE:
        local_path = cache_policy.get("local_path")
        start_date = None
        end_date = None
    elif cache_policy.mode is CacheParamMode.REMOTE_RANGE:
        local_path = None
        start_date = cache_policy.get("begin_date")
        end_date = cache_policy.get("end_date")

    base_cls = getattr(sdk, "BaseData", None)
    if base_cls is not None:
        base_instance = base_cls()
        fetch_candidates: tuple[tuple[str, dict[str, Any]], ...] = (
            ("get_code_list", {"security_type": security_type_value}),
            ("get_code_info", {"security_type": security_type_value}),
        )

        for method_name, extra_kwargs in fetch_candidates:
            fetch_method = getattr(base_instance, method_name, None)
            if not callable(fetch_method):
                continue
            try:
                result = fetch_method(**extra_kwargs)
            except TypeError as exc:  # pragma: no cover
                log_debug("BaseData.{} ����������: {}�������޲ε���", method_name, exc)
                try:
                    result = fetch_method()
                except Exception as inner_exc:  # noqa: BLE001
                    errors.append(f"BaseData.{method_name} ����ʧ��: {inner_exc}")
                    continue
            except Exception as exc:  # noqa: BLE001
                errors.append(f"BaseData.{method_name} 调用失败: {exc}")
                log_warning(
                    f"BaseData.{method_name} 调用失败，跳过该方法",
                    action="base_data_method",
                    metadata={"method": method_name, "error": str(exc)},
                )
                continue

            if result is None:
                log_warning(
                    f"BaseData.{method_name} 返回空结果，跳过该方法",
                    action="base_data_method",
                    metadata={"method": method_name},
                )
                continue
            log_debug("ͨ�� BaseData.{} ��ȡ��Ʊ������ɹ�", method_name)
            return result

        hist_method = getattr(base_instance, "get_hist_code_list", None)
        if callable(hist_method):
            start_normalized = _normalize_date_to_int(start_date) or DEFAULT_HIST_CODE_LIST_START
            end_normalized = _normalize_date_to_int(end_date)
            if end_normalized is None:
                end_normalized = int(datetime.now().strftime("%Y%m%d"))
            if end_normalized < start_normalized:
                start_normalized, end_normalized = end_normalized, start_normalized

            local_mode = cache_policy.mode is CacheParamMode.LOCAL_CACHE
            cache_path: str | None = None
            if local_mode:
                default_cache_path = get_default_local_data_path()
                cache_path_candidate = str(local_path or default_cache_path).strip()
                cache_path = cache_path_candidate or default_cache_path
                try:
                    Path(cache_path).mkdir(parents=True, exist_ok=True)
                except Exception as path_exc:  # pragma: no cover
                    log_debug("�������ػ���Ŀ¼ {} ʧ��: {}", cache_path, path_exc)

            hist_kwargs: dict[str, object] = {
                "security_type": security_type_value,
            }
            if local_mode and cache_path:
                hist_kwargs["local_path"] = cache_path
                hist_kwargs["is_local"] = bool(cache_policy.values.get("is_local", True))
                log_info(
                    "׼������ BaseData.get_hist_code_list security_type=%s local_path=%s is_local=%s",
                    security_type_value,
                    cache_path,
                    hist_kwargs["is_local"],
                )
            else:
                hist_kwargs["start_date"] = start_normalized
                hist_kwargs["end_date"] = end_normalized
                log_info(
                    "׼������ BaseData.get_hist_code_list security_type=%s start_date=%s end_date=%s",
                    security_type_value,
                    start_normalized,
                    end_normalized,
                )
            try:
                result = hist_method(**hist_kwargs)
            except TypeError as exc:
                message = str(exc)
                if (
                    "unexpected keyword argument 'is_local'" in message
                    and "is_local" in hist_kwargs
                ):
                    log_debug("BaseData.get_hist_code_list ��֧�� is_local��ʹ�ü���ģʽ����")
                    hist_kwargs.pop("is_local", None)
                    try:
                        result = hist_method(**hist_kwargs)
                    except Exception as compat_exc:  # noqa: BLE001
                        errors.append(f"BaseData.get_hist_code_list ���ݵ���ʧ��: {compat_exc}")
                        result = None
                else:
                    errors.append(f"BaseData.get_hist_code_list ����ʧ��: {exc}")
                    result = None
            except Exception as exc:  # noqa: BLE001
                errors.append(f"BaseData.get_hist_code_list ����ʧ��: {exc}")
                result = None

            if result is not None:
                log_debug(
                    "获取 BaseData.get_hist_code_list 股票列表成功 (mode=%s)",
                    "local" if local_mode else "remote",
                )
                return result
            log_warning(
                "BaseData.get_hist_code_list 返回空集合",
                action="hist_code_list",
                metadata={
                    "mode": "local" if local_mode else "remote",
                    "start": start_normalized,
                    "end": end_normalized,
                },
            )
    if errors:
        raise RuntimeError("; ".join(errors))
    raise RuntimeError("AmazingData SDK δ�ṩ���õĹ�Ʊ�б��ӿ�")


def normalize_stock_records(dataset: Any) -> list[dict[str, Any]]:
    """�� AmazingData ��Ʊ�б�ԭʼ���ݹ�һ��Ϊ�ֵ��б���."""

    if dataset is None:
        return []

    if isinstance(dataset, pd.DataFrame):
        df_reset = dataset.reset_index()
        if "code" not in df_reset.columns:
            index_candidates = [
                col for col in ("index", dataset.index.name) if col and col in df_reset.columns
            ]
            if index_candidates:
                df_reset = df_reset.rename(columns={index_candidates[0]: "code"})
            elif "index" in df_reset.columns:
                df_reset = df_reset.rename(columns={"index": "code"})
        records: list[dict[str, Any]] = []
        for item in df_reset.to_dict("records"):
            if not isinstance(item, Mapping):
                continue
            record: dict[str, Any] = dict(item)
            index_value = record.pop("index", None)
            code_value = str(record.get("code") or index_value or "")
            record["code"] = code_value
            record.setdefault("symbol", str(record.get("symbol", code_value)))
            record.setdefault("name", str(record.get("name", record["symbol"])))
            record.setdefault("status", record.get("status", "listed"))
            records.append(record)
        return records

    if isinstance(dataset, Mapping):
        records_map: list[dict[str, Any]] = []
        for key, value in dataset.items():
            if isinstance(value, Mapping):
                record_map: dict[str, Any] = dict(value)
            else:
                record_map = {}
            record_map["code"] = str(key)
            record_map.setdefault("symbol", record_map.get("symbol", record_map["code"]))
            record_map.setdefault("name", record_map.get("name", record_map["symbol"]))
            record_map.setdefault("status", record_map.get("status", "listed"))
            records_map.append(record_map)
        return records_map

    if isinstance(dataset, Sequence) and not isinstance(dataset, (str, bytes, bytearray)):
        records = []
        for entry in dataset:
            if isinstance(entry, Mapping):
                record = dict(entry)
                code_value = str(
                    record.get("code")
                    or record.get("symbol")
                    or record.get("MARKET_CODE")
                    or record.get("SECURITY_ID")
                    or record.get("SECURITY_CODE")
                    or ""
                )
                record["code"] = code_value
                record.setdefault("symbol", str(record.get("symbol", code_value)))
                record.setdefault("name", str(record.get("name", record["symbol"])))
                record.setdefault("status", record.get("status", "listed"))
                records.append(record)
            else:
                code_value = str(entry)
                records.append(
                    {
                        "code": code_value,
                        "symbol": code_value,
                        "name": code_value,
                        "status": "listed",
                    }
                )
        return records

    return []


def _has_board_field(record: Mapping[str, Any]) -> bool:
    for field in BOARD_FIELD_CANDIDATES:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _records_need_board(records: Sequence[Mapping[str, Any]]) -> bool:
    return any(not _has_board_field(record) for record in records)


def _extract_symbol(record: Mapping[str, Any]) -> str:
    raw = (
        record.get("symbol")
        or record.get("code")
        or record.get("MARKET_CODE")
        or record.get("SECURITY_ID")
        or record.get("SECURITY_CODE")
    )
    return str(raw or "").upper().strip()


def fetch_stock_board_metadata_blocking(
    sdk: AmazingDataSDKProtocol,
    symbols: Sequence[str],
) -> list[dict[str, Any]]:
    """ͨ�� InfoData/BaseData ��ȡ��չ�ĵ�Ʊ������."""

    if not symbols:
        return []

    normalized_symbols = sorted({symbol.upper() for symbol in symbols if symbol})
    info_cls = getattr(sdk, "InfoData", None)
    payloads: list[dict[str, Any]] = []

    if info_cls is not None:
        info_instance = info_cls()
        method_obj = getattr(info_instance, "get_stock_basic", None)
        info_method: Callable[..., Any] | None = method_obj if callable(method_obj) else None
        if info_method:
            try:
                result = info_method(code_list=normalized_symbols)
            except TypeError:
                result = info_method(normalized_symbols)
            except Exception as exc:  # noqa: BLE001
                log_debug("InfoData.get_stock_basic ����ʧ��: {}", exc)
                result = None
            if result is not None:
                payloads.extend(normalize_stock_records(result))

    if payloads:
        return payloads

    base_cls = getattr(sdk, "BaseData", None)
    if base_cls is None:
        return []
    base_instance = base_cls()
    code_info_method = getattr(base_instance, "get_code_info", None)
    if not callable(code_info_method):
        return []
    try:
        result = code_info_method(security_type="EXTRA_STOCK_A")
    except Exception as exc:  # noqa: BLE001
        log_debug("BaseData.get_code_info ����ʧ��: {}", exc)
        return []
    return normalize_stock_records(result)


def _merge_board_metadata(
    records: list[dict[str, Any]],
    metadata: Sequence[Mapping[str, Any]],
) -> None:
    """�� metadata ���������������״̬."""

    board_map: dict[str, str] = {}
    for item in metadata:
        board_value = None
        for field in BOARD_FIELD_CANDIDATES:
            raw = item.get(field)
            if isinstance(raw, str) and raw.strip():
                board_value = raw.strip()
                break
        if not board_value:
            continue
        symbol = _extract_symbol(item)
        if symbol:
            board_map.setdefault(symbol, board_value)

    if not board_map:
        return

    for record in records:
        symbol = _extract_symbol(record)
        board_value = board_map.get(symbol)
        if not board_value:
            continue

        existing_aliases: set[str] = set()
        for field in BOARD_FIELD_CANDIDATES:
            raw_value = record.get(field)
            if not isinstance(raw_value, str):
                continue
            tokens = [
                token.strip() for token in raw_value.replace(";", ",").replace("/", ",").split(",")
            ]
            existing_aliases.update(token for token in tokens if token)

        record["LISTPLATE_NAME"] = board_value
        if not isinstance(record.get("board_name"), str) or not record.get("board_name"):
            record["board_name"] = board_value

        if board_value not in existing_aliases:
            record["board"] = board_value


P = ParamSpec("P")
T = TypeVar("T")


def async_retry(
    max_attempts: int = 3, backoff_base: float = 2, max_delay: float = 60, jitter: bool = True
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    �첽����װ�������ṩָ���˱ܺͶ���.

    Args:
        max_attempts: ������Դ���
        backoff_base: �˱ܻ���
        max_delay: ����ӳ�ʱ�䣨�룩
        jitter: �Ƿ������������
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None

            strategy = build_retry_strategy(
                max_attempts=max_attempts,
                backoff_base=backoff_base,
                max_delay=max_delay,
                jitter=jitter,
            )
            delays = strategy.delays()

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exception = exc
                    if attempt == max_attempts - 1:
                        log_error(
                            "所有尝试均失败",
                            action=func.__name__,
                            metadata={"attempts": max_attempts, "error": repr(exc)},
                        )
                        raise

                    delay = delays[attempt] if attempt < len(delays) else delays[-1]
                    log_warning(
                        "调用失败，等待重试",
                        action=func.__name__,
                        metadata={
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "delay": round(delay, 3),
                            "error": repr(exc),
                        },
                    )
                    await asyncio.sleep(delay)

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("async_retry exhausted without capturing exception")

        return wrapper

    return decorator


__all__ = [
    "_coalesce",
    "_ensure_float",
    "_resolve_constant_variant",
    "_normalize_date_to_int",
    "_create_market_data_instance",
    "_ensure_int",
    "_format_date",
    "fetch_stock_dataset_blocking",
    "normalize_stock_records",
    "_records_need_board",
    "_extract_symbol",
    "fetch_stock_board_metadata_blocking",
    "_merge_board_metadata",
    "async_retry",
]
