# encoding:utf-8
"""
Data Validator for Backtrader Integration
数据验证器 - 验证数据源的准确性和一致性
Author: DeepSearch Team
Version: 1.0.0
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import backtrader as bt

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    bt = None


class ValidationLevel(Enum):
    """验证级别"""
    BASIC = "basic"  # 基础验证
    STANDARD = "standard"  # 标准验证
    STRICT = "strict"  # 严格验证


class DataValidator:
    """
    数据验证器
    
    功能：
    1. OHLC关系验证
    2. 时间序列连续性验证
    3. 价格合理性验证
    4. 成交量验证
    5. 数据源对比验证
    """

    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        """
        初始化验证器
        
        Args:
            level: 验证级别
        """
        self.level = level
        self.validation_results = []
        self.errors = []
        self.warnings = []

    def validate_ohlc_relationships(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        验证OHLC关系
        
        规则：
        1. High >= Max(Open, Close)
        2. Low <= Min(Open, Close)
        3. High >= Low
        4. 所有价格 > 0
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if df.empty:
            result['passed'] = False
            result['errors'].append("数据为空")
            return result

        # 检查必要字段
        required_fields = ['open', 'high', 'low', 'close']
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            result['passed'] = False
            result['errors'].append(f"缺少必要字段: {missing_fields}")
            return result

        # 检查价格为正
        negative_prices = (df[required_fields] <= 0).any(axis=1)
        if negative_prices.any():
            count = negative_prices.sum()
            result['passed'] = False
            result['errors'].append(f"发现 {count} 条负价格或零价格记录")

        # 检查High >= Low
        invalid_hl = df['high'] < df['low']
        if invalid_hl.any():
            count = invalid_hl.sum()
            dates = df.index[invalid_hl].tolist()[:5]  # 最多显示5个
            result['passed'] = False
            result['errors'].append(f"发现 {count} 条High < Low的记录")
            result['errors'].append(f"  问题日期: {dates}")

        # 检查High >= Max(Open, Close)
        max_oc = df[['open', 'close']].max(axis=1)
        invalid_high = df['high'] < max_oc
        if invalid_high.any():
            count = invalid_high.sum()
            if self.level == ValidationLevel.STRICT:
                result['passed'] = False
                result['errors'].append(f"发现 {count} 条High低于Open/Close的记录")
            else:
                result['warnings'].append(f"发现 {count} 条High略低于Open/Close的记录")

        # 检查Low <= Min(Open, Close)
        min_oc = df[['open', 'close']].min(axis=1)
        invalid_low = df['low'] > min_oc
        if invalid_low.any():
            count = invalid_low.sum()
            if self.level == ValidationLevel.STRICT:
                result['passed'] = False
                result['errors'].append(f"发现 {count} 条Low高于Open/Close的记录")
            else:
                result['warnings'].append(f"发现 {count} 条Low略高于Open/Close的记录")

        # 统计信息
        result['stats'] = {
            'total_records': len(df),
            'price_range': {
                'min': df[required_fields].min().min(),
                'max': df[required_fields].max().max(),
                'avg': df['close'].mean()
            },
            'volatility': df['close'].pct_change().std()
        }

        return result

    def validate_time_series(self, df: pd.DataFrame, expected_freq: str = 'D') -> Dict[str, Any]:
        """
        验证时间序列连续性
        
        Args:
            df: 数据DataFrame
            expected_freq: 期望的频率 ('D'=日, 'W'=周, 'M'=月)
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if df.empty:
            result['passed'] = False
            result['errors'].append("数据为空")
            return result

        # 确保索引是DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            result['passed'] = False
            result['errors'].append("索引不是日期时间类型")
            return result

        # 检查时间排序
        if not df.index.is_monotonic_increasing:
            result['passed'] = False
            result['errors'].append("时间序列未按升序排列")

        # 检查重复日期
        duplicates = df.index.duplicated()
        if duplicates.any():
            count = duplicates.sum()
            result['passed'] = False
            result['errors'].append(f"发现 {count} 个重复的日期")

        # 检查缺失日期（仅对日频数据）
        if expected_freq == 'D':
            # 创建完整的交易日期范围
            start_date = df.index[0]
            end_date = df.index[-1]

            # 生成工作日序列（简化处理，不考虑节假日）
            expected_dates = pd.bdate_range(start=start_date, end=end_date)
            missing_dates = expected_dates.difference(df.index)

            if len(missing_dates) > 0:
                # 计算缺失比例
                missing_ratio = len(missing_dates) / len(expected_dates)

                if missing_ratio > 0.3:  # 缺失超过30%
                    result['warnings'].append(f"缺失 {len(missing_dates)} 个交易日 ({missing_ratio:.1%})")

                    if self.level == ValidationLevel.STRICT:
                        result['passed'] = False
                        result['errors'].append("缺失交易日过多")

        # 统计信息
        result['stats'] = {
            'start_date': str(df.index[0]),
            'end_date': str(df.index[-1]),
            'total_days': len(df),
            'date_range_days': (df.index[-1] - df.index[0]).days,
            'avg_gap_days': np.mean(np.diff(df.index.values).astype('timedelta64[D]').astype(int)) if len(df) > 1 else 0
        }

        return result

    def validate_price_continuity(self, df: pd.DataFrame, max_gap: float = 0.11) -> Dict[str, Any]:
        """
        验证价格连续性
        
        Args:
            df: 数据DataFrame
            max_gap: 最大允许的价格跳空比例（默认11%，涨跌停）
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if df.empty or 'close' not in df.columns:
            result['passed'] = False
            result['errors'].append("数据为空或缺少close字段")
            return result

        # 计算收益率
        returns = df['close'].pct_change()

        # 检查异常涨跌幅
        extreme_moves = returns.abs() > max_gap
        if extreme_moves.any():
            count = extreme_moves.sum()
            dates = df.index[extreme_moves].tolist()[:5]

            if self.level == ValidationLevel.STRICT:
                result['passed'] = False
                result['errors'].append(f"发现 {count} 个异常价格跳动 (>{max_gap:.0%})")
                result['errors'].append(f"  问题日期: {dates}")
            else:
                result['warnings'].append(f"发现 {count} 个大幅价格跳动 (>{max_gap:.0%})")

        # 检查价格停滞（连续相同价格）
        price_unchanged = (returns == 0)
        consecutive_unchanged = 0
        max_consecutive = 0

        for unchanged in price_unchanged:
            if unchanged:
                consecutive_unchanged += 1
                max_consecutive = max(max_consecutive, consecutive_unchanged)
            else:
                consecutive_unchanged = 0

        if max_consecutive > 5:  # 连续5天价格不变
            result['warnings'].append(f"发现最长连续 {max_consecutive} 天价格未变化")

            if self.level == ValidationLevel.STRICT and max_consecutive > 10:
                result['passed'] = False
                result['errors'].append("价格长期停滞，数据可能异常")

        # 统计信息
        result['stats'] = {
            'max_daily_return': returns.max(),
            'min_daily_return': returns.min(),
            'avg_daily_return': returns.mean(),
            'volatility': returns.std(),
            'extreme_moves_count': extreme_moves.sum(),
            'unchanged_days': price_unchanged.sum()
        }

        return result

    def validate_volume(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        验证成交量数据
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if df.empty or 'volume' not in df.columns:
            result['warnings'].append("缺少成交量数据")
            return result

        # 检查负成交量
        negative_volume = df['volume'] < 0
        if negative_volume.any():
            count = negative_volume.sum()
            result['passed'] = False
            result['errors'].append(f"发现 {count} 条负成交量记录")

        # 检查零成交量
        zero_volume = df['volume'] == 0
        if zero_volume.any():
            count = zero_volume.sum()
            ratio = count / len(df)

            if ratio > 0.1:  # 超过10%的零成交量
                result['warnings'].append(f"发现 {count} 条零成交量记录 ({ratio:.1%})")

                if self.level == ValidationLevel.STRICT and ratio > 0.2:
                    result['passed'] = False
                    result['errors'].append("零成交量记录过多")

        # 检查成交量异常值（使用IQR方法）
        if 'volume' in df.columns and len(df) > 10:
            Q1 = df['volume'].quantile(0.25)
            Q3 = df['volume'].quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR

            outliers = (df['volume'] < lower_bound) | (df['volume'] > upper_bound)
            if outliers.any():
                count = outliers.sum()
                result['warnings'].append(f"发现 {count} 个成交量异常值")

        # 统计信息
        if 'volume' in df.columns:
            result['stats'] = {
                'avg_volume': df['volume'].mean(),
                'max_volume': df['volume'].max(),
                'min_volume': df['volume'].min(),
                'zero_volume_days': zero_volume.sum(),
                'volume_cv': df['volume'].std() / df['volume'].mean() if df['volume'].mean() > 0 else 0
            }

        return result

    def compare_data_sources(
            self,
            data_dict: Dict[str, pd.DataFrame],
            tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        对比不同数据源的数据
        
        Args:
            data_dict: {source_name: dataframe}
            tolerance: 价格差异容忍度（1%）
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'comparison': {}
        }

        if len(data_dict) < 2:
            result['warnings'].append("需要至少2个数据源进行对比")
            return result

        sources = list(data_dict.keys())
        base_source = sources[0]
        base_df = data_dict[base_source]

        for compare_source in sources[1:]:
            compare_df = data_dict[compare_source]

            comparison = {
                'matching_dates': 0,
                'missing_dates': 0,
                'price_differences': [],
                'volume_differences': []
            }

            # 找出共同日期
            common_dates = base_df.index.intersection(compare_df.index)
            comparison['matching_dates'] = len(common_dates)
            comparison['missing_dates'] = len(base_df.index.symmetric_difference(compare_df.index))

            if len(common_dates) == 0:
                result['errors'].append(f"{base_source} 和 {compare_source} 没有共同日期")
                result['passed'] = False
                continue

            # 对比价格
            for field in ['open', 'high', 'low', 'close']:
                if field in base_df.columns and field in compare_df.columns:
                    base_prices = base_df.loc[common_dates, field]
                    compare_prices = compare_df.loc[common_dates, field]

                    # 计算相对差异
                    rel_diff = (base_prices - compare_prices).abs() / base_prices
                    max_diff = rel_diff.max()

                    if max_diff > tolerance:
                        diff_count = (rel_diff > tolerance).sum()
                        comparison['price_differences'].append({
                            'field': field,
                            'max_diff': max_diff,
                            'diff_count': diff_count
                        })

                        if self.level == ValidationLevel.STRICT:
                            result['passed'] = False
                            result['errors'].append(
                                f"{compare_source} 的 {field} 价格差异过大: {max_diff:.2%}"
                            )
                        else:
                            result['warnings'].append(
                                f"{compare_source} 的 {field} 有 {diff_count} 个价格差异 > {tolerance:.1%}"
                            )

            # 对比成交量
            if 'volume' in base_df.columns and 'volume' in compare_df.columns:
                base_volume = base_df.loc[common_dates, 'volume']
                compare_volume = compare_df.loc[common_dates, 'volume']

                # 成交量差异允许更大
                volume_diff = (base_volume - compare_volume).abs() / base_volume.replace(0, 1)
                if volume_diff.max() > 0.5:  # 50%差异
                    comparison['volume_differences'].append({
                        'max_diff': volume_diff.max(),
                        'avg_diff': volume_diff.mean()
                    })
                    result['warnings'].append(f"{compare_source} 成交量差异较大")

            result['comparison'][f"{base_source}_vs_{compare_source}"] = comparison

        return result

    async def validate_with_backtrader(
            self,
            df: pd.DataFrame,
            symbol: str
    ) -> Dict[str, Any]:
        """
        使用Backtrader进行数据验证
        
        通过运行简单策略测试数据可用性
        """
        if not HAS_BACKTRADER:
            return {
                'passed': None,
                'errors': ['Backtrader未安装'],
                'warnings': [],
                'stats': {}
            }

        result = {
            'passed': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        try:
            # 创建Cerebro引擎
            cerebro = bt.Cerebro()

            # 添加数据
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,
                open='open' if 'open' in df.columns else -1,
                high='high' if 'high' in df.columns else -1,
                low='low' if 'low' in df.columns else -1,
                close='close' if 'close' in df.columns else -1,
                volume='volume' if 'volume' in df.columns else -1,
                openinterest=-1
            )

            cerebro.adddata(data, name=symbol)

            # 添加简单策略
            class TestStrategy(bt.Strategy):
                def __init__(self):
                    self.data_points = 0
                    self.errors = []

                def next(self):
                    self.data_points += 1

                    # 检查数据有效性
                    if self.data.close[0] <= 0:
                        self.errors.append(f"Invalid close price at {self.data.datetime.date(0)}")

                    if len(self.data.high) > 0 and self.data.high[0] < self.data.low[0]:
                        self.errors.append(f"High < Low at {self.data.datetime.date(0)}")

            cerebro.addstrategy(TestStrategy)

            # 运行回测
            initial_cash = 100000
            cerebro.broker.setcash(initial_cash)

            results = cerebro.run()
            strategy = results[0]

            # 获取结果
            final_value = cerebro.broker.getvalue()

            result['stats'] = {
                'data_points_processed': strategy.data_points,
                'initial_cash': initial_cash,
                'final_value': final_value,
                'strategy_errors': len(strategy.errors)
            }

            if strategy.errors:
                result['passed'] = False
                result['errors'].extend(strategy.errors[:5])  # 最多显示5个错误

            if strategy.data_points == 0:
                result['passed'] = False
                result['errors'].append("Backtrader无法处理数据")
            elif strategy.data_points < len(df) * 0.9:
                result['warnings'].append(f"只处理了 {strategy.data_points}/{len(df)} 个数据点")

        except Exception as e:
            result['passed'] = False
            result['errors'].append(f"Backtrader验证失败: {str(e)}")

        return result

    def generate_report(
            self,
            validations: List[Dict[str, Any]],
            output_file: Optional[str] = None
    ) -> str:
        """
        生成验证报告
        
        Args:
            validations: 验证结果列表
            output_file: 输出文件路径
        """
        report = []
        report.append("=" * 70)
        report.append("数据验证报告")
        report.append("=" * 70)
        report.append(f"生成时间: {datetime.now()}")
        report.append(f"验证级别: {self.level.value}")
        report.append("")

        # 汇总统计
        total_tests = len(validations)
        passed_tests = sum(1 for v in validations if v.get('passed', False))
        failed_tests = total_tests - passed_tests

        report.append("验证汇总:")
        report.append(f"  总测试数: {total_tests}")
        report.append(f"  通过: {passed_tests}")
        report.append(f"  失败: {failed_tests}")
        report.append(f"  通过率: {passed_tests / total_tests * 100:.1f}%")
        report.append("")

        # 详细结果
        report.append("-" * 70)
        report.append("详细验证结果:")
        report.append("-" * 70)

        for i, validation in enumerate(validations, 1):
            test_name = validation.get('test_name', f'Test {i}')
            passed = validation.get('passed', False)

            report.append(f"\n{i}. {test_name}")
            report.append(f"   状态: {'✅ 通过' if passed else '❌ 失败'}")

            if validation.get('errors'):
                report.append("   错误:")
                for error in validation['errors']:
                    report.append(f"     - {error}")

            if validation.get('warnings'):
                report.append("   警告:")
                for warning in validation['warnings']:
                    report.append(f"     - {warning}")

            if validation.get('stats'):
                report.append("   统计:")
                for key, value in validation['stats'].items():
                    if isinstance(value, float):
                        report.append(f"     - {key}: {value:.4f}")
                    else:
                        report.append(f"     - {key}: {value}")

        # 建议
        report.append("")
        report.append("-" * 70)
        report.append("建议:")
        report.append("-" * 70)

        if failed_tests > 0:
            report.append("- 检查数据源的数据质量")
            report.append("- 验证数据获取和转换逻辑")
            report.append("- 考虑使用更可靠的数据源")
        else:
            report.append("- 数据质量良好，可以用于回测")
            report.append("- 建议定期进行数据验证")
            report.append("- 保持数据源的更新和维护")

        report_text = "\n".join(report)

        # 保存到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"验证报告已保存到: {output_file}")

        return report_text


# 便捷函数
async def validate_data(
        df: pd.DataFrame,
        symbol: str,
        level: ValidationLevel = ValidationLevel.STANDARD
) -> Dict[str, Any]:
    """
    验证单个数据源
    
    Args:
        df: 数据DataFrame
        symbol: 股票代码
        level: 验证级别
    """
    validator = DataValidator(level)

    validations = []

    # OHLC关系验证
    ohlc_result = validator.validate_ohlc_relationships(df)
    ohlc_result['test_name'] = 'OHLC关系验证'
    validations.append(ohlc_result)

    # 时间序列验证
    time_result = validator.validate_time_series(df)
    time_result['test_name'] = '时间序列验证'
    validations.append(time_result)

    # 价格连续性验证
    price_result = validator.validate_price_continuity(df)
    price_result['test_name'] = '价格连续性验证'
    validations.append(price_result)

    # 成交量验证
    volume_result = validator.validate_volume(df)
    volume_result['test_name'] = '成交量验证'
    validations.append(volume_result)

    # Backtrader验证
    bt_result = await validator.validate_with_backtrader(df, symbol)
    bt_result['test_name'] = 'Backtrader兼容性验证'
    validations.append(bt_result)

    # 生成报告
    report = validator.generate_report(validations)

    return {
        'symbol': symbol,
        'validations': validations,
        'report': report,
        'passed': all(v.get('passed', False) for v in validations)
    }
