"""
BacktestResult - 回测结果类

存储和管理回测结果数据
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np


@dataclass
class BacktestResult:
    """
    回测结果数据类
    
    包含回测的所有关键指标和详细数据
    """

    # 基本信息（必需参数）
    backtest_id: str
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime

    # 资金信息（必需参数）
    initial_cash: float
    final_cash: float
    total_return: float  # 总收益率

    # 风险指标（必需参数）
    sharpe_ratio: float  # 夏普比率
    max_drawdown: float  # 最大回撤
    win_rate: float  # 胜率

    # 交易统计（必需参数）
    total_trades: int  # 总交易次数
    profit_trades: int  # 盈利交易次数
    loss_trades: int  # 亏损交易次数

    # 带默认值的参数必须放在最后
    timestamp: datetime = field(default_factory=datetime.now)

    # 年化数据
    annual_returns: Dict[int, float] = field(default_factory=dict)  # 年化收益

    # 手续费和滑点
    commission: float = 0.001
    slippage: float = 0.001

    # 详细数据
    trades: List[Dict[str, Any]] = field(default_factory=list)  # 交易记录
    daily_returns: Dict[str, float] = field(default_factory=dict)  # 每日收益
    positions: List[Dict[str, Any]] = field(default_factory=list)  # 持仓记录

    # 额外指标
    profit_factor: Optional[float] = None  # 盈亏比
    average_win: Optional[float] = None  # 平均盈利
    average_loss: Optional[float] = None  # 平均亏损
    largest_win: Optional[float] = None  # 最大单笔盈利
    largest_loss: Optional[float] = None  # 最大单笔亏损
    calmar_ratio: Optional[float] = None  # 卡尔玛比率
    sortino_ratio: Optional[float] = None  # 索提诺比率

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'backtest_id': self.backtest_id,
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'start_date': self.start_date.isoformat() if isinstance(self.start_date, datetime) else self.start_date,
            'end_date': self.end_date.isoformat() if isinstance(self.end_date, datetime) else self.end_date,
            'timestamp': self.timestamp.isoformat(),
            'initial_cash': self.initial_cash,
            'final_cash': self.final_cash,
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'profit_trades': self.profit_trades,
            'loss_trades': self.loss_trades,
            'annual_returns': self.annual_returns,
            'commission': self.commission,
            'slippage': self.slippage,
            'profit_factor': self.profit_factor,
            'average_win': self.average_win,
            'average_loss': self.average_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'calmar_ratio': self.calmar_ratio,
            'sortino_ratio': self.sortino_ratio,
            'trades_count': len(self.trades),
            'has_daily_returns': bool(self.daily_returns)
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        """从字典创建实例"""
        # 转换日期字符串为 datetime 对象
        if isinstance(data.get('start_date'), str):
            data['start_date'] = datetime.fromisoformat(data['start_date'])
        if isinstance(data.get('end_date'), str):
            data['end_date'] = datetime.fromisoformat(data['end_date'])
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        return cls(**data)

    def get_summary(self) -> str:
        """获取结果摘要"""
        duration = (self.end_date - self.start_date).days

        summary = f"""
回测结果摘要
====================
策略名称: {self.strategy_name}
交易标的: {self.symbol}
回测周期: {self.start_date.date()} 至 {self.end_date.date()} ({duration} 天)

收益情况
--------------------
初始资金: ¥{self.initial_cash:,.2f}
最终资金: ¥{self.final_cash:,.2f}
总收益率: {self.total_return:.2%}
年化收益: {self._calculate_annualized_return():.2%}

风险指标
--------------------
夏普比率: {self.sharpe_ratio:.2f}
最大回撤: {self.max_drawdown:.2%}
卡尔玛比率: {self.calmar_ratio:.2f} (如果可用)

交易统计
--------------------
总交易次数: {self.total_trades}
盈利次数: {self.profit_trades}
亏损次数: {self.loss_trades}
胜率: {self.win_rate:.2%}
盈亏比: {self.profit_factor:.2f} (如果可用)

交易成本
--------------------
手续费率: {self.commission:.3%}
滑点: {self.slippage:.3%}
        """
        return summary.strip()

    def _calculate_annualized_return(self) -> float:
        """计算年化收益率"""
        if not self.start_date or not self.end_date:
            return 0

        days = (self.end_date - self.start_date).days
        if days <= 0:
            return 0

        years = days / 365
        if years <= 0:
            return 0

        return ((1 + self.total_return) ** (1 / years)) - 1

    def calculate_additional_metrics(self):
        """计算额外的性能指标"""
        if not self.trades:
            return

        # 分离盈利和亏损交易
        profits = [t['pnl'] for t in self.trades if t.get('pnl', 0) > 0]
        losses = [abs(t['pnl']) for t in self.trades if t.get('pnl', 0) < 0]

        # 计算盈亏比
        if losses and sum(losses) > 0:
            self.profit_factor = sum(profits) / sum(losses) if profits else 0
        else:
            self.profit_factor = float('inf') if profits else 0

        # 计算平均盈亏
        self.average_win = sum(profits) / len(profits) if profits else 0
        self.average_loss = sum(losses) / len(losses) if losses else 0

        # 最大单笔盈亏
        self.largest_win = max(profits) if profits else 0
        self.largest_loss = max(losses) if losses else 0

        # 计算卡尔玛比率
        if self.max_drawdown != 0:
            annualized_return = self._calculate_annualized_return()
            self.calmar_ratio = annualized_return / abs(self.max_drawdown)
        else:
            self.calmar_ratio = 0

        # 计算索提诺比率（需要下行波动率）
        if self.daily_returns:
            returns = list(self.daily_returns.values())
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns) * np.sqrt(252)  # 年化
                if downside_std > 0:
                    risk_free_rate = 0.03  # 假设无风险利率为3%
                    excess_return = self._calculate_annualized_return() - risk_free_rate
                    self.sortino_ratio = excess_return / downside_std
                else:
                    self.sortino_ratio = 0
            else:
                self.sortino_ratio = float('inf')  # 没有负收益

    def compare_with(self, other: 'BacktestResult') -> Dict[str, Dict[str, Any]]:
        """
        与另一个回测结果比较
        
        Args:
            other: 另一个回测结果
            
        Returns:
            比较结果字典
        """
        comparison = {
            'current': {
                'strategy': self.strategy_name,
                'total_return': self.total_return,
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': self.max_drawdown,
                'win_rate': self.win_rate,
                'total_trades': self.total_trades
            },
            'other': {
                'strategy': other.strategy_name,
                'total_return': other.total_return,
                'sharpe_ratio': other.sharpe_ratio,
                'max_drawdown': other.max_drawdown,
                'win_rate': other.win_rate,
                'total_trades': other.total_trades
            },
            'difference': {
                'total_return': self.total_return - other.total_return,
                'sharpe_ratio': self.sharpe_ratio - other.sharpe_ratio,
                'max_drawdown': self.max_drawdown - other.max_drawdown,
                'win_rate': self.win_rate - other.win_rate,
                'total_trades': self.total_trades - other.total_trades
            }
        }

        return comparison
