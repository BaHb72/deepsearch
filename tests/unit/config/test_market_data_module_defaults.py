from core.config.models.market_data import MarketModuleConfig


def test_market_module_auto_fallback_defaults_to_disabled() -> None:
    config = MarketModuleConfig(primary="amazingdata")

    assert config.enable_auto_fallback is False
