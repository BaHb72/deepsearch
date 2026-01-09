# encoding:utf-8
"""
Test Strategies for Data Validation
数据验证测试策略 - 用于验证数据准确性
Author: DeepSearch Team
Version: 1.0.0
"""

from types import ModuleType, SimpleNamespace
from typing import cast

from loguru import logger

try:
    import backtrader as bt
    import backtrader.indicators as btind

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    fallback_strategy = type("FallbackStrategy", (), {"params": ()})
    bt = cast(ModuleType, SimpleNamespace(Strategy=fallback_strategy))
    btind = cast(
        ModuleType,
        SimpleNamespace(
            SimpleMovingAverage=object,
            ExponentialMovingAverage=object,
            RelativeStrengthIndex=object,
            MACD=object,
            BollingerBands=object,
            AverageTrueRange=object,
        ),
    )


class DataValidationStrategy(bt.Strategy):
    """
    数据验证策略

    用于验证数据的完整性和准确性
    """

    params = (
        ("printlog", True),
        ("check_ohlc", True),
        ("check_volume", True),
        ("check_gaps", True),
    )

    def __init__(self):
        """初始化策略"""
        self.data_errors = []
        self.data_warnings = []
        self.stats = {
            "total_bars": 0,
            "valid_bars": 0,
            "ohlc_errors": 0,
            "volume_errors": 0,
            "gap_warnings": 0,
            "max_gap": 0,
            "min_price": float("inf"),
            "max_price": 0,
        }

        # 记录第一个和最后一个数据点
        self.first_date = None
        self.last_date = None

    def log(self, txt, dt=None):
        """日志函数"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            logger.info(f"{dt.isoformat()} {txt}")

    def next(self):
        """处理每个数据点"""
        current_date = self.data.datetime.date(0)

        # 记录第一个日期
        if self.first_date is None:
            self.first_date = current_date
        self.last_date = current_date

        # 更新统计
        self.stats["total_bars"] += 1

        # 获取OHLCV数据
        o = self.data.open[0]
        h = self.data.high[0]
        low = self.data.low[0]
        c = self.data.close[0]
        v = self.data.volume[0] if len(self.data.volume) else 0

        is_valid = True

        # 检查OHLC关系
        if self.params.check_ohlc:
            # High应该是最高价
            if h < max(o, c):
                self.data_errors.append(f"{current_date}: High({h}) < Max(Open({o}), Close({c}))")
                self.stats["ohlc_errors"] += 1
                is_valid = False

            # Low应该是最低价
            if low > min(o, c):
                self.data_errors.append(f"{current_date}: Low({low}) > Min(Open({o}), Close({c}))")
                self.stats["ohlc_errors"] += 1
                is_valid = False

            # High >= Low
            if h < low:
                self.data_errors.append(f"{current_date}: High({h}) < Low({low})")
                self.stats["ohlc_errors"] += 1
                is_valid = False

            # 所有价格应该为正
            if any(p <= 0 for p in [o, h, low, c]):
                self.data_errors.append(f"{current_date}: 发现负价格或零价格")
                self.stats["ohlc_errors"] += 1
                is_valid = False

        # 检查成交量
        if self.params.check_volume:
            if v < 0:
                self.data_errors.append(f"{current_date}: 负成交量 ({v})")
                self.stats["volume_errors"] += 1
                is_valid = False
            elif v == 0:
                self.data_warnings.append(f"{current_date}: 零成交量")
                self.stats["volume_errors"] += 1

        # 检查价格跳空
        if self.params.check_gaps and len(self.data.close) > 1:
            prev_close = self.data.close[-1]
            gap = abs(o - prev_close) / prev_close

            if gap > 0.11:  # 11%涨跌停
                self.data_warnings.append(f"{current_date}: 大幅跳空 {gap:.2%}")
                self.stats["gap_warnings"] += 1

            self.stats["max_gap"] = max(self.stats["max_gap"], gap)

        # 更新价格范围
        self.stats["min_price"] = min(self.stats["min_price"], low)
        self.stats["max_price"] = max(self.stats["max_price"], h)

        if is_valid:
            self.stats["valid_bars"] += 1

    def stop(self):
        """策略结束时的处理"""
        # 计算有效率
        if self.stats["total_bars"] > 0:
            valid_rate = self.stats["valid_bars"] / self.stats["total_bars"]
            self.stats["valid_rate"] = valid_rate
        else:
            self.stats["valid_rate"] = 0

        # 打印汇总
        if self.params.printlog:
            self.log("=" * 60)
            self.log("数据验证完成")
            self.log(f"数据范围: {self.first_date} 至 {self.last_date}")
            self.log(f'总数据点: {self.stats["total_bars"]}')
            self.log(f'有效数据点: {self.stats["valid_bars"]} ({self.stats["valid_rate"]:.1%})')
            self.log(f'OHLC错误: {self.stats["ohlc_errors"]}')
            self.log(f'成交量错误: {self.stats["volume_errors"]}')
            self.log(f'跳空警告: {self.stats["gap_warnings"]}')
            self.log(f'最大跳空: {self.stats["max_gap"]:.2%}')
            self.log(f'价格范围: {self.stats["min_price"]:.2f} - {self.stats["max_price"]:.2f}')

            if self.data_errors:
                self.log(f"发现 {len(self.data_errors)} 个错误")
                for error in self.data_errors[:5]:  # 只显示前5个
                    self.log(f"  - {error}")

            if self.data_warnings:
                self.log(f"发现 {len(self.data_warnings)} 个警告")

            self.log("=" * 60)


class ComparisonStrategy(bt.Strategy):
    """
    数据源对比策略

    对比多个数据源的数据差异
    """

    params = (
        ("tolerance", 0.01),  # 价格容差 1%
        ("printlog", True),
    )

    def __init__(self):
        """初始化策略"""
        self.price_diffs = []
        self.volume_diffs = []
        self.missing_dates = []
        self.stats = {
            "common_bars": 0,
            "price_matches": 0,
            "volume_matches": 0,
            "max_price_diff": 0,
            "max_volume_diff": 0,
            "avg_price_diff": 0,
            "avg_volume_diff": 0,
        }

    def log(self, txt, dt=None):
        """日志函数"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            logger.info(f"{dt.isoformat()} {txt}")

    def next(self):
        """处理每个数据点"""
        if len(self.datas) < 2:
            return

        current_date = self.datas[0].datetime.date(0)

        # 检查所有数据源是否都有当前日期的数据
        all_have_data = True
        for data in self.datas:
            if len(data) == 0:
                all_have_data = False
                break

        if not all_have_data:
            self.missing_dates.append(current_date)
            return

        self.stats["common_bars"] += 1

        # 获取基准数据源的价格
        base_open = self.datas[0].open[0]
        base_high = self.datas[0].high[0]
        base_low = self.datas[0].low[0]
        base_close = self.datas[0].close[0]
        base_volume = self.datas[0].volume[0] if len(self.datas[0].volume) else 0

        # 对比其他数据源
        for i, data in enumerate(self.datas[1:], 1):
            comp_open = data.open[0]
            comp_high = data.high[0]
            comp_low = data.low[0]
            comp_close = data.close[0]
            comp_volume = data.volume[0] if len(data.volume) else 0

            # 计算价格差异
            price_diffs = [
                abs(base_open - comp_open) / base_open if base_open != 0 else 0,
                abs(base_high - comp_high) / base_high if base_high != 0 else 0,
                abs(base_low - comp_low) / base_low if base_low != 0 else 0,
                abs(base_close - comp_close) / base_close if base_close != 0 else 0,
            ]

            max_price_diff = max(price_diffs)
            avg_price_diff = sum(price_diffs) / len(price_diffs)

            self.price_diffs.append(
                {
                    "date": current_date,
                    "source": i,
                    "max_diff": max_price_diff,
                    "avg_diff": avg_price_diff,
                }
            )

            # 更新统计
            if max_price_diff < self.params.tolerance:
                self.stats["price_matches"] += 1

            self.stats["max_price_diff"] = max(self.stats["max_price_diff"], max_price_diff)

            # 计算成交量差异
            if base_volume > 0:
                volume_diff = abs(base_volume - comp_volume) / base_volume
                self.volume_diffs.append({"date": current_date, "source": i, "diff": volume_diff})

                if volume_diff < 0.5:  # 成交量允许50%差异
                    self.stats["volume_matches"] += 1

                self.stats["max_volume_diff"] = max(self.stats["max_volume_diff"], volume_diff)

    def stop(self):
        """策略结束时的处理"""
        # 计算平均差异
        if self.price_diffs:
            self.stats["avg_price_diff"] = sum(d["avg_diff"] for d in self.price_diffs) / len(
                self.price_diffs
            )

        if self.volume_diffs:
            self.stats["avg_volume_diff"] = sum(d["diff"] for d in self.volume_diffs) / len(
                self.volume_diffs
            )

        # 计算匹配率
        total_comparisons = self.stats["common_bars"] * (len(self.datas) - 1)
        if total_comparisons > 0:
            self.stats["price_match_rate"] = self.stats["price_matches"] / total_comparisons
            self.stats["volume_match_rate"] = self.stats["volume_matches"] / total_comparisons
        else:
            self.stats["price_match_rate"] = 0
            self.stats["volume_match_rate"] = 0

        # 打印结果
        if self.params.printlog:
            self.log("=" * 60)
            self.log("数据源对比完成")
            self.log(f"数据源数量: {len(self.datas)}")
            self.log(f'共同数据点: {self.stats["common_bars"]}')
            self.log(f"缺失日期: {len(self.missing_dates)}")
            self.log(f'价格匹配率: {self.stats["price_match_rate"]:.1%}')
            self.log(f'成交量匹配率: {self.stats["volume_match_rate"]:.1%}')
            self.log(f'最大价格差异: {self.stats["max_price_diff"]:.2%}')
            self.log(f'平均价格差异: {self.stats["avg_price_diff"]:.2%}')
            self.log(f'最大成交量差异: {self.stats["max_volume_diff"]:.2%}')
            self.log(f'平均成交量差异: {self.stats["avg_volume_diff"]:.2%}')

            # 显示差异最大的日期
            if self.price_diffs:
                sorted_diffs = sorted(self.price_diffs, key=lambda x: x["max_diff"], reverse=True)
                self.log("价格差异最大的日期:")
                for diff in sorted_diffs[:5]:
                    self.log(
                        f'  {diff["date"]}: 数据源{diff["source"]} 差异 {diff["max_diff"]:.2%}'
                    )

            self.log("=" * 60)


class SimpleTestStrategy(bt.Strategy):
    """
    简单测试策略

    用于测试数据的可交易性
    """

    params = (
        ("maperiod", 20),
        ("printlog", True),
    )

    def __init__(self):
        """初始化策略"""
        # 添加移动平均线指标
        self.sma = btind.SimpleMovingAverage(self.datas[0], period=self.params.maperiod)

        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0

    def log(self, txt, dt=None):
        """日志函数"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            logger.info(f"{dt.isoformat()} {txt}")

    def next(self):
        """处理每个数据点"""
        # 简单的均线策略
        if not self.position:
            if self.data.close[0] > self.sma[0]:
                # 买入信号
                self.buy()
                self.trade_count += 1
        else:
            if self.data.close[0] < self.sma[0]:
                # 卖出信号
                self.sell()

    def notify_trade(self, trade):
        """交易通知"""
        if trade.isclosed:
            if trade.pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1

            self.total_pnl += trade.pnl

            if self.params.printlog:
                self.log(f"交易完成 - 盈亏: {trade.pnl:.2f}")

    def stop(self):
        """策略结束时的处理"""
        # 计算胜率
        if self.trade_count > 0:
            win_rate = self.win_count / self.trade_count
        else:
            win_rate = 0

        final_value = self.broker.getvalue()

        if self.params.printlog:
            self.log("=" * 60)
            self.log("简单策略测试完成")
            self.log(f"总交易次数: {self.trade_count}")
            self.log(f"获利交易: {self.win_count}")
            self.log(f"亏损交易: {self.loss_count}")
            self.log(f"胜率: {win_rate:.1%}")
            self.log(f"总盈亏: {self.total_pnl:.2f}")
            self.log(f"最终价值: {final_value:.2f}")
            self.log("=" * 60)

        self.stats = {
            "trades": self.trade_count,
            "wins": self.win_count,
            "losses": self.loss_count,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "final_value": final_value,
        }


class IndicatorTestStrategy(bt.Strategy):
    """
    技术指标测试策略

    测试各种技术指标的计算准确性
    """

    params = (("printlog", True),)

    def __init__(self):
        """初始化策略"""
        # 添加各种技术指标
        self.sma20 = btind.SimpleMovingAverage(self.datas[0], period=20)
        self.ema20 = btind.ExponentialMovingAverage(self.datas[0], period=20)
        self.rsi = btind.RelativeStrengthIndex(self.datas[0])
        self.macd = btind.MACD(self.datas[0])
        self.bb = btind.BollingerBands(self.datas[0])
        self.atr = btind.AverageTrueRange(self.datas[0])

        self.indicator_values = []

    def next(self):
        """处理每个数据点"""
        # 记录指标值
        self.indicator_values.append(
            {
                "date": self.data.datetime.date(0),
                "close": self.data.close[0],
                "sma20": self.sma20[0] if len(self.sma20) else None,
                "ema20": self.ema20[0] if len(self.ema20) else None,
                "rsi": self.rsi[0] if len(self.rsi) else None,
                "macd": self.macd.macd[0] if len(self.macd.macd) else None,
                "macd_signal": self.macd.signal[0] if len(self.macd.signal) else None,
                "bb_top": self.bb.top[0] if len(self.bb.top) else None,
                "bb_mid": self.bb.mid[0] if len(self.bb.mid) else None,
                "bb_bot": self.bb.bot[0] if len(self.bb.bot) else None,
                "atr": self.atr[0] if len(self.atr) else None,
            }
        )

    def stop(self):
        """策略结束时的处理"""
        # 验证指标计算
        valid_count = 0
        error_count = 0

        for values in self.indicator_values:
            # 检查指标值的合理性
            if values["rsi"] is not None:
                if 0 <= values["rsi"] <= 100:
                    valid_count += 1
                else:
                    error_count += 1
                    if self.params.printlog:
                        self.log(f"RSI异常值: {values['date']} = {values['rsi']}")

            # 检查布林带
            if all(v is not None for v in [values["bb_top"], values["bb_mid"], values["bb_bot"]]):
                if values["bb_top"] > values["bb_mid"] > values["bb_bot"]:
                    valid_count += 1
                else:
                    error_count += 1
                    if self.params.printlog:
                        self.log(f"布林带异常: {values['date']}")

        if self.params.printlog:
            self.log("=" * 60)
            self.log("技术指标测试完成")
            self.log(f"计算的指标数量: {len(self.indicator_values)}")
            self.log(f"有效指标: {valid_count}")
            self.log(f"异常指标: {error_count}")

            # 显示最后几个指标值
            if self.indicator_values:
                self.log("最近的指标值:")
                for values in self.indicator_values[-3:]:
                    self.log(
                        f"  {values['date']}: RSI={values['rsi']:.2f if values['rsi'] else 0}, "
                        f"SMA20={values['sma20']:.2f if values['sma20'] else 0}"
                    )

            self.log("=" * 60)
