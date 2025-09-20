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
    RequestType
)
from .amazingdata_process_pool import get_global_pool


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
        datasource_id: str = "default",
        auto_restart: bool = True,
        max_retries: int = 3,
        default_timeout: float = 30.0,
        auto_cleanup: bool = False
    ):
        """
        初始化安全包装器

        Args:
            datasource_id: 数据源标识
            auto_restart: 进程崩溃后是否自动重启
            max_retries: 最大重试次数
            default_timeout: 默认超时时间
            auto_cleanup: 是否自动清理进程（用于测试）
        """
        self.datasource_id = datasource_id
        self.auto_restart = auto_restart
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        self.auto_cleanup = auto_cleanup

        # 从进程池获取专属进程
        pool = get_global_pool()
        self.proxy = pool.get_or_create(
            datasource_id,
            auto_cleanup=auto_cleanup,
            cleanup_delay=60.0 if auto_cleanup else 0
        )

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

        # 首先检查进程代理是否正常
        if not self.proxy:
            logger.error("[SafeWrapper] Process proxy is None")
            return False, "进程代理未初始化"

        if not self.proxy.is_running:
            logger.warning("[SafeWrapper] Process proxy not running, attempting to start...")
            if not self.proxy.start():
                logger.error("[SafeWrapper] Failed to start process proxy")
                error_msg = (
                    "进程代理启动失败。可能原因：\n"
                    "1. Windows系统需要管理员权限\n"
                    "2. 防火墙或杀毒软件阻止\n"
                    "3. Python multiprocessing限制\n"
                    "请查看日志获取详细诊断信息"
                )
                return False, error_msg

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


def test_connection_with_datasource(
    datasource_id: str,
    username: str,
    password: str,
    host: str = "101.230.159.234",
    port: int = 8600
) -> Dict[str, Any]:
    """
    测试指定数据源的连接（使用独立进程）

    每次测试创建新的临时进程，测试完成后自动清理

    Args:
        datasource_id: 数据源标识
        username: 用户名
        password: 密码
        host: 服务器地址
        port: 端口

    Returns:
        测试结果
    """
    # 为测试创建唯一ID
    test_id = f"{datasource_id}_test_{int(time.time() * 1000)}"

    # 创建临时wrapper
    wrapper = AmazingDataSafeWrapper(
        datasource_id=test_id,
        auto_restart=False,
        max_retries=2,
        auto_cleanup=True  # 启用自动清理
    )

    start_time = time.time()

    try:
        # 执行登录测试
        success, error = wrapper.safe_login(username, password, host, port)

        result = {
            "success": success,
            "error": error,
            "datasource_id": datasource_id,
            "test_id": test_id,
            "latency_ms": (time.time() - start_time) * 1000,
            "stats": wrapper.get_stats()
        }

        return result

    finally:
        # 立即清理测试进程
        pool = get_global_pool()
        pool.stop(test_id, force=True)
        logger.info(f"[Test] Cleaned up test process: {test_id}")


def test_connection_with_reuse(
    username: str,
    password: str,
    host: str = "101.230.159.234",
    port: int = 8600,
    reuse_window: float = 30.0
) -> Dict[str, Any]:
    """
    测试连接（支持进程复用，适合连续测试）

    在指定时间窗口内复用同一个测试进程，避免频繁创建销毁。
    超过时间窗口会创建新进程，确保状态干净。

    Args:
        username: 用户名
        password: 密码
        host: 服务器地址
        port: 端口
        reuse_window: 复用时间窗口（秒），默认30秒

    Returns:
        测试结果字典
    """
    from .amazingdata_process_proxy import RequestType

    start_time = time.time()
    pool = get_global_pool()

    try:
        # 获取测试进程（可能复用）
        proxy, process_id = pool.get_test_process(
            datasource_type="amazingdata",
            reuse_window=reuse_window
        )

        logger.info(f"[Test] Using process {process_id} for testing")

        # 执行登录测试
        response = proxy.execute(
            "login",
            username,
            password,
            host,
            port,
            timeout=30.0,
            request_type=RequestType.LOGIN
        )

        if response.success:
            login_result = response.result
            success = login_result == 0 or login_result is True

            result = {
                "success": success,
                "error": None if success else f"登录失败，返回码: {login_result}",
                "process_id": process_id,
                "latency_ms": (time.time() - start_time) * 1000,
                "stats": proxy.get_stats()
            }
        else:
            result = {
                "success": False,
                "error": response.error or "登录失败",
                "process_id": process_id,
                "latency_ms": (time.time() - start_time) * 1000,
                "stats": proxy.get_stats()
            }

        logger.info(f"[Test] Test completed: success={result['success']}, "
                   f"latency={result['latency_ms']:.0f}ms")

        # 测试成功后，进程会被保留供后续复用
        # 超过时间窗口后会自动清理

        return result

    except Exception as e:
        logger.error(f"[Test] Test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "process_id": None,
            "latency_ms": (time.time() - start_time) * 1000
        }