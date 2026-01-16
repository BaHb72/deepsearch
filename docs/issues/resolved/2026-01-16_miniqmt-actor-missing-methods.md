# MiniQMTActor 缺少核心方法实现

> 发现日期: 2026-01-16
> 发现位置: packages/core/compute/actors/miniqmt_actor.py
> 类型: code-quality
> 严重程度: high
> 状态: resolved

---

## 问题描述

`MiniQMTActor` 类缺少多个核心方法的实现，导致通过 API 调用这些功能时返回 500 错误。

### 现象

以下 API 端点返回错误 `type object 'MiniQMTActor' has no attribute 'xxx'`:

| 接口 | 缺失方法 |
|------|----------|
| `POST /api/miniqmt/subscribe` | `subscribe` |
| `POST /api/miniqmt/unsubscribe` | `unsubscribe` |
| `GET /api/miniqmt/realtime` | `get_data` |
| `GET /api/miniqmt/history` | `get_data` |
| `GET /api/miniqmt/minute` | `get_data` |

### 影响

- 前端无法通过这些接口订阅和获取实时行情数据
- 历史K线和分钟线数据无法通过标准接口获取
- 只能使用 `/api/miniqmt/xtdata/*` 系列接口作为替代

---

## 发现上下文

> 在执行 MiniQMT API 全接口测试时发现此问题

对每个 miniqmt 接口进行最小量测试时，发现这些接口返回 500 错误。

---

## 相关代码

```python
# 文件: packages/core/compute/actors/miniqmt_actor.py
# API 端点期望的方法签名:

class MiniQMTActor:
    async def subscribe(self, symbols: list[str]) -> dict:
        """订阅股票实时行情"""
        ...

    async def unsubscribe(self, symbols: list[str]) -> dict:
        """取消订阅"""
        ...

    async def get_data(self, symbols: list[str], data_type: str) -> dict:
        """获取实时/历史数据"""
        ...
```

---

## 建议修复方案

### 方案 A: 实现缺失方法

在 `MiniQMTActor` 中添加这些方法的实现，委托给底层的 `MiniQMTProvider`。

### 方案 B: 统一使用 xtdata 接口

如果 Actor 模式不再需要，可以考虑：

1. 废弃这些旧接口
2. 在 API 文档中标注使用 `/api/miniqmt/xtdata/*` 替代

### 预估工作量

- [x] 中（30分钟 - 2小时）

### 相关文件

- `packages/core/compute/actors/miniqmt_actor.py`
- `apps/api/api/endpoints/qmt/miniqmt.py`

---

## 备注

`/api/miniqmt/xtdata/*` 系列接口工作正常，说明底层 Provider 功能是完整的，问题仅在于 Actor 层没有正确暴露方法。
