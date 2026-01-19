# 时区统一 + 登录预热机制

> 日期: 2026-01-18
> 模块: ORM 模型、AmazingData Actor、Dask Adapter
> 类型: architecture | design-change

---

## 为什么要改

### 遇到的问题

1. **时区错误导致数据写入失败**

   ```
   can't subtract offset-naive and offset-aware datetimes
   ```

   - ORM 模型使用默认的 `TIMESTAMP` 类型（无时区）
   - 但部分代码使用 `datetime.now(timezone.utc)` 生成带时区的时间
   - 两者混用导致数据库操作失败，板块数据预热显示 `板块数: 0`

2. **首次 API 调用超时**
   - AmazingData SDK 登录需要 15-20s
   - 默认超时 30s，加上网络波动容易触发超时重试
   - 登录是后台异步执行，首次调用仍需等待

### 现有方案的问题

- ORM 模型没有显式声明时区类型
- 登录预热是 `asyncio.create_task()` 后台执行，不阻塞但也不保证首次调用前完成
- 超时时间不区分首次调用（含登录）和后续调用（纯 SDK 执行）

---

## 尝试过的方案

### 方案 A: 统一使用 UTC

**思路**: 所有 datetime 使用 `datetime.now(timezone.utc)`

**问题**:

- A 股交易系统，交易时段、K 线时间都是北京时间
- 日志和调试不直观，需要 +8 小时换算
- 与数据源原生格式不匹配

### 方案 B: 统一使用北京时间 (Asia/Shanghai)

**思路**: 创建统一的 `now()` 函数，返回北京时间

**优势**:

- 与 A 股交易场景直接对应
- 日志直观易读
- 只需改一处即可全局调整

---

## 最终方案

### 选择: 方案 B - 统一使用北京时间

**原因**:

- 这是专门针对 A 股的量化交易系统
- 北京时间更符合业务场景，减少心智负担
- 通过工具模块统一管理，未来调整方便

### 关键改动

#### 1. ORM 模型时区支持

文件: `packages/core/infrastructure/persistence/models/*.py`

```python
# 改之前
time: Mapped[datetime] = mapped_column(index=True)

# 改之后
from sqlalchemy import DateTime
time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
```

**为什么**: 显式声明 `DateTime(timezone=True)` 让数据库存储 `TIMESTAMP WITH TIME ZONE`，避免 naive/aware 混用错误。

#### 2. 统一时间工具模块

文件: `packages/core/utils/time/market_time.py`

```python
from zoneinfo import ZoneInfo

# 系统统一时区：北京时间
CHINA_TZ = ZoneInfo("Asia/Shanghai")

def now() -> datetime:
    """获取当前北京时间（带时区信息）"""
    return datetime.now(CHINA_TZ)
```

**为什么**: 集中管理时区配置，所有地方 `from core.utils.time.market_time import now` 统一调用。

#### 3. 同步预热登录

文件: `packages/core/compute/actors/amazingdata_actor.py`

```python
# 改之前（后台异步，不保证首次调用前完成）
if self._config.get("prewarm", False):
    asyncio.create_task(self._prewarm_login())

# 改之后（同步阻塞，确保登录完成）
if self._config.get("prewarm", False):
    await self._ensure_logged_in()
    logger.info("同步预热登录完成，首次调用无延迟")
```

**为什么**: 用 Worker 启动时间换取首次调用速度，启动多等 15s，但首次 API 调用无延迟。

#### 4. 分层超时策略

文件: `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`

```python
def __init__(
    self,
    dask_client: "Client",
    timeout: float = 45.0,           # 后续调用超时
    first_call_timeout: float = 90.0, # 首次调用超时（含登录）
):
```

**为什么**: 首次调用可能包含登录流程，需要更长超时；后续调用是纯 SDK 执行，45s 足够。

---

## 注意事项

### 这个方案的局限

1. **数据库迁移**: ORM 模型类型变更需要运行 Alembic 迁移
2. **历史数据**: 旧数据无时区信息，PostgreSQL 会视为服务器时区处理
3. **跨时区部署**: 如果未来需要跨时区部署，需要重新评估时区策略

### 如果要改回 UTC

1. 修改 `market_time.py` 中的 `CHINA_TZ = timezone.utc`
2. ORM 模型不需要改（`DateTime(timezone=True)` 通用）
3. 所有使用 `now()` 的代码自动生效

### 相关文件清单

| 文件 | 修改内容 |
|------|----------|
| `models/ingestion.py` | 6 个 datetime 字段 |
| `models/market.py` | 4 个 datetime 字段 |
| `models/watchlist.py` | 10 个 datetime 字段 |
| `models/module_source.py` | 2 个 datetime 字段 |
| `market_time.py` | 新增 `now()` 和 `CHINA_TZ` |
| `amazingdata_actor.py` | 同步预热登录 |
| `dask_adapter.py` | 分层超时策略 |
| `settings.dev.yaml` | 添加 `prewarm: true` |
| `plugins/config.py` | 添加 `prewarm` 配置字段 |
| `dask_plugin.py` | 传递 `prewarm` 参数 |
| 5 个应用代码文件 | `datetime.now()` -> `now()` |

---

## 关键结论

> **统一使用北京时间 + 同步预热登录 + 分层超时**，从根本上解决了时区混用错误和首次调用延迟问题。通过工具模块集中管理时区，未来调整只需改一处。
