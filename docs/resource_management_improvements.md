# 资源管理和异常处理改进方案

## 一、已识别的问题

### 1. 异常处理问题

#### 1.1 裸露的 except 语句

- **位置**: `examples/webui_integration_example.py:81`
- **问题**: 使用 `except Exception:` 并直接 `pass`，可能隐藏重要错误
- **修复方案**:

```python
except websockets.exceptions.WebSocketException as e:
    logger.warning(f"WebSocket 连接异常: {e}")
except Exception as e:
    logger.error(f"未预期的错误: {e}")
```

#### 1.2 不明确的异常处理

- **位置**: `config/crypto.py:88`
- **问题**: 捕获所有异常并假设是明文密码
- **修复方案**:

```python
except (InvalidToken, ValueError) as e:
    # 明确指定可能的异常类型
    logger.debug(f"解密失败，可能是明文密码: {e}")
    return encrypted_password
```

### 2. 资源管理问题

#### 2.1 数据库连接管理

- **位置**: `webui/api/data.py`
- **问题**: 使用 `next(get_db())` 但在 finally 块中手动关闭
- **改进方案**:

```python
from contextlib import contextmanager

@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 使用方式
with get_db_session() as db:
    # 执行数据库操作
    pass
```

#### 2.2 文件句柄管理

- **位置**: `cli.py` 配置文件读写
- **当前**: 已正确使用 `with open()` 语句
- **建议**: 继续保持良好实践

### 3. 并发安全问题

#### 3.1 组件管理器单例

- **位置**: `core/component_manager.py`
- **潜在问题**: 多线程环境下的单例模式可能存在竞争条件
- **改进方案**:

```python
import threading

class ComponentManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

## 二、改进实施计划

### 第一步：异常处理规范化

1. **定义异常层次结构**

```python
# exceptions.py
class DeepSearchError(Exception):
    """基础异常类"""
    pass

class ConfigurationError(DeepSearchError):
    """配置相关错误"""
    pass

class ComponentError(DeepSearchError):
    """组件相关错误"""
    pass

class DataError(DeepSearchError):
    """数据处理错误"""
    pass
```

2. **统一异常处理模式**

- 明确指定要捕获的异常类型
- 记录异常信息到日志
- 适当的错误恢复或传播

### 第二步：资源管理增强

1. **实现资源池**

```python
class ResourcePool:
    """通用资源池"""
    def __init__(self, factory, max_size=10):
        self.factory = factory
        self.max_size = max_size
        self.pool = queue.Queue(maxsize=max_size)
        self.size = 0
        self._lock = threading.Lock()
    
    @contextmanager
    def get_resource(self):
        resource = self._acquire()
        try:
            yield resource
        finally:
            self._release(resource)
```

2. **数据库连接池优化**

- 使用 SQLAlchemy 的内置连接池
- 配置合理的池大小和超时时间
- 实现连接健康检查

### 第三步：监控和诊断

1. **资源使用监控**

```python
class ResourceMonitor:
    """资源使用监控器"""
    def __init__(self):
        self.active_connections = 0
        self.peak_connections = 0
        self.total_requests = 0
    
    def track_usage(self):
        """跟踪资源使用情况"""
        pass
```

2. **泄露检测**

- 定期检查未释放的资源
- 记录资源分配和释放的调用栈
- 生成资源使用报告

## 三、最佳实践指南

### 1. 异常处理

- 使用具体的异常类型，避免捕获 `Exception`
- 在适当的层级处理异常
- 记录足够的上下文信息
- 不要忽略异常（避免空的 except 块）

### 2. 资源管理

- 始终使用上下文管理器（with 语句）
- 实现 `__enter__` 和 `__exit__` 方法
- 在 finally 块中释放资源
- 考虑使用资源池来复用昂贵的资源

### 3. 并发安全

- 使用线程安全的数据结构
- 最小化锁的持有时间
- 避免死锁（按固定顺序获取锁）
- 使用原子操作where possible

## 四、测试策略

### 1. 资源泄露测试

```python
def test_resource_cleanup():
    """测试资源是否正确清理"""
    initial_count = get_open_file_count()
    
    # 执行操作
    with ResourceManager() as rm:
        rm.do_something()
    
    # 验证资源已释放
    final_count = get_open_file_count()
    assert final_count == initial_count
```

### 2. 异常处理测试

```python
def test_exception_handling():
    """测试异常是否被正确处理"""
    with pytest.raises(SpecificError):
        risky_operation()
    
    # 验证日志记录
    assert "Expected error message" in caplog.text
```

### 3. 并发安全测试

```python
def test_thread_safety():
    """测试多线程环境下的安全性"""
    results = []
    threads = []
    
    for i in range(10):
        t = threading.Thread(target=concurrent_operation, args=(results,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 验证结果一致性
    assert len(set(results)) == 1
```

## 五、实施优先级

1. **高优先级**
    - 修复裸露的 except 语句
    - 实现数据库连接的上下文管理器
    - 添加资源使用监控

2. **中优先级**
    - 定义统一的异常层次结构
    - 实现资源池
    - 增强并发安全

3. **低优先级**
    - 完善测试覆盖
    - 性能优化
    - 文档更新