"""
智能信号检测服务
用于检测金叉、死叉、背离等技术信号
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger


class SignalDetector:
    """技术信号检测器"""

    def __init__(self):
        """初始化信号检测器"""
        self.signal_history = []
        self.alert_callbacks = []

    def detect_crossovers(self,
                          fast_line: pd.Series,
                          slow_line: pd.Series,
                          names: Tuple[str, str] = ("Fast", "Slow")) -> List[Dict]:
        """
        检测均线交叉信号（金叉/死叉）
        
        Args:
            fast_line: 快线数据
            slow_line: 慢线数据
            names: 线的名称
            
        Returns:
            交叉信号列表
        """
        signals = []

        # 计算交叉点
        diff = fast_line - slow_line
        diff_shift = diff.shift(1)

        # 金叉：快线从下向上穿越慢线
        golden_cross = (diff > 0) & (diff_shift <= 0)

        # 死叉：快线从上向下穿越慢线
        death_cross = (diff < 0) & (diff_shift >= 0)

        # 生成信号
        for idx in golden_cross[golden_cross].index:
            signals.append({
                "type": "golden_cross",
                "time": str(idx),
                "name": f"{names[0]}金叉{names[1]}",
                "level": "bullish",
                "strength": self._calculate_cross_strength(diff, idx),
                "values": {
                    names[0]: float(fast_line[idx]) if not pd.isna(fast_line[idx]) else None,
                    names[1]: float(slow_line[idx]) if not pd.isna(slow_line[idx]) else None
                }
            })

        for idx in death_cross[death_cross].index:
            signals.append({
                "type": "death_cross",
                "time": str(idx),
                "name": f"{names[0]}死叉{names[1]}",
                "level": "bearish",
                "strength": self._calculate_cross_strength(diff, idx),
                "values": {
                    names[0]: float(fast_line[idx]) if not pd.isna(fast_line[idx]) else None,
                    names[1]: float(slow_line[idx]) if not pd.isna(slow_line[idx]) else None
                }
            })

        return signals

    def detect_divergence(self,
                          price: pd.Series,
                          indicator: pd.Series,
                          window: int = 20) -> List[Dict]:
        """
        检测价格与指标的背离
        
        Args:
            price: 价格数据
            indicator: 指标数据
            window: 检测窗口
            
        Returns:
            背离信号列表
        """
        signals = []

        # 找出局部高点和低点
        price_highs = self._find_peaks(price, window, is_high=True)
        price_lows = self._find_peaks(price, window, is_high=False)
        ind_highs = self._find_peaks(indicator, window, is_high=True)
        ind_lows = self._find_peaks(indicator, window, is_high=False)

        # 检测顶背离：价格创新高，但指标未创新高
        for i in range(1, len(price_highs)):
            if len(ind_highs) > i:
                price_idx_curr = price_highs[i]
                price_idx_prev = price_highs[i - 1]
                ind_idx_curr = ind_highs[i]
                ind_idx_prev = ind_highs[i - 1]

                if (price[price_idx_curr] > price[price_idx_prev] and
                        indicator[ind_idx_curr] <= indicator[ind_idx_prev]):
                    signals.append({
                        "type": "bearish_divergence",
                        "time": str(price_idx_curr),
                        "name": "顶背离",
                        "level": "bearish",
                        "strength": "medium",
                        "description": "价格创新高但指标未创新高，可能见顶"
                    })

        # 检测底背离：价格创新低，但指标未创新低
        for i in range(1, len(price_lows)):
            if len(ind_lows) > i:
                price_idx_curr = price_lows[i]
                price_idx_prev = price_lows[i - 1]
                ind_idx_curr = ind_lows[i]
                ind_idx_prev = ind_lows[i - 1]

                if (price[price_idx_curr] < price[price_idx_prev] and
                        indicator[ind_idx_curr] >= indicator[ind_idx_prev]):
                    signals.append({
                        "type": "bullish_divergence",
                        "time": str(price_idx_curr),
                        "name": "底背离",
                        "level": "bullish",
                        "strength": "medium",
                        "description": "价格创新低但指标未创新低，可能见底"
                    })

        return signals

    def detect_pattern_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        检测K线形态信号
        
        Args:
            df: K线数据
            
        Returns:
            形态信号列表
        """
        signals = []

        if len(df) < 3:
            return signals

        # 检测锤子线/倒锤子
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1] if i > 0 else None

            body = abs(row['close'] - row['open'])
            upper_shadow = row['high'] - max(row['open'], row['close'])
            lower_shadow = min(row['open'], row['close']) - row['low']

            # 锤子线：下影线长，实体小
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                if prev_row is not None and row['low'] < prev_row['low']:
                    signals.append({
                        "type": "hammer",
                        "time": str(df.index[i]),
                        "name": "锤子线",
                        "level": "bullish",
                        "strength": "weak",
                        "description": "可能的底部反转信号"
                    })

            # 倒锤子线：上影线长，实体小
            if upper_shadow > body * 2 and lower_shadow < body * 0.5:
                if prev_row is not None and row['high'] > prev_row['high']:
                    signals.append({
                        "type": "inverted_hammer",
                        "time": str(df.index[i]),
                        "name": "倒锤子线",
                        "level": "bearish",
                        "strength": "weak",
                        "description": "可能的顶部反转信号"
                    })

        # 检测吞没形态
        for i in range(1, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i - 1]

            # 看涨吞没
            if (prev['close'] < prev['open'] and  # 前一根是阴线
                    curr['close'] > curr['open'] and  # 当前是阳线
                    curr['open'] <= prev['close'] and  # 开盘低于前收盘
                    curr['close'] >= prev['open']):  # 收盘高于前开盘
                signals.append({
                    "type": "bullish_engulfing",
                    "time": str(df.index[i]),
                    "name": "看涨吞没",
                    "level": "bullish",
                    "strength": "medium",
                    "description": "强烈的上涨信号"
                })

            # 看跌吞没
            if (prev['close'] > prev['open'] and  # 前一根是阳线
                    curr['close'] < curr['open'] and  # 当前是阴线
                    curr['open'] >= prev['close'] and  # 开盘高于前收盘
                    curr['close'] <= prev['open']):  # 收盘低于前开盘
                signals.append({
                    "type": "bearish_engulfing",
                    "time": str(df.index[i]),
                    "name": "看跌吞没",
                    "level": "bearish",
                    "strength": "medium",
                    "description": "强烈的下跌信号"
                })

        return signals

    def detect_support_resistance(self,
                                  df: pd.DataFrame,
                                  window: int = 20,
                                  min_touches: int = 2) -> Dict[str, List[float]]:
        """
        检测支撑阻力位
        
        Args:
            df: K线数据
            window: 检测窗口
            min_touches: 最少触及次数
            
        Returns:
            支撑和阻力位列表
        """
        highs = df['high'].rolling(window=window).max()
        lows = df['low'].rolling(window=window).min()

        # 统计价格触及次数
        price_levels = {}

        # 检测阻力位（高点）
        for price in highs.dropna().unique():
            touches = ((df['high'] >= price * 0.995) &
                       (df['high'] <= price * 1.005)).sum()
            if touches >= min_touches:
                price_levels[price] = {'type': 'resistance', 'touches': touches}

        # 检测支撑位（低点）
        for price in lows.dropna().unique():
            touches = ((df['low'] >= price * 0.995) &
                       (df['low'] <= price * 1.005)).sum()
            if touches >= min_touches:
                if price in price_levels:
                    price_levels[price]['type'] = 'both'
                    price_levels[price]['touches'] += touches
                else:
                    price_levels[price] = {'type': 'support', 'touches': touches}

        # 分类整理
        support_levels = []
        resistance_levels = []

        for price, info in sorted(price_levels.items()):
            if info['type'] in ['support', 'both']:
                support_levels.append(price)
            if info['type'] in ['resistance', 'both']:
                resistance_levels.append(price)

        return {
            'support': support_levels,
            'resistance': resistance_levels
        }

    def detect_volume_signals(self, df: pd.DataFrame, volume_ma_period: int = 20) -> List[Dict]:
        """
        检测成交量异常信号
        
        Args:
            df: K线数据
            volume_ma_period: 成交量均线周期
            
        Returns:
            成交量信号列表
        """
        signals = []

        if 'volume' not in df.columns:
            return signals

        # 计算成交量均线
        volume_ma = df['volume'].rolling(window=volume_ma_period).mean()

        # 检测放量信号
        for i in range(volume_ma_period, len(df)):
            curr_vol = df['volume'].iloc[i]
            avg_vol = volume_ma.iloc[i]

            if pd.notna(curr_vol) and pd.notna(avg_vol):
                # 大幅放量（超过均量2倍）
                if curr_vol > avg_vol * 2:
                    price_change = df['close'].iloc[i] - df['open'].iloc[i]

                    if price_change > 0:
                        signals.append({
                            "type": "volume_surge_bullish",
                            "time": str(df.index[i]),
                            "name": "放量上涨",
                            "level": "bullish",
                            "strength": "strong" if curr_vol > avg_vol * 3 else "medium",
                            "description": f"成交量是均量的{curr_vol / avg_vol:.1f}倍"
                        })
                    else:
                        signals.append({
                            "type": "volume_surge_bearish",
                            "time": str(df.index[i]),
                            "name": "放量下跌",
                            "level": "bearish",
                            "strength": "strong" if curr_vol > avg_vol * 3 else "medium",
                            "description": f"成交量是均量的{curr_vol / avg_vol:.1f}倍"
                        })

                # 缩量信号（低于均量50%）
                elif curr_vol < avg_vol * 0.5:
                    signals.append({
                        "type": "volume_dry",
                        "time": str(df.index[i]),
                        "name": "极度缩量",
                        "level": "neutral",
                        "strength": "weak",
                        "description": "成交量极度萎缩，可能变盘"
                    })

        return signals

    def detect_all_signals(self,
                           df: pd.DataFrame,
                           indicators: Optional[Dict] = None) -> Dict[str, List[Dict]]:
        """
        检测所有类型的信号
        
        Args:
            df: K线数据
            indicators: 计算好的指标数据
            
        Returns:
            按类型分组的信号字典
        """
        all_signals = {
            "crossovers": [],
            "divergences": [],
            "patterns": [],
            "volume": [],
            "support_resistance": []
        }

        # 检测K线形态
        all_signals["patterns"] = self.detect_pattern_signals(df)

        # 检测成交量信号
        all_signals["volume"] = self.detect_volume_signals(df)

        # 检测支撑阻力
        sr_levels = self.detect_support_resistance(df)
        all_signals["support_resistance"] = [{
            "type": "levels",
            "support": sr_levels['support'][:5],  # 最近5个支撑位
            "resistance": sr_levels['resistance'][:5]  # 最近5个阻力位
        }]

        # 如果有指标数据，检测交叉和背离
        if indicators:
            # 检测MA交叉
            if 'MA5' in indicators and 'MA10' in indicators:
                crosses = self.detect_crossovers(
                    indicators['MA5'],
                    indicators['MA10'],
                    ("MA5", "MA10")
                )
                all_signals["crossovers"].extend(crosses)

            # 检测MACD交叉
            if 'MACD' in indicators and 'Signal' in indicators:
                macd_crosses = self.detect_crossovers(
                    indicators['MACD'],
                    indicators['Signal'],
                    ("MACD", "Signal")
                )
                all_signals["crossovers"].extend(macd_crosses)

            # 检测RSI背离
            if 'RSI' in indicators and 'close' in df.columns:
                divergences = self.detect_divergence(
                    df['close'],
                    indicators['RSI']
                )
                all_signals["divergences"].extend(divergences)

        # 记录到历史
        timestamp = datetime.now()
        for signal_type, signals in all_signals.items():
            for signal in signals:
                signal['detected_at'] = timestamp.isoformat()
                self.signal_history.append(signal)

        # 触发告警回调
        self._trigger_alerts(all_signals)

        return all_signals

    def _calculate_cross_strength(self, diff: pd.Series, idx) -> str:
        """计算交叉信号强度"""
        try:
            # 获取交叉点附近的斜率
            window = 5
            start_idx = max(0, idx - window)
            end_idx = min(len(diff), idx + window)

            if end_idx - start_idx > 1:
                slope = (diff.iloc[end_idx - 1] - diff.iloc[start_idx]) / (end_idx - start_idx)

                if abs(slope) > 0.5:
                    return "strong"
                elif abs(slope) > 0.2:
                    return "medium"
                else:
                    return "weak"
            else:
                return "weak"
        except:
            return "weak"

    def _find_peaks(self, series: pd.Series, window: int, is_high: bool = True) -> List[int]:
        """找出局部极值点"""
        peaks = []

        for i in range(window, len(series) - window):
            window_data = series.iloc[i - window:i + window + 1]

            if is_high:
                if series.iloc[i] == window_data.max():
                    peaks.append(i)
            else:
                if series.iloc[i] == window_data.min():
                    peaks.append(i)

        return peaks

    def _trigger_alerts(self, signals: Dict[str, List[Dict]]):
        """触发告警回调"""
        important_signals = []

        # 筛选重要信号
        for signal_type, signal_list in signals.items():
            for signal in signal_list:
                if signal.get('strength') == 'strong':
                    important_signals.append(signal)
                elif signal.get('level') in ['bullish', 'bearish'] and signal.get('strength') == 'medium':
                    important_signals.append(signal)

        # 触发回调
        for callback in self.alert_callbacks:
            try:
                callback(important_signals)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")

    def register_alert_callback(self, callback):
        """注册告警回调函数"""
        self.alert_callbacks.append(callback)

    def get_signal_summary(self, time_window: int = 24) -> Dict:
        """
        获取信号摘要统计
        
        Args:
            time_window: 时间窗口（小时）
            
        Returns:
            信号统计摘要
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=time_window)
        recent_signals = [
            s for s in self.signal_history
            if datetime.fromisoformat(s['detected_at']) > cutoff_time
        ]

        summary = {
            "total": len(recent_signals),
            "bullish": len([s for s in recent_signals if s.get('level') == 'bullish']),
            "bearish": len([s for s in recent_signals if s.get('level') == 'bearish']),
            "neutral": len([s for s in recent_signals if s.get('level') == 'neutral']),
            "by_type": {},
            "by_strength": {
                "strong": len([s for s in recent_signals if s.get('strength') == 'strong']),
                "medium": len([s for s in recent_signals if s.get('strength') == 'medium']),
                "weak": len([s for s in recent_signals if s.get('strength') == 'weak'])
            }
        }

        # 按类型统计
        for signal in recent_signals:
            signal_type = signal.get('type', 'unknown')
            summary["by_type"][signal_type] = summary["by_type"].get(signal_type, 0) + 1

        return summary
