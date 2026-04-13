# DeepSearch

DeepSearch 是一个高性能量化交易事件系统，采用 Monorepo v2 架构，专注于实时行情处理、策略编排与智能诊断。

系统基于六边形架构设计，后端使用 Python 3.14 + FastAPI 构建，前端采用 React 19，集成依赖注入、多级缓存、Dask 混合计算与完整的可观测性能力。

## 核心特性

- **Monorepo v2 架构**：清晰的模块划分，核心逻辑与应用入口分离
- **六边形架构**：领域驱动设计，数据源通过 Ports 隔离，易于扩展
- **依赖注入容器**：基于 dependency-injector 的声明式 DI，拓扑排序初始化
- **多级缓存系统**：L1（TTLCache 内存）→ L2（Redis）→ L3（PostgreSQL）自动降级
- **Dask 混合计算**：Windows Workers + Docker Scheduler，支持异构环境
- **100% 类型检查**：mypy + Pyright 全项目合规（32 个错误已修复）
- **现代技术栈**：SQLAlchemy 2.0 MappedAsDataclass、React 19、Zustand 状态管理

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户界面层                                   │
│    React 19 WebUI (3000)  │  FastAPI Backend (8000)                 │
├─────────────────────────────────────────────────────────────────────┤
│                         应用服务层                                   │
│    UnifiedDataFeed  │  RealTimeMarketDataService  │  Services       │
├─────────────────────────────────────────────────────────────────────┤
│                         核心引擎层                                   │
│    MainEngine (Facade)  │  DI Container  │  LifecycleCoordinator    │
├─────────────────────────────────────────────────────────────────────┤
│                         基础设施层                                   │
│    Data Providers  │  多级缓存  │  Persistence  │  Dask 计算层      │
└─────────────────────────────────────────────────────────────────────┘
```

## Monorepo 目录结构

```text
deepsearch/
├── packages/core/              # 核心业务逻辑（可复用模块）
│   ├── core/                   # 核心引擎
│   │   ├── runtime/            # MainEngine、DI 容器、生命周期管理
│   │   ├── components/         # 组件实现（Database、Cache、EventEngine）
│   │   ├── managers/           # 组件管理器、进程管理器
│   │   └── utils/              # 容器工具、IPC 工具
│   ├── compute/                # 分布式计算层
│   │   ├── actors/             # Dask Actors（AmazingData、MiniQMT、AkShare）
│   │   ├── clients/            # RPC 客户端
│   │   └── dask_worker_manager.py  # Windows Worker 状态机管理
│   ├── infrastructure/         # 基础设施层
│   │   ├── providers/          # 数据源适配器（六边形架构 Ports）
│   │   │   └── implementations/ # AmazingData、MiniQMT、AkShare 实现
│   │   ├── cache/              # 多级缓存（L1+L2+L3）
│   │   ├── persistence/        # PostgreSQL、DuckDB 持久化
│   │   └── messaging/          # 消息总线（inmem）
│   ├── config/                 # 配置系统
│   │   ├── models/             # Pydantic 配置模型
│   │   └── *.yaml              # 分层配置文件（infrastructure、settings）
│   ├── application/            # 应用服务层
│   │   └── services/           # 统一数据访问、聚合引擎
│   ├── event/                  # 事件引擎（重写版）
│   │   └── engine/             # 线程池调度器 + 状态机
│   ├── domain/                 # 领域层
│   ├── observability/          # 可观测性（日志、指标）
│   └── cli/                    # 命令行接口
│
├── apps/                       # 应用入口
│   ├── api/                    # FastAPI 后端
│   │   ├── api/                # API 路由（endpoints/）
│   │   ├── server.py           # FastAPI 应用入口
│   │   └── runner.py           # WebUI 运行器
│   └── web/                    # React 19 前端
│       ├── src/                # 源代码
│       ├── package.json        # 前端依赖
│       └── vite.config.ts      # Vite 配置
│
├── tests/                      # 测试套件
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   └── api/                    # API 测试
├── docs/                       # 文档
│   ├── architecture/           # 架构设计
│   ├── development/            # 开发指南
│   ├── datasources/            # 数据源接入
│   └── operations/             # 运维手册
├── scripts/                    # 开发脚本
├── tools/                      # 诊断工具
├── docker/                     # Docker 配置
├── typings/                    # 第三方库类型存根
├── pyproject.toml              # 项目配置
└── docker-compose.yml          # 容器编排
```

## 核心技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **运行时** | Python 3.14 | >=3.14,<3.15 | MappedAsDataclass 支持 |
| **包管理** | UV | 官方推荐 | 快速依赖解析 |
| **后端框架** | FastAPI + Uvicorn | 0.135.3+ / 0.44.0+ | 异步 ASGI 服务器 |
| **ORM** | SQLAlchemy 2.0 | 2.0.49+ | MappedAsDataclass 迁移完成 |
| **异步数据库** | asyncpg | 0.31.0+ | PostgreSQL 异步驱动 |
| **缓存** | Redis + TTLCache | 7.2.0+ | 三级缓存（L1+L2+L3） |
| **分布式计算** | Dask | 2026.3.0+ | 混合 Windows/Docker 架构 |
| **依赖注入** | dependency-injector | 4.48.3+ | 声明式 DI |
| **前端框架** | React | 19.2.3 | 最新版 |
| **UI 组件** | Ant Design Pro | 2.8.10 | 企业级 UI 组件 |
| **状态管理** | Zustand | 5.0.8 | 轻量级替代 Redux |
| **图表库** | ECharts + Lightweight Charts | 5.6 + 5.1 | 实时 K 线图表 |
| **类型检查** | mypy + Pyright | 1.0+ | 100% 合规（32 错误已修复） |
| **数据源** | AmazingData | 1.1.0 | 默认数据源（主链路） |
|  | TGW (MiniQMT) | 1.0.8.6 | 本地 SDK 回退路径 |
|  | AkShare | 1.18.54+ | 备用数据源（代理模式） |

> MiniQMT 的 `xtquant` 最新公开包 `250516.1.1` 仍声明 `Python <3.14`，因此不再作为 Python 3.14 主环境的直接依赖安装；相关适配器保留运行时可选导入，待上游发布兼容版本后再恢复锁定。

## 核心能力

### 依赖注入容器

基于 [dependency-injector](https://github.com/ets-labs/python-dependency-injector) 实现声明式依赖管理：

- **自动依赖解析**：组件间依赖自动注入
- **拓扑排序初始化**：按依赖顺序启动组件（Infrastructure → Business → WebUI）
- **加载时间监控**：记录每个组件的启动耗时
- **Wiring 自动扫描**：支持 `@inject` 装饰器

### 多级缓存系统

```
L1: TTLCache（内存）    ← 毫秒级，最快
  ↓ 未命中
L2: Redis（共享缓存）    ← 秒级，跨进程
  ↓ 未命中
L3: PostgreSQL（持久化） ← 分钟级，持久化
```

特性：

- 自动降级策略：L1 → L2 → L3
- 缓存预热：启动时加载热点数据
- 透明访问：业务层无感知缓存层级

### Dask 混合架构

```
┌──────────────────────┐
│ Dask Scheduler       │  ← Docker 容器（Linux，端口 8786）
│ (localhost:8786)     │
└────────┬─────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼────┐ ┌─▼──────────┐
│Windows │ │Linux Workers│
│Workers │ │(Docker容器) │
│(自动启动)│ │(通用计算)   │
└────────┘ └────────────┘
    ↑
    └─ 支持 AmazingData/MiniQMT SDK
    └─ 资源标签：WIN=1.0
```

**特性**：

- **Docker Scheduler**：Linux 容器运行 Dask Scheduler（端口 8786）
- **Windows Workers**：自动启动，支持 Windows-only SDK（AmazingData、MiniQMT）
- **Linux Workers**：Docker 容器，运行通用计算任务
- **任务路由**：`@requires_windows` 装饰器自动分配任务到 Windows Worker

### 数据源优先级

```
AmazingData（默认）   ← 主数据源（当前配置默认）
   ↓ 失败/熔断
MiniQMT（首个回退）   ← 本地 SDK（低延迟）
   ↓ 失败/熔断
AkShare（第二回退）   ← Cloudflare Worker 代理（避免封禁）
```

> 运行时口径（2026-02-17）：`data_sources.default=amazingdata`，`fallback_order=miniqmt -> amazingdata -> akshare`（由 `packages/core/config/data_sources.yaml` 合并后生效）。

**统一接口**：

- `DataProvider` 协议（六边形架构 Ports）
- 自动断路器：失败阈值自动熔断 + 自动恢复
- 降级链：配置 `fallback_order`，透明切换

### EventEngine 重写

**旧版问题**：

- 基于条件变量 + 全局状态 → 关闭不可靠
- 时序依赖 → 竞态条件
- 手动线程管理 → 生命周期复杂

**新版设计**：

- **线程模型**：Dispatcher + Scheduler 双线程（ThreadPoolExecutor）
- **异步支持**：`async_flag=True` → 自动使用线程池执行异步处理器
- **批处理**：支持批量事件处理，减少上下文切换
- **状态机**：严格生命周期管理（STOPPED → RUNNING → STOPPING → STOPPED）

## 快速开始

### 环境准备

```powershell
# 1. 克隆仓库
git clone https://github.com/BaHb/deepsearch.git
cd deepsearch

# 2. 安装 UV 包管理器
python -m pip install --upgrade uv

# 3. 创建虚拟环境（Python 3.14）
uv venv --python (Get-Content .python-version)
.\.venv\Scripts\Activate.ps1

# 4. 放置本地 SDK wheel（不进入 Git）
# 以下文件需从内部制品来源放入 packages/：
#   - packages/AmazingData-1.1.0-cp314-none-any.whl
#   - packages/tgw-1.0.8.6-py3-none-any.whl
python scripts/check_local_wheels.py

# 5. 安装依赖（包含开发工具）
uv sync --all-extras --dev

# 6. 配置环境
# 复制配置模板
cp packages/core/config/settings.template.yaml packages/core/config/settings.dev.yaml
# 根据环境修改以下配置文件：
#   - settings.dev.yaml: 数据源优先级、日志级别、性能参数
#   - infrastructure.dev.yaml: 数据库连接、Redis 地址、Dask Scheduler 地址

# 7. 启动依赖服务（Docker Compose）
docker-compose up -d
# 启动：PostgreSQL（端口 5432）、Redis（端口 6379）、Dask Scheduler（端口 8786）

# 8. 安装前端依赖
cd apps/web && npm install && cd ../..
```

### 启动系统

```powershell
# 开发模式（推荐）
uv run deepsearch run dev --log-level DEBUG

# 生产模式
uv run deepsearch run prod

# 仅启动引擎（不启动 WebUI）
uv run deepsearch run dev --mode engine

# 仅启动 WebUI（跳过部分引擎组件）
uv run deepsearch run dev --mode webui

# 仅启动后端 API（需手动启动前端）
uv run deepsearch run dev --no-frontend
```

### 前端服务（单独启动）

```powershell
cd apps/web
npm run dev
```

### 访问入口

- **WebUI**：<http://localhost:3000>
- **API 文档**：<http://localhost:8000/docs> （Swagger UI）
- **Dask Dashboard**：<http://localhost:8787>

## 配置管理

### 配置文件层次

```
packages/core/config/
├── infrastructure.<env>.yaml   # 基础设施（DB、Redis、Dask、消息总线）
├── settings.<env>.yaml         # 应用配置（数据源、日志、性能参数）
├── database_connections.<env>.yaml  # 数据库连接字符串
├── market_data.<env>.yaml      # 行情配置
└── data_sources.yaml           # 数据源定义（共享）
```

**环境支持**：

- `dev` - 开发环境（WSL Redis、本地 PostgreSQL、DEBUG 日志）
- `test` - 测试环境（内存数据库、Mock 数据源）
- `prod` - 生产环境（加密密码、INFO 日志、严格安全策略）

### 示例配置

**settings.dev.yaml** - 数据源优先级：

```yaml
data_sources:
  default: amazingdata
  fallback_order:
    - miniqmt      # 首个回退（快速、稳定、本地 SDK）
    - amazingdata  # 次级回退（功能全面、专业服务）
    - akshare      # 最终回退（代理模式，避免封禁）

  providers:
    miniqmt:
      priority: 1
      timeout: 10.0
    amazingdata:
      priority: 2
      config:
        implementation_mode: optimized  # 使用 Dask 插件（废弃 process 模式）
    akshare:
      priority: 3
      config:
        mode: proxy  # Cloudflare Worker 代理
        proxy_url: https://your-worker.workers.dev
```

**infrastructure.dev.yaml** - Dask 混合架构：

```yaml
dask:
  scheduler_address: "localhost:8786"
  windows_workers:
    enabled: true
    auto_start: true
    num_workers: 2
    resources:
      WIN: 1.0  # Windows 资源标签（必须为浮点数，兼容 Dask 2024.1.0+）
  task_routing:
    windows_tasks:
      - amazingdata_*
      - miniqmt_*
      - akshare_*
```

## 开发指南

### 代码质量检查

```powershell
# 一键检查（推荐，自动使用 APP__ENV=test）
uv run python scripts/run_all_tests.py --quick

# 完整本地检查（默认跳过 external/manual 集成测试）
uv run python scripts/run_all_tests.py

# 本地 SDK wheel 校验
uv run python scripts/check_local_wheels.py

# 单元测试（串行，默认可执行）
$env:APP__ENV = "test"
uv run pytest tests/unit --no-cov -q -m "not slow"

# 单元测试（并行，需要安装 pytest-xdist）
uv run pytest tests/unit -n auto

# 默认集成测试（只运行非外部、非手动用例）
uv run pytest tests/integration --no-cov -q -m "integration and not external and not manual" --timeout=300

# API 测试
uv run pytest tests/api --no-cov -q

# 真实 SDK / 外部集成测试（需要本机 SDK、凭据或外部服务）
uv run pytest tests/integration --no-cov -q -m "external" --include-external --include-manual --timeout=1200

# run_all_tests.py 也支持显式开启外部或手动集成测试
uv run python scripts/run_all_tests.py --include-external
uv run python scripts/run_all_tests.py --include-manual
uv run python scripts/run_all_tests.py --suite-timeout 1200

# 类型检查（100% 合规）
uv run mypy packages/core

# 代码格式检查
uv run ruff check packages/core apps

# 代码格式化
uv run black packages/core apps

# 前端检查
cd apps/web
npx eslint . --ext .js,.jsx,.ts,.tsx
npm test -- --runInBand
npm run build:react
cd ../..
```

> Vite 构建如仍出现大 chunk 警告，应首先确认超大 chunk 是否为明确命名的 vendor chunk
>（如 `react-vendor`、`antd-vendor`、`charts-vendor`），不要通过提高阈值掩盖匿名业务 chunk 问题。

### 本地 SDK wheel 管理

`packages/AmazingData-1.1.0-cp314-none-any.whl` 与
`packages/tgw-1.0.8.6-py3-none-any.whl` 是本地 SDK 依赖文件，只由 `pyproject.toml`
的 `uv.sources` 引用，不再进入 Git 索引。干净克隆后需先从内部制品来源放置这两个文件，
再执行依赖安装。

```powershell
python scripts/check_local_wheels.py
uv sync --all-extras --dev
uv run python scripts/check_local_wheels.py
```

已推送历史中的大文件属于遗留风险；当前策略不重写 Git 历史、不启用 Git LFS，后续如需彻底清理需单独安排历史改写或制品化迁移。

### 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)，使用中文：

```
feat: 新增 MiniQMT 数据源适配器
fix: 修复 Dask Worker 资源属性兼容性问题
refactor: 重构 EventEngine 为线程池模式
docs: 更新 README 反映 Monorepo v2 架构
test: 添加 AmazingData Provider 单元测试
perf: 优化多级缓存命中率
chore: 升级 SQLAlchemy 至 2.0.44
```

**重要规范**（CLAUDE.md）：

- 提交信息使用中文
- **不添加** `Co-Authored-By: Claude` 署名
- **禁止**在代码和文档中使用 emoji 表情符号
- 禁止生产代码中的 Mock 数据

## 架构约束

### 强制约束

1. **单机部署**：禁止分布式架构（Dask 仅用于环境隔离，非分布式计算）
2. **依赖注入**：新组件必须通过 DI 容器注册（`packages/core/core/utils/container.py`）
3. **分层架构**：严格遵守六边形架构，禁止跨层调用
4. **数据源策略**：默认 `AmazingData`，回退顺序以 `data_sources.fallback_order` 为准（当前：`miniqmt -> amazingdata -> akshare`）
5. **第一性原理**：优先重构而非补丁（见 CLAUDE.md 方法论）

### 代码规范

- **类型检查**：100% mypy 合规（已完成，32 个错误已修复）
- **配置管理**：所有配置从 YAML 文件加载（Pydantic 验证）
- **包管理**：使用 UV（禁用 pip、poetry）
- **安全性**：避免 SQL 注入、XSS、命令注入等 OWASP Top 10 漏洞

## 近期重构变化

从旧版到 Monorepo v2 的关键升级：

| 变化项 | 旧版 | Monorepo v2（当前） |
|--------|------|---------------------|
| **默认数据源** | AmazingData 优先 | AmazingData 默认（回退顺序见 `data_sources.yaml`） |
| **Python 版本** | 3.12 | 3.14 |
| **SQLAlchemy** | 1.4 | 2.0 (MappedAsDataclass) |
| **React 版本** | 18.x | 19.2.3 |
| **消息总线** | ZeroMQ | inmem（内存总线） |
| **AmazingData 模式** | process 模式 | optimized 模式（Dask 插件） |
| **EventEngine** | 条件变量 + 全局状态 | 线程池 + 状态机 |
| **目录结构** | `domain/data_proxy/adapters/` | `infrastructure/providers/implementations/` |
| **类型检查** | 部分合规 | 100% mypy 合规 |
| **Dask 资源** | `WIN: 1` (int) | `WIN: 1.0` (float，兼容 2024.1.0+) |

**相关提交**：

- `e97a9f9` - Monorepo v2 完整架构迁移
- `d22d868` - SQLAlchemy 2.0 MappedAsDataclass 迁移
- `3bc3f62` - Dask Worker 资源属性兼容性修复
- `4c986df` - mypy 全项目类型检查合规（32 错误修复）

## 文档导航

| 文档 | 说明 |
|------|------|
| `docs/overview/system_architecture_latest_2026-02-17.md` | 面向非技术读者的最新架构现状与风险说明（建议先读） |
| `docs/architecture/` | 架构设计文档 |
| `docs/development/` | 开发指南与规范 |
| `docs/datasources/` | 数据源接入文档（AmazingData、MiniQMT、AkShare） |
| `docs/operations/` | 运维手册 |
| `docs/operations/runbooks/akshare_worker_proxy_acceptance_checklist.md` | AkShare Cloudflare Worker 代理迁移验收清单 |
| `CLAUDE.md` | 项目规范与第一性原理方法论 |

## 许可证

MIT License

## 联系方式

- GitHub Issues: <https://github.com/BaHb/deepsearch/issues>
