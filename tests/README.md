# DeepSearch Test Suite

## 概述

测试套件已按照API模块进行重新组织，提供清晰的测试结构和完整的覆盖率。

## 测试结构

```
tests/
├── __init__.py              # 测试套件初始化
├── conftest.py              # Pytest配置和通用fixtures
├── README.md                # 本文档
│
├── test_data_sources.py     # 数据源API测试
├── test_market_data.py      # 市场数据API测试
├── test_database.py         # 数据库API测试
├── test_monitoring.py       # 监控API测试
└── test_system.py           # 系统管理API测试
```

## 测试模块说明

### 1. 数据源测试 (test_data_sources.py)
- 数据源状态检查
- 配置验证
- 数据源刷新
- 特定数据源测试
- 故障转移机制
- 熔断器模式

### 2. 市场数据测试 (test_market_data.py)
- 实时行情获取
- K线数据查询
- 盘口数据
- 成交明细
- 市场指数
- 热门股票

### 3. 数据库测试 (test_database.py)
- 连接状态
- 健康检查
- 性能统计
- 缓存管理
- 迁移状态

### 4. 监控测试 (test_monitoring.py)
- 系统状态
- 性能指标
- 事件监控
- 性能分析
- 告警管理

### 5. 系统管理测试 (test_system.py)
- 系统信息
- 配置管理
- 日志管理
- 系统控制
- 备份恢复

## 运行测试

### 运行所有测试
```bash
uv run pytest tests/
```

### 运行特定模块测试
```bash
# 测试数据源
uv run pytest tests/test_data_sources.py -v

# 测试市场数据
uv run pytest tests/test_market_data.py -v

# 测试数据库
uv run pytest tests/test_database.py -v
```

### 运行特定测试类
```bash
uv run pytest tests/test_data_sources.py::TestDataSourceStatus -v
```

### 运行特定测试方法
```bash
uv run pytest tests/test_data_sources.py::TestDataSourceStatus::test_get_status_report -v
```

### 生成覆盖率报告
```bash
uv run pytest tests/ --cov=deepsearch --cov-report=html
```

## 测试配置

### Fixtures

在 `conftest.py` 中定义了以下通用fixtures：

- `event_loop`: 异步事件循环
- `mock_config`: 模拟配置对象
- `mock_redis`: 模拟Redis客户端
- `test_data_provider`: 模拟数据提供者

### 使用示例

```python
@pytest.mark.asyncio
async def test_example(mock_config, test_data_provider):
    """测试示例"""
    # 使用mock_config
    assert mock_config.database.main.enabled == True
    
    # 使用test_data_provider
    quote = await test_data_provider.get_realtime_quote("000001")
    assert quote["symbol"] == "000001"
```

## 编写新测试

### 1. 按API模块组织

为新的API端点创建测试时，将其添加到相应的测试文件中：

```python
class TestNewFeature:
    """Test new feature endpoints."""
    
    @pytest.mark.asyncio
    async def test_new_endpoint(self):
        """Test the new endpoint."""
        # 测试逻辑
        pass
```

### 2. 使用适当的Mock

```python
from unittest.mock import Mock, AsyncMock, patch

# Mock同步函数
mock_func = Mock(return_value="result")

# Mock异步函数
async_mock = AsyncMock(return_value="async_result")

# 使用patch装饰器
@patch('deepsearch.module.function')
def test_with_patch(mock_function):
    mock_function.return_value = "mocked"
    # 测试逻辑
```

### 3. 测试异步代码

```python
@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await async_function()
    assert result == expected_value
```

## 测试标准

### 命名规范
- 测试文件: `test_<module_name>.py`
- 测试类: `Test<FeatureName>`
- 测试方法: `test_<specific_behavior>`

### 断言风格
```python
# 推荐
assert result == expected
assert "key" in dictionary
assert len(items) > 0

# 不推荐
assert result is expected  # 使用 == 而非 is
assert dictionary.get("key")  # 明确检查存在性
```

### 测试隔离
- 每个测试应该独立运行
- 使用fixtures进行setup/teardown
- 避免测试间的依赖关系

## 持续集成

测试套件可以集成到CI/CD流程中：

```yaml
# GitHub Actions示例
- name: Run tests
  run: |
    uv sync --all-extras
    uv run pytest tests/ --cov=deepsearch
```

## 故障排除

### 常见问题

1. **导入错误**
   ```bash
   # 确保已安装所有依赖
   uv sync --all-extras
   ```

2. **异步测试超时**
   ```python
   # 增加超时时间
   @pytest.mark.asyncio
   @pytest.mark.timeout(30)  # 30秒超时
   async def test_slow_operation():
       pass
   ```

3. **Mock对象未正确配置**
   ```python
   # 确保Mock返回正确的类型
   mock.return_value = AsyncMock()  # 对于异步方法
   mock.return_value = Mock()  # 对于同步方法
   ```

## 维护指南

1. **定期更新测试**：当API接口变更时，同步更新相关测试
2. **保持覆盖率**：新功能必须包含测试，目标覆盖率 > 80%
3. **性能测试**：关键路径需要包含性能测试
4. **文档同步**：测试变更时更新本README

## 联系方式

如有问题或建议，请通过项目Issue跟踪器联系。