# 数据源专属进程池架构技术报告

**报告时间**：2025-01-21 10:30 (UTC+8)
**报告类型**：技术设计文档
**状态**：待实施

## 一、问题诊断报告

### 1.1 问题现象
- **症状**：AmazingData数据源第一次测试成功，第二次测试失败
- **错误**：第二次测试超时，提示"登录超时（30秒）"
- **影响**：用户无法连续测试数据源，必须重启服务

### 1.2 根本原因分析

#### 核心问题
1. **单例模式缺陷**：全局进程代理导致所有操作共享同一SDK实例
2. **SDK设计问题**：AmazingData SDK不支持重复登录，已登录状态下再次login会卡死
3. **状态残留**：由于logout会崩溃，系统跳过logout，SDK状态无法清理

#### 技术栈分析
```
当前架构：
FastAPI Server
    ↓
AmazingDataSafeWrapper (多个实例)
    ↓
AmazingDataProcessProxy (全局单例) ← 问题根源
    ↓
Worker Process (单个，持久运行)
    ↓
AmazingData SDK (状态残留)
```

### 1.3 执行流程对比

| 步骤 | 第一次测试 | 第二次测试 |
|------|------------|------------|
| 1 | 创建SafeWrapper实例 | 创建新的SafeWrapper实例 |
| 2 | 获取全局代理（首次创建） | 获取全局代理（已存在） |
| 3 | 启动新工作进程 | 工作进程已运行 |
| 4 | 导入SDK | SDK已导入 |
| 5 | 执行login → **成功** | 执行login → **卡死** |
| 6 | 跳过logout | - |
| 7 | 进程保持运行 | 超时失败 |

## 二、解决方案设计

### 2.1 架构升级方案

```
新架构：
FastAPI Server
    ↓
DataSource Manager
    ↓
AmazingDataProcessPool (进程池管理器)
    ├── amazingdata → Dedicated Process 1
    ├── akshare → Dedicated Process 2
    └── qmt → Dedicated Process 3
```

### 2.2 核心设计理念

1. **进程隔离**：每个数据源独享专属进程
2. **生命周期管理**：进程与数据源状态同步
3. **资源优化**：按需创建，及时释放
4. **故障隔离**：单个进程崩溃不影响其他数据源

## 三、详细实施方案

### 3.1 新增组件：进程池管理器

**文件路径**：`deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_pool.py`

```python
"""
AmazingData进程池管理器

为每个数据源维护独立的工作进程，实现完全隔离。

Author: DeepSearch Team
Version: 2.0.0
Date: 2025-01-21
"""

import threading
import time
from typing import Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from .amazingdata_process_proxy import AmazingDataProcessProxy


class AmazingDataProcessPool:
    """
    数据源进程池管理器

    特性：
    - 每个数据源独立进程
    - 自动健康检查
    - 崩溃自动恢复
    - 资源使用监控
    """

    def __init__(self, max_processes: int = 10):
        """
        初始化进程池

        Args:
            max_processes: 最大进程数限制
        """
        self.max_processes = max_processes
        self.processes: Dict[str, AmazingDataProcessProxy] = {}
        self.process_info: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=3)

        # 启动健康检查
        self._start_health_monitor()

    def get_or_create(
        self,
        datasource_id: str,
        auto_cleanup: bool = False,
        cleanup_delay: float = 60.0,
        config: Optional[Dict[str, Any]] = None
    ) -> AmazingDataProcessProxy:
        """
        获取或创建数据源专属进程

        Args:
            datasource_id: 数据源唯一标识
            auto_cleanup: 是否自动清理（测试场景）
            cleanup_delay: 自动清理延迟时间
            config: 进程配置参数

        Returns:
            进程代理实例

        Raises:
            Exception: 进程创建失败
        """
        with self.lock:
            # 检查进程数量限制
            if len(self.processes) >= self.max_processes:
                self._cleanup_idle_processes()

            # 检查现有进程
            if datasource_id in self.processes:
                proxy = self.processes[datasource_id]
                if proxy.is_running:
                    # 更新最后使用时间
                    self.process_info[datasource_id]["last_used"] = time.time()
                    logger.info(f"[ProcessPool] Reusing process for {datasource_id}")
                    return proxy
                else:
                    # 进程已死，清理并重建
                    logger.warning(f"[ProcessPool] Dead process detected for {datasource_id}")
                    self._remove_process(datasource_id)

            # 创建新进程
            logger.info(f"[ProcessPool] Creating new process for {datasource_id}")
            proxy = AmazingDataProcessProxy(
                restart_on_crash=not auto_cleanup
            )

            if not proxy.start():
                raise Exception(f"Failed to start process for {datasource_id}")

            # 注册进程
            self.processes[datasource_id] = proxy
            self.process_info[datasource_id] = {
                "created_at": time.time(),
                "last_used": time.time(),
                "auto_cleanup": auto_cleanup,
                "cleanup_delay": cleanup_delay,
                "config": config or {},
                "restart_count": 0,
                "total_requests": 0,
                "failed_requests": 0
            }

            # 设置自动清理
            if auto_cleanup:
                self.executor.submit(self._schedule_cleanup, datasource_id, cleanup_delay)

            logger.info(f"[ProcessPool] Process created for {datasource_id} (PID: {proxy.worker_process.pid})")
            return proxy

    def stop(self, datasource_id: str, force: bool = False) -> bool:
        """
        停止指定数据源的进程

        Args:
            datasource_id: 数据源标识
            force: 是否强制停止

        Returns:
            是否成功停止
        """
        with self.lock:
            if datasource_id not in self.processes:
                return True

            logger.info(f"[ProcessPool] Stopping process for {datasource_id}")
            proxy = self.processes[datasource_id]

            # 尝试优雅停止
            success = proxy.stop(timeout=5.0 if not force else 1.0)

            if not success and force:
                # 强制终止
                logger.warning(f"[ProcessPool] Force killing process for {datasource_id}")
                if proxy.worker_process and proxy.worker_process.is_alive():
                    proxy.worker_process.kill()

            # 清理记录
            self._remove_process(datasource_id)
            return success

    def stop_all(self, force: bool = False):
        """停止所有进程"""
        logger.info("[ProcessPool] Stopping all processes")
        datasource_ids = list(self.processes.keys())

        for datasource_id in datasource_ids:
            self.stop(datasource_id, force=force)

    def restart(self, datasource_id: str) -> bool:
        """
        重启指定数据源的进程

        Args:
            datasource_id: 数据源标识

        Returns:
            是否成功重启
        """
        logger.info(f"[ProcessPool] Restarting process for {datasource_id}")

        # 保存配置
        config = None
        if datasource_id in self.process_info:
            config = self.process_info[datasource_id].get("config")

        # 停止旧进程
        self.stop(datasource_id)

        # 创建新进程
        try:
            proxy = self.get_or_create(datasource_id, auto_cleanup=False, config=config)
            if datasource_id in self.process_info:
                self.process_info[datasource_id]["restart_count"] += 1
            return proxy is not None
        except Exception as e:
            logger.error(f"[ProcessPool] Failed to restart process: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取进程池状态

        Returns:
            状态信息字典
        """
        with self.lock:
            status = {
                "total_processes": len(self.processes),
                "max_processes": self.max_processes,
                "processes": {}
            }

            for datasource_id, proxy in self.processes.items():
                info = self.process_info.get(datasource_id, {})
                proxy_stats = proxy.get_stats()

                status["processes"][datasource_id] = {
                    "pid": proxy.worker_process.pid if proxy.worker_process else None,
                    "is_running": proxy.is_running,
                    "created_at": info.get("created_at"),
                    "last_used": info.get("last_used"),
                    "uptime_seconds": time.time() - info.get("created_at", time.time()),
                    "restart_count": info.get("restart_count", 0),
                    "requests_completed": proxy_stats.get("requests_completed", 0),
                    "requests_failed": proxy_stats.get("requests_failed", 0),
                    "auto_cleanup": info.get("auto_cleanup", False)
                }

            return status

    def _remove_process(self, datasource_id: str):
        """内部方法：移除进程记录"""
        if datasource_id in self.processes:
            del self.processes[datasource_id]
        if datasource_id in self.process_info:
            del self.process_info[datasource_id]

    def _cleanup_idle_processes(self):
        """清理空闲进程"""
        current_time = time.time()
        idle_threshold = 300  # 5分钟

        for datasource_id, info in list(self.process_info.items()):
            if info.get("auto_cleanup"):
                continue

            last_used = info.get("last_used", current_time)
            if current_time - last_used > idle_threshold:
                logger.info(f"[ProcessPool] Cleaning idle process: {datasource_id}")
                self.stop(datasource_id)

    def _schedule_cleanup(self, datasource_id: str, delay: float):
        """调度自动清理任务"""
        time.sleep(delay)

        with self.lock:
            if datasource_id in self.process_info:
                info = self.process_info[datasource_id]
                if info.get("auto_cleanup"):
                    logger.info(f"[ProcessPool] Auto-cleanup triggered for {datasource_id}")
                    self.stop(datasource_id)

    def _start_health_monitor(self):
        """启动健康监控线程"""
        def monitor():
            while True:
                time.sleep(30)  # 每30秒检查一次
                self._check_process_health()

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _check_process_health(self):
        """检查所有进程健康状态"""
        with self.lock:
            for datasource_id, proxy in list(self.processes.items()):
                if not proxy.health_check():
                    logger.warning(f"[ProcessPool] Unhealthy process detected: {datasource_id}")
                    # 尝试重启
                    self.restart(datasource_id)


# 全局进程池实例
_global_pool = None


def get_global_pool() -> AmazingDataProcessPool:
    """获取全局进程池实例"""
    global _global_pool
    if _global_pool is None:
        _global_pool = AmazingDataProcessPool()
    return _global_pool


def shutdown_pool():
    """关闭进程池"""
    global _global_pool
    if _global_pool:
        _global_pool.stop_all(force=True)
        _global_pool = None
```

### 3.2 修改现有组件

#### 3.2.1 修改进程代理（amazingdata_process_proxy.py）

**修改内容**：
- 删除第486-509行的全局单例相关代码
- 保持类实现不变，支持多实例

```python
# 删除以下代码：
# 第486-509行
"""
# 全局代理实例
_global_proxy = None

def get_proxy() -> AmazingDataProcessProxy:
    global _global_proxy
    if _global_proxy is None:
        _global_proxy = AmazingDataProcessProxy()
        _global_proxy.start()
    return _global_proxy

def shutdown_proxy():
    global _global_proxy
    if _global_proxy:
        _global_proxy.stop()
        _global_proxy = None
"""
```

#### 3.2.2 修改安全包装器（amazingdata_safe_wrapper.py）

**修改内容**：

```python
# 修改导入
from .amazingdata_process_pool import get_global_pool

class AmazingDataSafeWrapper:
    def __init__(
        self,
        datasource_id: str = "default",  # 新增参数
        auto_restart: bool = True,
        max_retries: int = 3,
        default_timeout: float = 30.0,
        auto_cleanup: bool = False  # 新增参数
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

        # 其余代码保持不变...

# 新增测试专用函数
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
```

#### 3.2.3 修改数据源管理器（datasource_manager.py）

**修改测试接口**：

```python
@router.post("/test")
async def test_datasource(request: TestDataSourceRequest):
    """测试数据源连接"""

    logger.info(f"[API] Testing datasource: {request.type}")

    if request.type.lower() == "amazingdata":
        try:
            # 使用新的测试函数（每次创建独立进程）
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
                test_connection_with_datasource
            )

            # 执行测试
            result = test_connection_with_datasource(
                datasource_id="amazingdata",
                username=request.config.username,
                password=request.config.password,
                host=request.config.host or "101.230.159.234",
                port=request.config.port or 8600
            )

            # 更新数据源状态
            if result["success"]:
                update_datasource_status_after_test(
                    request.type,
                    True,
                    int(result["latency_ms"])
                )

                return JSONResponse(content={
                    "success": True,
                    "message": "AmazingData连接成功",
                    "data": {
                        "latency": int(result["latency_ms"]),
                        "stats": result["stats"]
                    }
                })
            else:
                return JSONResponse(content={
                    "success": False,
                    "message": f"AmazingData连接失败: {result['error']}",
                    "data": {"error": result["error"]}
                }, status_code=400)

        except Exception as e:
            logger.error(f"[API] Test failed: {e}")
            return JSONResponse(content={
                "success": False,
                "message": str(e)
            }, status_code=500)
```

**修改切换接口**：

```python
@router.patch("/{datasource_id}/toggle")
async def toggle_datasource(datasource_id: str, enabled: bool):
    """
    切换数据源启用状态

    启用时创建专属进程，停用时销毁进程
    """
    logger.info(f"[API] Toggling datasource {datasource_id}: enabled={enabled}")

    if datasource_id not in data_sources:
        raise HTTPException(status_code=404, detail="数据源不存在")

    if enabled:
        # 启用数据源：创建长期运行的专属进程
        try:
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
                get_global_pool
            )

            pool = get_global_pool()

            # 获取数据源配置
            datasource = data_sources[datasource_id]
            config = datasource.config.dict() if datasource.config else {}

            # 创建专属进程（不自动清理）
            proxy = pool.get_or_create(
                datasource_id,
                auto_cleanup=False,  # 生产进程不自动清理
                config=config
            )

            if proxy and proxy.is_running:
                data_sources[datasource_id].enabled = True
                data_sources[datasource_id].status = "online"
                logger.info(f"[API] Started dedicated process for {datasource_id}")

                return JSONResponse(content={
                    "success": True,
                    "message": f"{datasource_id}已启用",
                    "data": {"enabled": True}
                })
            else:
                raise Exception("Failed to start process")

        except Exception as e:
            logger.error(f"[API] Failed to enable datasource: {e}")
            return JSONResponse(content={
                "success": False,
                "message": f"启用失败: {str(e)}"
            }, status_code=500)

    else:
        # 停用数据源：销毁专属进程
        try:
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
                get_global_pool
            )

            pool = get_global_pool()

            # 停止进程
            success = pool.stop(datasource_id)

            data_sources[datasource_id].enabled = False
            data_sources[datasource_id].status = "offline"

            logger.info(f"[API] Stopped process for {datasource_id}")

            return JSONResponse(content={
                "success": True,
                "message": f"{datasource_id}已停用",
                "data": {"enabled": False}
            })

        except Exception as e:
            logger.error(f"[API] Failed to disable datasource: {e}")
            return JSONResponse(content={
                "success": False,
                "message": f"停用失败: {str(e)}"
            }, status_code=500)
```

**新增进程状态接口**：

```python
@router.get("/process-status")
async def get_process_status():
    """
    获取进程池状态

    返回所有数据源进程的运行状态
    """
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
            get_global_pool
        )

        pool = get_global_pool()
        status = pool.get_status()

        return JSONResponse(content={
            "success": True,
            "data": status
        })

    except Exception as e:
        logger.error(f"[API] Failed to get process status: {e}")
        return JSONResponse(content={
            "success": False,
            "message": str(e)
        }, status_code=500)
```

## 四、测试验证方案

### 4.1 功能测试

```python
# 测试脚本：test_process_pool.py

import asyncio
import aiohttp
import json

async def test_multiple_connections():
    """测试多次连接"""
    url = "http://localhost:8000/api/data-source/test"

    payload = {
        "type": "amazingdata",
        "config": {
            "username": "test_user",
            "password": "test_pass",
            "host": "101.230.159.234",
            "port": 8600
        }
    }

    async with aiohttp.ClientSession() as session:
        for i in range(5):
            print(f"\n测试 #{i+1}")
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                print(f"结果: {result['success']}")
                if not result['success']:
                    print(f"错误: {result.get('message')}")

            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(test_multiple_connections())
```

### 4.2 性能测试

```python
# 并发测试
async def test_concurrent_datasources():
    """测试多个数据源并发"""
    tasks = []

    # 同时测试3个数据源
    datasources = ["amazingdata", "akshare", "qmt"]

    for ds in datasources:
        task = test_datasource(ds)
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    for ds, result in zip(datasources, results):
        print(f"{ds}: {result}")
```

## 五、监控和运维

### 5.1 监控指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| process_count | 活跃进程数 | < 10 |
| memory_per_process | 单进程内存 | < 500MB |
| request_success_rate | 请求成功率 | > 95% |
| process_restart_count | 进程重启次数 | < 5/hour |
| idle_process_count | 空闲进程数 | < 3 |

### 5.2 日志示例

```
2025-01-21 10:30:00 INFO [ProcessPool] Creating new process for amazingdata_test_1737427800000
2025-01-21 10:30:01 INFO [ProcessPool] Process created for amazingdata_test_1737427800000 (PID: 12345)
2025-01-21 10:30:05 INFO [SafeWrapper] Login successful
2025-01-21 10:30:05 INFO [ProcessPool] Auto-cleanup triggered for amazingdata_test_1737427800000
2025-01-21 10:30:05 INFO [ProcessPool] Stopping process for amazingdata_test_1737427800000
```

## 六、预期效果

### 6.1 问题解决
- ✅ 连续测试不再失败
- ✅ 每次测试独立环境
- ✅ SDK状态完全隔离

### 6.2 性能提升
- 并发支持：多数据源并行处理
- 资源优化：按需分配，及时释放
- 响应速度：进程预热，减少冷启动

### 6.3 可靠性增强
- 故障隔离：单点故障不扩散
- 自动恢复：进程崩溃自动重启
- 健康监控：实时检测异常

## 七、实施计划

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 创建进程池管理器 | 30分钟 |
| 2 | 修改现有组件 | 20分钟 |
| 3 | 更新API接口 | 15分钟 |
| 4 | 单元测试 | 20分钟 |
| 5 | 集成测试 | 15分钟 |
| 6 | 文档更新 | 10分钟 |

**总计预估时间**：110分钟

## 八、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 进程创建失败 | 低 | 高 | 重试机制+降级方案 |
| 内存泄漏 | 低 | 中 | 定期重启+内存监控 |
| 进程通信中断 | 低 | 高 | 超时重试+健康检查 |
| Windows权限问题 | 中 | 中 | 文档说明+诊断日志 |

## 九、总结

本方案通过引入数据源专属进程池架构，彻底解决了AmazingData SDK状态残留导致的重复测试失败问题。方案具有以下优势：

1. **根本解决**：每次操作独立环境，无状态残留
2. **架构优化**：进程级隔离，提高系统稳定性
3. **资源高效**：按需管理，避免资源浪费
4. **易于扩展**：支持更多数据源类型
5. **运维友好**：完善的监控和诊断机制

---

**报告状态**：已完成设计，待实施
**下一步**：根据此报告进行代码实施