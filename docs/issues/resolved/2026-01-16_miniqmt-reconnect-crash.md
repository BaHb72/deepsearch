# MiniQMT reconnect 接口导致服务崩溃

> 发现日期: 2026-01-16
> 发现位置: apps/api/api/endpoints/qmt/miniqmt.py
> 类型: code-quality
> 严重程度: critical
> 状态: resolved

---

## 问题描述

调用 `POST /api/miniqmt/reconnect` 接口会导致整个后端服务崩溃，需要重新启动。

### 现象

```bash
curl -s -X POST http://localhost:8000/api/miniqmt/reconnect
# 返回 exit code 7 (连接被拒绝)
# 服务进程退出
```

### 影响

- 服务不可用，需要人工重启
- 可能导致正在处理的其他请求丢失
- 潜在的安全风险（DoS 攻击向量）

---

## 发现上下文

> 在执行 MiniQMT API 全接口测试时发现此问题

测试订阅相关接口时，调用 reconnect 后服务停止响应。

---

## 相关代码

```python
# 文件: apps/api/api/endpoints/qmt/miniqmt.py
# reconnect 端点的实现需要检查

@router.post("/reconnect")
async def reconnect():
    """重新连接 MiniQMT"""
    # 可能的问题:
    # 1. 未捕获的异常
    # 2. 阻塞主线程
    # 3. 资源释放问题
    ...
```

---

## 建议修复方案

1. **添加异常处理** - 确保所有异常被捕获并返回友好错误
2. **异步执行** - reconnect 操作应该在后台任务中执行
3. **超时保护** - 添加操作超时，避免无限等待
4. **状态检查** - reconnect 前检查当前状态，避免重复操作

### 预估工作量

- [x] 中（30分钟 - 2小时）

### 相关文件

- `apps/api/api/endpoints/qmt/miniqmt.py`
- `packages/core/infrastructure/providers/implementations/qmt/miniqmt.py`

---

## 备注

这是一个严重问题，应该优先修复。任何能导致服务崩溃的 API 都是潜在的安全风险。
