"""
AmazingData SDK安全包装器

提供SDK方法的安全调用接口，通过进程隔离防止崩溃。

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-20
"""
import time
from typing import Any, Dict, Optional, Tuple
from loguru import logger

from .amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    RequestType,
    get_proxy
)


class AmazingDataSafeWrapper:
    """
    AmazingData SDK安全包装器

    通过进程代理调用SDK，提供：
    - 崩溃隔离
    - 自动重试
    - 超时控制
    - 错误处理
    - 降级支持
    """

    def __init__(
        self,
        auto_restart: bool = True,
        max_retries: int = 3,
        default_timeout: float = 30.0
    ):
        """
        初始化安全包装器

        Args:
            auto_restart: 进程崩溃后是否自动重启
            max_retries: 最大重试次数
            default_timeout: 默认超时时间
        """
        self.auto_restart = auto_restart
        self.max_retries = max_retries
        self.default_timeout = default_timeout

        # 获取进程代理
        self.proxy = get_proxy()

        # 连接状态
        self.is_connected = False
        self.login_info = None

        # 统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "crashes_handled": 0
        }

    def safe_login(
        self,
        username: str,
        password: str,
        host: str = "101.230.159.234",
        port: int = 8600,
        timeout: float = 30.0
    ) -> Tuple[bool, Optional[str]]:
        """
        安全的登录方法

        Args:
            username: 用户名
            password: 密码
            host: 服务器地址
            port: 端口
            timeout: 超时时间

        Returns:
            (成功标志, 错误信息)
        """
        logger.info(f"[SafeWrapper] Attempting login: {username}@{host}:{port}")

        # 重试逻辑
        for attempt in range(self.max_retries):
            if attempt > 0:
                logger.info(f"[SafeWrapper] Retry attempt {attempt + 1}/{self.max_retries}")
                time.sleep(2 ** attempt)  # 指数退避

            try:
                # 通过进程代理执行登录
                response = self.proxy.execute(
                    "login",
                    username,
                    password,
                    host,
                    port,
                    request_type=RequestType.LOGIN,
                    timeout=timeout
                )

                if response.success:
                    logger.info("[SafeWrapper] Login successful")
                    self.is_connected = True
                    self.login_info = {
                        "username": username,
                        "host": host,
                        "port": port,
                        "login_time": time.time()
                    }
                    self.stats["successful_calls"] += 1
                    return True, None

                elif response.error_type == "SystemExit":
                    # SDK尝试退出，这是最严重的错误
                    logger.critical("[SafeWrapper] SDK attempted SystemExit during login")
                    self.stats["crashes_handled"] += 1

                    error_msg = (
                        "AmazingData SDK崩溃（SystemExit）。可能原因：\n"
                        "1. 网络连接失败\n"
                        "2. 服务器地址或端口错误\n"
                        "3. 认证信息无效\n"
                        f"详细错误：{response.error}"
                    )

                    # 最后一次重试
                    if attempt == self.max_retries - 1:
                        self.stats["failed_calls"] += 1
                        return False, error_msg

                elif response.error_type == "ProcessCrash":
                    # 进程崩溃
                    logger.error("[SafeWrapper] Worker process crashed")
                    self.stats["crashes_handled"] += 1

                    # 尝试重启进程
                    if self.auto_restart and self.proxy.start():
                        logger.info("[SafeWrapper] Worker process restarted")
                        continue
                    else:
                        self.stats["failed_calls"] += 1
                        return False, "工作进程崩溃且无法重启"

                elif response.error_type == "Timeout":
                    # 超时
                    logger.warning(f"[SafeWrapper] Login timeout after {timeout}s")
                    if attempt < self.max_retries - 1:
                        continue
                    else:
                        self.stats["failed_calls"] += 1
                        return False, f"登录超时（{timeout}秒）"

                else:
                    # 其他错误
                    logger.error(f"[SafeWrapper] Login failed: {response.error}")
                    if attempt < self.max_retries - 1:
                        self.stats["retries"] += 1
                        continue
                    else:
                        self.stats["failed_calls"] += 1
                        return False, response.error or "未知错误"

            except Exception as e:
                logger.error(f"[SafeWrapper] Unexpected error: {e}")
                if attempt < self.max_retries - 1:
                    self.stats["retries"] += 1
                    continue
                else:
                    self.stats["failed_calls"] += 1
                    return False, str(e)

        self.stats["failed_calls"] += 1
        return False, "所有重试均失败"

    def safe_logout(self, username: str = None) -> bool:
        """
        安全的登出方法

        Args:
            username: 用户名

        Returns:
            是否成功
        """
        # 直接返回成功，避免SDK崩溃
        logger.info("[SafeWrapper] Skipping logout to avoid SDK crash")
        self.is_connected = False
        self.login_info = None
        return True

    def safe_get_data(
        self,
        method: str,
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        安全的数据获取方法

        Args:
            method: SDK方法名
            *args: 位置参数
            timeout: 超时时间
            **kwargs: 关键字参数

        Returns:
            (成功标志, 结果数据, 错误信息)
        """
        if not self.is_connected:
            return False, None, "未登录"

        timeout = timeout or self.default_timeout
        logger.debug(f"[SafeWrapper] Calling {method} with timeout={timeout}s")

        self.stats["total_calls"] += 1

        try:
            response = self.proxy.execute(
                method,
                *args,
                request_type=RequestType.GET_DATA,
                timeout=timeout,
                **kwargs
            )

            if response.success:
                self.stats["successful_calls"] += 1
                return True, response.result, None
            else:
                self.stats["failed_calls"] += 1

                # 处理特殊错误
                if response.error_type == "SystemExit":
                    self.stats["crashes_handled"] += 1
                    logger.critical(f"[SafeWrapper] SDK crashed during {method}")
                    return False, None, "SDK崩溃（SystemExit）"

                elif response.error_type == "ProcessCrash":
                    self.stats["crashes_handled"] += 1
                    logger.error(f"[SafeWrapper] Process crashed during {method}")
                    return False, None, "进程崩溃"

                return False, None, response.error or "未知错误"

        except Exception as e:
            logger.error(f"[SafeWrapper] Error calling {method}: {e}")
            self.stats["failed_calls"] += 1
            return False, None, str(e)

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            是否健康
        """
        return self.proxy.health_check()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        stats = self.stats.copy()
        stats["proxy_stats"] = self.proxy.get_stats()
        stats["is_connected"] = self.is_connected
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "crashes_handled": 0
        }


# 全局包装器实例
_global_wrapper = None


def get_safe_wrapper() -> AmazingDataSafeWrapper:
    """
    获取全局安全包装器实例（单例模式）

    Returns:
        安全包装器实例
    """
    global _global_wrapper
    if _global_wrapper is None:
        _global_wrapper = AmazingDataSafeWrapper()
    return _global_wrapper


def test_connection(
    username: str,
    password: str,
    host: str = "101.230.159.234",
    port: int = 8600
) -> Dict[str, Any]:
    """
    测试AmazingData连接（便捷方法）

    Args:
        username: 用户名
        password: 密码
        host: 服务器地址
        port: 端口

    Returns:
        测试结果
    """
    wrapper = get_safe_wrapper()
    start_time = time.time()

    success, error = wrapper.safe_login(username, password, host, port)

    result = {
        "success": success,
        "error": error,
        "latency_ms": (time.time() - start_time) * 1000,
        "stats": wrapper.get_stats()
    }

    # 登录成功后自动登出（实际跳过）
    if success:
        wrapper.safe_logout()

    return result