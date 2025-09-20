"""
AmazingData SDK进程隔离代理

通过独立进程运行AmazingData SDK，防止SDK崩溃影响主进程。
主要解决SDK的SystemExit和段错误问题。

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-20
"""
import multiprocessing as mp
import queue
import time
import pickle
import traceback
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class RequestType(Enum):
    """请求类型枚举"""
    LOGIN = "login"
    LOGOUT = "logout"
    GET_DATA = "get_data"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    HEALTH_CHECK = "health_check"
    SHUTDOWN = "shutdown"


@dataclass
class ProxyRequest:
    """代理请求数据结构"""
    request_id: str
    request_type: RequestType
    method: str
    args: tuple
    kwargs: dict
    timeout: float = 30.0


@dataclass
class ProxyResponse:
    """代理响应数据结构"""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: float = 0


class AmazingDataProcessProxy:
    """
    AmazingData SDK进程隔离代理

    通过独立进程运行SDK，实现完全隔离：
    - SDK崩溃不影响主进程
    - 自动检测和重启工作进程
    - 请求排队和超时控制
    - 健康检查和监控
    """

    def __init__(self, max_workers: int = 1, restart_on_crash: bool = True):
        """
        初始化进程代理

        Args:
            max_workers: 最大工作进程数（目前只支持1）
            restart_on_crash: 崩溃后是否自动重启
        """
        self.max_workers = max_workers
        self.restart_on_crash = restart_on_crash

        # 进程通信
        self.manager = mp.Manager()
        self.request_queue = self.manager.Queue()
        self.response_queue = self.manager.Queue()

        # 工作进程
        self.worker_process = None
        self.is_running = False

        # 统计信息
        self.stats = {
            "requests_sent": 0,
            "requests_completed": 0,
            "requests_failed": 0,
            "process_restarts": 0,
            "last_crash_time": None,
            "last_crash_reason": None
        }

        # 请求跟踪
        self.pending_requests = {}

        # 保存最后登录的用户名，用于logout
        self.last_login_username = None

    def start(self) -> bool:
        """
        启动工作进程

        Returns:
            是否成功启动
        """
        if self.is_running and self.worker_process and self.worker_process.is_alive():
            logger.info("AmazingData worker process already running")
            return True

        try:
            logger.info("Starting AmazingData worker process...")

            # 创建工作进程
            self.worker_process = mp.Process(
                target=self._worker_loop,
                args=(self.request_queue, self.response_queue),
                daemon=True
            )
            self.worker_process.start()

            # 等待进程启动
            time.sleep(0.5)

            if self.worker_process.is_alive():
                self.is_running = True
                logger.info(f"AmazingData worker process started (PID: {self.worker_process.pid})")
                return True
            else:
                import platform
                logger.error("Worker process failed to start")

                # 添加平台特定的诊断信息
                if platform.system() == "Windows":
                    logger.error("===== Windows进程启动失败诊断 =====")
                    logger.error("可能的原因：")
                    logger.error("1. Python multiprocessing在Windows上需要if __name__ == '__main__'保护")
                    logger.error("2. 需要以管理员权限运行")
                    logger.error("3. Windows防火墙或杀毒软件阻止了进程创建")
                    logger.error("4. 系统资源不足（内存、句柄等）")
                    logger.error("5. Python环境问题（建议使用Python 3.8+）")
                    logger.error("解决建议：")
                    logger.error("- 尝试以管理员身份运行")
                    logger.error("- 临时禁用杀毒软件测试")
                    logger.error("- 检查系统事件日志")
                else:
                    logger.error(f"进程在{platform.system()}系统上启动失败")
                    logger.error("可能的原因：资源限制、权限问题或Python环境问题")

                return False

        except Exception as e:
            logger.error(f"Failed to start worker process: {e}")
            return False

    def stop(self, timeout: float = 5.0, with_logout: bool = False) -> bool:
        """
        停止工作进程

        Args:
            timeout: 等待超时时间
            with_logout: 是否先尝试执行logout

        Returns:
            是否成功停止
        """
        if not self.is_running:
            return True

        try:
            logger.info(f"Stopping AmazingData worker process (with_logout={with_logout})...")

            # 如果需要logout，先发送logout请求
            if with_logout:
                logger.info("Sending logout request before stopping...")

                # 构建logout请求，包含用户名参数
                logout_args = ()
                if self.last_login_username:
                    logout_args = (self.last_login_username,)
                    logger.info(f"Including username in logout request: {self.last_login_username}")

                logout_request = ProxyRequest(
                    request_id="logout_before_stop",
                    request_type=RequestType.LOGOUT,
                    method="logout",
                    args=logout_args,
                    kwargs={}
                )
                self.request_queue.put(pickle.dumps(logout_request))

                # 给logout一些时间执行（进程可能会崩溃）
                self.worker_process.join(timeout=2.0)

                # 如果进程已经退出（logout导致），直接返回成功
                if not self.worker_process.is_alive():
                    logger.info("Process terminated after logout")
                    self.is_running = False
                    return True

            # 发送关闭请求
            shutdown_request = ProxyRequest(
                request_id="shutdown",
                request_type=RequestType.SHUTDOWN,
                method="shutdown",
                args=(),
                kwargs={}
            )
            self.request_queue.put(pickle.dumps(shutdown_request))

            # 等待进程结束
            remaining_timeout = max(1.0, timeout - (2.0 if with_logout else 0))
            self.worker_process.join(timeout=remaining_timeout)

            if self.worker_process.is_alive():
                logger.warning("Worker process not responding, terminating...")
                self.worker_process.terminate()
                self.worker_process.join(timeout=2)

                if self.worker_process.is_alive():
                    logger.error("Force killing worker process")
                    self.worker_process.kill()

            self.is_running = False
            logger.info("AmazingData worker process stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping worker process: {e}")
            return False

    def execute(
        self,
        method: str,
        *args,
        request_type: RequestType = RequestType.GET_DATA,
        timeout: float = 30.0,
        **kwargs
    ) -> ProxyResponse:
        """
        执行SDK方法

        Args:
            method: 方法名
            *args: 位置参数
            request_type: 请求类型
            timeout: 超时时间
            **kwargs: 关键字参数

        Returns:
            代理响应
        """
        # 确保进程在运行
        if not self.is_running or not self.worker_process or not self.worker_process.is_alive():
            if self.restart_on_crash:
                logger.warning("Worker process not running, attempting restart...")
                if not self.start():
                    return ProxyResponse(
                        request_id="",
                        success=False,
                        error="Failed to start worker process"
                    )
                self.stats["process_restarts"] += 1
            else:
                return ProxyResponse(
                    request_id="",
                    success=False,
                    error="Worker process not running"
                )

        # 创建请求
        request_id = f"{method}_{time.time()}"
        request = ProxyRequest(
            request_id=request_id,
            request_type=request_type,
            method=method,
            args=args,
            kwargs=kwargs,
            timeout=timeout
        )

        self.stats["requests_sent"] += 1

        try:
            # 发送请求
            self.request_queue.put(pickle.dumps(request))

            # 等待响应
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # 检查进程是否崩溃
                    if not self.worker_process.is_alive():
                        logger.error("Worker process crashed during request")
                        self.stats["last_crash_time"] = time.time()
                        self.stats["last_crash_reason"] = "Process died during request"

                        if self.restart_on_crash:
                            self.start()

                        return ProxyResponse(
                            request_id=request_id,
                            success=False,
                            error="Worker process crashed",
                            error_type="ProcessCrash"
                        )

                    # 检查响应队列
                    response_data = self.response_queue.get(timeout=0.1)
                    response = pickle.loads(response_data)

                    if response.request_id == request_id:
                        if response.success:
                            self.stats["requests_completed"] += 1

                            # 如果是登录成功，保存用户名
                            if request_type == RequestType.LOGIN and args and len(args) > 0:
                                self.last_login_username = args[0]
                                logger.info(f"[Proxy] Saved login username: {self.last_login_username}")

                        else:
                            self.stats["requests_failed"] += 1
                        return response

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error getting response: {e}")

            # 超时
            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request_id,
                success=False,
                error=f"Request timeout after {timeout}s",
                error_type="Timeout"
            )

        except Exception as e:
            logger.error(f"Error executing request: {e}")
            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request_id,
                success=False,
                error=str(e),
                error_type=type(e).__name__
            )

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            工作进程是否健康
        """
        if not self.is_running or not self.worker_process:
            return False

        if not self.worker_process.is_alive():
            return False

        # 发送健康检查请求
        response = self.execute(
            "health_check",
            request_type=RequestType.HEALTH_CHECK,
            timeout=5.0
        )

        return response.success

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        return self.stats.copy()

    @staticmethod
    def _worker_loop(request_queue: mp.Queue, response_queue: mp.Queue):
        """
        工作进程主循环

        在独立进程中运行，处理SDK调用。

        Args:
            request_queue: 请求队列
            response_queue: 响应队列
        """
        # 在工作进程中导入SDK
        sdk_imported = False
        ad = None

        logger.info(f"Worker process started (PID: {mp.current_process().pid})")

        # SDK实例缓存
        sdk_instances = {}

        # 保存登录的用户名，用于logout
        logged_in_username = None

        while True:
            try:
                # 获取请求
                request_data = request_queue.get(timeout=1)
                request = pickle.loads(request_data)

                # 处理关闭请求
                if request.request_type == RequestType.SHUTDOWN:
                    logger.info("Worker received shutdown request")
                    break

                # 延迟导入SDK
                if not sdk_imported:
                    try:
                        import AmazingData as ad_module
                        ad = ad_module
                        sdk_imported = True
                        logger.info("AmazingData SDK imported in worker process")
                    except ImportError as e:
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=f"Failed to import SDK: {e}",
                            error_type="ImportError"
                        )
                        response_queue.put(pickle.dumps(response))
                        continue

                # 处理健康检查
                if request.request_type == RequestType.HEALTH_CHECK:
                    response = ProxyResponse(
                        request_id=request.request_id,
                        success=True,
                        result="healthy"
                    )
                    response_queue.put(pickle.dumps(response))
                    continue

                # 执行SDK方法
                try:
                    # 特殊处理login
                    if request.request_type == RequestType.LOGIN:
                        result = ad.login(*request.args, **request.kwargs)

                        # 判断登录结果
                        if result == 0 or result is True:
                            # 登录成功，保存用户名（第一个参数）
                            if request.args and len(request.args) > 0:
                                logged_in_username = request.args[0]
                                logger.info(f"Login successful, saved username: {logged_in_username}")

                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result=result
                            )
                        else:
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=False,
                                error=f"Login failed with code: {result}",
                                result=result
                            )

                    # 特殊处理logout - 尝试安全执行
                    elif request.request_type == RequestType.LOGOUT:
                        logger.info("Attempting safe logout...")
                        try:
                            # 设置一个标记表示即将logout
                            # logout后进程可能崩溃，这是预期行为
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result="logout_initiated"
                            )
                            # 先发送响应
                            response.timestamp = time.time()
                            response_queue.put(pickle.dumps(response))

                            # 尝试执行logout（可能导致进程退出）
                            logger.info("Executing logout, process may terminate...")
                            if hasattr(ad, 'logout'):
                                # 使用保存的用户名，如果没有则尝试从请求中获取
                                username_to_logout = logged_in_username

                                # 如果没有保存的用户名，尝试从请求参数中获取
                                if not username_to_logout and request.args and len(request.args) > 0:
                                    username_to_logout = request.args[0]

                                if username_to_logout:
                                    logger.info(f"Logging out user: {username_to_logout}")
                                    ad.logout(username_to_logout)
                                else:
                                    logger.warning("No username available for logout, skipping")

                            # 如果执行到这里，说明logout没有崩溃
                            logger.info("Logout completed without crash")
                            # 清除保存的用户名
                            logged_in_username = None
                            # 主动退出进程，确保状态清理
                            break

                        except Exception as e:
                            logger.warning(f"Logout failed: {e}, terminating process")
                            # logout失败，退出进程
                            break

                        # 跳过后续的响应发送
                        continue

                    # 通用方法调用
                    else:
                        # 获取SDK方法
                        method = getattr(ad, request.method, None)
                        if method is None:
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=False,
                                error=f"Method {request.method} not found",
                                error_type="AttributeError"
                            )
                        else:
                            result = method(*request.args, **request.kwargs)
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result=result
                            )

                except SystemExit as e:
                    # SDK调用了exit
                    logger.critical(f"SDK called SystemExit: {e}")
                    response = ProxyResponse(
                        request_id=request.request_id,
                        success=False,
                        error=f"SDK attempted to exit with code: {e.code}",
                        error_type="SystemExit"
                    )
                    # 继续运行，不退出

                except Exception as e:
                    logger.error(f"Error executing SDK method: {e}")
                    logger.error(traceback.format_exc())
                    response = ProxyResponse(
                        request_id=request.request_id,
                        success=False,
                        error=str(e),
                        error_type=type(e).__name__
                    )

                # 发送响应
                response.timestamp = time.time()
                response_queue.put(pickle.dumps(response))

            except queue.Empty:
                # 队列为空，继续等待
                continue

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                logger.error(traceback.format_exc())

        logger.info("Worker process exiting")