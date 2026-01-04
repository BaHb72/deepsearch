"""
Dask Actor 全量测试

测试 AmazingDataActor 的全部 19 个接口，通过 AmazingDataAdapter 访问。
需要 Dask Worker 运行环境。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytest

# 测试配置
TEST_CODES = ["000001.SZ", "600000.SH"]  # 测试用股票代码
TEST_DAYS = 30  # 默认查询天数


def get_date_range(days: int = TEST_DAYS) -> tuple[int, int]:
    """获取测试日期范围"""
    end = datetime.now()
    begin = end - timedelta(days=days)
    return int(begin.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))


def get_amazingdata_config() -> dict[str, Any]:
    """从应用配置加载 AmazingData 凭据"""
    try:
        from core.config import get_config

        config = get_config()

        # 从 data_sources.providers['amazingdata'].config['connection'] 获取
        if hasattr(config, "data_sources") and config.data_sources is not None:
            providers = getattr(config.data_sources, "providers", None)
            if providers and isinstance(providers, dict):
                ad_provider = providers.get("amazingdata")
                if ad_provider and hasattr(ad_provider, "config"):
                    ad_cfg = ad_provider.config
                    if isinstance(ad_cfg, dict):
                        conn = ad_cfg.get("connection", {})
                        if conn:
                            return {
                                "username": conn.get("username", "") or "",
                                "password": conn.get("password", "") or "",
                            }

        print("⚠️ 配置中没有 amazingdata 凭据，尝试环境变量")
        import os

        return {
            "username": os.getenv("AMAZINGDATA_USERNAME", ""),
            "password": os.getenv("AMAZINGDATA_PASSWORD", ""),
        }
    except Exception as e:
        import os

        print(f"⚠️ 配置加载失败 ({e})，尝试环境变量")
        return {
            "username": os.getenv("AMAZINGDATA_USERNAME", ""),
            "password": os.getenv("AMAZINGDATA_PASSWORD", ""),
        }


@pytest.fixture(scope="module")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def adapter():
    """初始化 Dask Adapter"""
    from core.domain.data_proxy.adapters.amazingdata import AmazingDataAdapter

    config = get_amazingdata_config()
    adapter = AmazingDataAdapter(config)
    success = await adapter.initialize_actor()
    if not success:
        pytest.skip("Dask Actor 初始化失败，跳过测试")
    yield adapter
    await adapter.shutdown_actor()


class TestDaskActorFinancialData:
    """财务数据接口测试 (5个)"""

    @pytest.mark.asyncio
    async def test_get_profit_express(self, adapter):
        """测试业绩快报"""
        begin, end = get_date_range(90)
        result = await adapter.get_profit_express(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_profit_express: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_profit_notice(self, adapter):
        """测试业绩预告"""
        begin, end = get_date_range(90)
        result = await adapter.get_profit_notice(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_profit_notice: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_balance_sheet(self, adapter):
        """测试资产负债表"""
        result = await adapter.get_balance_sheet(TEST_CODES)
        assert isinstance(result, list)
        print(f"✅ get_balance_sheet: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_cash_flow(self, adapter):
        """测试现金流量表"""
        result = await adapter.get_cash_flow(TEST_CODES)
        assert isinstance(result, list)
        print(f"✅ get_cash_flow: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_income(self, adapter):
        """测试利润表"""
        result = await adapter.get_income(TEST_CODES)
        assert isinstance(result, list)
        print(f"✅ get_income: 返回 {len(result)} 条记录")


class TestDaskActorShareholderData:
    """股东数据接口测试 (2个)"""

    @pytest.mark.asyncio
    async def test_get_share_holder(self, adapter):
        """测试十大股东"""
        begin, end = get_date_range(365)
        result = await adapter.get_share_holder(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_share_holder: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_holder_num(self, adapter):
        """测试股东人数"""
        begin, end = get_date_range(365)
        result = await adapter.get_holder_num(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_holder_num: 返回 {len(result)} 条记录")


class TestDaskActorEquityData:
    """股本数据接口测试 (3个)"""

    @pytest.mark.asyncio
    async def test_get_equity_structure(self, adapter):
        """测试股本结构"""
        begin, end = get_date_range(365)
        result = await adapter.get_equity_structure(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_equity_structure: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_equity_pledge_freeze(self, adapter):
        """测试股权质押冻结"""
        begin, end = get_date_range(365)
        result = await adapter.get_equity_pledge_freeze(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_equity_pledge_freeze: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_equity_restricted(self, adapter):
        """测试限售股解禁"""
        begin, end = get_date_range(365)
        result = await adapter.get_equity_restricted(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_equity_restricted: 返回 {len(result)} 条记录")


class TestDaskActorDividendData:
    """分红配股接口测试 (2个)"""

    @pytest.mark.asyncio
    async def test_get_dividend(self, adapter):
        """测试分红数据"""
        begin, end = get_date_range(365)
        result = await adapter.get_dividend(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_dividend: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_right_issue(self, adapter):
        """测试配股数据"""
        begin, end = get_date_range(365)
        result = await adapter.get_right_issue(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_right_issue: 返回 {len(result)} 条记录")


class TestDaskActorMarginData:
    """融资融券接口测试 (2个)"""

    @pytest.mark.asyncio
    async def test_get_margin_summary(self, adapter):
        """测试融资融券汇总"""
        begin, end = get_date_range(30)
        result = await adapter.get_margin_summary(begin, end)
        assert isinstance(result, list)
        print(f"✅ get_margin_summary: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_margin_detail(self, adapter):
        """测试融资融券明细"""
        begin, end = get_date_range(30)
        result = await adapter.get_margin_detail(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_margin_detail: 返回 {len(result)} 条记录")


class TestDaskActorMarketData:
    """市场异动接口测试 (2个)"""

    @pytest.mark.asyncio
    async def test_get_long_hu_bang(self, adapter):
        """测试龙虎榜"""
        begin, end = get_date_range(30)
        result = await adapter.get_long_hu_bang(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_long_hu_bang: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_block_trading(self, adapter):
        """测试大宗交易"""
        begin, end = get_date_range(30)
        result = await adapter.get_block_trading(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_block_trading: 返回 {len(result)} 条记录")


class TestDaskActorIndustryData:
    """行业数据接口测试 (2个)"""

    @pytest.mark.asyncio
    async def test_get_industry_daily(self, adapter):
        """测试行业日行情"""
        begin, end = get_date_range(30)
        result = await adapter.get_industry_daily(None, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_industry_daily: 返回 {len(result)} 条记录")

    @pytest.mark.asyncio
    async def test_get_industry_weight(self, adapter):
        """测试行业成分权重"""
        begin, end = get_date_range(30)
        result = await adapter.get_industry_weight(None, begin, end)
        assert isinstance(result, list)
        print(f"✅ get_industry_weight: 返回 {len(result)} 条记录")


class TestDaskActorKline:
    """K线数据接口测试"""

    @pytest.mark.asyncio
    async def test_query_kline(self, adapter):
        """测试 K 线查询"""
        begin, end = get_date_range(30)
        result = await adapter.query_kline(TEST_CODES, begin, end)
        assert isinstance(result, list)
        print(f"✅ query_kline: 返回 {len(result)} 条记录")


# ==================== 快速验证脚本 ====================


async def run_quick_test():
    """快速测试 - 可直接运行验证"""
    from core.domain.data_proxy.adapters.amazingdata import AmazingDataAdapter

    print("=" * 60)
    print("Dask Actor 全量测试")
    print("=" * 60)

    config = get_amazingdata_config()
    adapter = AmazingDataAdapter(config)

    print("\n[1/2] 初始化 Dask Actor...")
    success = await adapter.initialize_actor()
    if not success:
        print("❌ Dask Actor 初始化失败")
        return False

    print("✅ Dask Actor 初始化成功")

    begin, end = get_date_range(30)
    begin_long, end_long = get_date_range(90)
    tests = [
        (
            "get_profit_express",
            lambda: adapter.get_profit_express(TEST_CODES, begin_long, end_long),
        ),
        ("get_profit_notice", lambda: adapter.get_profit_notice(TEST_CODES, begin_long, end_long)),
        ("get_balance_sheet", lambda: adapter.get_balance_sheet(TEST_CODES)),
        ("get_cash_flow", lambda: adapter.get_cash_flow(TEST_CODES)),
        ("get_income", lambda: adapter.get_income(TEST_CODES)),
        ("get_share_holder", lambda: adapter.get_share_holder(TEST_CODES, begin_long, end_long)),
        ("get_holder_num", lambda: adapter.get_holder_num(TEST_CODES, begin_long, end_long)),
        (
            "get_equity_structure",
            lambda: adapter.get_equity_structure(TEST_CODES, begin_long, end_long),
        ),
        (
            "get_equity_pledge_freeze",
            lambda: adapter.get_equity_pledge_freeze(TEST_CODES, begin_long, end_long),
        ),
        (
            "get_equity_restricted",
            lambda: adapter.get_equity_restricted(TEST_CODES, begin_long, end_long),
        ),
        ("get_dividend", lambda: adapter.get_dividend(TEST_CODES, begin_long, end_long)),
        ("get_right_issue", lambda: adapter.get_right_issue(TEST_CODES, begin_long, end_long)),
        ("get_margin_summary", lambda: adapter.get_margin_summary(begin, end)),
        ("get_margin_detail", lambda: adapter.get_margin_detail(TEST_CODES, begin, end)),
        ("get_long_hu_bang", lambda: adapter.get_long_hu_bang(TEST_CODES, begin, end)),
        ("get_block_trading", lambda: adapter.get_block_trading(TEST_CODES, begin, end)),
        ("get_industry_daily", lambda: adapter.get_industry_daily(None, begin, end)),
        ("get_industry_weight", lambda: adapter.get_industry_weight(None, begin, end)),
        ("query_kline", lambda: adapter.query_kline(TEST_CODES, begin, end)),
    ]

    print(f"\n[2/2] 测试 {len(tests)} 个接口...")
    passed = 0
    failed = 0

    for name, func in tests:
        try:
            result = await func()
            count = len(result) if result else 0
            print(f"  ✅ {name}: {count} 条记录")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    await adapter.shutdown_actor()
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_quick_test())
