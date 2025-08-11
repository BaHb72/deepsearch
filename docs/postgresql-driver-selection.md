# PostgreSQL Python 驱动技术选型

## 最终选择：psycopg3

我们选择了 **psycopg3**（正式名称为 `psycopg`）作为 DeepSearch 项目的 PostgreSQL 驱动。

### 选择理由

1. **最新技术栈**
    - psycopg3 是 PostgreSQL 官方推荐的 Python 驱动
    - 2024年的主流选择，活跃维护
    - 原生支持 Python 3.8+

2. **完整异步支持**
    - 内置 asyncio 支持，API 设计优雅
    - 同时支持同步和异步操作
    - 与 FastAPI 完美集成

3. **性能优秀**
    - 虽然不如 asyncpg 极致，但对大多数应用足够快
    - 支持连接池，可以有效管理数据库连接
    - 二进制协议通信，效率高

4. **易用性强**
    - 支持 Pydantic 模型映射
    - Row Factory 功能强大
    - DB-API 2.0 兼容

5. **生态系统**
    - 与 SQLAlchemy、Django ORM 等兼容
    - 丰富的文档和社区支持
    - 大量生产环境验证

### 安装方式

```bash
# 开发环境（快速开始）
pip install "psycopg[binary,pool]"

# 生产环境（推荐）
pip install "psycopg[c,pool]"
```

### 使用示例

```python
import asyncio
import psycopg
import sys

# Windows 兼容性
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

async def get_connection():
    """创建异步数据库连接"""
    return await psycopg.AsyncConnection.connect(
        host="localhost",
        port=5432,
        dbname="deepsearch",
        user="postgres",
        password="password"
    )

async def test_query():
    """执行异步查询"""
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users")
            rows = await cur.fetchall()
            return rows
```

### 连接池使用

```python
from psycopg_pool import AsyncConnectionPool

# 创建连接池
pool = AsyncConnectionPool(
    "postgresql://user:password@localhost/dbname",
    min_size=1,
    max_size=10
)

# 使用连接池
async with pool.connection() as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")
```

### 与其他驱动对比

| 特性         | psycopg3 | asyncpg | psycopg2  |
|------------|----------|---------|-----------|
| 异步支持       | ✅ 原生     | ✅ 专用    | ❌ 需要aiopg |
| 性能         | 优秀       | 极致      | 一般        |
| DB-API兼容   | ✅        | ❌       | ✅         |
| 维护状态       | 活跃       | 活跃      | 维护模式      |
| 学习曲线       | 平缓       | 陡峭      | 平缓        |
| Pydantic支持 | ✅        | ❌       | ❌         |
| Windows支持  | ✅ 需要配置   | ✅       | ✅         |

### 注意事项

1. **Windows 平台**
    - 需要设置事件循环策略为 `WindowsSelectorEventLoopPolicy`
    - 已在代码中自动处理

2. **连接管理**
    - 推荐使用连接池管理连接
    - 异步连接需要显式关闭

3. **错误处理**
    - 提供了详细的异常类型
    - 支持事务回滚

### 迁移指南

从 asyncpg 迁移到 psycopg3：

```python
# asyncpg (旧)
conn = await asyncpg.connect(...)
version = await conn.fetchval("SELECT version()")
await conn.close()

# psycopg3 (新)
async with await psycopg.AsyncConnection.connect(...) as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT version()")
        result = await cur.fetchone()
        version = result[0]
```

### 总结

psycopg3 是一个现代化、功能完整的 PostgreSQL Python 驱动，特别适合：

- 需要同时支持同步和异步的项目
- 重视代码可维护性的团队
- 需要与现有 Python 生态系统集成的应用
- Windows 平台开发

对于 DeepSearch 这样的量化交易系统，psycopg3 提供了足够的性能和灵活性，同时保持了良好的开发体验。