# AmazingData SDK 隔离实施计划

**创建时间**: 2025-09-18 15:30:00 (UTC+8)
**目标**: 防止 AmazingData SDK 的 exit(0) 调用导致整个系统崩溃

## 问题根因

```
File: AmazingData/login/tgw_login.py:69
行为: SDK 在登录失败时调用 exit(0) 强制退出整个进程
影响: 导致 FastAPI 服务器崩溃，整个 Web 服务不可用
```

## 解决方案架构

```
┌─────────────────────────────────────┐
│         Main Process (FastAPI)       │
├─────────────────────────────────────┤
│  DataProviderFactory                 │
│    ├─ try: AmazingDataProvider       │
│    │    └─ Safe Login Wrapper        │
│    │        └─ Catch SystemExit      │
│    └─ except: Fallback Provider      │
│         └─ AkShareProvider           │
└─────────────────────────────────────┘
```

## Phase 1: 核心隔离实现 (必须完成)

### 1.1 修改 _login 方法 - 捕获 SystemExit

**文件**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py`
**位置**: 第 268-298 行

```python
async def _login(self) -> bool:
    """
    登录 AmazingData - 带 SystemExit 保护

    Returns:
        是否登录成功
    """
    try:
        logger.info(f"正在登录 AmazingData (host={self.config.host}:{self.config.port})...")

        # 创建安全的登录包装函数
        def safe_login():
            """
            安全的登录函数，捕获 SystemExit

            Returns:
                登录结果或错误码
                -999: SDK 尝试退出程序
                -998: 其他异常
            """
            try:
                # 调用 SDK 登录
                return ad.login(
                    self.config.username,
                    self.config.password,
                    self.config.host,
                    self.config.port
                )
            except SystemExit as e:
                # SDK 尝试退出程序
                logger.error(f"AmazingData SDK attempted system exit: {e.code}")
                return -999
            except Exception as e:
                logger.error(f"AmazingData login exception: {e}")
                return -998

        # 在线程池中执行，添加超时控制
        loop = asyncio.get_event_loop()

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, safe_login),
                timeout=5.0  # 5秒超时
            )
        except asyncio.TimeoutError:
            logger.error("AmazingData 登录超时（5秒）")
            raise DataProviderError("登录超时，服务器可能不可达")

        # 处理返回结果
        if result == -999:
            # SDK 强制退出 - 这是关键的错误码
            raise DataProviderError(
                "AmazingData SDK 强制退出程序，可能是网络配置问题。"
                "建议检查: 1) 网络连接 2) 服务器地址 3) 防火墙设置"
            )
        elif result == -998:
            raise DataProviderError("AmazingData 登录发生异常")
        elif result == 0 or result is True:
            # 登录成功
            self._connected = True
            self._login_time = datetime.now()
            logger.info("AmazingData 登录成功")
            return True
        else:
            # 其他错误码
            error_msg = f"AmazingData 登录失败，错误码: {result}"
            logger.error(error_msg)
            raise DataProviderError(error_msg)

    except DataProviderError:
        raise
    except Exception as e:
        logger.error(f"AmazingData 登录意外错误: {e}")
        raise DataProviderError(f"登录异常: {e}")
```

### 1.2 修改所有 SDK 调用点

**需要包装的方法** (同文件):
- `get_kline()` - 第 246 行
- `get_realtime_quote()` - 第 304 行
- `get_financial_data()` - 第 372-391 行
- 所有其他调用 ad.* 的地方

**包装模板**:
```python
async def _safe_sdk_call(self, func, *args, **kwargs):
    """
    安全调用 SDK 函数

    Args:
        func: SDK 函数
        *args, **kwargs: 函数参数

    Returns:
        函数返回值

    Raises:
        DataProviderError: SDK 错误
    """
    def safe_wrapper():
        try:
            return func(*args, **kwargs)
        except SystemExit as e:
            logger.error(f"SDK attempted exit in {func.__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"SDK call failed in {func.__name__}: {e}")
            raise

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, safe_wrapper)

    if result is None:
        raise DataProviderError(f"SDK 调用失败: {func.__name__}")

    return result
```

## Phase 2: Provider Factory 改进

### 2.1 改进初始化和降级逻辑

**文件**: `deepsearch/webui/api/providers.py`
**位置**: 第 117-152 行

```python
elif provider_type == "amazingdata":
    """
    AmazingData Provider 初始化
    带完整的错误处理和降级机制
    """
    provider_instance = None
    init_success = False

    # 步骤1: 尝试导入和创建实例
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
            AmazingDataProvider, AmazingDataConfig
        )

        # 从配置或环境变量读取
        config = AmazingDataConfig(
            username=os.getenv("AMAZINGDATA_USERNAME", "212200038719"),
            password=os.getenv("AMAZINGDATA_PASSWORD", "212200038719@2025"),
            host=os.getenv("AMAZINGDATA_HOST", "101.230.159.234"),
            port=int(os.getenv("AMAZINGDATA_PORT", "8600")),
            timeout=10,
            retry_count=1,  # 减少重试次数，快速失败
            heartbeat_interval=60,
            auto_reconnect=True
        )

        provider_instance = AmazingDataProvider(config)
        logger.info("AmazingData provider instance created")

    except ImportError as e:
        logger.error(f"AmazingData SDK not installed: {e}")
        provider_instance = None
    except Exception as e:
        logger.error(f"Failed to create AmazingData instance: {e}")
        provider_instance = None

    # 步骤2: 尝试初始化
    if provider_instance:
        try:
            # 创建初始化任务，设置超时
            init_task = asyncio.create_task(provider_instance.initialize())
            await asyncio.wait_for(init_task, timeout=10.0)

            # 初始化成功
            cls._instances[provider_type] = provider_instance
            init_success = True
            logger.info("AmazingData provider initialized successfully")

        except asyncio.TimeoutError:
            logger.error("AmazingData initialization timeout (10s)")
            init_success = False

        except DataProviderError as e:
            error_msg = str(e)
            if "SDK 强制退出" in error_msg:
                logger.error("AmazingData SDK attempted to exit program, critical error")
                # 记录到监控系统
                await cls._record_provider_failure("amazingdata", "SDK_EXIT", error_msg)
            else:
                logger.error(f"AmazingData initialization failed: {e}")
            init_success = False

        except Exception as e:
            logger.error(f"Unexpected error during AmazingData init: {e}")
            init_success = False

    # 步骤3: 降级处理
    if not init_success:
        logger.warning("AmazingData initialization failed, falling back to AkShare")

        try:
            # 尝试使用 AkShare 作为降级
            from deepsearch.infrastructure.providers.implementations.akshare.akshare_refactored import (
                AkShareRefactoredProvider
            )

            fallback_provider = AkShareRefactoredProvider()
            await fallback_provider.initialize()

            cls._instances[provider_type] = fallback_provider
            cls._fallback_status[provider_type] = {
                'original': 'amazingdata',
                'fallback': 'akshare',
                'reason': 'initialization_failed',
                'timestamp': datetime.now()
            }

            logger.info("Successfully fell back to AkShare provider")

        except Exception as fallback_error:
            logger.error(f"Fallback provider also failed: {fallback_error}")

            # 最后的降级 - 返回错误 provider
            from deepsearch.infrastructure.providers.implementations.mock.error_provider import (
                MockErrorProvider
            )

            cls._instances[provider_type] = MockErrorProvider(
                error_message="All data providers failed to initialize"
            )

            logger.error("All providers failed, using error provider")
```

### 2.2 添加监控记录方法

```python
@classmethod
async def _record_provider_failure(cls, provider: str, failure_type: str, error: str):
    """
    记录 provider 失败信息

    Args:
        provider: provider 名称
        failure_type: 失败类型
        error: 错误信息
    """
    try:
        from deepsearch.observability.monitoring.provider_health import ProviderHealthMonitor

        monitor = ProviderHealthMonitor.get_instance()
        monitor.record_failure(
            provider_name=provider,
            failure_type=failure_type,
            error=error
        )

        # 发送告警（如果配置了）
        if failure_type == "SDK_EXIT":
            logger.critical(f"CRITICAL: {provider} SDK attempted system exit!")
            # 这里可以发送邮件/短信告警

    except Exception as e:
        logger.error(f"Failed to record provider failure: {e}")
```

## Phase 3: 创建 Error Provider

### 3.1 MockErrorProvider 实现

**文件**: `deepsearch/infrastructure/providers/implementations/mock/error_provider.py`

```python
"""
错误 Provider
当所有真实数据源都失败时使用，返回明确的错误信息
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataProviderError
)

class MockErrorProvider(DataProvider):
    """
    错误 Mock Provider

    功能:
    1. 不提供假数据
    2. 返回明确的错误信息
    3. 记录所有调用尝试
    """

    def __init__(self, error_message: str = "Data provider not available"):
        """
        初始化错误 provider

        Args:
            error_message: 默认错误信息
        """
        config = DataProviderConfig(
            name="mock_error",
            enabled=False,
            priority=999  # 最低优先级
        )
        super().__init__(config)

        self.error_message = error_message
        self.call_count = 0
        self.last_call_time = None
        self.call_history = []

    def _record_call(self, method: str, params: Dict[str, Any]):
        """记录调用"""
        self.call_count += 1
        self.last_call_time = datetime.now()

        self.call_history.append({
            'method': method,
            'params': params,
            'timestamp': self.last_call_time
        })

        # 只保留最近100条记录
        if len(self.call_history) > 100:
            self.call_history = self.call_history[-100:]

    async def initialize(self) -> bool:
        """初始化（总是成功，但标记为不可用）"""
        return True

    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表 - 返回错误"""
        self._record_call('get_stock_list', {'limit': limit, **kwargs})
        raise DataProviderError(f"{self.error_message} (method: get_stock_list)")

    async def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """获取K线数据 - 返回错误"""
        self._record_call('get_kline_data', {
            'symbol': symbol,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'limit': limit,
            **kwargs
        })
        raise DataProviderError(f"{self.error_message} (method: get_kline_data, symbol: {symbol})")

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """获取实时行情 - 返回错误"""
        self._record_call('get_realtime_quotes', {'symbols': symbols})
        raise DataProviderError(
            f"{self.error_message} (method: get_realtime_quotes, symbols: {','.join(symbols)})"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'provider': 'mock_error',
            'error_message': self.error_message,
            'call_count': self.call_count,
            'last_call_time': self.last_call_time.isoformat() if self.last_call_time else None,
            'recent_calls': self.call_history[-10:]  # 最近10次调用
        }
```

## Phase 4: 健康监控系统

### 4.1 Provider 健康监控

**文件**: `deepsearch/observability/monitoring/provider_health.py`

```python
"""
数据提供者健康监控系统
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json
from pathlib import Path

class ProviderStatus(Enum):
    """提供者状态"""
    HEALTHY = "healthy"          # 正常
    DEGRADED = "degraded"        # 降级
    FAILED = "failed"            # 失败
    RECOVERING = "recovering"    # 恢复中
    FALLBACK = "fallback"        # 使用降级

class FailureType(Enum):
    """失败类型"""
    SDK_EXIT = "sdk_exit"              # SDK 强制退出
    TIMEOUT = "timeout"                # 超时
    CONNECTION = "connection"          # 连接失败
    AUTHENTICATION = "auth"            # 认证失败
    NETWORK = "network"               # 网络错误
    UNKNOWN = "unknown"               # 未知错误

@dataclass
class FailureRecord:
    """失败记录"""
    timestamp: datetime
    failure_type: FailureType
    error_message: str
    recovery_attempted: bool = False
    recovery_success: bool = False

@dataclass
class ProviderHealth:
    """提供者健康状态"""
    name: str
    status: ProviderStatus
    last_check: datetime
    last_success: Optional[datetime] = None
    error_count: int = 0
    consecutive_errors: int = 0
    failure_history: List[FailureRecord] = field(default_factory=list)
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def add_failure(self, failure_type: FailureType, error: str):
        """添加失败记录"""
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_check = datetime.now()

        record = FailureRecord(
            timestamp=datetime.now(),
            failure_type=failure_type,
            error_message=error
        )

        self.failure_history.append(record)

        # 只保留最近100条
        if len(self.failure_history) > 100:
            self.failure_history = self.failure_history[-100:]

        # 更新状态
        if failure_type == FailureType.SDK_EXIT:
            self.status = ProviderStatus.FAILED
        elif self.consecutive_errors >= 3:
            self.status = ProviderStatus.FAILED
        else:
            self.status = ProviderStatus.DEGRADED

    def record_success(self):
        """记录成功"""
        self.consecutive_errors = 0
        self.last_success = datetime.now()
        self.last_check = datetime.now()

        if self.status != ProviderStatus.HEALTHY:
            self.status = ProviderStatus.RECOVERING

            # 如果连续成功3次，恢复为健康
            recent_successes = sum(
                1 for r in self.failure_history[-3:]
                if not r.error_message
            )
            if recent_successes >= 3:
                self.status = ProviderStatus.HEALTHY

class ProviderHealthMonitor:
    """
    提供者健康监控器
    单例模式
    """

    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.health_records: Dict[str, ProviderHealth] = {}
        self.fallback_map: Dict[str, str] = {}  # original -> fallback
        self.monitoring_task = None
        self.alert_callbacks = []
        self.persistence_path = Path("data/monitoring/provider_health.json")

    @classmethod
    async def get_instance(cls):
        """获取单例实例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                await cls._instance.initialize()
            return cls._instance

    async def initialize(self):
        """初始化监控器"""
        # 加载历史数据
        self._load_history()

        # 启动监控任务
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

    def _load_history(self):
        """加载历史健康数据"""
        if self.persistence_path.exists():
            try:
                with open(self.persistence_path, 'r') as f:
                    data = json.load(f)
                    # 恢复健康记录
                    # ...
            except Exception as e:
                logger.error(f"Failed to load health history: {e}")

    def record_failure(
        self,
        provider_name: str,
        failure_type: str,
        error: str
    ):
        """
        记录失败

        Args:
            provider_name: provider 名称
            failure_type: 失败类型
            error: 错误信息
        """
        if provider_name not in self.health_records:
            self.health_records[provider_name] = ProviderHealth(
                name=provider_name,
                status=ProviderStatus.FAILED,
                last_check=datetime.now()
            )

        # 转换失败类型
        try:
            ft = FailureType(failure_type)
        except ValueError:
            ft = FailureType.UNKNOWN

        record = self.health_records[provider_name]
        record.add_failure(ft, error)

        # 触发告警
        if ft == FailureType.SDK_EXIT:
            self._trigger_critical_alert(provider_name, error)

    def record_fallback(self, original: str, fallback: str, reason: str):
        """
        记录降级

        Args:
            original: 原始 provider
            fallback: 降级 provider
            reason: 降级原因
        """
        self.fallback_map[original] = fallback

        # 更新原始 provider 状态
        if original in self.health_records:
            self.health_records[original].status = ProviderStatus.FALLBACK
            self.health_records[original].fallback_reason = reason

        # 记录降级 provider
        if fallback not in self.health_records:
            self.health_records[fallback] = ProviderHealth(
                name=fallback,
                status=ProviderStatus.HEALTHY,
                last_check=datetime.now(),
                is_fallback=True
            )

    def _trigger_critical_alert(self, provider: str, error: str):
        """触发关键告警"""
        alert = {
            'level': 'CRITICAL',
            'provider': provider,
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'message': f"Provider {provider} encountered critical error: SDK EXIT"
        }

        logger.critical(f"CRITICAL ALERT: {alert}")

        # 调用告警回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查

                # 持久化健康数据
                self._save_history()

                # 清理老数据
                self._cleanup_old_data()

                # 生成报告
                if datetime.now().minute == 0:  # 每小时
                    await self._generate_report()

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    def _save_history(self):
        """保存健康历史"""
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'timestamp': datetime.now().isoformat(),
                'health_records': {
                    name: {
                        'status': record.status.value,
                        'error_count': record.error_count,
                        'consecutive_errors': record.consecutive_errors,
                        'is_fallback': record.is_fallback
                    }
                    for name, record in self.health_records.items()
                },
                'fallback_map': self.fallback_map
            }

            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save health history: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康摘要"""
        healthy = sum(1 for r in self.health_records.values()
                     if r.status == ProviderStatus.HEALTHY)
        degraded = sum(1 for r in self.health_records.values()
                      if r.status == ProviderStatus.DEGRADED)
        failed = sum(1 for r in self.health_records.values()
                    if r.status == ProviderStatus.FAILED)

        return {
            'total_providers': len(self.health_records),
            'healthy': healthy,
            'degraded': degraded,
            'failed': failed,
            'fallback_active': len(self.fallback_map),
            'critical_errors': sum(
                1 for r in self.health_records.values()
                for f in r.failure_history
                if f.failure_type == FailureType.SDK_EXIT
            ),
            'last_update': datetime.now().isoformat()
        }
```

## Phase 5: 测试用例

### 5.1 隔离测试

**文件**: `tests/test_amazingdata_isolation.py`

```python
"""
测试 AmazingData SDK 隔离机制
确保 SDK 的异常行为不影响系统
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
    AmazingDataProvider, AmazingDataConfig
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError

class TestAmazingDataIsolation:
    """AmazingData 隔离测试套件"""

    @pytest.fixture
    def config(self):
        """测试配置"""
        return AmazingDataConfig(
            username="test_user",
            password="test_pass",
            host="127.0.0.1",
            port=8600,
            timeout=5,
            retry_count=1
        )

    @pytest.fixture
    def provider(self, config):
        """创建 provider 实例"""
        return AmazingDataProvider(config)

    @pytest.mark.asyncio
    async def test_system_exit_handling(self, provider):
        """
        测试 SystemExit 处理
        验证 SDK 调用 exit() 时不会崩溃
        """
        with patch('AmazingData.login') as mock_login:
            # 模拟 SDK 调用 exit(0)
            mock_login.side_effect = SystemExit(0)

            # 应该捕获并转换为 DataProviderError
            with pytest.raises(DataProviderError) as exc_info:
                await provider._login()

            # 验证错误信息
            assert "SDK 强制退出" in str(exc_info.value)
            assert provider._connected is False

    @pytest.mark.asyncio
    async def test_system_exit_with_error_code(self, provider):
        """测试带错误码的 SystemExit"""
        with patch('AmazingData.login') as mock_login:
            # 模拟 SDK 调用 exit(1)
            mock_login.side_effect = SystemExit(1)

            with pytest.raises(DataProviderError) as exc_info:
                await provider._login()

            assert "SDK 强制退出" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, provider):
        """测试登录超时处理"""
        with patch('AmazingData.login') as mock_login:
            # 模拟长时间阻塞
            async def slow_login(*args):
                await asyncio.sleep(10)
                return 0

            mock_login.side_effect = lambda *args: asyncio.run(slow_login(*args))

            # 应该在5秒后超时
            with pytest.raises(DataProviderError) as exc_info:
                await provider._login()

            assert "登录超时" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_normal_exception_handling(self, provider):
        """测试普通异常处理"""
        with patch('AmazingData.login') as mock_login:
            mock_login.side_effect = RuntimeError("Network error")

            with pytest.raises(DataProviderError) as exc_info:
                await provider._login()

            assert "登录异常" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_login(self, provider):
        """测试正常登录流程"""
        with patch('AmazingData.login') as mock_login:
            mock_login.return_value = 0  # 成功

            result = await provider._login()

            assert result is True
            assert provider._connected is True
            assert provider._login_time is not None

    @pytest.mark.asyncio
    async def test_sdk_call_wrapper(self, provider):
        """测试 SDK 调用包装器"""
        # 模拟一个会调用 exit() 的 SDK 函数
        def bad_sdk_function():
            raise SystemExit(0)

        with pytest.raises(DataProviderError):
            await provider._safe_sdk_call(bad_sdk_function)

    @pytest.mark.asyncio
    async def test_provider_factory_fallback(self):
        """测试 Provider Factory 降级机制"""
        from deepsearch.webui.api.providers import DataProviderFactory

        with patch('deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.AmazingDataProvider.initialize') as mock_init:
            # 模拟初始化失败
            mock_init.side_effect = DataProviderError("SDK 强制退出程序")

            # 应该降级到备用 provider
            provider = await DataProviderFactory.get_provider_async("amazingdata")

            # 验证不是 AmazingDataProvider
            assert not isinstance(provider, AmazingDataProvider)

            # 验证降级状态被记录
            assert "amazingdata" in DataProviderFactory._fallback_status

    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """测试健康监控记录"""
        from deepsearch.observability.monitoring.provider_health import (
            ProviderHealthMonitor, FailureType
        )

        monitor = await ProviderHealthMonitor.get_instance()

        # 记录 SDK 退出错误
        monitor.record_failure(
            "amazingdata",
            FailureType.SDK_EXIT.value,
            "SDK attempted to exit"
        )

        # 验证记录
        assert "amazingdata" in monitor.health_records
        health = monitor.health_records["amazingdata"]
        assert health.error_count == 1
        assert health.status.value == "failed"

        # 验证失败历史
        assert len(health.failure_history) == 1
        assert health.failure_history[0].failure_type == FailureType.SDK_EXIT

    @pytest.mark.asyncio
    async def test_mock_error_provider(self):
        """测试错误 Provider"""
        from deepsearch.infrastructure.providers.implementations.mock.error_provider import (
            MockErrorProvider
        )

        provider = MockErrorProvider("Test error message")

        # 初始化应该成功
        assert await provider.initialize() is True

        # 但所有数据方法应该抛出错误
        with pytest.raises(DataProviderError) as exc_info:
            await provider.get_stock_list()

        assert "Test error message" in str(exc_info.value)
        assert provider.call_count == 1
```

## Phase 6: 配置更新

### 6.1 生产配置

**文件**: `deepsearch/config/settings.prod.yaml`

```yaml
# AmazingData 配置
amazingdata:
  enabled: true
  username: "${AMAZINGDATA_USERNAME:212200038719}"
  password: "${AMAZINGDATA_PASSWORD:212200038719@2025}"
  host: "${AMAZINGDATA_HOST:101.230.159.234}"
  port: ${AMAZINGDATA_PORT:8600}
  timeout: 10
  retry_count: 1  # 减少重试，快速失败
  heartbeat_interval: 60
  auto_reconnect: true

  # SDK 隔离配置
  isolation:
    enabled: true               # 启用隔离
    init_timeout: 10            # 初始化超时（秒）
    fallback_on_exit: true      # SDK 退出时自动降级
    fallback_provider: "akshare" # 降级数据源
    monitor_sdk_calls: true     # 监控所有 SDK 调用

# 降级策略
fallback:
  # 数据源优先级
  priority:
    - amazingdata    # 首选
    - akshare_proxy  # 次选
    - akshare        # 备选
    - error          # 最后返回错误

  # 快速降级设置
  quick_fallback: true         # 快速降级（不重试）
  fallback_timeout: 5000       # 降级超时（毫秒）

  # 恢复策略
  recovery:
    enabled: true              # 启用自动恢复
    check_interval: 300        # 检查间隔（秒）
    success_threshold: 3       # 连续成功次数阈值

# 监控配置
monitoring:
  provider_health:
    enabled: true
    persist_history: true
    history_path: "data/monitoring/provider_health.json"
    alert_on_sdk_exit: true   # SDK 退出时发送告警

  alerts:
    email:
      enabled: false
      recipients: []
    webhook:
      enabled: false
      url: ""
```

## 实施检查清单

### Phase 1 检查项
- [ ] _login 方法添加 safe_login 包装
- [ ] 捕获 SystemExit 异常
- [ ] 返回特定错误码 -999
- [ ] 添加详细错误信息
- [ ] 测试 SystemExit 处理

### Phase 2 检查项
- [ ] DataProviderFactory 添加 try-except
- [ ] 实现降级到 AkShare
- [ ] 添加降级状态记录
- [ ] 添加监控记录调用
- [ ] 测试降级机制

### Phase 3 检查项
- [ ] 创建 MockErrorProvider 类
- [ ] 实现所有必要方法
- [ ] 添加调用记录
- [ ] 返回明确错误信息
- [ ] 测试错误 provider

### Phase 4 检查项
- [ ] 创建 ProviderHealthMonitor
- [ ] 实现失败记录
- [ ] 实现降级记录
- [ ] 添加告警机制
- [ ] 测试监控系统

### Phase 5 检查项
- [ ] 编写单元测试
- [ ] 测试 SystemExit 处理
- [ ] 测试超时处理
- [ ] 测试降级机制
- [ ] 测试监控记录

### Phase 6 检查项
- [ ] 更新生产配置
- [ ] 添加隔离配置
- [ ] 配置降级策略
- [ ] 配置监控告警
- [ ] 测试配置加载

## 风险矩阵

| 风险等级 | 风险描述 | 缓解措施 |
|---------|---------|---------|
| 高 | SDK 其他地方也可能调用 exit() | 包装所有 SDK 调用 |
| 高 | 线程池异常传播到主线程 | 使用 safe wrapper |
| 中 | 降级后性能下降 | 优化降级 provider |
| 中 | 错误信息不够详细 | 添加详细日志 |
| 低 | 配置更新需要重启 | 支持热加载 |

## 回滚计划

如果实施后出现问题：

1. **立即措施**
   - 设置环境变量 `DISABLE_AMAZINGDATA=true`
   - 系统自动使用 AkShare

2. **代码回滚**
   ```bash
   git revert HEAD
   git push
   ```

3. **配置回滚**
   ```yaml
   amazingdata:
     enabled: false  # 禁用 AmazingData
   ```

## 验收标准

1. ✅ SDK 调用 exit() 不会导致系统崩溃
2. ✅ 自动降级到备用数据源（< 10秒）
3. ✅ 错误信息明确指出问题原因
4. ✅ 监控系统记录所有失败
5. ✅ 测试覆盖率 > 80%
6. ✅ 生产环境稳定运行24小时

## 时间估算

| 阶段 | 工作量 | 说明 |
|------|--------|------|
| Phase 1 | 2小时 | 核心隔离实现 |
| Phase 2 | 1小时 | Factory 改进 |
| Phase 3 | 0.5小时 | Error Provider |
| Phase 4 | 1.5小时 | 监控系统 |
| Phase 5 | 1小时 | 测试编写 |
| Phase 6 | 0.5小时 | 配置更新 |
| 测试验证 | 1小时 | 集成测试 |
| **总计** | **7.5小时** | |

---

**文档维护**：每个阶段完成后更新此文档，记录实际修改和遇到的问题。