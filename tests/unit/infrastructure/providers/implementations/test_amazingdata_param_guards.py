"""Unit tests for AmazingData parameter guards utilities."""

from __future__ import annotations

import pytest
from core.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataPeriod,
    AmazingDataSecurityType,
)
from core.infrastructure.providers.implementations.amazingdata.param_guards import (
    CacheParamMode,
    CachePolicy,
    normalize_security_type,
    validate_security_period,
)
from core.infrastructure.providers.interfaces.base import DataProviderError


def test_cache_policy_local_mode_trims_path() -> None:
    policy = CachePolicy.from_params(
        context="unit-test",
        local_path="  C:/cache  ",
        is_local=None,
        begin_date=None,
        end_date=None,
    )

    assert policy.mode is CacheParamMode.LOCAL_CACHE
    assert policy.values["local_path"] == "C:/cache"
    assert policy.values["begin_date"] is None
    assert policy.values["end_date"] is None
    assert policy.values["is_local"] is True


def test_cache_policy_remote_mode_wins_on_conflict() -> None:
    policy = CachePolicy.from_params(
        context="unit-test",
        local_path="C:/cache",
        is_local=True,
        begin_date=20240101,
        end_date=20240131,
    )

    assert policy.mode is CacheParamMode.REMOTE_RANGE
    assert policy.values["local_path"] is None
    assert policy.values["is_local"] is None
    assert policy.values["begin_date"] == 20240101
    assert policy.values["end_date"] == 20240131


def test_cache_policy_apply_removes_unspecified_keys() -> None:
    policy = CachePolicy.from_params(
        context="unit-test",
        local_path=None,
        is_local=None,
        begin_date=20230101,
        end_date=20230131,
    )
    merged = policy.apply({"local_path": "legacy", "begin_date": 20200101})

    assert "local_path" not in merged
    assert merged["begin_date"] == 20230101
    assert merged["end_date"] == 20230131


def test_normalize_security_type_handles_alias() -> None:
    normalized = normalize_security_type("stock_a_shsz", allow_empty=False)
    assert normalized == AmazingDataSecurityType.STOCK_A_SH_SZ.value


def test_validate_security_period_auto_adjusts_hkt_snapshot() -> None:
    security, period = validate_security_period(
        AmazingDataSecurityType.HKT.value,
        AmazingDataPeriod.SNAPSHOT.value,
        context="snapshot-check",
    )
    assert security == AmazingDataSecurityType.HKT.value
    assert period == AmazingDataPeriod.SNAPSHOT_HKT.value


def test_validate_security_period_raises_on_invalid_combo() -> None:
    with pytest.raises(DataProviderError):
        validate_security_period(
            AmazingDataSecurityType.STOCK_A.value,
            AmazingDataPeriod.SNAPSHOT_FUTURE.value,
            context="invalid",
        )
