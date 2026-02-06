# AkShare 代理被 Cloudflare 限流

- **发现日期**: 2026-02-07
- **严重程度**: 中等
- **影响范围**: AkShare 通过代理的大数据量请求（股票列表、实时行情等）

## 问题描述

AkShare 的 Cloudflare Workers 代理 (`akshare-proxy.934073514.workers.dev`) 在处理多个请求后触发 520 错误限流：

```
HTTPSConnectionPool(host='akshare-proxy.934073514.workers.dev', port=443):
Max retries exceeded with url: /proxy?url=...
(Caused by ResponseError('too many 520 error responses'))
```

## 根本原因

Cloudflare Workers 有请求频率限制。当 AkShare 尝试分页获取大量数据（如股票列表需要 17+ 页）时，频繁请求触发了限流保护。

## 额外发现

`AkShareProxyProvider` 缺少多个必要方法：

- `get_kline` - K线数据获取
- `get_calendar` - 交易日历获取

这些方法在 `AkShareProxyProvider` 类中未实现，导致对应端点直接报错：

```
'AkShareProxyProvider' object has no attribute 'get_kline'
'AkShareProxyProvider' object has no attribute 'get_calendar'
```

## 影响

- `/api/akshare/stock/list` -> 超时（代理限流）
- `/api/akshare/stock/{symbol}/kline` -> 500（方法缺失）
- `/api/akshare/calendar` -> 500（方法缺失）
- `/api/market/akshare/realtime/quote` -> 超时（代理限流）

## 建议修复

1. 在 AkShareProxyProvider 中实现缺失的 `get_kline` 和 `get_calendar` 方法
2. 对代理请求增加退避策略（backoff），避免触发限流
3. 考虑增加本地缓存层减少对代理的请求频率
4. 评估是否需要升级 Cloudflare Workers 计划以获得更高的请求配额

## 相关问题

- `2026-01-19_akshare-proxy-log-confusion.md` -- AkShare 代理/直连模式日志混淆
- `2026-01-18_datasource-access-failures.md` -- 数据源访问失败（含 AkShare）
- `2026-01-16_akshare-provider-lifecycle.md` -- AkShare Provider 生命周期问题

**关键文件**：

- `packages/core/infrastructure/providers/implementations/akshare/akshare_adapter.py`
- `packages/core/infrastructure/providers/implementations/akshare/akshare_direct.py`
- `packages/core/utils/network/proxy_client.py`
