import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataPeriod,
    AmazingDataSecurityType,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.param_guards import (
    CacheParamMode,
    CachePolicy,
    validate_security_period,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError


def test_sanitize_cache_params_mixed_groups():
    policy = CachePolicy.from_params(
        local_path="D://cache//",
        is_local=True,
        begin_date=20240101,
        end_date=20240131,
        context="test.mixed"
    )
    assert policy.mode is CacheParamMode.REMOTE_RANGE
    assert policy.values["local_path"] is None
    assert policy.values["is_local"] is None
    assert policy.values["begin_date"] == 20240101
    assert policy.values["end_date"] == 20240131


def test_validate_security_period_autoadjust_hkt():
    security, period = validate_security_period(
        AmazingDataSecurityType.HKT.value,
        "snapshot",
        context="test.hkt"
    )
    assert security == AmazingDataSecurityType.HKT.value
    assert period == AmazingDataPeriod.SNAPSHOT_HKT.value


def test_validate_security_period_invalid_combo():
    with pytest.raises(DataProviderError):
        validate_security_period(
            AmazingDataSecurityType.FUTURE.value,
            AmazingDataPeriod.SNAPSHOT_HKT.value,
            context="test.invalid"
        )
