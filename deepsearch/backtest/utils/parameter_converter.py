"""
参数类型转换器
用于将API接收的各种格式数据转换为Backtrader期望的类型
"""
from typing import Dict, Any, Union, Type, Tuple, Optional
from loguru import logger


class ParameterConverter:
    """
    策略参数类型转换器
    
    负责将前端API传入的参数（可能是字符串、数字等）
    转换为Backtrader策略期望的正确类型
    """
    
    # 定义每个策略的参数类型映射
    STRATEGY_PARAM_TYPES = {
        'simple_ma': {
            'short_period': int,
            'long_period': int,
            'position_size': (int, type(None)),  # 可以是int或None
            'position_pct': float,
            'stop_loss': float,
            'take_profit': float,
            'printlog': bool
        },
        'momentum': {
            'momentum_period': int,
            'volume_period': int,
            'breakout_period': int,
            'atr_period': int,
            'atr_multiplier': float,
            'momentum_threshold': float,
            'volume_multiplier': float,
            'max_holding_period': int,
            'position_size': (int, type(None)),
            'position_pct': float,
            'use_trailing_stop': bool,
            'printlog': bool
        },
        'turtle': {
            'entry_period': int,
            'exit_period': int,
            'atr_period': int,
            'risk_percent': float,
            'max_units': int,
            'stop_atr_multiplier': float,
            'pyramid_atr': float,
            'position_size': (int, type(None)),
            'position_pct': float,
            'printlog': bool
        },
        'mean_reversion': {
            'lookback_period': int,
            'entry_threshold': float,
            'exit_threshold': float,
            'stop_loss': float,
            'position_size': (int, type(None)),
            'position_pct': float,
            'use_volume_filter': bool,
            'volume_factor': float,
            'printlog': bool
        }
    }
    
    # 通用参数类型（适用于所有策略）
    COMMON_PARAM_TYPES = {
        'position_size': (int, type(None)),
        'position_pct': float,
        'printlog': bool,
        'stop_loss': float,
        'take_profit': float
    }
    
    @classmethod
    def convert_strategy_params(cls, strategy: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换策略参数到正确的类型
        
        Args:
            strategy: 策略名称
            params: 原始参数字典
            
        Returns:
            转换后的参数字典
            
        Raises:
            ValueError: 参数转换失败时
        """
        if not params:
            return {}
            
        converted = {}
        
        # 获取策略特定的类型映射
        type_map = cls.STRATEGY_PARAM_TYPES.get(strategy, {})
        
        # 如果没有找到策略特定的映射，使用通用映射
        if not type_map:
            logger.warning(f"未找到策略 {strategy} 的参数类型定义，使用通用类型")
            type_map = cls.COMMON_PARAM_TYPES
        
        for key, value in params.items():
            try:
                if key in type_map:
                    expected_type = type_map[key]
                    converted[key] = cls._convert_value(value, expected_type, key)
                    logger.debug(f"参数 {key}: {value} ({type(value).__name__}) -> "
                               f"{converted[key]} ({type(converted[key]).__name__})")
                else:
                    # 未定义的参数，保持原样
                    converted[key] = value
                    logger.debug(f"参数 {key} 未定义类型，保持原值: {value}")
                    
            except Exception as e:
                logger.error(f"转换参数 {key} 失败: {e}")
                raise ValueError(f"参数 {key} 转换失败: {e}")
                
        return converted
    
    @classmethod
    def _convert_value(cls, value: Any, expected_type: Union[Type, Tuple], param_name: str = "") -> Any:
        """
        转换单个值到期望的类型
        
        Args:
            value: 要转换的值
            expected_type: 期望的类型或类型元组
            param_name: 参数名称（用于错误信息）
            
        Returns:
            转换后的值
            
        Raises:
            ValueError: 无法转换到期望类型
        """
        # 处理None值
        if value is None or value == 'None' or value == 'null' or value == '':
            # 检查是否允许None
            if isinstance(expected_type, tuple) and type(None) in expected_type:
                return None
            # 如果不允许None但是收到了空值，某些参数可以有默认值
            if param_name == 'position_size':
                return None  # position_size 允许为None
            elif expected_type == bool:
                return False  # 布尔值默认False
            elif expected_type in (int, float):
                raise ValueError(f"数值参数不能为空")
            return None
            
        # 处理元组类型（多种可能的类型）
        if isinstance(expected_type, tuple):
            # 尝试每种可能的类型
            for typ in expected_type:
                if typ is type(None):
                    continue
                try:
                    return cls._convert_single_type(value, typ)
                except (ValueError, TypeError):
                    continue
            # 如果所有类型都失败了
            type_names = [t.__name__ for t in expected_type if t is not type(None)]
            raise ValueError(f"无法转换为任何期望的类型: {', '.join(type_names)}")
        else:
            return cls._convert_single_type(value, expected_type)
    
    @classmethod
    def _convert_single_type(cls, value: Any, expected_type: Type) -> Any:
        """
        转换到单一类型
        
        Args:
            value: 要转换的值
            expected_type: 目标类型
            
        Returns:
            转换后的值
        """
        # 如果已经是正确的类型，直接返回
        if isinstance(value, expected_type):
            return value
            
        # 布尔值转换
        if expected_type == bool:
            return cls._to_bool(value)
            
        # 整数转换
        elif expected_type == int:
            # 处理可能的浮点数字符串如 "100.0"
            if isinstance(value, str):
                value = value.strip()
                # 移除可能的千分位分隔符
                value = value.replace(',', '')
            return int(float(value))
            
        # 浮点数转换
        elif expected_type == float:
            if isinstance(value, str):
                value = value.strip()
                # 移除可能的千分位分隔符和百分号
                value = value.replace(',', '').rstrip('%')
            return float(value)
            
        # 字符串转换
        elif expected_type == str:
            return str(value)
            
        else:
            # 其他类型，尝试直接转换
            return expected_type(value)
    
    @staticmethod
    def _to_bool(value: Any) -> bool:
        """
        转换值为布尔类型
        
        Args:
            value: 要转换的值
            
        Returns:
            布尔值
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.strip().lower()
            if value in ('true', 'yes', '1', 'on', '是', '真'):
                return True
            elif value in ('false', 'no', '0', 'off', '否', '假', ''):
                return False
            else:
                raise ValueError(f"无法将 '{value}' 转换为布尔值")
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(value)
    
    @classmethod
    def get_strategy_param_info(cls, strategy: str) -> Dict[str, str]:
        """
        获取策略参数类型信息（用于文档或前端提示）
        
        Args:
            strategy: 策略名称
            
        Returns:
            参数类型信息字典
        """
        type_map = cls.STRATEGY_PARAM_TYPES.get(strategy, cls.COMMON_PARAM_TYPES)
        info = {}
        
        for param_name, param_type in type_map.items():
            if isinstance(param_type, tuple):
                # 多种可能的类型
                type_names = []
                for t in param_type:
                    if t is type(None):
                        type_names.append('null')
                    else:
                        type_names.append(t.__name__)
                info[param_name] = ' | '.join(type_names)
            else:
                info[param_name] = param_type.__name__
                
        return info


class DataValidator:
    """
    数据验证器
    
    验证回测配置的合法性
    """
    
    @classmethod
    def validate_backtest_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和清理回测配置
        
        Args:
            config: 原始配置字典
            
        Returns:
            验证和转换后的配置
            
        Raises:
            ValueError: 配置无效时
        """
        from datetime import datetime
        
        # 验证必需字段
        required_fields = ['strategy', 'symbols', 'start_date', 'end_date']
        for field in required_fields:
            if field not in config or not config[field]:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证日期格式
        try:
            start_date = datetime.strptime(config['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(config['end_date'], '%Y-%m-%d')
            if start_date >= end_date:
                raise ValueError("开始日期必须早于结束日期")
        except ValueError as e:
            raise ValueError(f"日期格式错误: {e}")
        
        # 验证数值范围
        initial_cash = float(config.get('initial_cash', 100000))
        if initial_cash <= 0:
            raise ValueError("初始资金必须大于0")
        config['initial_cash'] = initial_cash
        
        commission = float(config.get('commission', 0.001))
        if not 0 <= commission <= 1:
            raise ValueError("手续费率必须在0-1之间")
        config['commission'] = commission
        
        slippage = float(config.get('slippage', 0.0))
        if slippage < 0:
            raise ValueError("滑点不能为负数")
        config['slippage'] = slippage
        
        # 验证股票代码列表
        symbols = config.get('symbols', [])
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            raise ValueError("至少需要一个股票代码")
        config['symbols'] = symbols
        
        # 转换策略参数
        strategy_params = config.get('strategy_params', {})
        if strategy_params:
            converter = ParameterConverter()
            try:
                config['strategy_params'] = converter.convert_strategy_params(
                    config['strategy'],
                    strategy_params
                )
            except ValueError as e:
                raise ValueError(f"策略参数转换失败: {e}")
        
        return config
    
    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """
        验证日期格式是否为 YYYY-MM-DD
        
        Args:
            date_str: 日期字符串
            
        Returns:
            是否有效
        """
        from datetime import datetime
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False