# 生产代码中的 Mock 数据违规

- **发现日期**: 2026-02-07
- **严重程度**: 中等（违规）
- **影响范围**: `/api/data/realtime/{symbol}`

## 问题描述

`/api/data/realtime/{symbol}` 端点在无法获取真实数据时返回硬编码的 Mock 数据：

```json
{
  "symbol": "000001",
  "name": "演示000001",
  "exchange": "SZSE",
  "industry": "示例行业",
  "price": 10.5,
  "change": 0.12,
  "change_pct": 1.15,
  "current": 10.5,
  "amount": 12345678.9,
  "volume": 1234567
}
```

## 违规项

CLAUDE.md 明确规定：**"禁止生产代码中的 Mock 数据"**

## 正确行为

当无法获取真实数据时，应返回明确的错误信息（如 503 或 404），而非伪装成正常数据的 Mock 值。Mock 数据可能误导前端展示错误的市场信息。

## 建议修复

移除 Mock 数据生成逻辑，当数据源不可用时返回标准的 HTTP 错误响应。

**关键文件**：

- 需要定位返回 "演示000001" 的具体代码位置（可能在 `apps/api/api/endpoints/data/data.py` 或相关服务层中）
