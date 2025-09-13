"""
BacktestEngine - 回测引擎

核心回测执行引擎，管理回测流程
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Type

try:
    import backtrader as bt

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    bt = None

from ..data.data_feed import DeepSearchDataFeed
from ..interfaces.strategy import BaseStrategy
from ..adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter as BacktraderStrategyAdapter
from ..utils.results import BacktestResult


class BacktestEngine:
    """
    回测引擎
    
    负责：
    1. 配置和运行回测
    2. 管理数据源和策略
    3. 收集和分析结果
    4. 与事件系统集成
    """

    def __init__(self, data_provider=None, event_engine=None):
        """
        初始化回测引擎
        
        Args:
            data_provider: 数据提供者
            event_engine: 事件引擎（可选，用于发送回测事件）
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

        self.logger = logging.getLogger(f"deepsearch.{self.__class__.__name__}")
        self.data_provider = data_provider
        self.event_engine = event_engine

        # Backtrader 组件
        self.cerebro = None
        self.data_feed = DeepSearchDataFeed(data_provider)

        # 配置参数
        self.strategy_class = None
        self.strategy_params = {}
        self.symbol = None
        self.start_date = None
        self.end_date = None
        self.initial_cash = 100000
        self.commission = 0.001
        self.slippage = 0.001

        # 运行状态
        self.is_running = False
        self.is_cancelled = False
        self.result = None

    async def configure(
            self,
            strategy_class: Type[BaseStrategy],
            symbol: str,
            start_date: datetime,
            end_date: datetime,
            initial_cash: float = 100000,
            commission: float = 0.001,
            slippage: float = 0.001,
            strategy_params: Optional[Dict[str, Any]] = None,
            **kwargs
    ):
        """
        配置回测参数
        
        Args:
            strategy_class: 策略类
            symbol: 交易标的
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission: 手续费率
            slippage: 滑点
            strategy_params: 策略参数
            **kwargs: 其他参数
        """
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

        # 创建 Cerebro 实例
        self.cerebro = bt.Cerebro()

        # 设置初始资金
        self.cerebro.broker.setcash(initial_cash)

        # 设置手续费
        self.cerebro.broker.setcommission(commission=commission)

        # 设置滑点
        if slippage > 0:
            self.cerebro.broker.set_slippage_perc(slippage)

        # 加载数据
        await self._load_data()

        # 添加策略
        self._add_strategy()

        # 添加分析器
        self._add_analyzers()

        self.logger.info(
            f"回测配置完成: {symbol} [{start_date} - {end_date}], "
            f"初始资金: {initial_cash}, 手续费: {commission}"
        )

    async def _load_data(self):
        """加载数据"""
        # 获取数据
        df = await self.data_feed.get_data(
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            timeframe='1d',
            adjust='qfq'
        )

        # 创建 Backtrader 数据源
        data = self.data_feed.create_backtrader_feed(df)

        # 添加到 Cerebro
        self.cerebro.adddata(data, name=self.symbol)

        self.logger.info(f"加载数据完成: {len(df)} 条记录")

    def _add_strategy(self):
        """添加策略"""
        # 创建策略实例
        strategy_instance = self.strategy_class(self.strategy_params)

        # 创建 Backtrader 策略适配器
        bt_strategy = BacktraderStrategyAdapter.create_backtrader_strategy(
            strategy_instance
        )

        # 添加到 Cerebro
        self.cerebro.addstrategy(bt_strategy)

        self.logger.info(f"添加策略: {self.strategy_class.__name__}")

    def _add_analyzers(self):
        """添加分析器"""
        # 收益率分析
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

        # 夏普比率
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')

        # 最大回撤
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

        # 交易统计
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

        # 年化收益
        self.cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')

        # 累计收益
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')

        self.logger.info("添加分析器完成")

    def run(self) -> BacktestResult:
        """
        同步运行回测
        
        Returns:
            BacktestResult: 回测结果
        """
        if not self.cerebro:
            raise RuntimeError("请先调用 configure 方法配置回测")

        if self.is_running:
            raise RuntimeError("回测正在运行中")

        self.is_running = True
        self.is_cancelled = False

        try:
            # 记录开始值
            start_value = self.cerebro.broker.getvalue()

            # 运行回测
            self.logger.info("开始运行回测...")
            results = self.cerebro.run()

            # 获取结束值
            end_value = self.cerebro.broker.getvalue()

            # 提取分析结果
            strategy = results[0]

            # 创建回测结果
            self.result = self._create_result(
                strategy, start_value, end_value
            )

            sharpe_value = self.result.sharpe_ratio if self.result.sharpe_ratio else 0
            self.logger.info(
                f"Backtest complete: Total return {self.result.total_return:.2%}, "
                f"Sharpe ratio {sharpe_value:.2f}"
            )

            # 发送完成事件
            if self.event_engine:
                self._send_complete_event()

            return self.result

        except Exception as e:
            self.logger.error(f"回测运行失败: {e}")

            # 发送错误事件
            if self.event_engine:
                self._send_error_event(str(e))

            raise

        finally:
            self.is_running = False

    async def run_async(self) -> BacktestResult:
        """
        异步运行回测
        
        Returns:
            BacktestResult: 回测结果
        """
        # 在线程池中运行同步回测
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)

    def cancel(self):
        """取消回测"""
        self.is_cancelled = True
        self.logger.info("回测已取消")

    def _create_result(
            self,
            strategy,
            start_value: float,
            end_value: float
    ) -> BacktestResult:
        """
        创建回测结果
        
        Args:
            strategy: Backtrader 策略实例
            start_value: 初始资金
            end_value: 最终资金
            
        Returns:
            BacktestResult: 回测结果对象
        """
        # 提取分析器结果
        returns = strategy.analyzers.returns.get_analysis()
        sharpe = strategy.analyzers.sharpe.get_analysis()
        drawdown = strategy.analyzers.drawdown.get_analysis()
        trades = strategy.analyzers.trades.get_analysis()
        annual = strategy.analyzers.annual.get_analysis()

        # 创建结果对象
        result = BacktestResult(
            backtest_id=f"{self.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            strategy_name=self.strategy_class.__name__,
            symbol=self.symbol,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_cash=start_value,
            final_cash=end_value,
            total_return=(end_value - start_value) / start_value,
            sharpe_ratio=sharpe.get('sharperatio', 0) if sharpe.get('sharperatio') is not None else 0,
            max_drawdown=drawdown.get('max', {}).get('drawdown', 0) / 100 if drawdown.get('max', {}).get(
                'drawdown') else 0,
            win_rate=self._calculate_win_rate(trades),
            total_trades=trades.get('total', {}).get('total', 0),
            profit_trades=trades.get('won', {}).get('total', 0),
            loss_trades=trades.get('lost', {}).get('total', 0),
            annual_returns=annual,
            commission=self.commission,
            slippage=self.slippage
        )

        # 添加详细的交易记录
        result.trades = self._extract_trades(strategy)

        # 添加每日收益率
        if hasattr(strategy.analyzers, 'timereturn'):
            result.daily_returns = strategy.analyzers.timereturn.get_analysis()

        return result

    def _calculate_win_rate(self, trades: Dict) -> float:
        """计算胜率"""
        total = trades.get('total', {}).get('total', 0)
        if total == 0:
            return 0
        won = trades.get('won', {}).get('total', 0)
        return won / total

    def _extract_trades(self, strategy) -> List[Dict[str, Any]]:
        """提取交易记录"""
        trades = []

        # 这里需要从 Backtrader 的交易记录中提取
        # 具体实现依赖于 Backtrader 的内部结构

        return trades

    def _send_complete_event(self):
        """发送回测完成事件"""
        if self.event_engine and self.result:
            from deepsearch.event.engine.engine import Event
            event = Event(
                type="BACKTEST_ENGINE_COMPLETE",
                data={
                    'symbol': self.symbol,
                    'strategy': self.strategy_class.__name__,
                    'result': self.result.to_dict()
                }
            )
            self.event_engine.put(event)

    def _send_error_event(self, error_message: str):
        """发送回测错误事件"""
        if self.event_engine:
            from deepsearch.event.engine.engine import Event
            event = Event(
                type="BACKTEST_ENGINE_ERROR",
                data={
                    'symbol': self.symbol,
                    'strategy': self.strategy_class.__name__,
                    'error': error_message
                }
            )
            self.event_engine.put(event)

    def plot(self, **kwargs):
        """
        绘制回测结果图表
        
        Args:
            **kwargs: 传递给 Cerebro.plot 的参数
        """
        if not self.cerebro:
            raise RuntimeError("请先运行回测")

        try:
            self.cerebro.plot(**kwargs)
        except Exception as e:
            self.logger.error(f"绘图失败: {e}")
            self.logger.info("提示: 如果在服务器环境，可能需要设置 matplotlib 后端")
