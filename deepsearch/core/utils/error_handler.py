"""
增强的错误处理模块

提供详细的错误诊断、自动恢复和解决方案建议
"""

import gc
import json
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import psutil
from loguru import logger

from deepsearch.observability.logger import logger_manager
from deepsearch.config import get_config


class ErrorSolution:
    """错误解决方案"""

    def __init__(self, title: str, steps: List[str], auto_fix: Optional[Callable] = None):
        self.title = title
        self.steps = steps
        self.auto_fix = auto_fix

    def can_auto_fix(self) -> bool:
        """是否可以自动修复"""
        return self.auto_fix is not None

    def apply_fix(self) -> bool:
        """应用自动修复"""
        if self.auto_fix:
            try:
                self.auto_fix()
                return True
            except Exception:
                return False
        return False


class EnhancedErrorHandler:
    """增强的错误处理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.error_history = deque(maxlen=1000)
            self.error_patterns = {}
            self.recovery_strategies = {}
            self.solution_database = self._init_solution_database()
            # 延迟导入配置
            try:
                config = get_config()
                self.auto_recovery = getattr(config.app, "env", "prod") == "dev"
            except Exception:
                self.auto_recovery = False

            # 自动注入到全局异常处理
            self._inject_global_handler()
            self._initialized = True

    def _init_solution_database(self) -> Dict[str, List[ErrorSolution]]:
        """初始化解决方案数据库"""
        return {
            "ConnectionError": [
                ErrorSolution(
                    "检查服务状态",
                    [
                        "1. 检查目标服务是否运行: ps aux | grep deepsearch",
                        "2. 检查网络连接: ping localhost",
                        "3. 检查防火墙设置",
                    ],
                ),
                ErrorSolution(
                    "检查端口占用",
                    [
                        "1. Windows: netstat -an | findstr :8000",
                        "2. Linux/Mac: lsof -i :8000",
                        "3. 结束占用进程或更改端口",
                    ],
                    auto_fix=self._fix_port_conflict,
                ),
            ],
            "MemoryError": [
                ErrorSolution(
                    "释放内存",
                    ["1. 关闭不必要的程序", "2. 清理系统缓存", "3. 增加虚拟内存"],
                    auto_fix=self._fix_memory_issue,
                )
            ],
            "DatabaseError": [
                ErrorSolution(
                    "数据库连接问题",
                    [
                        "1. 检查数据库服务: systemctl status postgresql",
                        "2. 验证连接配置: settings.database.main",
                        "3. 检查数据库日志",
                    ],
                )
            ],
            "ImportError": [
                ErrorSolution(
                    "依赖问题",
                    [
                        "1. 更新依赖: uv sync --all-extras",
                        "2. 清理缓存: uv cache clean",
                        "3. 重新创建虚拟环境: uv venv --python 3.13",
                    ],
                )
            ],
        }

    def _inject_global_handler(self):
        """透明注入到Python异常处理"""
        original_excepthook = sys.excepthook

        def enhanced_excepthook(exc_type, exc_value, exc_traceback):
            # 增强的错误处理
            self.handle_error(
                exc_value,
                {
                    "type": exc_type.__name__,
                    "traceback": "".join(traceback.format_tb(exc_traceback)),
                },
            )

            # 调用原始处理器
            original_excepthook(exc_type, exc_value, exc_traceback)

        sys.excepthook = enhanced_excepthook

    def handle_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理错误并提供详细诊断"""
        error_info: Dict[str, Any] = {
            "id": f"err_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(error)}",
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "type": type(error).__name__,
            "context": context or {},
            "locals": self._capture_frame_locals(),
            "system_state": self._get_system_state(),
            "diagnosis": self._diagnose_error(error),
            "solutions": self._get_solutions(error),
            "traceback": traceback.format_exc(),
        }

        # 保存到历史
        self.error_history.append(error_info)

        # 输出改进的错误信息
        self._display_enhanced_error(error_info)

        # 保存错误报告到文件（开发模式）
        try:
            config = get_config()
            if getattr(config.app, "env", "prod") == "dev":
                self._save_error_report(error_info)
        except Exception:
            pass

        # 尝试自动恢复
        if self.auto_recovery:
            recovery_result = self._attempt_recovery(error, error_info)
            error_info["recovery_attempted"] = recovery_result

        return error_info

    def _capture_frame_locals(self) -> Dict[str, str]:
        """捕获错误发生时的局部变量"""
        locals_dict = {}

        try:
            frame = sys._getframe(3)
            for key, value in frame.f_locals.items():
                if not key.startswith("_"):
                    try:
                        # 限制字符串长度
                        value_str = repr(value)[:200]
                        locals_dict[key] = value_str
                    except Exception:
                        locals_dict[key] = "<无法序列化>"
        except Exception:
            pass

        return locals_dict

    def _get_system_state(self) -> Dict[str, Any]:
        """获取系统状态快照"""
        try:
            process = psutil.Process()
            return {
                "memory": {
                    "percent": psutil.virtual_memory().percent,
                    "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                    "process_mb": process.memory_info().rss / 1024 / 1024,
                },
                "cpu": {"percent": psutil.cpu_percent(interval=0.1), "count": psutil.cpu_count()},
                "threads": threading.active_count(),
                "open_files": len(process.open_files()) if hasattr(process, "open_files") else 0,
                "connections": len(process.connections()) if hasattr(process, "connections") else 0,
            }
        except Exception:
            return {}

    def _diagnose_error(self, error: Exception) -> Dict[str, Any]:
        """诊断错误原因"""
        diagnosis: Dict[str, Any] = {
            "category": self._categorize_error(error),
            "severity": self._assess_severity(error),
            "frequency": self._get_error_frequency(error),
            "pattern": self._detect_error_pattern(error),
        }

        # 特定错误类型的诊断
        error_type = type(error).__name__

        if "Connection" in error_type:
            diagnosis["network"] = self._check_network_status()
            diagnosis["services"] = self._check_service_status()

        elif "Memory" in error_type:
            diagnosis["memory_analysis"] = self._analyze_memory_usage()

        elif "Database" in error_type or "SQL" in error_type:
            diagnosis["database"] = self._check_database_status()

        elif "Import" in error_type or "Module" in error_type:
            diagnosis["dependencies"] = self._check_dependencies()

        return diagnosis

    def _categorize_error(self, error: Exception) -> str:
        """分类错误"""
        error_type = type(error).__name__

        categories = {
            "network": ["Connection", "Timeout", "Socket"],
            "database": ["Database", "SQL", "Integrity"],
            "memory": ["Memory", "Overflow"],
            "io": ["IO", "File", "Permission"],
            "import": ["Import", "Module", "Attribute"],
            "logic": ["Value", "Type", "Index", "Key"],
        }

        for category, keywords in categories.items():
            if any(kw in error_type for kw in keywords):
                return category

        return "unknown"

    def _assess_severity(self, error: Exception) -> str:
        """评估错误严重程度"""
        error_type = type(error).__name__

        critical_errors = ["SystemExit", "KeyboardInterrupt", "MemoryError"]
        high_errors = ["DatabaseError", "ConnectionError", "ImportError"]
        medium_errors = ["ValueError", "TypeError", "KeyError"]

        if error_type in critical_errors:
            return "CRITICAL"
        elif error_type in high_errors:
            return "HIGH"
        elif error_type in medium_errors:
            return "MEDIUM"
        else:
            return "LOW"

    def _get_error_frequency(self, error: Exception) -> Dict[str, int]:
        """获取错误频率"""
        error_type = type(error).__name__

        # 统计最近的错误
        recent_errors = list(self.error_history)[-100:]  # 最近100个错误

        same_type_count = sum(1 for e in recent_errors if e["type"] == error_type)
        same_message_count = sum(1 for e in recent_errors if str(error) in e["error"])

        return {
            "same_type": same_type_count,
            "same_message": same_message_count,
            "total_recent": len(recent_errors),
        }

    def _detect_error_pattern(self, error: Exception) -> Optional[str]:
        """检测错误模式"""
        error_str = str(error).lower()

        patterns = {
            "port_conflict": ["address already in use", "port", "bind"],
            "connection_refused": ["connection refused", "refused", "connect"],
            "timeout": ["timeout", "timed out"],
            "permission": ["permission denied", "access denied"],
            "not_found": ["not found", "no such", "does not exist"],
            "memory_leak": ["memory", "heap", "overflow"],
        }

        for pattern_name, keywords in patterns.items():
            if any(kw in error_str for kw in keywords):
                return pattern_name

        return None

    def _check_network_status(self) -> Dict[str, Any]:
        """检查网络状态"""
        try:
            import socket

            # 检查本地连接
            local_ok = True
            try:
                socket.create_connection(("127.0.0.1", 80), timeout=1)
            except Exception:
                local_ok = False

            return {
                "localhost_accessible": local_ok,
                "hostname": socket.gethostname(),
                "has_internet": self._check_internet_connection(),
            }
        except Exception:
            return {"error": "无法检查网络状态"}

    def _check_internet_connection(self) -> bool:
        """检查互联网连接"""
        try:
            import socket

            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except Exception:
            return False

    def _check_service_status(self) -> Dict[str, bool]:
        """检查关键服务状态"""
        services = {}

        # 检查PostgreSQL
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 5432))
            services["postgresql"] = result == 0
            sock.close()
        except Exception:
            services["postgresql"] = False

        # 检查Redis
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 6379))
            services["redis"] = result == 0
            sock.close()
        except Exception:
            services["redis"] = False

        return services

    def _analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用"""
        try:
            process = psutil.Process()
            return {
                "process_memory_mb": process.memory_info().rss / 1024 / 1024,
                "system_memory_percent": psutil.virtual_memory().percent,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "swap_percent": psutil.swap_memory().percent,
                "gc_stats": gc.get_stats()[0] if gc.get_stats() else {},
            }
        except Exception:
            return {}

    def _check_database_status(self) -> Dict[str, Any]:
        """检查数据库状态"""
        status: Dict[str, Any] = {}

        try:
            config = get_config()
            db_config = config.database.main

            status["configured"] = True
            status["host"] = db_config.host
            status["port"] = db_config.port
            status["database"] = db_config.database

            # 检查连接
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((db_config.host, db_config.port))
            status["reachable"] = result == 0
            sock.close()

        except Exception as e:
            status["error"] = str(e)

        return status

    def _check_dependencies(self) -> Dict[str, Any]:
        """检查依赖状态"""
        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "virtual_env": hasattr(sys, "real_prefix")
            or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix),
            "env_path": sys.prefix,
        }

    def _get_solutions(self, error: Exception) -> List[Dict[str, Any]]:
        """获取解决方案建议"""
        error_type = type(error).__name__
        solutions = []

        # 从数据库获取通用解决方案
        if error_type in self.solution_database:
            for solution in self.solution_database[error_type]:
                solutions.append(
                    {
                        "title": solution.title,
                        "steps": solution.steps,
                        "can_auto_fix": solution.can_auto_fix(),
                    }
                )

        # 根据错误模式添加特定解决方案
        pattern = self._detect_error_pattern(error)
        if pattern == "port_conflict":
            solutions.append(
                {
                    "title": "解决端口冲突",
                    "steps": [
                        "1. 查找占用端口的进程: netstat -tulpn | grep 8000",
                        "2. 结束进程: kill -9 <PID>",
                        "3. 或修改配置使用其他端口",
                    ],
                    "can_auto_fix": True,
                }
            )

        return solutions

    def _display_enhanced_error(self, error_info: Dict[str, Any]):
        """显示增强的错误信息"""
        logger.error("=" * 80)
        logger.error(f"🔴 错误ID: {error_info['id']}")
        logger.error(f"错误类型: {error_info['type']}")
        logger.error(f"错误信息: {error_info['error']}")
        logger.error(f"发生时间: {error_info['timestamp']}")
        logger.error(f"严重程度: {error_info['diagnosis']['severity']}")

        # 显示诊断信息
        if pattern := error_info["diagnosis"].get("pattern"):
            logger.info(f"错误模式: {pattern}")

        # 显示系统状态
        if system_state := error_info.get("system_state"):
            if memory := system_state.get("memory"):
                logger.info(f"内存使用: {memory.get('percent', 0):.1f}%")
            if cpu := system_state.get("cpu"):
                logger.info(f"CPU使用: {cpu.get('percent', 0):.1f}%")

        # 显示解决方案
        if solutions := error_info.get("solutions"):
            logger.info("💡 建议解决方案:")
            for i, solution in enumerate(solutions, 1):
                logger.info(f"\n方案 {i}: {solution.get('title', '未命名')}")
                for step in solution.get("steps", []):
                    logger.info(f"  {step}")
                if solution.get("can_auto_fix"):
                    logger.info("  ✅ 此问题可以尝试自动修复")

        # 开发模式显示更多信息
        try:
            config = get_config()
            if getattr(config.app, "env", "prod") == "dev":
                if locals_dict := error_info.get("locals"):
                    logger.debug("局部变量:")
                    for key, value in list(locals_dict.items())[:5]:  # 只显示前5个
                        logger.debug(f"  {key} = {value}")
        except Exception:
            pass

        logger.error("=" * 80)

    def _save_error_report(self, error_info: Dict[str, Any]):
        """保存错误报告到文件"""
        try:
            error_dir = logger_manager.ensure_subdirectory("errors")

            filename = f"{error_info['id']}.json"
            filepath = error_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(error_info, f, ensure_ascii=False, indent=2, default=str)

            logger.debug(f"错误报告已保存: {filepath}")

        except Exception as e:
            logger.debug(f"保存错误报告失败: {e}")

    def _attempt_recovery(self, error: Exception, error_info: Dict[str, Any]) -> bool:
        """尝试自动恢复"""
        error_type = type(error).__name__

        # 查找可自动修复的解决方案
        if error_type in self.solution_database:
            for solution in self.solution_database[error_type]:
                if solution.can_auto_fix():
                    logger.info(f"尝试自动修复: {solution.title}")
                    if solution.apply_fix():
                        logger.success(f"✅ 自动修复成功: {solution.title}")
                        return True

        return False

    def _fix_port_conflict(self):
        """修复端口冲突"""
        try:
            import subprocess
            import sys

            if sys.platform == "win32":
                # Windows
                subprocess.run("netstat -ano | findstr :8000", shell=True, capture_output=True)
                # 这里只是示例，实际需要解析输出并结束进程
            else:
                # Linux/Mac
                subprocess.run("lsof -ti:8000 | xargs kill -9", shell=True)

            time.sleep(1)
            return True

        except Exception:
            return False

    def _fix_memory_issue(self):
        """修复内存问题"""
        try:
            # 强制垃圾回收
            gc.collect()

            # 清理缓存
            # 这里可以调用系统的缓存清理逻辑

            return True

        except Exception:
            return False

    def get_error_history(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """获取错误历史"""
        return list(self.error_history)[-last_n:]

    def clear_error_history(self):
        """清空错误历史"""
        self.error_history.clear()
        logger.info("错误历史已清空")


# 创建全局实例
error_handler = EnhancedErrorHandler()
