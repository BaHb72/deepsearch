"""
Semantic Types 单元测试。

测试 ports/data/semantic_types.py 中的类型定义。
"""

from datetime import datetime, timedelta

import pytest
from core.ports.data.semantic_types import (
    AdjustType,
    AssetSpec,
    Exchange,
    LatencyHint,
    Timeframe,
    TimeRange,
)


class TestAssetSpec:
    """AssetSpec 测试"""

    def test_from_code_with_sz_suffix(self):
        """测试深交所后缀"""
        asset = AssetSpec.from_code("000001.SZ")
        assert asset.symbol == "000001"
        assert asset.exchange == Exchange.SZ

    def test_from_code_with_sh_suffix(self):
        """测试上交所后缀"""
        asset = AssetSpec.from_code("600000.SH")
        assert asset.symbol == "600000"
        assert asset.exchange == Exchange.SH

    def test_from_code_with_bj_suffix(self):
        """测试北交所后缀"""
        asset = AssetSpec.from_code("430047.BJ")
        assert asset.symbol == "430047"
        assert asset.exchange == Exchange.BJ

    def test_from_code_prefix_format(self):
        """测试前缀格式 SZ000001"""
        asset = AssetSpec.from_code("SZ000001")
        assert asset.symbol == "000001"
        assert asset.exchange == Exchange.SZ

    def test_from_code_dot_prefix_format(self):
        """测试点分前缀格式 SZ.000001"""
        asset = AssetSpec.from_code("SZ.000001")
        assert asset.symbol == "000001"
        assert asset.exchange == Exchange.SZ

    def test_from_code_case_insensitive(self):
        """测试大小写不敏感"""
        asset = AssetSpec.from_code("000001.sz")
        assert asset.exchange == Exchange.SZ

    def test_from_code_invalid_format(self):
        """测试无效格式抛出异常"""
        with pytest.raises(ValueError):
            AssetSpec.from_code("000001")  # 缺少交易所

    def test_to_standard(self):
        """测试标准格式输出"""
        asset = AssetSpec(symbol="000001", exchange=Exchange.SZ)
        assert asset.to_standard() == "000001.SZ"

    def test_to_compact(self):
        """测试紧凑格式输出"""
        asset = AssetSpec(symbol="000001", exchange=Exchange.SZ)
        assert asset.to_compact() == "SZ000001"

    def test_str_representation(self):
        """测试字符串表示"""
        asset = AssetSpec(symbol="600000", exchange=Exchange.SH)
        assert str(asset) == "600000.SH"

    def test_equality(self):
        """测试相等性比较"""
        a1 = AssetSpec.from_code("000001.SZ")
        a2 = AssetSpec.from_code("000001.SZ")
        a3 = AssetSpec.from_code("600000.SH")
        assert a1 == a2
        assert a1 != a3

    def test_hash(self):
        """测试哈希值"""
        a1 = AssetSpec.from_code("000001.SZ")
        a2 = AssetSpec.from_code("000001.SZ")
        assert hash(a1) == hash(a2)
        # 可用于集合和字典
        s = {a1, a2}
        assert len(s) == 1


class TestTimeframe:
    """Timeframe 测试"""

    def test_timeframe_values(self):
        """测试周期枚举值"""
        assert Timeframe.M1.value == "1m"
        assert Timeframe.M5.value == "5m"
        assert Timeframe.D1.value == "1d"
        assert Timeframe.W1.value == "1w"
        assert Timeframe.MO1.value == "1mo"

    def test_timeframe_comparison(self):
        """测试周期比较"""
        assert Timeframe.M1 < Timeframe.M5
        assert Timeframe.M5 < Timeframe.D1
        assert Timeframe.D1 < Timeframe.W1
        assert Timeframe.D1 >= Timeframe.M1

    def test_timeframe_from_string(self):
        """测试从字符串创建"""
        assert Timeframe("1m") == Timeframe.M1
        assert Timeframe("1d") == Timeframe.D1


class TestAdjustType:
    """AdjustType 测试"""

    def test_adjust_values(self):
        """测试复权类型枚举值"""
        assert AdjustType.NONE.value == "none"
        assert AdjustType.FORWARD.value == "qfq"
        assert AdjustType.BACKWARD.value == "hfq"


class TestTimeRange:
    """TimeRange 测试"""

    def test_last_days(self):
        """测试最近N天"""
        tr = TimeRange.last_days(30)
        assert tr.start is not None
        assert tr.end is not None
        assert tr.limit is None
        # 检查起始日期在合理范围内
        expected_start = datetime.now() - timedelta(days=30)
        assert abs((tr.start - expected_start).total_seconds()) < 60

    def test_last_n(self):
        """测试最近N条"""
        tr = TimeRange.last_n(100)
        assert tr.start is None
        assert tr.end is None
        assert tr.limit == 100

    def test_between(self):
        """测试时间区间"""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        tr = TimeRange.between(start, end)
        assert tr.start == start
        assert tr.end == end
        assert tr.limit is None

    def test_between_no_end(self):
        """测试时间区间无结束时间"""
        start = datetime(2024, 1, 1)
        tr = TimeRange.between(start)
        assert tr.start == start
        assert tr.end is not None  # 默认为 now

    def test_is_bounded(self):
        """测试是否有时间边界"""
        tr1 = TimeRange.last_days(30)
        assert tr1.is_bounded() is True

        tr2 = TimeRange.last_n(100)
        assert tr2.is_bounded() is False

    def test_is_limited(self):
        """测试是否有条数限制"""
        tr1 = TimeRange.last_n(100)
        assert tr1.is_limited() is True

        tr2 = TimeRange.last_days(30)
        assert tr2.is_limited() is False


class TestLatencyHint:
    """LatencyHint 测试"""

    def test_latency_hints(self):
        """测试延迟提示枚举"""
        assert LatencyHint.REALTIME.value == "realtime"
        assert LatencyHint.LOW.value == "low"
        assert LatencyHint.NORMAL.value == "normal"
        assert LatencyHint.BATCH.value == "batch"
