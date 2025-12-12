"""
模块级数据源配置解析器的单元测试。
"""

from deepsearch.infrastructure.providers.managers.module_source_config import (
    ModuleSourceConfig,
    ModuleSourceResolver,
    create_resolver_from_config,
)
from deepsearch.ports.data_sources import DataAccessType, DataSourceType


class TestModuleSourceConfig:
    """ModuleSourceConfig 单元测试"""

    def test_get_source_order_with_primary_and_fallback(self):
        config = ModuleSourceConfig(
            primary=DataSourceType.AMAZINGDATA,
            fallback=[DataSourceType.AKSHARE],
        )
        order = config.get_source_order()
        assert order == [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]

    def test_get_source_order_primary_only(self):
        config = ModuleSourceConfig(primary=DataSourceType.AKSHARE, fallback=[])
        order = config.get_source_order()
        assert order == [DataSourceType.AKSHARE]

    def test_get_source_order_empty(self):
        config = ModuleSourceConfig()
        order = config.get_source_order()
        assert order == []


class TestModuleSourceResolver:
    """ModuleSourceResolver 单元测试"""

    def test_resolve_module_override(self):
        resolver = ModuleSourceResolver(
            module_overrides={
                "market_strength": {
                    "primary": "akshare",
                    "fallback": ["amazingdata"],
                }
            },
            global_fallback_order=["amazingdata", "akshare"],
        )

        result = resolver.resolve(module="market_strength")
        assert result == [DataSourceType.AKSHARE, DataSourceType.AMAZINGDATA]

    def test_resolve_access_type_override(self):
        resolver = ModuleSourceResolver(
            access_type_overrides={
                "historical_kline": {
                    "primary": "akshare",
                    "fallback": [],
                }
            },
            global_fallback_order=["amazingdata", "akshare"],
        )

        result = resolver.resolve(access_type=DataAccessType.HISTORICAL_KLINE)
        assert result == [DataSourceType.AKSHARE]

    def test_resolve_module_takes_priority_over_access_type(self):
        resolver = ModuleSourceResolver(
            module_overrides={
                "my_module": {"primary": "amazingdata", "fallback": []},
            },
            access_type_overrides={
                "realtime_quote": {"primary": "akshare", "fallback": []},
            },
            global_fallback_order=["akshare"],
        )

        # module override should take priority
        result = resolver.resolve(
            module="my_module",
            access_type=DataAccessType.REALTIME_QUOTE,
        )
        assert result == [DataSourceType.AMAZINGDATA]

    def test_resolve_fallback_to_global(self):
        resolver = ModuleSourceResolver(
            module_overrides={},
            access_type_overrides={},
            global_fallback_order=["amazingdata", "akshare"],
        )

        result = resolver.resolve(module="unknown_module")
        assert result == [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]

    def test_resolve_fallback_to_default(self):
        resolver = ModuleSourceResolver(
            global_default="akshare",
        )

        result = resolver.resolve()
        assert result == [DataSourceType.AKSHARE]

    def test_get_module_names(self):
        resolver = ModuleSourceResolver(
            module_overrides={
                "mod_a": {"primary": "akshare"},
                "mod_b": {"primary": "amazingdata"},
            },
        )

        names = resolver.get_module_names()
        assert set(names) == {"mod_a", "mod_b"}


class TestCreateResolverFromConfig:
    """create_resolver_from_config 工厂函数测试"""

    def test_create_from_full_config(self):
        config = {
            "default": "amazingdata",
            "fallback_order": ["amazingdata", "akshare"],
            "module_overrides": {
                "test_module": {"primary": "akshare"},
            },
            "access_type_overrides": {
                "realtime_quote": {"primary": "amazingdata"},
            },
        }

        resolver = create_resolver_from_config(config)

        # module override
        assert resolver.resolve(module="test_module") == [DataSourceType.AKSHARE]

        # access_type override
        assert resolver.resolve(access_type=DataAccessType.REALTIME_QUOTE) == [
            DataSourceType.AMAZINGDATA
        ]

        # global fallback
        assert resolver.resolve() == [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]

    def test_create_from_empty_config(self):
        resolver = create_resolver_from_config({})
        assert resolver.resolve() == []
