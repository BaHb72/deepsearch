# mypy 静态检查报告（2025-10-08）

## 检查命令与总体结果
- 执行命令：`mypy`
- 输出摘要：共检测到 549 个错误，分布在 173 个文件中（主扫描目标 11 个文件）。【b58674†L1-L85】

## 主要问题分类与根源分析

### 1. 运行环境缺失导致的导入错误
- 现有 `pyproject.toml` 已声明大量核心依赖（如 `fastapi`、`loguru`、`pydantic`、`numpy`、`pandas`、`backtrader` 等），但当前运行环境未安装这些包或对应类型存根，触发 `import-not-found` 与 `import-untyped` 错误。【6d7bfb†L17-L66】【9e241e†L1-L44】【41fe3c†L1-L42】
- 第一性原理分析：静态类型检查需要在编译期解析模块接口；依赖包缺失时，类型信息无法构建，导致连锁报错。根本矛盾是“工具期望的依赖状态”与“当前环境的实际状态”不一致。
- 解决建议：在隔离虚拟环境中补齐运行时依赖与类型存根包（如 `types-redis`、`types-requests`、`pandas-stubs` 已在依赖列表中但未安装），先使用 `uv pip sync pyproject.toml` 或 `uv pip install <package>` 等命令快速拉取声明依赖，确保 mypy 可以解析所有外部接口。

### 2. 内部模块结构不完整
- 多个错误指向仓库内缺失的模块（例如 `deepsearch.data.types`、`deepsearch.qmt.models.tick`、`domain.interfaces.*`）。检查目录可知 `deepsearch/data` 仅包含 `__init__.py` 与 `cleaner.py`，并无 `types.py` 等声明文件。【d1ee8c†L1-L2】【514fea†L57-L116】
- 第一性原理分析：类型检查依赖于稳定的模块边界；当核心模型文件缺失或未纳入当前仓库时，mypy 会认为接口不存在并拒绝类型推断。问题根源在于代码仓库与设计契约不一致，提示需回溯构建流程确认哪些子包未同步。
- 解决建议：补充缺失模块、为跨项目依赖建立本地占位存根，或调整导入路径（如使用特性注入）以符合 mypy 的查找逻辑；相关行动已确认按建议执行。

### 3. 接口设计与类型定义不匹配
- `DataResponse` 将 `metadata` 限定为 `Dict[str, object]`，但调用端普遍传入 `dict[str, str]`，触发 `dict` 不变性带来的 `arg-type` 报错。【514fea†L30-L90】【16514b†L120-L160】
- 第一性原理分析：泛型容器的协变/逆变特性必须与实际用途一致。此处的根因是接口对外“声明可接受任意对象”，但实现阶段默认向内写入字符串字典，违反了类型系统的预期。
- 解决建议：统一接口契约（例如将 `metadata` 类型改为 `Mapping[str, object]` 或提供结构化模型），并在调用端遵循同一抽象层次；方案已获确认并将实施。

### 4. 业务组件能力缺口
- Web API 多处调用 `data_manager.get_kline`、`provider.subscribe_kzz_snapshot` 等方法，但在管理器与 `AmazingDataExtended` 类中并未实现这些接口，导致 `attr-defined` 错误。【57bf8b†L31-L120】【9da542†L944-L1019】【c233f6†L1-L2】
- 第一性原理分析：这是“接口→实现”链路断裂的体现。接口层为了满足业务场景扩展了调用点，但底层数据提供者未同步增强，破坏了系统的抽象完整性。根本原因是需求演化缺乏逆向约束，导致 API 声明与核心组件功能脱节。
- 解决建议：补充缺失的方法实现或在接口层增加能力检查，确保编译期能感知真实可用的调用路径；团队已同意沿此方向推进。

### 5. 额外观察
- 大量 `By default the bodies of untyped functions are not checked` 提示说明当前 mypy 未启用 `--check-untyped-defs`，即便修复导入问题仍可能隐藏运行时缺陷。【9e241e†L25-L44】
- `pyproject.toml` 将 Python 版本锁定为 `3.13`，需确认运行环境版本是否一致，否则某些第三方包可能尚未提供兼容构建。【6d7bfb†L15-L38】

## 建议的下一步行动
1. 在项目规范的虚拟环境中安装 `pyproject.toml` 中列出的依赖与类型存根，确保 mypy 能解析外部接口。
2. 补全缺失的内部模块或提供临时类型占位，恢复仓库结构与文档契约的一致性。
3. 审视 `DataResponse` 等核心数据结构的类型设计，使其与调用方约定一致；必要时扩展或重构业务组件接口。
4. 在依赖补齐后再次运行 `mypy`，若仍有业务层类型冲突，再逐项定位并修复，实现从“环境问题”到“类型约束问题”的分层清理。
5. 针对“额外观察”中的第 5 点（启用 `--check-untyped-defs` 等增强检查），计划在完成前述步骤并稳定现有类型问题后再处理。

## 2025-10-09 错误分布与治理规划（327 项）

### 最新扫描摘要
- 执行命令：`uv run --no-sync mypy`（依赖补齐后在本地锁定虚拟环境内运行）。
- 输出摘要：共检测到 327 个错误，分布在 66 个文件中，数量较前次扫描下降 40.3%。
- 目录分布：
  - `deepsearch/webui`：114 项（34.9%），集中在中间件与 API 响应模型。
  - `deepsearch/infrastructure`：106 项（32.4%），以数据提供者、SQLAlchemy 封装和缓存客户端为主。
  - `deepsearch/backtest` 与 `deepsearch/indicators`：合计 67 项（20.5%），主要源于数值序列运算缺乏准确的 pandas 建模。
  - 其余目录（`core`、`utils`、`config` 等）：40 项（12.2%），多与上下文管理、配置对象和系统工具函数相关。

### 共性问题分类
| 分类 | 典型错误数* | 主要触发模块 | 根源分析 |
| --- | --- | --- | --- |
| 三方接口类型桩缺口 | ≈137 | `infrastructure.database`, `infrastructure.persistence`, `webui.api.cache`, `utils.network` | 当前自建桩未覆盖 SQLAlchemy `AsyncEngine.begin/dispose`、Requests `Session.request/mount`、Redis `setex/scan_iter` 等常用方法，导致 mypy 认为接口不存在。 |
| 数值序列类型建模 | ≈38 | `backtest.interfaces`, `indicators.simple`, `indicators.technical` | `NumericSeries` 与 pandas/NumPy 的占位桩仍缺少运算符与链式方法签名，推断结果退化为 `float`，进而引起算术与属性访问报错。 |
| 参数与调用契约不一致 | ≈89 | `webui.api.middleware`, `webui.api.endpoints`, `infrastructure.providers.akshare` | FastAPI 端点默认返回 `JSONResponse` 却声明为 `Response`、`Query` 关键字参数与签名不匹配、`CacheManager.get` 调用缺参数等，体现接口契约未与类型约束同步。 |
| 可选配置未做显式分支 | 28 | `core.components`, `utils.system.port_checker`, `config.settings` | 多处对象被声明为 `Config | None` 但直接访问属性，需在运行前聚合缺省策略或补充断言。 |
| 异步上下文与协程封装 | 27 | `infrastructure.database.optimized_pool`, `infrastructure.providers.akshare.worker_manager` | `asynccontextmanager` 使用方式、`async with` 上下文返回类型以及 `Coroutine` 标注未与实现对齐，导致 `__aenter__/__aexit__` 等协议校验失败。 |
| 返回值未与声明对齐 | 31 | `webui.api.middleware.rate_limit`, `infrastructure.providers.akshare.request_handler`, `core.components.analytics_components` | 函数签名声明返回具体类型却直接透传 `Any` 或协程，需通过显式模型、判空分支或封装帮助函数收敛返回值。 |

> *分类数量基于 2025-10-09 扫描结果的关键词统计，因同一错误可能同时满足多个条件，故合计会超过 327。

### 治理路径规划
1. **第一阶段（桩能力补齐）**：集中修订 `typings/` 目录，优先覆盖 SQLAlchemy `AsyncEngine`、Requests `Session`、Redis `Redis`、FastAPI 中 `Security` 等高频缺口，并同步调整 `NumericSeries` 的 pandas 算术与聚合接口，使工具能够理解主要依赖的 API 形态。
2. **第二阶段（接口契约收敛）**：对 WebUI 中间件与 Akshare 适配层逐一核对签名与返回值，必要时拆分响应模型或引入数据类，将 `JSONResponse`/`dict` 的动态结构显式化；同时补全 `CacheManager`、`DataSyncService` 等注入依赖的参数与返回类型。
3. **第三阶段（配置与异步语义强化）**：为声明为可选的配置对象统一提供 `ensure_xxx()` 帮助函数或在初始化阶段落地默认值；审查所有 `async with`、`asynccontextmanager` 的实现，确保返回类型遵循 `AsyncIterator[T]`，并在协程中显式 `await` 引擎与会话构造。
4. **收尾阶段（增量检查策略）**：在上述问题收敛后，逐步开启 `--check-untyped-defs` 与更严格的 mypy 配置，结合模块级 `TypedDict`/`Protocol` 精细化模型，防止新增告警回潮。

### 近期优先事项（未来 2~3 次迭代）
- 产出 `typings/sqlalchemy/engine.pyi`、`typings/requests/sessions.pyi`、`typings/redis/asyncio/client.pyi` 等针对缺失方法的桩更新，保障数据库与缓存相关模块可进行下一步类型重构。
- 调整 `NumericSeries` 定义为 `pandas.Series` 的细化子类或通过 `Protocol` 描述常用运算符，解除回测与指标模块的批量算术告警。
- 逐个排查 `webui/api/middleware` 返回值，补齐 `Response`/`JSONResponse` 类型之间的桥接辅助函数，避免 `Any` 扩散。
- 在 `core/components` 与 `utils/system` 中为配置对象新增空值校验或工厂方法，减少 `Optional` 属性访问导致的告警。

以上规划为后续批量治理的路线基线，具体执行时应在每个阶段引入增量 mypy 扫描验证，确保指标持续下降且未引入新的类型回归。

