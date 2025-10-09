"""
动量策略
基于价格和成交量的动量突破策略
"""

import backtrader as bt


class OBV(bt.Indicator):
    """
    自定义 On Balance Volume (OBV) 指标

    OBV 是一个基于成交量的技术指标，用于测量买卖压力。
    - 当价格上涨时，将成交量加到OBV
    - 当价格下跌时，从OBV中减去成交量
    - 当价格不变时，OBV保持不变
    """

    alias = ("OnBalanceVolume",)
    lines = ("obv",)

    plotlines = dict(obv=dict(_name="OBV", color="purple", alpha=0.50))

    def __init__(self):
        # 设置水平参考线
        self.plotinfo.plotyhlines = [0]

    def next(self):
        # 如果是第一个数据点
        if len(self) == 1:
            self.lines.obv[0] = self.data.volume[0]
        else:
            # 根据价格变化计算OBV
            if self.data.close[0] > self.data.close[-1]:
                # 价格上涨，加上成交量
                self.lines.obv[0] = self.lines.obv[-1] + self.data.volume[0]
            elif self.data.close[0] < self.data.close[-1]:
                # 价格下跌，减去成交量
                self.lines.obv[0] = self.lines.obv[-1] - self.data.volume[0]
            else:
                # 价格不变，OBV保持不变
                self.lines.obv[0] = self.lines.obv[-1]


class MomentumStrategy(bt.Strategy):
    """
    动量策略

    策略逻辑：
    1. 计算价格动量（ROC）和成交量动量
    2. 当价格突破新高且动量强劲时买入
    3. 使用ATR跟踪止损
    4. 动量衰减或跌破止损时卖出
    """

    params = (
        ("momentum_period", 20),  # 动量计算周期
        ("volume_period", 20),  # 成交量均值周期
        ("breakout_period", 50),  # 突破周期（新高）
        ("atr_period", 14),  # ATR周期
        ("atr_multiplier", 2.0),  # ATR止损倍数
        ("momentum_threshold", 0.05),  # 动量阈值 5%
        ("volume_multiplier", 1.5),  # 成交量放大倍数
        ("max_holding_period", 60),  # 最大持仓天数
        ("position_size", None),  # 固定仓位大小（None表示使用百分比）
        ("position_pct", 0.95),  # 使用资金的百分比
        ("use_trailing_stop", True),  # 是否使用跟踪止损
        ("printlog", False),  # 打印日志
    )

    def __init__(self):
        """初始化策略"""
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume

        # 价格动量（ROC - Rate of Change）
        self.roc = bt.indicators.ROC(self.dataclose, period=self.params.momentum_period)

        # 成交量均值
        self.volume_sma = bt.indicators.SMA(self.datavolume, period=self.params.volume_period)

        # 价格新高
        self.highest = bt.indicators.Highest(self.datahigh, period=self.params.breakout_period)

        # ATR用于止损
        self.atr = bt.indicators.ATR(self.datas[0], period=self.params.atr_period)

        # 相对强弱（与市场比较，这里用移动平均代替）
        self.sma_short = bt.indicators.SMA(self.dataclose, period=20)
        self.sma_long = bt.indicators.SMA(self.dataclose, period=50)

        # MACD用于确认
        self.macd = bt.indicators.MACD(self.dataclose)

        # 威廉姆斯%R
        self.williams = bt.indicators.WilliamsR(self.datas[0], period=14)

        # OBV（On Balance Volume）能量潮 - 使用自定义OBV指标
        self.obv = OBV(self.datas[0])
        self.obv_sma = bt.indicators.SMA(self.obv, period=20)

        # 记录
        self.order = None
        self.entry_price = 0
        self.entry_date = None
        self.stop_loss = 0
        self.highest_price = 0
        self.holding_days = 0

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.stop_loss = self.entry_price - self.params.atr_multiplier * self.atr[0]
                self.highest_price = self.entry_price
                self.holding_days = 0

                if self.params.printlog:
                    self.log(
                        f"买入执行: 价格={order.executed.price:.2f}, "
                        f"动量={self.roc[0]:.2f}%, "
                        f"止损={self.stop_loss:.2f}"
                    )
            else:
                if self.params.printlog:
                    profit = (order.executed.price - self.entry_price) / self.entry_price * 100
                    self.log(
                        f"卖出执行: 价格={order.executed.price:.2f}, "
                        f"收益={profit:.2f}%, "
                        f"持仓天数={self.holding_days}"
                    )

                self.entry_price = 0
                self.entry_date = None
                self.stop_loss = 0
                self.highest_price = 0
                self.holding_days = 0

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.printlog:
                self.log("订单取消/保证金不足/拒绝")

        self.order = None

    def next(self):
        """策略主逻辑"""
        # 检查待处理订单
        if self.order:
            return

        # 更新持仓天数
        if self.position:
            self.holding_days += 1

        # 当前指标值
        price = self.dataclose[0]
        momentum = self.roc[0] / 100  # 转换为小数
        volume_ratio = self.datavolume[0] / self.volume_sma[0] if self.volume_sma[0] > 0 else 1

        # 没有持仓
        if not self.position:
            # 买入条件
            # 1. 价格突破新高
            is_breakout = self.datahigh[0] >= self.highest[-1] * 0.995

            # 2. 动量强劲
            is_strong_momentum = momentum > self.params.momentum_threshold

            # 3. 成交量放大
            is_volume_surge = volume_ratio > self.params.volume_multiplier

            # 4. 技术面确认
            is_trend_up = self.sma_short[0] > self.sma_long[0]
            is_macd_positive = self.macd.macd[0] > self.macd.signal[0]
            self.obv[0] > self.obv_sma[0]

            # 综合判断
            if (
                is_breakout
                and is_strong_momentum
                and is_volume_surge
                and is_trend_up
                and is_macd_positive
            ):

                if self.params.printlog:
                    self.log(
                        f"动量买入信号: 价格{price:.2f}, "
                        f"动量{momentum*100:.2f}%, "
                        f"成交量比{volume_ratio:.2f}"
                    )

                size = self.calculate_position_size()
                self.order = self.buy(size=size)

        else:
            # 有持仓
            # 更新跟踪止损
            if self.params.use_trailing_stop:
                if price > self.highest_price:
                    self.highest_price = price
                    new_stop = price - self.params.atr_multiplier * self.atr[0]
                    self.stop_loss = max(self.stop_loss, new_stop)

            # 卖出条件
            sell_signal = False
            sell_reason = ""

            # 1. 止损
            if price <= self.stop_loss:
                sell_signal = True
                sell_reason = f"止损: {price:.2f} <= {self.stop_loss:.2f}"

            # 2. 动量衰减
            elif momentum < -self.params.momentum_threshold * 0.5:
                sell_signal = True
                sell_reason = f"动量衰减: {momentum*100:.2f}%"

            # 3. 超过最大持仓期
            elif self.holding_days >= self.params.max_holding_period:
                sell_signal = True
                sell_reason = f"超过最大持仓期: {self.holding_days}天"

            # 4. 技术面转弱
            elif self.macd.macd[0] < self.macd.signal[0] and self.williams[0] > -20:  # 超买
                sell_signal = True
                sell_reason = "技术面转弱"

            # 5. 成交量萎缩（动量耗尽）
            elif volume_ratio < 0.5 and momentum < 0:
                sell_signal = True
                sell_reason = "成交量萎缩"

            if sell_signal:
                if self.params.printlog:
                    self.log(f"卖出信号: {sell_reason}")
                self.order = self.close()

    def calculate_position_size(self):
        """计算仓位大小"""
        cash = self.broker.getcash()
        price = self.dataclose[0]

        # 基于动量强度调整仓位
        momentum_factor = min(abs(self.roc[0]) / 10, 2.0)  # 最多2倍

        # 基础仓位为资金的25%
        base_size = int((cash * 0.25) / price / 100) * 100

        # 根据动量调整
        adjusted_size = int(base_size * momentum_factor / 100) * 100

        # 限制最大仓位
        final_size = min(adjusted_size, self.params.position_size)

        return max(final_size, 100)  # 至少100股

    def log(self, txt, dt=None):
        """日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def stop(self):
        """策略结束"""
        if self.params.printlog:
            self.log(
                f"动量策略结束 - 动量周期: {self.params.momentum_period}, "
                f"突破周期: {self.params.breakout_period}, "
                f"最终价值: {self.broker.getvalue():.2f}"
            )
