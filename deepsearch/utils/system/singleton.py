"""
单例模式实现
"""

from typing import Any, Dict


class Singleton(type):
    """
    单例元类

    使用方法：
        class MyClass(metaclass=Singleton):
            pass
    """

    _instances: Dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
