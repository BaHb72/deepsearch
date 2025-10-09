"""
均值回归策略
基于布林带和RSI的统计套利策略
"""

import backtrader as bt


class MeanReversionStrategy(bt.Strategy):
    """
    均值回归策略

    策略逻辑：
    1. 价格触及布林带下轨且RSI超卖时买入
    2. 价格触及布林带上轨且RSI超买时卖出
    3. 价格回归到均线附近时平仓
    4. 使用标准差倍数作为入场和出场信号
    """

    params = (
        ("bb_period", 20),  # 布林带周期
        ("bb_devfactor", 2.0),  # 布林带标准差倍数
        ("rsi_period", 14),  # RSI周期
        ("rsi_oversold", 30),  # RSI超卖阈值
        ("rsi_overbought", 70),  # RSI超买阈值
        ("position_size", None),  # 固定仓位大小（None表示使用百分比）
        ("position_pct", 0.95),  # 使用资金的百分比
        ("stop_loss", 0.03),  # 止损 3%
        ("take_profit_ratio", 0.5),  # 止盈位置（相对于布林带宽度）
        ("min_bb_width", 0.01),  # 最小布林带宽度（避免低波动期）
        ("printlog", False),  # 打印日志
    )

    def __init__(self):
        """初始化策略"""
        self.dataclose = self.datas[0].close

        # 布林带
        self.bbands = bt.indicators.BollingerBands(
            self.datas[0], period=self.params.bb_period, devfactor=self.params.bb_devfactor
        )

        # RSI
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)

        # 布林带宽度（用于判断市场波动性）
        self.bb_width = self.bbands.top - self.bbands.bot
        self.bb_width_pct = self.bb_width / self.bbands.mid

        # Z-Score（标准化指标）
        self.zscore = (self.dataclose - self.bbands.mid) / (self.bbands.top - self.bbands.mid)

        # 成交量指标
        self.volume_sma = bt.indicators.SMA(self.datas[0].volume, period=20)

        # MACD用于趋势确认
        self.macd = bt.indicators.MACD(self.datas[0])

        # 记录
        self.order = None
        self.entry_price = 0
        self.entry_type = None  # 'long' or 'short'
        self.trades_count = 0

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.entry_type = "long"
                if self.params.printlog:
                    self.log(
                        f"买入执行: 价格={order.executed.price:.2f}, " f"RSI={self.rsi[0]:.2f}"
                    )
            else:
                if self.params.printlog:
                    self.log(f"卖出执行: 价格={order.executed.price:.2f}")
                self.entry_type = None
                self.entry_price = 0

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.printlog:
                self.log("订单取消/保证金不足/拒绝")

        self.order = None

    def notify_trade(self, trade):
        """交易通知"""
        if trade.isclosed:
            self.trades_count += 1
            if self.params.printlog:
                self.log(
                    f"交易关闭 #{self.trades_count}: "
                    f"毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f}"
                )

    def next(self):
        """策略主逻辑"""
        # 检查待处理订单
        if self.order:
            return

        # 检查布林带宽度（避免在低波动期交易）
        if self.bb_width_pct[0] < self.params.min_bb_width:
            return

        # 当前价格位置
        price = self.dataclose[0]
        bb_upper = self.bbands.top[0]
        bb_middle = self.bbands.mid[0]
        bb_lower = self.bbands.bot[0]
        rsi_value = self.rsi[0]

        # 没有持仓
        if not self.position:
            # 买入信号：价格接近下轨且RSI超卖
            if price <= bb_lower * 1.01 and rsi_value < self.params.rsi_oversold:
                # 额外确认：成交量放大
                if self.datas[0].volume[0] > self.volume_sma[0] * 1.2:
                    if self.params.printlog:
                        self.log(
                            f"买入信号: 价格{price:.2f}接近下轨{bb_lower:.2f}, "
                            f"RSI={rsi_value:.2f}"
                        )

                    size = self.calculate_position_size()
                    self.order = self.buy(size=size)

            # 做空信号（如果支持）：价格接近上轨且RSI超买
            # 注意：A股不支持做空，这里仅作示例
            elif price >= bb_upper * 0.99 and rsi_value > self.params.rsi_overbought:
                if self.params.printlog:
                    self.log(
                        f"卖空信号: 价格{price:.2f}接近上轨{bb_upper:.2f}, " f"RSI={rsi_value:.2f}"
                    )
                # 如果支持做空：self.order = self.sell(size=size)

        else:
            # 有多头持仓
            if self.entry_type == "long":
                # 止损
                if price < self.entry_price * (1 - self.params.stop_loss):
                    if self.params.printlog:
                        self.log(
                            f"多头止损: 价格{price:.2f} < "
                            f"止损价{self.entry_price * (1 - self.params.stop_loss):.2f}"
                        )
                    self.order = self.close()

                # 止盈：价格回归到中线附近
                elif price >= bb_middle * 0.98:
                    profit_pct = (price - self.entry_price) / self.entry_price
                    if profit_pct > 0.01:  # 至少1%利润
                        if self.params.printlog:
                            self.log(
                                f"均值回归止盈: 价格{price:.2f}接近中线{bb_middle:.2f}, "
                                f"利润{profit_pct*100:.2f}%"
                            )
                        self.order = self.close()

                # 反转信号：触及上轨
                elif price >= bb_upper and rsi_value > self.params.rsi_overbought:
                    if self.params.printlog:
                        self.log("反转信号平仓: 价格触及上轨")
                    self.order = self.close()

    def calculate_position_size(self):
        """计算仓位大小"""
        # 如果指定了固定仓位且不为None，使用固定值
        if self.params.position_size is not None:
            return self.params.position_size

        # 否则使用百分比方式
        cash = self.broker.getcash()
        price = self.dataclose[0]

        # 使用position_pct参数（默认0.95，即95%）
        position_value = cash * self.params.position_pct
        size = int(position_value / price / 100) * 100

        # 根据RSI调整仓位（RSI越低，仓位越大）
        if self.rsi[0] < 20:
            size = int(size * 1.5 / 100) * 100
        elif self.rsi[0] < 25:
            size = int(size * 1.2 / 100) * 100

        return max(size, 100)  # 至少100股

    def log(self, txt, dt=None):
        """日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def stop(self):
        """策略结束"""
        if self.params.printlog:
            if self.trades_count > 0:
                # 计算胜率等统计信息
                pass

            self.log(
                f"均值回归策略结束 - BB周期: {self.params.bb_period}, "
                f"RSI周期: {self.params.rsi_period}, "
                f"最终价值: {self.broker.getvalue():.2f}, "
                f"交易次数: {self.trades_count}"
            )
