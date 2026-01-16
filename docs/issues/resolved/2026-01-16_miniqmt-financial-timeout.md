# MiniQMT 财务数据接口超时问题

> 发现日期: 2026-01-16
> 发现位置: apps/api/api/endpoints/qmt/miniqmt.py
> 类型: performance
> 严重程度: medium
> 状态: resolved

---

## 问题描述

以下接口请求时会超时（>15秒无响应），可能导致服务阻塞：

| 接口 | 说明 |
|------|------|
| `GET /api/miniqmt/xtdata/financial` | 财务数据 |
| `GET /api/miniqmt/xtdata/etf-info` | ETF 信息 |
| `GET /api/miniqmt/xtdata/index-weight` | 指数权重 |

### 现象

```bash
curl -s "http://localhost:8000/api/miniqmt/xtdata/financial?symbols=000001.SZ" --max-time 15
# Exit code 28 (超时)
```

### 影响

- 客户端请求超时，用户体验差
- 长时间阻塞可能影响其他请求处理
- 多个并发请求可能导致服务不稳定

---

## 发现上下文

> 在执行 MiniQMT API 全接口测试时发现此问题

---

## 可能原因

1. **数据下载** - 这些接口可能触发 xtdata 的数据下载，耗时较长
2. **同步阻塞** - 接口可能是同步执行，阻塞了事件循环
3. **无超时保护** - 底层操作没有超时限制

---

## 建议修复方案

### 方案 A: 添加超时保护

```python
import asyncio

@router.get("/xtdata/financial")
async def get_financial(symbols: str, timeout: int = 30):
    try:
        result = await asyncio.wait_for(
            fetch_financial_data(symbols),
            timeout=timeout
        )
        return {"success": True, "data": result}
    except asyncio.TimeoutError:
        return {"success": False, "message": f"请求超时({timeout}秒)"}
```

### 方案 B: 后台任务模式

对于耗时操作，使用后台任务：

1. 接口立即返回任务 ID
2. 客户端轮询任务状态
3. 任务完成后获取结果

### 方案 C: 缓存策略

财务数据更新频率低，可以：

1. 定时预加载到缓存
2. API 优先从缓存返回
3. 缓存未命中时触发异步更新

### 预估工作量

- [ ] 中（30分钟 - 2小时）

### 相关文件

- `apps/api/api/endpoints/qmt/miniqmt.py`

---

## 备注

需要了解 xtdata 的数据下载机制，确定是首次下载慢还是每次请求都慢。
