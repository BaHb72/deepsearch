# encoding:utf-8
"""
AmazingData 数据转换器
将 AmazingData 的数据格式转换为系统统一格式
"""

from datetime import datetime
from typing import Dict, List, Any, Union

import pandas as pd
from loguru import logger

from .amazingdata_types import (
    FIELD_MAPPING
)


class AmazingDataConverter:
    """
    AmazingData 数据格式转换器
    
    负责将 AmazingData SDK 返回的数据转换为系统标准格式
    """

    @staticmethod
    def convert_kline(data: Dict[str, Any], symbol: str = None) -> pd.DataFrame:
        """
        转换K线数据
        
        Args:
            data: AmazingData K线原始数据
            symbol: 股票代码
            
        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 如果数据是字典格式（多股票）
            if isinstance(data, dict) and symbol and symbol in data:
                data = data[symbol]

            # 转换为 DataFrame
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                df = data.copy()
            else:
                df = pd.DataFrame([data])

            # 字段映射
            field_map = FIELD_MAPPING.get('kline', {})
            df.rename(columns=field_map, inplace=True)

            # 标准化必要字段
            required_fields = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            for field in required_fields:
                if field not in df.columns:
                    if field == 'datetime' and 'time' in df.columns:
                        df['datetime'] = df['time']
                    else:
                        logger.warning(f"K线数据缺少字段: {field}")

            # 时间处理
            if 'datetime' in df.columns:
                # 处理不同的时间格式
                if df['datetime'].dtype == 'object':
                    # 字符串格式
                    df['datetime'] = pd.to_datetime(df['datetime'])
                elif df['datetime'].dtype in ['int64', 'int32']:
                    # 时间戳格式（可能是秒或毫秒）
                    if df['datetime'].iloc[0] > 10000000000:
                        # 毫秒时间戳
                        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    else:
                        # 秒时间戳
                        df['datetime'] = pd.to_datetime(df['datetime'], unit='s')

                # 设置为索引
                df.set_index('datetime', inplace=True)

            # 数据类型转换
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount',
                               'turnover_rate', 'change', 'change_percent']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 排序
            df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"K线数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_snapshot(data: Union[Dict, List[Dict]], symbols: List[str] = None) -> Dict[str, Dict]:
        """
        转换快照数据
        
        Args:
            data: AmazingData 快照原始数据
            symbols: 股票代码列表
            
        Returns:
            {symbol: snapshot_dict} 格式
        """
        try:
            result = {}

            # 处理不同的数据格式
            if isinstance(data, dict):
                # 如果是 {symbol: snapshot} 格式
                for symbol, snapshot in data.items():
                    result[symbol] = AmazingDataConverter._convert_single_snapshot(snapshot, symbol)
            elif isinstance(data, list):
                # 如果是列表格式
                for item in data:
                    symbol = item.get('code') or item.get('symbol')
                    if symbol:
                        result[symbol] = AmazingDataConverter._convert_single_snapshot(item, symbol)

            return result

        except Exception as e:
            logger.error(f"快照数据转换失败: {e}")
            return {}

    @staticmethod
    def _convert_single_snapshot(snapshot: Dict, symbol: str) -> Dict:
        """转换单个快照数据"""
        try:
            # 字段映射
            field_map = FIELD_MAPPING.get('snapshot', {})

            result = {
                'symbol': symbol,
                'name': snapshot.get('name', ''),
                'time': snapshot.get('time', ''),
                'last': float(snapshot.get('last', 0) or snapshot.get('last_price', 0)),
                'open': float(snapshot.get('open', 0)),
                'high': float(snapshot.get('high', 0)),
                'low': float(snapshot.get('low', 0)),
                'close': float(snapshot.get('pre_close', 0) or snapshot.get('prev_close', 0)),
                'volume': float(snapshot.get('volume', 0)),
                'amount': float(snapshot.get('amount', 0)),
                'change': float(snapshot.get('change', 0)),
                'change_percent': float(snapshot.get('change_rate', 0) or snapshot.get('change_percent', 0)),
                'turnover_rate': float(snapshot.get('turnover', 0) or snapshot.get('turnover_rate', 0)),
                'amplitude': float(snapshot.get('amplitude', 0)),
            }

            # 买卖盘数据
            for i in range(1, 6):
                bid_price_key = f'bid{i}'
                bid_volume_key = f'bid{i}_volume'
                ask_price_key = f'ask{i}'
                ask_volume_key = f'ask{i}_volume'

                result[bid_price_key] = float(snapshot.get(bid_price_key, 0))
                result[bid_volume_key] = float(snapshot.get(bid_volume_key, 0))
                result[ask_price_key] = float(snapshot.get(ask_price_key, 0))
                result[ask_volume_key] = float(snapshot.get(ask_volume_key, 0))

            # 涨跌停价
            result['limit_up'] = float(snapshot.get('limit_up', 0))
            result['limit_down'] = float(snapshot.get('limit_down', 0))

            # 状态
            result['status'] = snapshot.get('status', 'normal')

            return result

        except Exception as e:
            logger.error(f"单个快照转换失败: {e}")
            return {'symbol': symbol, 'error': str(e)}

    @staticmethod
    def convert_financial(data: Dict[str, Any], symbol: str, report_type: str) -> pd.DataFrame:
        """
        转换财务数据
        
        Args:
            data: AmazingData 财务原始数据
            symbol: 股票代码
            report_type: 报表类型
            
        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 提取股票数据
            if isinstance(data, dict) and symbol in data:
                stock_data = data[symbol]
            else:
                stock_data = data

            # 转换为 DataFrame
            if isinstance(stock_data, list):
                df = pd.DataFrame(stock_data)
            elif isinstance(stock_data, pd.DataFrame):
                df = stock_data.copy()
            elif isinstance(stock_data, dict):
                # 如果是单条记录
                df = pd.DataFrame([stock_data])
            else:
                return pd.DataFrame()

            # 添加元信息
            df['symbol'] = symbol
            df['report_type'] = report_type

            # 时间字段处理
            date_fields = ['report_date', 'announce_date', 'end_date']
            for field in date_fields:
                if field in df.columns:
                    df[field] = pd.to_datetime(df[field])

            # 设置索引
            if 'report_date' in df.columns:
                df.set_index('report_date', inplace=True)
                df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"财务数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_tick(data: Union[Dict, List], symbol: str = None) -> pd.DataFrame:
        """
        转换逐笔数据
        
        Args:
            data: AmazingData 逐笔原始数据
            symbol: 股票代码
            
        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 处理不同格式
            if isinstance(data, dict) and symbol and symbol in data:
                tick_data = data[symbol]
            else:
                tick_data = data

            # 转换为 DataFrame
            if isinstance(tick_data, list):
                df = pd.DataFrame(tick_data)
            elif isinstance(tick_data, pd.DataFrame):
                df = tick_data.copy()
            else:
                return pd.DataFrame()

            # 字段标准化
            column_map = {
                'deal_time': 'time',
                'deal_price': 'price',
                'deal_volume': 'volume',
                'deal_amount': 'amount',
                'bs_flag': 'direction'
            }
            df.rename(columns=column_map, inplace=True)

            # 时间处理
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)

            # 方向映射
            if 'direction' in df.columns:
                direction_map = {1: 'B', 2: 'S', 0: 'N'}
                df['direction'] = df['direction'].map(direction_map).fillna('N')

            # 添加股票代码
            if symbol:
                df['symbol'] = symbol

            return df

        except Exception as e:
            logger.error(f"逐笔数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_order_book(data: Dict, symbol: str = None) -> Dict:
        """
        转换盘口数据（Level2）
        
        Args:
            data: AmazingData 盘口原始数据
            symbol: 股票代码
            
        Returns:
            标准化的盘口数据
        """
        try:
            if not data:
                return {}

            result = {
                'symbol': symbol or data.get('symbol', ''),
                'time': data.get('time', ''),
                'bid_queue': [],
                'ask_queue': [],
                'bid_prices': [],
                'ask_prices': [],
                'bid_volumes': [],
                'ask_volumes': []
            }

            # 提取买卖队列
            for i in range(1, 11):  # 通常有10档
                bid_price = data.get(f'bid{i}_price') or data.get(f'bid{i}')
                bid_volume = data.get(f'bid{i}_volume') or data.get(f'bid{i}_vol')
                ask_price = data.get(f'ask{i}_price') or data.get(f'ask{i}')
                ask_volume = data.get(f'ask{i}_volume') or data.get(f'ask{i}_vol')

                if bid_price:
                    result['bid_prices'].append(float(bid_price))
                    result['bid_volumes'].append(int(bid_volume or 0))

                if ask_price:
                    result['ask_prices'].append(float(ask_price))
                    result['ask_volumes'].append(int(ask_volume or 0))

            # 委托队列明细
            if 'bid_queue' in data:
                result['bid_queue'] = data['bid_queue']
            if 'ask_queue' in data:
                result['ask_queue'] = data['ask_queue']

            return result

        except Exception as e:
            logger.error(f"盘口数据转换失败: {e}")
            return {}

    @staticmethod
    def convert_shareholder(data: Dict, symbol: str) -> Dict:
        """
        转换股东数据
        
        Args:
            data: AmazingData 股东原始数据
            symbol: 股票代码
            
        Returns:
            标准化的股东数据
        """
        try:
            if not data:
                return {}

            # 提取股票数据
            if isinstance(data, dict) and symbol in data:
                holder_data = data[symbol]
            else:
                holder_data = data

            result = {
                'symbol': symbol,
                'report_date': holder_data.get('report_date', ''),
                'shareholder_count': int(holder_data.get('holder_num', 0)),
                'avg_holding': float(holder_data.get('avg_hold', 0)),
                'institution_ratio': float(holder_data.get('institution_ratio', 0)),
                'concentration': float(holder_data.get('concentration', 0)),
                'top10_holders': [],
                'top10_tradable': []
            }

            # 前十大股东
            if 'top10_holders' in holder_data:
                for holder in holder_data['top10_holders']:
                    result['top10_holders'].append({
                        'name': holder.get('holder_name', ''),
                        'holding': float(holder.get('hold_num', 0)),
                        'ratio': float(holder.get('hold_ratio', 0)),
                        'change': float(holder.get('change', 0))
                    })

            # 前十大流通股东
            if 'top10_tradable' in holder_data:
                for holder in holder_data['top10_tradable']:
                    result['top10_tradable'].append({
                        'name': holder.get('holder_name', ''),
                        'holding': float(holder.get('hold_num', 0)),
                        'ratio': float(holder.get('hold_ratio', 0)),
                        'change': float(holder.get('change', 0))
                    })

            return result

        except Exception as e:
            logger.error(f"股东数据转换失败: {e}")
            return {}

    @staticmethod
    def convert_dragon_tiger(data: Union[Dict, List], symbol: str = None) -> List[Dict]:
        """
        转换龙虎榜数据
        
        Args:
            data: AmazingData 龙虎榜原始数据
            symbol: 股票代码
            
        Returns:
            标准化的龙虎榜数据列表
        """
        try:
            if not data:
                return []

            result = []

            # 处理不同格式
            if isinstance(data, dict):
                if symbol and symbol in data:
                    items = data[symbol]
                else:
                    items = [data]
            elif isinstance(data, list):
                items = data
            else:
                return []

            # 转换每条龙虎榜记录
            for item in items:
                record = {
                    'symbol': symbol or item.get('symbol', ''),
                    'trade_date': item.get('trade_date', ''),
                    'reason': item.get('reason', ''),
                    'buy_amount': float(item.get('buy_amount', 0)),
                    'sell_amount': float(item.get('sell_amount', 0)),
                    'net_amount': float(item.get('net_amount', 0)),
                    'turnover_rate': float(item.get('turnover_rate', 0)),
                    'buy_list': [],
                    'sell_list': []
                }

                # 买入席位
                if 'buy_list' in item:
                    for seat in item['buy_list']:
                        record['buy_list'].append({
                            'name': seat.get('seat_name', ''),
                            'amount': float(seat.get('buy_amount', 0)),
                            'ratio': float(seat.get('buy_ratio', 0))
                        })

                # 卖出席位
                if 'sell_list' in item:
                    for seat in item['sell_list']:
                        record['sell_list'].append({
                            'name': seat.get('seat_name', ''),
                            'amount': float(seat.get('sell_amount', 0)),
                            'ratio': float(seat.get('sell_ratio', 0))
                        })

                result.append(record)

            return result

        except Exception as e:
            logger.error(f"龙虎榜数据转换失败: {e}")
            return []

    @staticmethod
    def convert_margin_trading(data: Dict, symbol: str = None) -> pd.DataFrame:
        """
        转换融资融券数据
        
        Args:
            data: AmazingData 融资融券原始数据
            symbol: 股票代码
            
        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 提取数据
            if isinstance(data, dict) and symbol and symbol in data:
                margin_data = data[symbol]
            else:
                margin_data = data

            # 转换为 DataFrame
            if isinstance(margin_data, list):
                df = pd.DataFrame(margin_data)
            elif isinstance(margin_data, pd.DataFrame):
                df = margin_data.copy()
            else:
                df = pd.DataFrame([margin_data])

            # 字段映射
            column_map = {
                'fin_balance': 'margin_balance',
                'fin_buy': 'margin_buy',
                'fin_repay': 'margin_repay',
                'sec_balance': 'short_balance',
                'sec_sell': 'short_sell',
                'sec_repay': 'short_repay',
                'fin_sec_ratio': 'margin_ratio'
            }
            df.rename(columns=column_map, inplace=True)

            # 添加股票代码
            if symbol:
                df['symbol'] = symbol

            # 时间处理
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df.set_index('trade_date', inplace=True)
                df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"融资融券数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_subscription_data(data: Any, data_type: str) -> Dict:
        """
        转换订阅推送的数据
        
        Args:
            data: 推送的原始数据
            data_type: 数据类型
            
        Returns:
            标准化的数据字典
        """
        try:
            result = {
                'type': data_type,
                'timestamp': datetime.now().isoformat(),
                'data': None
            }

            if data_type == 'snapshot':
                # 快照数据
                result['data'] = AmazingDataConverter._convert_single_snapshot(
                    data.__dict__ if hasattr(data, '__dict__') else data,
                    data.get('symbol', '') if isinstance(data, dict) else getattr(data, 'symbol', '')
                )
            elif data_type == 'kline':
                # K线数据
                result['data'] = {
                    'symbol': getattr(data, 'symbol', ''),
                    'period': getattr(data, 'period', ''),
                    'datetime': getattr(data, 'time', ''),
                    'open': float(getattr(data, 'open', 0)),
                    'high': float(getattr(data, 'high', 0)),
                    'low': float(getattr(data, 'low', 0)),
                    'close': float(getattr(data, 'close', 0)),
                    'volume': float(getattr(data, 'volume', 0)),
                    'amount': float(getattr(data, 'amount', 0))
                }
            elif data_type == 'tick':
                # 逐笔数据
                result['data'] = {
                    'symbol': getattr(data, 'symbol', ''),
                    'time': getattr(data, 'time', ''),
                    'price': float(getattr(data, 'price', 0)),
                    'volume': int(getattr(data, 'volume', 0)),
                    'direction': getattr(data, 'direction', 'N')
                }
            else:
                # 其他类型，直接返回
                result['data'] = data.__dict__ if hasattr(data, '__dict__') else data

            return result

        except Exception as e:
            logger.error(f"订阅数据转换失败: {e}")
            return {'type': data_type, 'error': str(e)}
