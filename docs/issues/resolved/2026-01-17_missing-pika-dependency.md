# 缺少 pika 依赖导致 RabbitMQ 模块导入失败

## 问题描述

`packages/core/messaging/implementations/rabbitmq.py` 需要 `pika` 包，但项目依赖中可能未正确安装。

## 错误信息

```
ModuleNotFoundError: No module named 'pika'
ImportError: pika is required for RabbitMQMessageBus
```

## 影响

- 导入 `bootstrap.py` 时会触发错误
- RabbitMQ 消息总线功能不可用

## 建议方案

### 方案 A：添加为可选依赖

```toml
# pyproject.toml
[project.optional-dependencies]
rabbitmq = ["pika>=1.3.0"]
```

### 方案 B：延迟导入

修改 `messaging/implementations/__init__.py`，使用延迟导入避免启动时报错：

```python
# 不在模块级别导入 RabbitMQ
# from .rabbitmq import RabbitMQMessageBus  # 移除

def get_rabbitmq_bus():
    from .rabbitmq import RabbitMQMessageBus
    return RabbitMQMessageBus
```

### 方案 C：条件导入

```python
try:
    from .rabbitmq import RabbitMQMessageBus
except ImportError:
    RabbitMQMessageBus = None  # 不可用时设为 None
```

## 优先级

中 - 影响部分模块的导入

## 发现时间

2026-01-17

## 发现场景

验证 Provider 工厂修复时，尝试导入 bootstrap 模块时发现
