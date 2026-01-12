from types import SimpleNamespace

import pandas as pd
import pytest
from core.infrastructure.providers.implementations.amazingdata import helpers as sut


def test_coalesce_skips_blank_strings() -> None:
    assert sut._coalesce(None, " ", "value") == "value"


def test_ensure_float_handles_invalid_input() -> None:
    assert sut._ensure_float(" 12.5 ") == 12.5
    assert sut._ensure_float("bad", default=1.5) == 1.5


def test_ensure_int_tracks_bool_and_strings() -> None:
    assert sut._ensure_int(True) == 1
    assert sut._ensure_int(" 42 ") == 42
    assert sut._ensure_int("bad", default=7) == 7


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-01-02", 20240102),
        (20240102, 20240102),
        ("2024/01/02", 20240102),
        ("invalid", None),
        (None, None),
    ],
)
def test_normalize_date_to_int(value: object | None, expected: int | None) -> None:
    assert sut._normalize_date_to_int(value) == expected


def test_format_date_produces_standard_string() -> None:
    assert sut._format_date(20240102) == "2024-01-02"
    assert sut._format_date("2024-01-02") == "2024-01-02"
    assert sut._format_date("") == ""


def test_resolve_constant_variant_prefers_value_attribute() -> None:
    class Holder:
        value = "target"

    namespace = SimpleNamespace(Option=Holder)
    assert sut._resolve_constant_variant(namespace, ["Option"]) == "target"
    assert sut._resolve_constant_variant(namespace, ["Missing"], fallback="fallback") == "fallback"


def test_normalize_stock_records_accepts_dataframe() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "AAA", "name": "Alpha"},
            {"symbol": "BBB", "name": "Beta"},
        ]
    ).set_index("symbol")

    records = sut.normalize_stock_records(frame)

    assert {record["symbol"] for record in records} == {"AAA", "BBB"}
    assert all("code" in record for record in records)
    assert records[0]["status"] == "listed"


def test_normalize_stock_records_accepts_mapping() -> None:
    payload = {"AAA": {"name": "Alpha"}, "BBB": {}}
    records = sut.normalize_stock_records(payload)
    assert {record["symbol"] for record in records} == {"AAA", "BBB"}


def test_normalize_stock_records_accepts_sequence() -> None:
    payload = [{"symbol": "AAA", "name": "Alpha"}, "BBB"]
    records = sut.normalize_stock_records(payload)
    assert {record["symbol"] for record in records} == {"AAA", "BBB"}


@pytest.mark.asyncio
async def test_async_retry_retries_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        calls.append(delay)

    monkeypatch.setattr(sut.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    @sut.async_retry(max_attempts=3, backoff_base=1, jitter=False)
    async def flaky() -> int:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("fail")
        return attempts["count"]

    result = await flaky()

    assert result == 3
    assert attempts["count"] == 3
    assert calls == [1, 1]
