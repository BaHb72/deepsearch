"""
进程和线程管理器

提供统一的进程、线程和异步任务管理功能，确保系统能够优雅地关闭所有资源。
"""
import asyncio
import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, Callable, Union

import psutil


class ResourceType(Enum):
    """资源类型"""
    PROCESS = "process"
    THREAD = "thread"
    EXECUTOR = "executor"
    ASYNC_TASK = "async_task"
    EVENT_LOOP = "event_loop"


class ResourceStatus(Enum):
    """资源状态"""
    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ResourceInfo:
    """资源信息"""
    resource_id: str
    resource_type: ResourceType
    name: str
    status: ResourceStatus
    created_at: datetime
    stopped_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cleanup_callback: Optional[Callable] = None


class ProcessManager:
    """
    进程和线程管理器（单例模式）
    
    负责：
    1. 注册和跟踪所有创建的进程、线程和异步任务
    2. 提供统一的清理接口
    3. 实现优雅关闭机制
    4. 处理信号和异常情况
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.logger = logging.getLogger(__name__)

        # 资源注册表
        self._resources: Dict[str, ResourceInfo] = {}
        self._resource_lock = threading.RLock()

        # 弱引用存储，避免循环引用
        self._threads: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._processes: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._executors: weakref.WeakSet = weakref.WeakSet()
        self._event_loops: weakref.WeakSet = weakref.WeakSet()

        # 引擎管理
        self._engines: weakref.WeakSet = weakref.WeakSet()
        self._primary_engine = None

        # 关闭标志
        self._shutting_down = False
        self._shutdown_event = threading.Event()

        # 注册退出处理器
        atexit.register(self._atexit_handler)

        # 设置信号处理器
        self._setup_signal_handlers()

        self.logger.debug("ProcessManager 初始化完成")

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}，开始优雅关闭...")

            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_running_loop()
                # 在事件循环内，创建异步任务
                loop.create_task(self._async_shutdown())
                self.logger.debug("Created async shutdown task in running event loop")
            except RuntimeError:
                # 不在事件循环内，进行同步关闭
                if self._primary_engine:
                    try:
                        self._primary_engine.stop()
                    except Exception as e:
                        self.logger.error(f"停止引擎时出错: {e}")
                # 执行全面清理
                self.shutdown()

        # Unix/Linux 信号
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            try:
                signal.signal(signal.SIGHUP, signal_handler)
            except AttributeError:
                pass
        else:
            # Windows 信号
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Windows 特殊处理
            try:
                import win32api
                win32api.SetConsoleCtrlHandler(lambda x: self.shutdown() or True, True)
            except ImportError:
                pass

    def _atexit_handler(self):
        """程序退出时的处理器"""
        if not self._shutting_down:
            self.logger.info("程序退出，执行清理...")
            self.shutdown(force=True)

    def register_engine(self, engine) -> None:
        """
        注册引擎实例
        
        Args:
            engine: MainEngine 实例
        """
        with self._resource_lock:
            self._engines.add(engine)
            if self._primary_engine is None:
                self._primary_engine = engine
            self.logger.debug(f"注册引擎: {id(engine)}")

    def unregister_engine(self, engine) -> None:
        """
        注销引擎实例
        
        Args:
            engine: MainEngine 实例
        """
        with self._resource_lock:
            self._engines.discard(engine)
            if self._primary_engine == engine:
                # 如果是主引擎，尝试选择另一个
                self._primary_engine = next(iter(self._engines), None)
            self.logger.debug(f"注销引擎: {id(engine)}")

    def register_thread(self, thread: threading.Thread,
                        name: Optional[str] = None,
                        cleanup_callback: Optional[Callable] = None) -> str:
        """
        注册线程
        
        Args:
            thread: 线程对象
            name: 线程名称
            cleanup_callback: 清理回调函数
            
        Returns:
            资源ID
        """
        with self._resource_lock:
            resource_id = f"thread_{id(thread)}"

            # 保存弱引用
            self._threads[resource_id] = thread

            # 创建资源信息
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=ResourceType.THREAD,
                name=name or thread.name,
                status=ResourceStatus.CREATED if not thread.is_alive() else ResourceStatus.RUNNING,
                created_at=datetime.now(),
                metadata={
                    "daemon": thread.daemon,
                    "ident": thread.ident
                },
                cleanup_callback=cleanup_callback
            )

            self._resources[resource_id] = info
            self.logger.debug(f"注册线程: {info.name} (daemon={thread.daemon})")

            return resource_id

    def register_process(self, process: subprocess.Popen,
                         name: Optional[str] = None,
                         cleanup_callback: Optional[Callable] = None) -> str:
        """
        注册进程
        
        Args:
            process: 进程对象
            name: 进程名称
            cleanup_callback: 清理回调函数
            
        Returns:
            资源ID
        """
        with self._resource_lock:
            resource_id = f"process_{process.pid}"

            # 保存弱引用
            self._processes[resource_id] = process

            # 创建资源信息
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=ResourceType.PROCESS,
                name=name or f"Process-{process.pid}",
                status=ResourceStatus.RUNNING if (hasattr(process, 'poll') and process.poll() is None) or (
                            hasattr(process, 'returncode') and process.returncode is None) else ResourceStatus.STOPPED,
                created_at=datetime.now(),
                metadata={
                    "pid": process.pid,
                    "args": process.args if hasattr(process, 'args') else None
                },
                cleanup_callback=cleanup_callback
            )

            self._resources[resource_id] = info
            self.logger.debug(f"注册进程: {info.name} (PID={process.pid})")

            return resource_id

    def register_executor(self, executor: ThreadPoolExecutor,
                          name: Optional[str] = None) -> str:
        """注册线程池执行器"""
        with self._resource_lock:
            resource_id = f"executor_{id(executor)}"

            # 保存弱引用
            self._executors.add(executor)

            # 创建资源信息
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=ResourceType.EXECUTOR,
                name=name or "ThreadPoolExecutor",
                status=ResourceStatus.RUNNING,
                created_at=datetime.now(),
                metadata={
                    "max_workers": executor._max_workers if hasattr(executor, '_max_workers') else None
                }
            )

            self._resources[resource_id] = info
            self.logger.debug(f"注册线程池: {info.name}")

            return resource_id

    def register_event_loop(self, loop: asyncio.AbstractEventLoop,
                            name: Optional[str] = None) -> str:
        """注册事件循环"""
        with self._resource_lock:
            resource_id = f"eventloop_{id(loop)}"

            # 保存弱引用
            self._event_loops.add(loop)

            # 创建资源信息
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=ResourceType.EVENT_LOOP,
                name=name or "EventLoop",
                status=ResourceStatus.RUNNING if loop.is_running() else ResourceStatus.CREATED,
                created_at=datetime.now()
            )

            self._resources[resource_id] = info
            self.logger.debug(f"注册事件循环: {info.name}")

            return resource_id

    def stop_thread(self, thread: Union[threading.Thread, str],
                    timeout: float = 5.0) -> bool:
        """
        停止线程
        
        Args:
            thread: 线程对象或资源ID
            timeout: 超时时间
            
        Returns:
            是否成功停止
        """
        if isinstance(thread, str):
            resource_id = thread
            thread = self._threads.get(resource_id)
            if not thread:
                return True
        else:
            resource_id = f"thread_{id(thread)}"

        if not thread or not thread.is_alive():
            return True

        self.logger.debug(f"停止线程: {thread.name}")

        # 更新状态
        if resource_id in self._resources:
            self._resources[resource_id].status = ResourceStatus.STOPPING

        # 如果是daemon线程，不需要等待
        if thread.daemon:
            self.logger.debug(f"线程 {thread.name} 是daemon线程，将自动退出")
            return True

        # 等待线程结束
        thread.join(timeout=timeout)

        success = not thread.is_alive()

        # 更新状态
        if resource_id in self._resources:
            self._resources[resource_id].status = ResourceStatus.STOPPED if success else ResourceStatus.FAILED
            if success:
                self._resources[resource_id].stopped_at = datetime.now()

        if not success:
            self.logger.warning(f"线程 {thread.name} 在 {timeout}秒内未能停止")

        return success

    def stop_process(self, process: Union[subprocess.Popen, str],
                     timeout: float = 5.0, force: bool = False) -> bool:
        """
        停止进程
        
        Args:
            process: 进程对象或资源ID
            timeout: 超时时间
            force: 是否强制终止
            
        Returns:
            是否成功停止
        """
        if isinstance(process, str):
            resource_id = process
            process = self._processes.get(resource_id)
            if not process:
                return True
        else:
            resource_id = f"process_{process.pid}"

        if not process or (hasattr(process, 'poll') and process.poll() is not None) or (
                hasattr(process, 'returncode') and process.returncode is not None):
            return True

        self.logger.debug(f"停止进程: PID={process.pid}")

        # 更新状态
        if resource_id in self._resources:
            self._resources[resource_id].status = ResourceStatus.STOPPING

        try:
            if sys.platform == "win32":
                # Windows上先尝试正常终止
                if not force:
                    process.terminate()
                    try:
                        process.wait(timeout=timeout)
                        success = True
                    except subprocess.TimeoutExpired:
                        success = False

                # 如果失败或强制模式，使用taskkill
                if force or not success:
                    result = subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                        text=True
                    )
                    success = result.returncode == 0
            else:
                # Unix/Linux
                if not force:
                    process.terminate()
                    try:
                        process.wait(timeout=timeout)
                        success = True
                    except subprocess.TimeoutExpired:
                        success = False

                if force or not success:
                    process.kill()
                    process.wait(timeout=1)
                    success = True

        except Exception as e:
            self.logger.error(f"停止进程失败: {e}")
            success = False

        # 更新状态
        if resource_id in self._resources:
            self._resources[resource_id].status = ResourceStatus.STOPPED if success else ResourceStatus.FAILED
            if success:
                self._resources[resource_id].stopped_at = datetime.now()

        return success

    def stop_executor(self, executor: ThreadPoolExecutor,
                      wait: bool = True, timeout: float = 5.0) -> bool:
        """停止线程池执行器"""
        try:
            if sys.version_info >= (3, 9):
                executor.shutdown(wait=wait, cancel_futures=True)
            else:
                executor.shutdown(wait=wait)
            return True
        except Exception as e:
            self.logger.error(f"停止线程池失败: {e}")
            return False

    def stop_event_loop(self, loop: asyncio.AbstractEventLoop) -> bool:
        """停止事件循环"""
        if loop.is_closed():
            return True

        try:
            # 取消所有任务
            if loop.is_running():
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # 给一些时间完成取消
                loop.call_soon(loop.stop)

            # 关闭循环
            if not loop.is_running():
                loop.close()

            return True
        except Exception as e:
            self.logger.error(f"停止事件循环失败: {e}")
            return False

    def cleanup_orphan_processes(self):
        """清理孤儿进程"""
        try:
            current_pid = os.getpid()
            current_proc = psutil.Process(current_pid)

            # 获取所有子进程
            children = current_proc.children(recursive=True)

            for child in children:
                try:
                    # 检查是否是DeepSearch相关进程
                    cmdline = ' '.join(child.cmdline()).lower()
                    if 'deepsearch' in cmdline or self._is_managed_process(child):
                        self.logger.info(f"清理孤儿进程: PID={child.pid} ({child.name()})")
                        child.terminate()
                        child.wait(timeout=2)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        child.kill()
                    except Exception as e:
                        self.logger.debug(f"Failed to kill child process {child.pid}: {e}")
                except Exception as e:
                    self.logger.debug(f"清理进程 {child.pid} 失败: {e}")

        except Exception as e:
            self.logger.error(f"清理孤儿进程失败: {e}")

    def _is_managed_process(self, process: psutil.Process) -> bool:
        """检查是否是被管理的进程"""
        try:
            # 检查进程ID是否在注册表中
            for resource_id, info in self._resources.items():
                if info.resource_type == ResourceType.PROCESS:
                    if info.metadata.get('pid') == process.pid:
                        return True

            # 检查是否是相关进程
            name = process.name().lower()
            return any(keyword in name for keyword in ['python', 'node', 'npm', 'uvicorn'])

        except Exception as e:
            self.logger.debug(f"Failed to check if process is related: {e}")
            return False

    async def _async_shutdown(self):
        """异步关闭方法"""
        if self._primary_engine:
            try:
                await self._primary_engine.stop_async()
            except Exception as e:
                self.logger.error(f"异步停止引擎时出错: {e}")

        # 调用同步的 shutdown 进行其他清理
        self.shutdown()

    def shutdown(self, timeout: float = 10.0, force: bool = False):
        """
        关闭所有资源
        
        Args:
            timeout: 总超时时间
            force: 是否强制关闭
        """
        if self._shutting_down:
            return

        self._shutting_down = True
        self._shutdown_event.set()

        self.logger.info("开始关闭所有资源...")
        start_time = time.time()

        # 首先停止所有引擎
        for engine in list(self._engines):
            try:
                if hasattr(engine, 'is_running') and engine.is_running():
                    self.logger.debug(f"停止引擎: {id(engine)}")
                    engine.stop()
            except Exception as e:
                self.logger.error(f"停止引擎时出错: {e}")

        with self._resource_lock:
            resources = list(self._resources.values())

        # 按类型分组
        threads = []
        processes = []
        executors = []
        event_loops = []

        for info in resources:
            if info.status not in (ResourceStatus.STOPPED, ResourceStatus.FAILED):
                if info.resource_type == ResourceType.THREAD:
                    threads.append(info)
                elif info.resource_type == ResourceType.PROCESS:
                    processes.append(info)
                elif info.resource_type == ResourceType.EXECUTOR:
                    executors.append(info)
                elif info.resource_type == ResourceType.EVENT_LOOP:
                    event_loops.append(info)

        # 1. 先停止事件循环（阻止新任务）
        for info in event_loops:
            loop = None
            for l in self._event_loops:
                if f"eventloop_{id(l)}" == info.resource_id:
                    loop = l
                    break
            if loop:
                self.stop_event_loop(loop)

        # 2. 停止线程池
        for info in executors:
            executor = None
            for e in self._executors:
                if f"executor_{id(e)}" == info.resource_id:
                    executor = e
                    break
            if executor:
                self.stop_executor(executor, wait=not force)

        # 3. 停止线程
        for info in threads:
            thread = self._threads.get(info.resource_id)
            if thread:
                # 执行清理回调
                if info.cleanup_callback:
                    try:
                        info.cleanup_callback()
                    except Exception as e:
                        self.logger.error(f"清理回调失败: {e}")

                # 计算剩余时间
                elapsed = time.time() - start_time
                remaining = max(0.1, timeout - elapsed)
                self.stop_thread(thread, timeout=remaining)

        # 4. 停止进程
        for info in processes:
            process = self._processes.get(info.resource_id)
            if process:
                # 执行清理回调
                if info.cleanup_callback:
                    try:
                        info.cleanup_callback()
                    except Exception as e:
                        self.logger.error(f"清理回调失败: {e}")

                # 计算剩余时间
                elapsed = time.time() - start_time
                remaining = max(0.1, timeout - elapsed)
                self.stop_process(process, timeout=remaining, force=force)

        # 5. 清理孤儿进程
        if force or sys.platform == "win32":
            self.cleanup_orphan_processes()

        # 6. 清理端口
        if force:
            self._cleanup_ports()

        self.logger.info(f"资源清理完成，耗时: {time.time() - start_time:.2f}秒")

    def _cleanup_ports(self):
        """清理占用的端口"""
        try:
            from deepsearch.config import get_config
            config = get_config()

            ports = [
                config.webui.backend_port,
                config.webui.frontend_port
            ]

            # 添加 ZMQ 端口（如果配置存在）
            if 'zmq' in config.message_bus.buses:
                zmq_config = config.message_bus.buses['zmq'].config
                # 处理不同类型的配置对象
                if hasattr(zmq_config, 'pub_port'):
                    ports.append(zmq_config.pub_port)
                    ports.append(zmq_config.sub_port)
                elif isinstance(zmq_config, dict):
                    ports.append(zmq_config.get('pub_port', 5556))
                    ports.append(zmq_config.get('sub_port', 5557))

            for conn in psutil.net_connections():
                if hasattr(conn, 'laddr') and conn.laddr.port in ports:
                    if conn.pid and conn.pid != os.getpid():
                        try:
                            proc = psutil.Process(conn.pid)
                            if self._is_managed_process(proc):
                                self.logger.info(f"清理端口 {conn.laddr.port} (PID={conn.pid})")
                                proc.terminate()
                                proc.wait(timeout=2)
                        except Exception as e:
                            self.logger.debug(f"Failed to clean up port process: {e}")

        except Exception as e:
            self.logger.error(f"清理端口失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取资源状态"""
        with self._resource_lock:
            status = {
                "shutting_down": self._shutting_down,
                "total_resources": len(self._resources),
                "resources_by_type": {},
                "resources_by_status": {},
                "active_resources": []
            }

            # 按类型统计
            for resource_type in ResourceType:
                count = sum(1 for r in self._resources.values()
                            if r.resource_type == resource_type)
                status["resources_by_type"][resource_type.value] = count

            # 按状态统计
            for resource_status in ResourceStatus:
                count = sum(1 for r in self._resources.values()
                            if r.status == resource_status)
                status["resources_by_status"][resource_status.value] = count

            # 活跃资源列表
            for info in self._resources.values():
                if info.status in (ResourceStatus.CREATED, ResourceStatus.RUNNING):
                    status["active_resources"].append({
                        "id": info.resource_id,
                        "type": info.resource_type.value,
                        "name": info.name,
                        "status": info.status.value,
                        "created_at": info.created_at.isoformat()
                    })

            return status


# 全局实例
process_manager = ProcessManager()
