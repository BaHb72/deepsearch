"""
海龟交易策略
经典的趋势跟踪策略，基于唐奇安通道突破
"""
import backtrader as bt


class TurtleTradingStrategy(bt.Strategy):
    """
    海龟交易策略
    
    策略逻辑：
    1. 突破20日高点买入（系统1）或55日高点买入（系统2）
    2. 跌破10日低点卖出（系统1）或20日低点卖出（系统2）
    3. 使用ATR进行仓位管理和止损
    4. 采用金字塔加仓
    """
    
    params = (
        ('entry_period_s1', 20),     # 系统1入场周期
        ('exit_period_s1', 10),      # 系统1出场周期
        ('entry_period_s2', 55),     # 系统2入场周期
        ('exit_period_s2', 20),      # 系统2出场周期
        ('atr_period', 20),          # ATR周期
        ('risk_percent', 0.02),      # 每单位风险比例 2%
        ('max_units', 4),            # 最大单位数
        ('stop_n', 2),               # 止损ATR倍数
        ('use_system', 1),           # 使用哪个系统 (1 or 2)
        ('printlog', False),         # 打印日志
    )
    
    def __init__(self):
        """初始化策略"""
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # 选择使用的系统
        if self.params.use_system == 1:
            entry_period = self.params.entry_period_s1
            exit_period = self.params.exit_period_s1
        else:
            entry_period = self.params.entry_period_s2
            exit_period = self.params.exit_period_s2
        
        # 唐奇安通道
        self.donchian_high = bt.indicators.Highest(
            self.datahigh, 
            period=entry_period
        )
        self.donchian_low = bt.indicators.Lowest(
            self.datalow, 
            period=exit_period
        )
        
        # ATR用于计算仓位和止损
        self.atr = bt.indicators.ATR(
            self.datas[0], 
            period=self.params.atr_period
        )
        
        # 记录
        self.order = None
        self.units = 0  # 当前单位数
        self.last_entry_price = 0  # 上次入场价格
        self.stop_price = 0  # 止损价格
        self.trades = []  # 交易记录
        
        # 额外指标
        self.sma = bt.indicators.SMA(self.datas[0], period=200)  # 长期趋势
        
    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.last_entry_price = order.executed.price
                self.units += 1
                
                # 更新止损价格
                self.stop_price = self.last_entry_price - self.params.stop_n * self.atr[0]
                
                if self.params.printlog:
                    self.log(f'买入执行: 价格={order.executed.price:.2f}, '
                            f'单位={self.units}, 止损={self.stop_price:.2f}')
                    
            else:  # 卖出
                if self.params.printlog:
                    self.log(f'卖出执行: 价格={order.executed.price:.2f}')
                self.units = 0
                self.last_entry_price = 0
                self.stop_price = 0
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.printlog:
                self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易通知"""
        if trade.isclosed:
            self.trades.append({
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm,
                'value': self.broker.getvalue()
            })
            
            if self.params.printlog:
                self.log(f'交易关闭: 毛利润={trade.pnl:.2f}, '
                        f'净利润={trade.pnlcomm:.2f}')
    
    def next(self):
        """策略主逻辑"""
        # 检查待处理订单
        if self.order:
            return
        
        # 计算仓位大小（基于ATR）
        unit_size = self.calculate_unit_size()
        
        # 没有持仓
        if not self.position:
            # 检查突破买入信号
            if self.datahigh[0] > self.donchian_high[-1]:
                # 额外过滤：价格在长期均线之上（趋势过滤）
                if self.dataclose[0] > self.sma[0]:
                    if self.params.printlog:
                        self.log(f'突破买入信号: 价格{self.datahigh[0]:.2f} > '
                                f'通道高点{self.donchian_high[-1]:.2f}')
                    
                    self.order = self.buy(size=unit_size)
                    
        else:
            # 有持仓
            # 1. 检查止损
            if self.dataclose[0] < self.stop_price:
                if self.params.printlog:
                    self.log(f'止损: 价格{self.dataclose[0]:.2f} < '
                            f'止损价{self.stop_price:.2f}')
                self.order = self.close()
                
            # 2. 检查正常退出信号
            elif self.datalow[0] < self.donchian_low[-1]:
                if self.params.printlog:
                    self.log(f'正常退出: 价格{self.datalow[0]:.2f} < '
                            f'通道低点{self.donchian_low[-1]:.2f}')
                self.order = self.close()
                
            # 3. 金字塔加仓
            elif self.units < self.params.max_units:
                # 价格上涨0.5个ATR后加仓
                if self.dataclose[0] > self.last_entry_price + 0.5 * self.atr[0]:
                    if self.params.printlog:
                        self.log(f'金字塔加仓: 单位{self.units + 1}')
                    self.order = self.buy(size=unit_size)
    
    def calculate_unit_size(self):
        """
        计算交易单位大小
        单位大小 = (账户资金 * 风险比例) / (N * 每点价值)
        """
        account_value = self.broker.getvalue()
        cash = self.broker.getcash()
        
        # 使用可用资金的比例
        risk_amount = account_value * self.params.risk_percent
        
        # 基于ATR计算仓位
        if self.atr[0] > 0:
            # 每单位风险 = N * 合约乘数（A股为100）
            unit_risk = self.atr[0] * 100
            unit_size = int(risk_amount / unit_risk) * 100
            
            # 确保不超过可用资金
            max_size_by_cash = int(cash / self.dataclose[0] / 100) * 100
            unit_size = min(unit_size, max_size_by_cash)
            
            # 最小100股
            unit_size = max(unit_size, 100)
        else:
            unit_size = 100
        
        return unit_size
    
    def log(self, txt, dt=None):
        """日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
    
    def stop(self):
        """策略结束"""
        if self.params.printlog:
            self.log(f'海龟策略结束 - 系统{self.params.use_system}, '
                    f'最终价值: {self.broker.getvalue():.2f}, '
                    f'总交易数: {len(self.trades)}')