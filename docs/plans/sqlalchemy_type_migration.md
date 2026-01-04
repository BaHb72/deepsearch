# SQLAlchemy 2.0 类型系统迁移计划

## 背景

当前项目使用 SQLAlchemy 2.0.44，但 ORM 模型类型系统未完全迁移到 SQLAlchemy 2.0 的原生 PEP-484 语法。
这导致 mypy 无法正确推断 ORM 模型的 `__init__` 参数类型，触发 `call-arg` 错误。

### 当前状态

- **SQLAlchemy 版本**: 2.0.44
- **Base 类定义**: 纯 `DeclarativeBase`（无 `MappedAsDataclass`）
- **字段语法**: 已使用 `Mapped` + `mapped_column()` 语法
- **mypy 处理**: 通过 `ignore_errors = true` 临时忽略 ORM 模块错误

### 问题分析

1. **`MappedAsDataclass` 约束**: 要求所有字段按 dataclass 规则排序（有默认值的必须在无默认值之后）
2. **现有模型不兼容**: 现有 ORM 模型的字段顺序不满足 dataclass 规则
3. **构造函数调用方式**: 现有代码使用关键字参数创建 ORM 实例，这在纯 dataclass 模式下可能失败

## 迁移目标

1. 启用 `MappedAsDataclass` 获得完整的 mypy 类型推断
2. 移除 `pyproject.toml` 中对 ORM 模块的 `ignore_errors = true`
3. 所有 ORM 模型的 `__init__` 参数类型正确推断

## 迁移步骤

### Phase 1: 分析现有模型

对每个 ORM 模型类执行：

1. **列出所有字段**及其 `init` 参数（默认 `True`）
2. **标记必填字段**（无默认值）和**可选字段**（有默认值）
3. **评估重排顺序**：必填字段在前，可选字段在后

受影响的模型：

- `WatchlistItemDB`
- `SignalHistoryDB`
- `TTradingRecordDB`
- `PositionDB`

### Phase 2: 修改模型定义

对每个模型：

```python
# 修改前
class WatchlistItemDB(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

# 修改后（支持 MappedAsDataclass）
class WatchlistItemDB(Base):
    __tablename__ = "watchlist_items"

    # 必填字段（无默认值）放前面
    symbol: Mapped[str] = mapped_column(String(32))

    # 有默认值的字段放后面（或使用 init=False）
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), init=False)
```

### Phase 3: 更新 Base 类

```python
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

class Base(MappedAsDataclass, DeclarativeBase):
    """SQLAlchemy 2.0 类型安全基类"""
    pass
```

### Phase 4: 更新构造函数调用

检查并更新所有创建 ORM 实例的代码，确保：

1. 参数顺序符合 dataclass 规则
2. 必填参数必须提供
3. `init=False` 的字段不能在构造函数中传递

### Phase 5: 移除 mypy 忽略规则

从 `pyproject.toml` 移除：

```toml
# 移除这个 override
[[tool.mypy.overrides]]
module = [
    "deepsearch.infrastructure.persistence.models.*",
    "deepsearch.infrastructure.persistence.watchlist_repository",
]
ignore_errors = true
```

## 验证

1. `uv run mypy deepsearch` 无 ORM 相关错误
2. `uv run pytest` 所有测试通过
3. 应用正常运行

## 参考资料

- [SQLAlchemy 2.0 Dataclasses](https://docs.sqlalchemy.org/en/20/orm/dataclasses.html)
- [SQLAlchemy 2.0 Mapped Column](https://docs.sqlalchemy.org/en/20/orm/mapping_api.html)
- [Context7 SQLAlchemy 文档](https://github.com/context7/sqlalchemy_en_20_orm)

## 预计工作量

- 分析和规划：1-2 小时
- 模型修改：2-3 小时
- 测试和验证：1-2 小时
- **总计：4-7 小时**

## 优先级

**中等** - 功能正常，但类型安全性受限。建议在下一个主要开发周期完成。
