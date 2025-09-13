"""
诊断日志系统

用于详细记录系统运行的每一个细节，帮助定位问题。
"""
import functools
import inspect
import json
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable


class DiagnosticLogger:
    """诊断日志记录器"""

    def __init__(self):
        self.log_file = Path("diagnostic_log.json")
        self.entries = []
        self._lock = threading.Lock()
        self._start_time = time.time()

        # 初始化日志文件
        self.log_event("DIAGNOSTIC_START", "DiagnosticLogger.__init__", {
            "start_time": datetime.now().isoformat(),
            "log_file": str(self.log_file)
        })

    def get_elapsed_time(self) -> float:
        """获取从开始到现在的经过时间"""
        return time.time() - self._start_time

    def log_event(self, event_type: str, location: str, details: Dict[str, Any], error: Optional[Exception] = None):
        """记录事件"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed": self.get_elapsed_time(),
            "thread_id": threading.current_thread().ident,
            "thread_name": threading.current_thread().name,
            "event_type": event_type,
            "location": location,
            "details": self._serialize_details(details),
            "error": str(error) if error else None,
            "error_type": type(error).__name__ if error else None,
            "traceback": traceback.format_exc() if error else None
        }

        with self._lock:
            self.entries.append(entry)

            # 实时写入文件
            try:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(self.entries, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Warning: Failed to write diagnostic log: {e}")

    def _serialize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """序列化详情，确保可以JSON编码"""
        result = {}
        for key, value in details.items():
            try:
                # 尝试直接序列化
                json.dumps(value)
                result[key] = value
            except (TypeError, ValueError):
                # 如果失败，转换为字符串
                result[key] = str(value)
                # 对于对象，尝试获取更多信息
                if hasattr(value, '__dict__'):
                    result[f"{key}_attrs"] = {
                        k: str(v) for k, v in value.__dict__.items()
                        if not k.startswith('_') and not callable(v)
                    }
                if hasattr(value, '__class__'):
                    result[f"{key}_type"] = f"{value.__class__.__module__}.{value.__class__.__name__}"
        return result

    def diagnostic_method(self, func: Callable) -> Callable:
        """装饰器：记录方法调用"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            location = f"{func.__module__}.{func.__name__}"

            # 记录方法参数
            arg_info = {}
            try:
                # 获取参数名
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                for param_name, param_value in bound_args.arguments.items():
                    if param_name == 'self':
                        arg_info['self_type'] = type(param_value).__name__
                        arg_info['self_id'] = id(param_value)
                    else:
                        arg_info[param_name] = str(param_value)[:200]
            except Exception:
                arg_info = {
                    "args": str(args)[:200],
                    "kwargs": str(kwargs)[:200]
                }

            self.log_event("METHOD_START", location, arg_info)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                result_info = {
                    "duration": duration,
                    "result_type": type(result).__name__,
                    "result_preview": str(result)[:200] if result is not None else "None",
                    "result_id": id(result) if result is not None else None
                }

                self.log_event("METHOD_SUCCESS", location, result_info)

                return result
            except Exception as e:
                duration = time.time() - start_time
                self.log_event("METHOD_ERROR", location, {
                    "duration": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }, error=e)
                raise

        # 支持异步方法
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                location = f"{func.__module__}.{func.__name__}"

                # 记录方法参数
                arg_info = {}
                try:
                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()

                    for param_name, param_value in bound_args.arguments.items():
                        if param_name == 'self':
                            arg_info['self_type'] = type(param_value).__name__
                            arg_info['self_id'] = id(param_value)
                        else:
                            arg_info[param_name] = str(param_value)[:200]
                except Exception:
                    arg_info = {
                        "args": str(args)[:200],
                        "kwargs": str(kwargs)[:200]
                    }

                self.log_event("ASYNC_METHOD_START", location, arg_info)

                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time

                    result_info = {
                        "duration": duration,
                        "result_type": type(result).__name__,
                        "result_preview": str(result)[:200] if result is not None else "None",
                        "result_id": id(result) if result is not None else None
                    }

                    self.log_event("ASYNC_METHOD_SUCCESS", location, result_info)

                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.log_event("ASYNC_METHOD_ERROR", location, {
                        "duration": duration,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }, error=e)
                    raise

            return async_wrapper

        return wrapper

    def diagnostic_class(self, cls):
        """装饰器：记录类的所有公共方法"""
        # 记录类创建
        self.log_event("CLASS_DECORATED", f"{cls.__module__}.{cls.__name__}", {
            "methods": [name for name, _ in inspect.getmembers(cls, inspect.ismethod)],
            "attributes": [name for name in dir(cls) if not name.startswith('_')]
        })

        # 装饰所有公共方法
        for name, method in inspect.getmembers(cls):
            if not name.startswith('_') and (inspect.ismethod(method) or inspect.isfunction(method)):
                setattr(cls, name, self.diagnostic_method(method))

        return cls


# 导入异步支持
try:
    import asyncio
except ImportError:
    asyncio = None

# 全局诊断日志实例
diagnostic_logger = DiagnosticLogger()


# 便捷函数
def log_diagnostic(event_type: str, location: str, details: Dict[str, Any], error: Optional[Exception] = None):
    """便捷的日志记录函数"""
    diagnostic_logger.log_event(event_type, location, details, error)
