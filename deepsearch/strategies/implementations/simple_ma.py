"""
简单均线策略
双均线交叉策略，金叉买入，死叉卖出
"""

import backtrader as bt


class SimpleMAStrategy(bt.Strategy):
    """
    简单移动平均线策略

    策略逻辑：
    1. 短期均线上穿长期均线时买入（金叉）
    2. 短期均线下穿长期均线时卖出（死叉）
    3. 支持止损和止盈
    """

    params = (
        ("short_period", 10),  # 短期均线周期
        ("long_period", 30),  # 长期均线周期
        ("position_size", None),  # 固定交易股数（None表示使用百分比）
        ("position_pct", 0.95),  # 使用资金的百分比（95%）
        ("stop_loss", 0.05),  # 止损比例 5%
        ("take_profit", 0.15),  # 止盈比例 15%
        ("printlog", False),  # 是否打印日志
    )

    def __init__(self):
        """初始化策略"""
        # 保存数据引用
        self.dataclose = self.datas[0].close

        # 创建均线指标
        self.sma_short = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.short_period
        )
        self.sma_long = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.long_period
        )

        # 创建交叉信号
        self.crossover = bt.indicators.CrossOver(self.sma_short, self.sma_long)

        # 记录订单
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # 添加更多指标用于分析
        self.rsi = bt.indicators.RSI(self.datas[0], period=14)
        self.macd = bt.indicators.MACD(self.datas[0])
        self.bbands = bt.indicators.BollingerBands(self.datas[0])

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交/已接受
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                if self.params.printlog:
                    self.log(
                        f"买入执行, 价格: {order.executed.price:.2f}, "
                        f"成本: {order.executed.comm:.2f}"
                    )
            else:  # 卖出
                if self.params.printlog:
                    self.log(
                        f"卖出执行, 价格: {order.executed.price:.2f}, "
                        f"成本: {order.executed.comm:.2f}"
                    )

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.printlog:
                self.log("订单取消/保证金不足/拒绝")

        self.order = None

    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return

        if self.params.printlog:
            self.log(f"交易利润, 毛利润: {trade.pnl:.2f}, 净利润: {trade.pnlcomm:.2f}")

    def next(self):
        """策略主逻辑"""
        # 记录当前价格
        if self.params.printlog:
            self.log(f"Close: {self.dataclose[0]:.2f}")

        # 检查是否有待处理订单
        if self.order:
            return

        # 检查是否持仓
        if not self.position:
            # 没有持仓，检查买入信号
            if self.crossover[0] > 0:  # 金叉
                # 额外条件：RSI不能过高
                if self.rsi[0] < 70:
                    if self.params.printlog:
                        self.log(f"买入信号: 金叉, RSI={self.rsi[0]:.2f}")

                    # 使用百分比下单（推荐方式）
                    if self.params.position_size is None:
                        # 使用目标百分比，自动计算仓位
                        self.order_target_percent(target=self.params.position_pct)
                    else:
                        # 使用固定仓位
                        size = self.calculate_position_size()
                        self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # 1. 死叉卖出
            if self.crossover[0] < 0:
                if self.params.printlog:
                    self.log("卖出信号: 死叉")
                # 清仓
                self.order_target_percent(target=0)

            # 2. 止损
            elif self.dataclose[0] < self.buyprice * (1 - self.params.stop_loss):
                if self.params.printlog:
                    self.log(
                        f"止损卖出: 当前价{self.dataclose[0]:.2f} < "
                        f"止损价{self.buyprice * (1 - self.params.stop_loss):.2f}"
                    )
                # 清仓
                self.order_target_percent(target=0)

            # 3. 止盈
            elif self.dataclose[0] > self.buyprice * (1 + self.params.take_profit):
                if self.params.printlog:
                    self.log(
                        f"止盈卖出: 当前价{self.dataclose[0]:.2f} > "
                        f"止盈价{self.buyprice * (1 + self.params.take_profit):.2f}"
                    )
                # 清仓
                self.order_target_percent(target=0)

    def calculate_position_size(self):
        """计算仓位大小"""
        # 如果指定了固定仓位，使用固定值
        if self.params.position_size is not None:
            return self.params.position_size

        # 否则使用百分比计算
        cash = self.broker.getcash()
        price = self.dataclose[0]

        # 使用指定百分比的资金
        position_value = cash * self.params.position_pct
        size = int(position_value / price / 100) * 100  # 取整到100股

        # 至少买100股
        return max(size, 100)

    def log(self, txt, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def stop(self):
        """策略结束"""
        if self.params.printlog:
            self.log(
                f"策略结束 - 短期均线: {self.params.short_period}, "
                f"长期均线: {self.params.long_period}, "
                f"最终价值: {self.broker.getvalue():.2f}"
            )
