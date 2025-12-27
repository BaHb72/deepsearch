"""
Backtrader回测引擎
封装backtrader的核心功能，提供统一的回测接口
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, Union, cast

import matplotlib
import pandas as pd
from loguru import logger

from deepsearch.backtest.adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter
from deepsearch.backtest.data.data_bridge import DataBridge
from deepsearch.observability import get_logger

# 使用非交互式后端，兼容服务器环境
matplotlib.use("Agg")  # 必须在导入 pyplot 之前设置

# 抑制所有图像处理相关的调试日志
get_logger("matplotlib").setLevel(logging.WARNING)
get_logger("matplotlib.font_manager").setLevel(logging.WARNING)
get_logger("matplotlib.fontmanager").setLevel(logging.WARNING)
get_logger("matplotlib.pyplot").setLevel(logging.WARNING)

# 抑制PIL/Pillow的调试日志
get_logger("PIL").setLevel(logging.WARNING)
get_logger("PIL.PngImagePlugin").setLevel(logging.WARNING)
get_logger("PIL.Image").setLevel(logging.WARNING)
get_logger("PIL.TiffImagePlugin").setLevel(logging.WARNING)

# 抑制Backtrader的调试日志
get_logger("backtrader").setLevel(logging.INFO)
get_logger("backtrader.plot").setLevel(logging.WARNING)

# 确保根logger不输出DEBUG
root_logger = get_logger()
if root_logger.level == logging.DEBUG:
    root_logger.setLevel(logging.INFO)

try:
    import backtrader as bt
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    # 设置中文字体
    rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    bt = cast(Any, None)
    plt = cast(Any, None)
    rcParams = cast(Any, {})


class BacktestAnalyzer(bt.Analyzer):
    """自定义分析器，收集详细的回测指标"""

    def __init__(self):
        self.rets = []
        self.trade_list = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_list.append(
                {
                    "ref": trade.ref,
                    "size": trade.size,
                    "price": trade.price,
                    "pnl": trade.pnl,
                    "pnlcomm": trade.pnlcomm,
                    "commission": trade.commission,
                }
            )

    def stop(self):
        # 计算性能指标 - 注意：BacktestAnalyzer作为分析器不应访问其他分析器
        # 性能指标将由其他专门的分析器（如Returns、SharpeRatio等）计算
        pass


class BacktestEngine:
    """
    Backtrader回测引擎

    功能：
    1. 统一的回测接口
    2. 支持多种数据源
    3. 自动性能分析
    4. 结果可视化
    5. 参数优化
    """

    def __init__(self):
        """初始化回测引擎"""
        if not HAS_BACKTRADER:
            raise ImportError("请先安装backtrader: pip install backtrader matplotlib")

        self.cerebro = None
        self.adapter = None
        self.results: List[Any] = []
        self.data_bridge = DataBridge()

    async def initialize(self):
        """异步初始化"""
        if not self.adapter:
            self.adapter = UnifiedBacktraderAdapter(source="auto")
            await self.adapter.initialize()
            logger.info("回测引擎初始化完成")

    def create_cerebro(
        self,
        initial_cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.0,
        **kwargs,
    ) -> bt.Cerebro:
        """
        创建Cerebro实例

        Args:
            initial_cash: 初始资金
            commission: 手续费率
            slippage: 滑点
            **kwargs: 其他参数

        Returns:
            配置好的Cerebro实例
        """
        cerebro = bt.Cerebro()

        # 设置初始资金
        cerebro.broker.setcash(initial_cash)

        # 设置手续费
        cerebro.broker.setcommission(commission=commission)

        # 设置滑点
        if slippage > 0:
            cerebro.broker.set_slippage_perc(slippage)

        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
        cerebro.addanalyzer(BacktestAnalyzer, _name="custom")

        # 添加观察器
        cerebro.addobserver(bt.observers.Value)
        cerebro.addobserver(bt.observers.DrawDown)
        cerebro.addobserver(bt.observers.Trades)
        cerebro.addobserver(bt.observers.BuySell)

        self.cerebro = cerebro
        return cerebro

    async def add_data(
        self,
        symbols: Union[str, List[str]],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = "1d",
        adjust: str = "qfq",
    ):
        """
        添加数据到回测引擎

        Args:
            symbols: 股票代码或代码列表
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            adjust: 复权方式
        """
        if not self.cerebro:
            raise ValueError("请先调用create_cerebro创建引擎")

        if not self.adapter:
            await self.initialize()

        # 确保symbols是列表
        if isinstance(symbols, str):
            symbols = [symbols]

        # 转换日期格式
        from datetime import datetime

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # 自动扩展数据范围以满足策略需求
        # 使用保守的默认值，确保有足够的数据
        max_lookback = 50  # 默认获取50个交易日，足够大部分策略使用

        # 尝试从策略参数中获取更准确的值
        if hasattr(self.cerebro, "strats") and self.cerebro.strats:
            try:
                for strat in self.cerebro.strats:
                    # 检查策略参数中的周期设置
                    if len(strat) > 0 and hasattr(strat[0], "params"):
                        params = strat[0].params
                        # 查找所有可能的周期参数
                        for param_name in ["long_period", "period", "ma_period", "slow_period"]:
                            if hasattr(params, param_name):
                                period_value = getattr(params, param_name)
                                if isinstance(period_value, (int, float)):
                                    max_lookback = max(
                                        max_lookback, int(period_value) + 10
                                    )  # 额外增加10天缓冲
            except Exception as e:
                logger.debug(f"无法从策略获取周期参数: {e}")
                # 使用默认值

        # 扩展开始日期，确保有足够的历史数据
        # 考虑周末和节假日，额外增加50%的天数
        extended_days = int(max_lookback * 1.5)
        extended_start_date = start_date - timedelta(days=extended_days)

        logger.info(
            f"自动扩展数据获取范围: 原始开始日期 {start_date.strftime('%Y-%m-%d')}, "
            f"扩展后 {extended_start_date.strftime('%Y-%m-%d')} (增加{extended_days}天)"
        )

        # 获取数据
        for symbol in symbols:
            df = await self.adapter.get_data(
                symbol=symbol,
                start_date=extended_start_date.strftime("%Y-%m-%d"),  # 使用扩展后的开始日期
                end_date=end_date.strftime("%Y-%m-%d"),
                timeframe=timeframe,
                adjust=adjust,
            )

            if not df.empty:
                # 验证数据量是否足够
                if len(df) < max_lookback:
                    logger.warning(
                        f"数据量不足: {symbol} 只有 {len(df)} 条记录，"
                        f"策略需要至少 {max_lookback} 条记录。"
                        f"尝试扩大日期范围或选择更早的开始日期。"
                    )
                    # 虽然数据不足，但仍尝试运行
                    logger.info("尝试使用有限的数据运行回测，结果可能不准确")

                # 创建数据源
                data_feed = self.adapter.create_backtrader_feed(df, name=symbol)
                if data_feed is not None:
                    self.cerebro.adddata(data_feed, name=symbol)
                    logger.info(f"添加数据: {symbol}, {len(df)}条记录")
                else:
                    logger.error(f"无法创建{symbol}的Backtrader数据源")
                    raise ValueError(f"Failed to create Backtrader feed for {symbol}")
            else:
                logger.error(f"无法获取{symbol}的数据。请检查：")
                logger.error("1. 股票代码是否正确")
                logger.error("2. 日期范围是否有效")
                logger.error("3. 数据源是否可用")
                raise ValueError(f"No data available for {symbol}")

    def add_strategy(self, strategy_class: Type[bt.Strategy], **params):
        """
        添加策略

        Args:
            strategy_class: 策略类
            **params: 策略参数
        """
        if not self.cerebro:
            raise ValueError("请先调用create_cerebro创建引擎")

        self.cerebro.addstrategy(strategy_class, **params)
        logger.info(f"添加策略: {strategy_class.__name__}")

    def run(self) -> List[bt.Strategy]:
        """
        运行回测

        Returns:
            策略实例列表
        """
        if not self.cerebro:
            raise ValueError("请先调用create_cerebro创建引擎")

        logger.info("开始运行回测...")
        self.results = list(self.cerebro.run())
        logger.info("回测完成")

        return self.results

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标

        Returns:
            性能指标字典
        """
        if not self.results:
            raise ValueError("请先运行回测")

        strat = self.results[0]

        # 获取分析器结果
        returns = strat.analyzers.returns.get_analysis()
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        sqn = strat.analyzers.sqn.get_analysis()

        # 计算额外指标
        initial_value = self.cerebro.broker.startingcash
        final_value = self.cerebro.broker.getvalue()

        # Safe division for total return
        if initial_value != 0:
            total_return = (final_value - initial_value) / initial_value
        else:
            total_return = 0

        # 计算年化收益
        if hasattr(strat, "data"):
            days = len(strat.data)
            if days > 0 and total_return > -1:  # Prevent negative base in power calculation
                annual_return = (1 + total_return) ** (252 / days) - 1
            else:
                annual_return = 0
        else:
            annual_return = total_return

        # 交易统计
        total_trades = trades.get("total", {}).get("total", 0)
        won_trades = trades.get("won", {}).get("total", 0)
        lost_trades = trades.get("lost", {}).get("total", 0)

        metrics = {
            "initial_value": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe_ratio": sharpe.get("sharperatio", 0),
            "max_drawdown": (drawdown.get("max", {}).get("drawdown", 0) or 0) / 100,
            "max_drawdown_period": drawdown.get("max", {}).get("len", 0),
            "total_trades": total_trades,
            "winning_trades": won_trades,
            "losing_trades": lost_trades,
            "win_rate": won_trades / total_trades if total_trades > 0 else 0,
            "sqn": sqn.get("sqn", 0),
            "profit_factor": self._calculate_profit_factor(trades),
            "avg_trade": trades.get("pnl", {}).get("average", 0),
            "trades_per_year": self._calculate_trades_per_year(total_trades, strat),
            "cumulative_return": returns.get("rtot", 0),
            "average_return": returns.get("ravg", 0),
        }

        # Sanitize all metrics to ensure no NaN or infinity values
        sanitized_metrics = self._sanitize_metrics(metrics)

        return sanitized_metrics

    def _sanitize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metrics to ensure no NaN or infinity values for JSON serialization
        """
        import math

        sanitized: Dict[str, Any] = {}

        for key, value in metrics.items():
            if isinstance(value, float):
                if math.isnan(value):
                    sanitized[key] = None
                elif math.isinf(value):
                    sanitized[key] = 999999.99 if value > 0 else -999999.99
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value

        return sanitized

    def _calculate_profit_factor(self, trades: Dict) -> float:
        """计算盈亏比"""
        gross_profit = abs(trades.get("won", {}).get("pnl", {}).get("total", 0))
        gross_loss = abs(trades.get("lost", {}).get("pnl", {}).get("total", 0))

        if gross_loss > 0:
            return float(gross_profit) / float(gross_loss)
        elif gross_profit > 0:
            # Return a large finite number instead of infinity for JSON compatibility
            return 999.99
        else:
            return 0

    def _calculate_trades_per_year(self, total_trades: int, strat) -> float:
        """计算年均交易次数"""
        if hasattr(strat, "data") and len(strat.data) > 0:
            years = len(strat.data) / 252
            return total_trades / years if years > 0 else 0
        return 0

    def get_trade_list(self) -> List[Dict[str, Any]]:
        """
        获取交易列表

        Returns:
            交易记录列表
        """
        if not self.results:
            raise ValueError("请先运行回测")

        strat = self.results[0]
        trades = []

        # 从自定义分析器获取交易记录
        if hasattr(strat.analyzers, "custom"):
            trades = strat.analyzers.custom.trade_list

        return trades

    def get_equity_curve(self) -> pd.DataFrame:
        """
        获取权益曲线

        Returns:
            权益曲线DataFrame
        """
        if not self.results:
            raise ValueError("请先运行回测")

        strat = self.results[0]

        # 提取权益曲线数据
        dates = []
        values = []

        # 获取 value observer 的数据
        value_observer = strat.observers.value

        # 使用数据的长度而不是策略的长度
        data_len = len(strat.data)

        for i in range(data_len):
            # 安全地获取日期和值
            try:
                # Backtrader 使用负索引，从 -len(data) 到 -1
                idx = i - data_len
                dates.append(strat.data.datetime.datetime(idx))
                values.append(value_observer.lines.value[idx])
            except (IndexError, AttributeError) as e:
                logger.debug(f"Skipping index {i}: {e}")
                continue

        if not dates:
            logger.warning("No equity curve data available")
            return pd.DataFrame()

        df = pd.DataFrame({"date": dates, "value": values})

        # 计算收益率
        df["returns"] = df["value"].pct_change()
        # 第一行的收益率为0（没有前一天数据）
        df["returns"] = df["returns"].fillna(0)
        df["cumulative_returns"] = (1 + df["returns"]).cumprod() - 1

        # 计算回撤
        df["drawdown"] = df["value"] / df["value"].cummax() - 1
        # 确保回撤值不为NaN
        df["drawdown"] = df["drawdown"].fillna(0)

        return df

    def plot_results(
        self, save_path: Optional[str] = None, use_backtrader_plot: bool = True
    ) -> Optional[str]:
        """
        绘制回测结果图表

        Args:
            save_path: 保存路径
            use_backtrader_plot: 是否使用Backtrader原生绘图

        Returns:
            Base64编码的图片或保存路径
        """
        if not self.results or not plt:
            return None

        try:
            figs: Any | None = None
            # 计算数据时间范围，用于动态优化
            days_diff = 90  # 默认值
            if self.cerebro and self.cerebro.datas and len(self.cerebro.datas) > 0:
                try:
                    data = self.cerebro.datas[0]
                    # 获取数据长度
                    data_len = len(data)
                    # 估算天数（假设日线数据）
                    days_diff = data_len
                    logger.info(f"回测数据长度: {data_len}个数据点，约{days_diff}天")
                except Exception as e:
                    logger.debug(f"无法计算数据天数: {e}")

            # 根据时间范围动态设置参数
            if days_diff <= 30:  # 1个月内 - 高质量
                figsize = (14, 10)
                dpi = 100
                timeout = 30
                show_volume = True
                show_labels = True
                show_orders = True
                logger.info("使用高质量图表设置（1个月内数据）")
            elif days_diff <= 90:  # 3个月内 - 标准质量
                figsize = (12, 8)
                dpi = 80
                timeout = 45
                show_volume = True
                show_labels = True
                show_orders = True
                logger.info("使用标准图表设置（1-3个月数据）")
            elif days_diff <= 180:  # 6个月内 - 优化性能
                figsize = (10, 6)
                dpi = 60
                timeout = 60
                show_volume = False  # 不显示成交量
                show_labels = False  # 不显示标签
                show_orders = True  # 仍显示买卖点
                logger.info("使用性能优化图表设置（3-6个月数据）")
            else:  # 超过6个月 - 使用简化图表
                logger.info(f"数据跨度{days_diff}天（>6个月），自动切换到简化图表")
                use_backtrader_plot = False  # 直接使用备用方案

            # 如果使用Backtrader原生绘图
            if use_backtrader_plot and self.cerebro:
                import base64
                import concurrent.futures
                import io

                # 禁用交互模式
                plt.ioff()

                # 使用线程池执行绘图，设置超时保护
                def plot_with_timeout():
                    try:
                        # 构建动态plot参数
                        plot_params = {
                            "style": "candlestick",  # K线样式
                            "barup": "red",  # 上涨颜色
                            "bardown": "green",  # 下跌颜色
                            "volume": show_volume,  # 根据数据量决定是否显示成交量
                            "volumeup": "red",
                            "volumedown": "green",
                            "grid": True,
                            "numfigs": 1,  # 单图
                            "figsize": figsize,  # 动态图表大小
                            "dpi": dpi,  # 动态DPI
                            "tight": True,
                            "use": None,  # 不直接显示
                            "plotlinelabels": show_labels,
                            "plotorders": show_orders,
                            "returnfig": True,  # 返回figure对象
                        }

                        # 长期数据的额外优化
                        if days_diff > 90:
                            plot_params["plotlinelabels"] = False  # 不显示线标签
                            plot_params["plotyticks"] = False  # 减少Y轴刻度

                        # 创建一个新的figure以捕获Backtrader的绘图
                        return self.cerebro.plot(**plot_params)
                    except Exception as e:
                        logger.error(f"Backtrader绘图失败: {e}")
                        return None

                # 执行绘图，动态超时时间
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(plot_with_timeout)
                    try:
                        figs = future.result(timeout=timeout)  # 动态超时
                    except concurrent.futures.TimeoutError:
                        logger.error(f"绘图操作超时({timeout}秒)，切换到简化图表")
                        future.cancel()  # 取消超时的任务
                        use_backtrader_plot = False  # 切换到备用方案
                    except Exception as e:
                        logger.error(f"绘图线程执行失败: {e}")
                        use_backtrader_plot = False  # 切换到备用方案

                # 获取第一个figure（Backtrader返回嵌套列表 [[fig1, fig2], ...]）
                if figs and len(figs) > 0 and use_backtrader_plot:  # 检查是否仍然使用backtrader绘图
                    # 遍历嵌套列表结构
                    fig = None
                    for fig_list in figs:
                        if isinstance(fig_list, list) and len(fig_list) > 0:
                            # 获取第一个figure
                            fig = fig_list[0]
                            break

                    # 如果没有找到figure，尝试直接访问（兼容旧版本）
                    if fig is None and not isinstance(figs[0], list):
                        fig = figs[0]

                    if fig is not None:
                        if save_path:
                            fig.savefig(save_path, dpi=100, bbox_inches="tight")
                            plt.close(fig)
                            return save_path
                        else:
                            # 转换为base64
                            buffer = io.BytesIO()
                            fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
                            buffer.seek(0)
                            image_base64 = base64.b64encode(buffer.read()).decode()
                            plt.close(fig)
                            return f"data:image/png;base64,{image_base64}"
                    else:
                        logger.warning("无法从Backtrader获取figure对象，使用备用方案")
                        # 跳转到备用方案
                        use_backtrader_plot = False

            # 使用自定义绘图（备用方案）
            if not use_backtrader_plot or figs is None:
                # 获取权益曲线
                equity_df = self.get_equity_curve()

                # 创建图表
                fig, axes = plt.subplots(3, 1, figsize=(12, 10))

                # 1. 权益曲线
                axes[0].plot(equity_df["date"], equity_df["value"], label="Portfolio Value")
                axes[0].set_title("权益曲线")
                axes[0].set_ylabel("价值")
                axes[0].grid(True)
                axes[0].legend()

                # 2. 收益率
                axes[1].plot(
                    equity_df["date"],
                    equity_df["cumulative_returns"] * 100,
                    label="Cumulative Returns",
                    color="green",
                )
                axes[1].set_title("累计收益率")
                axes[1].set_ylabel("收益率 (%)")
                axes[1].grid(True)
                axes[1].legend()

                # 3. 回撤
                axes[2].fill_between(
                    equity_df["date"], equity_df["drawdown"] * 100, 0, color="red", alpha=0.3
                )
                axes[2].set_title("回撤")
                axes[2].set_ylabel("回撤 (%)")
                axes[2].set_xlabel("日期")
                axes[2].grid(True)

                plt.tight_layout()

                if save_path:
                    plt.savefig(save_path, dpi=100, bbox_inches="tight")
                    plt.close()
                    return save_path
                else:
                    # 转换为base64
                    import base64
                    import io

                    buffer = io.BytesIO()
                    plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
                    buffer.seek(0)
                    image_base64 = base64.b64encode(buffer.read()).decode()
                    plt.close()

                    return f"data:image/png;base64,{image_base64}"

        except Exception as e:
            logger.error(f"绘制图表失败: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

        return None

    def optimize_parameters(
        self,
        strategy_class: Type[bt.Strategy],
        param_grid: Dict[str, List[Any]],
        symbols: Union[str, List[str]],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        metric: str = "sharpe_ratio",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        参数优化

        Args:
            strategy_class: 策略类
            param_grid: 参数网格
            symbols: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            metric: 优化指标
            **kwargs: 其他参数

        Returns:
            最优参数和结果
        """
        logger.info("开始参数优化...")

        best_params = None
        best_metric = -999999.99
        all_results = []

        # 生成参数组合
        import itertools

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for values in itertools.product(*param_values):
            params = dict(zip(param_names, values))
            logger.info(f"测试参数: {params}")

            try:
                # 创建新的cerebro
                cerebro = self.create_cerebro(**kwargs)

                # 添加数据（同步方式）
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.add_data(symbols, start_date, end_date))
                loop.close()

                # 添加策略
                cerebro.addstrategy(strategy_class, **params)

                # 运行回测
                self.results = list(cerebro.run())

                # 获取指标
                metrics = self.get_performance_metrics()
                metric_value = metrics.get(metric, -999999.99)

                # 记录结果
                result = {"params": params, "metrics": metrics, metric: metric_value}
                all_results.append(result)

                # 更新最优参数
                if metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params
                    logger.info(f"发现更优参数: {params}, {metric}={metric_value}")

            except Exception as e:
                logger.error(f"参数{params}回测失败: {e}")
                continue

        logger.info(f"优化完成，最优参数: {best_params}")

        return {"best_params": best_params, "best_metric": best_metric, "all_results": all_results}

    def export_results(self, format: str = "json") -> Union[str, pd.DataFrame]:
        """
        导出回测结果

        Args:
            format: 导出格式 ('json', 'csv', 'excel')

        Returns:
            导出的数据
        """
        if not self.results:
            raise ValueError("请先运行回测")

        # 收集所有数据
        data: Dict[str, Any] = {
            "metrics": self.get_performance_metrics(),
            "trades": self.get_trade_list(),
            "equity_curve": self.get_equity_curve().to_dict(orient="records"),
        }

        if format == "json":
            return json.dumps(data, indent=2, default=str)
        if format == "csv":
            df = pd.DataFrame([data["metrics"]])
            csv_content = df.to_csv(index=False)
            return cast(str, csv_content)
        if format == "excel":
            trades = cast(List[Dict[str, Any]], data["trades"])
            equity_records = cast(List[Dict[str, Any]], data["equity_curve"])
            with pd.ExcelWriter("backtest_results.xlsx", engine="openpyxl") as writer:
                pd.DataFrame([data["metrics"]]).to_excel(writer, sheet_name="Metrics", index=False)
                pd.DataFrame(trades).to_excel(writer, sheet_name="Trades", index=False)
                pd.DataFrame(equity_records).to_excel(writer, sheet_name="Equity", index=False)
            return "backtest_results.xlsx"
        raise ValueError(f"Unsupported export format: {format}")


# 创建全局实例
_backtest_engine = None


async def get_backtest_engine() -> BacktestEngine:
    """获取回测引擎实例"""
    global _backtest_engine
    if not _backtest_engine:
        _backtest_engine = BacktestEngine()
        await _backtest_engine.initialize()
    return _backtest_engine
