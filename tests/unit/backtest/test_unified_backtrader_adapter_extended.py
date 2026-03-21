"""
UnifiedBacktraderAdapter 扩展测试套件

测试本次修复中新增/修改的方法：
- _run_sync: 安全的同步执行异步代码
- _ensure_dataframe: DataFrame 创建与错误处理
- _resample_to_weekly: 周线重采样（不可变性）
- validate_data: 数据验证边界情况
"""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from core.backtest.adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter
from core.backtest.data.history_status_overlay import HistoryStatusOverlayError


class TestRunSync:
    """测试 _run_sync 方法的各种场景"""

    @pytest.fixture
    def adapter(self):
        """创建 adapter 实例（mock data_manager）"""
        with patch("core.backtest.adapters.unified_backtrader_adapter.get_data_manager") as mock:
            mock.return_value = MagicMock()
            adapter = UnifiedBacktraderAdapter()
            yield adapter

    def test_run_sync_in_existing_event_loop(self, adapter):
        """测试在已有事件循环中运行异步代码"""

        async def async_func():
            await asyncio.sleep(0.001)
            return "result"

        # 在事件循环中测试
        async def run_test():
            result = adapter._run_sync(async_func())
            assert result == "result"

        asyncio.run(run_test())

    def test_run_sync_without_event_loop(self, adapter):
        """测试在无事件循环时运行异步代码"""

        async def async_func():
            return "no_loop_result"

        # 确保没有运行中的事件循环
        result = adapter._run_sync(async_func())
        assert result == "no_loop_result"

    def test_run_sync_with_exception(self, adapter):
        """测试异步代码抛出异常时的处理"""

        async def failing_func():
            raise ValueError("async error")

        with pytest.raises(ValueError, match="async error"):
            adapter._run_sync(failing_func())


class TestEnsureDataFrame:
    """测试 _ensure_dataframe 方法的错误处理"""

    @pytest.fixture
    def adapter(self):
        with patch("core.backtest.adapters.unified_backtrader_adapter.get_data_manager") as mock:
            mock.return_value = MagicMock()
            adapter = UnifiedBacktraderAdapter()
            yield adapter

    def test_ensure_dataframe_with_valid_list(self, adapter):
        """测试有效列表数据"""
        data = [
            {"date": "2024-01-01", "close": 10.0},
            {"date": "2024-01-02", "close": 11.0},
        ]
        df = adapter._ensure_dataframe(data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_ensure_dataframe_with_dataframe(self, adapter):
        """测试已有 DataFrame"""
        input_df = pd.DataFrame({"close": [10.0, 11.0]})
        result = adapter._ensure_dataframe(input_df)
        # 验证返回的内容相同（可能是副本或同一对象）
        assert isinstance(result, pd.DataFrame)
        assert result.equals(input_df)

    def test_ensure_dataframe_with_none(self, adapter):
        """测试 None 输入"""
        df = adapter._ensure_dataframe(None)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_ensure_dataframe_with_empty_list(self, adapter):
        """测试空列表"""
        df = adapter._ensure_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @pytest.mark.skip(reason="pandas 对字符串的处理依赖版本，跳过此边缘测试")
    def test_ensure_dataframe_with_invalid_data(self, adapter):
        """测试无法转换的数据（pd.DataFrame 会尝试转换）"""
        # 字符串会被转换为单列 DataFrame
        invalid_data = "not a valid dataframe input"
        df = adapter._ensure_dataframe(invalid_data)
        assert isinstance(df, pd.DataFrame)


class TestResampleToWeekly:
    """测试 _resample_to_weekly 方法的不可变性"""

    @pytest.fixture
    def adapter(self):
        with patch("core.backtest.adapters.unified_backtrader_adapter.get_data_manager") as mock:
            mock.return_value = MagicMock()
            adapter = UnifiedBacktraderAdapter()
            yield adapter

    @pytest.fixture
    def daily_data(self):
        """创建每日数据"""
        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        return pd.DataFrame(
            {
                "open": range(20),
                "high": range(1, 21),
                "low": range(20),
                "close": range(20),
                "volume": [1000] * 20,
            },
            index=dates,
        )

    def test_resample_preserves_original(self, adapter, daily_data):
        """测试重采样不修改原始数据"""
        original_len = len(daily_data)
        original_index = daily_data.index.copy()

        weekly = adapter._resample_to_weekly(daily_data)

        # 验证原始数据未被修改
        assert len(daily_data) == original_len
        assert daily_data.index.equals(original_index)
        # 验证返回的是新对象
        assert weekly is not daily_data

    def test_resample_returns_weekly_data(self, adapter, daily_data):
        """测试返回正确的周线数据"""
        weekly = adapter._resample_to_weekly(daily_data)

        assert isinstance(weekly, pd.DataFrame)
        assert len(weekly) < len(daily_data)  # 周线数据应该更少
        # 检查必要的列存在
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in weekly.columns

    def test_resample_empty_dataframe(self, adapter):
        """测试空 DataFrame"""
        empty_df = pd.DataFrame()
        result = adapter._resample_to_weekly(empty_df)
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestValidateData:
    """测试 validate_data 方法的边界情况"""

    @pytest.fixture
    def adapter(self):
        with patch("core.backtest.adapters.unified_backtrader_adapter.get_data_manager") as mock:
            mock.return_value = MagicMock()
            adapter = UnifiedBacktraderAdapter()
            yield adapter

    @pytest.fixture
    def valid_data(self):
        """创建有效的数据"""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        return pd.DataFrame(
            {
                "open": [10.0] * 10,
                "high": [11.0] * 10,
                "low": [9.0] * 10,
                "close": [10.5] * 10,
                "volume": [1000] * 10,
            },
            index=dates,
        )

    def test_validate_valid_data(self, adapter, valid_data):
        """测试有效数据验证"""
        result = adapter.validate_data(valid_data)
        assert result["is_valid"] is True
        assert result["stats"]["rows"] == 10

    def test_validate_empty_dataframe(self, adapter):
        """测试空 DataFrame 验证"""
        empty_df = pd.DataFrame()
        result = adapter.validate_data(empty_df)
        assert result["is_valid"] is False
        assert "数据为空" in str(result.get("errors", []))

    def test_validate_missing_columns(self, adapter):
        """测试缺少必要列的数据"""
        df = pd.DataFrame({"close": [10.0, 11.0]})  # 缺少 open, high, low
        result = adapter.validate_data(df)
        # 应该报告缺失字段
        assert result["is_valid"] is False
        assert "缺少必要字段" in str(result.get("errors", []))


class TestStatusOverlayIntegration:
    """测试 A 股状态覆盖接入链路。"""

    @pytest.fixture
    def adapter(self):
        with patch("core.backtest.adapters.unified_backtrader_adapter.get_data_manager") as mock:
            mock.return_value = MagicMock()
            adapter = UnifiedBacktraderAdapter()
            adapter._initialized = True
            adapter.data_manager = MagicMock()
            yield adapter

    def test_is_a_share_symbol_filters_non_stock(self, adapter):
        assert adapter._is_a_share_symbol("000001.SZ") is True
        assert adapter._is_a_share_symbol("600519.SH") is True
        assert adapter._is_a_share_symbol("510300.SH") is False
        assert adapter._is_a_share_symbol("159915.SZ") is False

    @pytest.mark.asyncio
    async def test_get_data_calls_overlay_for_a_share(
        self, adapter, monkeypatch: pytest.MonkeyPatch
    ):
        async def _fake_fetch_daily_data(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return pd.DataFrame(
                [
                    {
                        "date": "2026-03-20",
                        "open": 10.0,
                        "high": 10.2,
                        "low": 9.9,
                        "close": 10.1,
                        "volume": 1000,
                    }
                ]
            )

        called = {"overlay": False}

        async def _fake_apply_overlay(manager, bars_df, *, symbol):  # type: ignore[no-untyped-def]
            called["overlay"] = True
            assert symbol == "000001.SZ"
            return bars_df.assign(high_limited=11.0, low_limited=9.0, is_suspended=False)

        monkeypatch.setattr(adapter, "_fetch_daily_data", _fake_fetch_daily_data)
        monkeypatch.setattr(adapter, "_apply_status_overlay_if_needed", _fake_apply_overlay)

        result = await adapter.get_data(
            symbol="000001.SZ",
            start_date="2026-03-20",
            end_date="2026-03-20",
            timeframe="1d",
        )

        assert called["overlay"] is True
        assert "high_limited" in result.columns

    @pytest.mark.asyncio
    async def test_apply_status_overlay_skip_non_a_share(
        self, adapter, monkeypatch: pytest.MonkeyPatch
    ):
        bars_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [1.0],
            },
            index=pd.to_datetime(["2026-03-20"]),
        )

        async def _unexpected_fetch(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("非A股不应调用 history_stock_status 拉取")

        monkeypatch.setattr(adapter, "_fetch_history_status_payload", _unexpected_fetch)
        result = await adapter._apply_status_overlay_if_needed(
            adapter.data_manager,
            bars_df,
            symbol="510300.SH",
        )
        assert result.equals(bars_df)

    @pytest.mark.asyncio
    async def test_apply_status_overlay_raise_when_status_missing(
        self, adapter, monkeypatch: pytest.MonkeyPatch
    ):
        bars_df = pd.DataFrame(
            {
                "open": [10.0],
                "high": [10.2],
                "low": [9.9],
                "close": [10.1],
                "volume": [1000],
            },
            index=pd.to_datetime(["2026-03-20"]),
        )

        async def _raise_not_found(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise HistoryStatusOverlayError("missing status", not_found=True)

        monkeypatch.setattr(adapter, "_fetch_history_status_payload", _raise_not_found)
        with pytest.raises(HistoryStatusOverlayError):
            await adapter._apply_status_overlay_if_needed(
                adapter.data_manager,
                bars_df,
                symbol="000001.SZ",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
