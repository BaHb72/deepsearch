"""Compatibility shim tests for RedisTimeSeriesStorage."""

import importlib
import sys

import redis


def test_timeseries_import_patches_redis_compat() -> None:
    module_name = "core.infrastructure.persistence.timeseries"
    sys.modules.pop(module_name, None)

    sys.modules.pop("redis._compat", None)
    sys.modules.pop("redistimeseries.client", None)
    if hasattr(redis, "_compat"):
        delattr(redis, "_compat")

    module = importlib.import_module(module_name)
    compat_module = sys.modules.get("redis._compat")

    assert compat_module is not None
    assert getattr(redis, "_compat", None) is compat_module
    assert hasattr(module, "_ensure_redis_compat")

    redistimeseries_module = importlib.import_module("redistimeseries.client")
    assert redistimeseries_module is not None
