# DeepSearch

DeepSearch 是一套面向 AmazingData 数据源的**单机量化交易事件系统**，聚焦实时行情处理、策略编排与诊断工具链。

工程采用**模块化六边形架构**，后端以 Python 3.13 + FastAPI 构建，前端提供 React 管理界面，并集成依赖注入、多级缓存、可观测性与自动化测试能力。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         表示层 (Presentation)                        │
│    WebUI (FastAPI + React)  │  CLI (click)                          │
├─────────────────────────────────────────────────────────────────────┤
│                         应用层 (Application)                         │
│    RealTimeMarketDataService  │  AggregationEngine  │  Services     │
├─────────────────────────────────────────────────────────────────────┤
│                         领域层 (Domain)                              │
│    Entities  │  Calculators  │  DataProxy  │  BoardUniverse         │
├─────────────────────────────────────────────────────────────────────┤
│                         核心引擎 (Core)                              │
│    MainEngine (Facade)  │  DI Container  │  Component Lifecycle     │
├─────────────────────────────────────────────────────────────────────┤
│                         基础设施 (Infrastructure)                    │
│    Providers  │  Cache (L1+L2+L3)  │  Persistence  │  Messaging     │
└─────────────────────────────────────────────────────────────────────┘
```

## 仓库结构 (Monorepo)

```text
deepsearch/
├── packages/                      # 核心包（可复用模块）
│   └── core/                      # 核心业务逻辑
│       ├── core/                  # 核心引擎
│       │   ├── runtime/           # MainEngine, DI容器, 生命周期
│       │   ├── components/        # 组件实现
│       │   └── managers/          # 组件/进程管理
│       ├── application/           # 应用层服务
│       │   └── market_data/       # 实时行情服务
│       ├── domain/                # 领域模型与计算器
│       ├── infrastructure/        # 基础设施
│       │   ├── providers/         # 数据源适配器 (AmazingData等)
│       │   ├── cache/             # 多级缓存
│       │   ├── persistence/       # 数据持久化
│       │   └── messaging/         # 消息总线
│       ├── strategies/            # 策略框架
│       ├── ports/                 # 端口定义（六边形架构）
│       ├── observability/         # 日志、指标、追踪
│       ├── config/                # 配置模型
│       └── cli/                   # 命令行接口
│
├── apps/                          # 应用入口
│   ├── api/                       # FastAPI 后端
│   │   ├── api/                   # API 路由
│   │   ├── dependencies.py        # 依赖注入
│   │   └── server.py              # 服务器入口
│   └── web/                       # React 前端
│       ├── src/                   # 源代码
│       ├── package.json           # 前端依赖
│       └── vite.config.ts         # Vite 配置
│
├── tests/                         # 测试套件
│   ├── unit/                      # 单元测试
│   ├── integration/               # 集成测试
│   └── api/                       # API 测试
├── scripts/                       # 开发脚本
├── tools/                         # 诊断工具
├── docker/                        # Docker 配置
├── docs/                          # 文档
├── pyproject.toml                 # 项目配置
└── docker-compose.yml             # 容器编排
```

## 核心能力

### 依赖注入容器

基于 [dependency-injector](https://github.com/ets-labs/python-dependency-injector) 库实现声明式依赖管理：

- **自动依赖解析**：组件间依赖自动注入
- **拓扑排序初始化**：按依赖顺序启动组件
- **加载时间监控**：记录每个组件的启动耗时
- **Wiring 自动扫描**：支持 `@inject` 装饰器

### 组件系统

| 层级 | 组件 | 职责 |
|------|------|------|
| 基础设施 | EventEngine | 异步事件调度 |
| 基础设施 | MessageBus | RabbitMQ 消息总线 |
| 基础设施 | Database | PostgreSQL + SQLAlchemy 2.0 |
| 基础设施 | Cache | 多级缓存 (内存 + Redis) |
| 业务 | Analytics | DuckDB 数据分析 |
| 业务 | Gateway | 数据源网关 |
| 业务 | QMTGateway | QMT 实时行情 |
| 业务 | Backtest | 回测引擎 |
| 界面 | WebUI | FastAPI + React |

### 数据源与缓存

- 默认由 **AmazingData** 驱动实时流水
- 多级缓存：L1 内存 → L2 Redis → L3 数据库
- 支持降级：AmazingData → AkShare → Cloudflare

### 可观测性

- 结构化日志 (Loguru)
- 组件健康检查
- 性能统计与告警

## 技术栈

| 层次 | 技术选型 |
|------|----------|
| **后端框架** | Python 3.13, FastAPI, Pydantic v2 |
| **依赖注入** | dependency-injector 4.48+ |
| **数据库** | PostgreSQL + SQLAlchemy 2.0 |
| **缓存** | Redis + 内存 TTLCache |
| **消息队列** | RabbitMQ |
| **分布式计算** | Dask |
| **前端框架** | React 19 + TypeScript |
| **UI 组件** | Ant Design Pro |
| **状态管理** | Zustand |
| **图表** | ECharts |
| **依赖管理** | uv |
| **类型检查** | mypy + Pyright |

## 快速开始

### 环境准备

```powershell
# 克隆仓库
git clone https://github.com/BaHb/deepsearch.git
cd deepsearch

# 安装 uv
python -m pip install --upgrade uv

# 创建虚拟环境
uv venv --python (Get-Content .python-version)
. .\.venv\Scripts\Activate.ps1

# 安装依赖
uv sync --all-extras --dev

# 安装前端依赖
cd apps/web && npm install && cd ../..
```

### 启动服务

```powershell
# 开发模式（推荐）
uv run deepsearch run dev --log-level DEBUG

# 生产模式
uv run deepsearch run

# 仅 WebUI
uv run deepsearch run dev --mode webui

# 仅引擎
uv run deepsearch run dev --mode engine
```

### 前端服务

```powershell
cd apps/web
npm run dev
```

### 访问入口

- WebUI：<http://localhost:3000>
- API 文档：<http://localhost:8000/docs>

## 配置管理

配置文件位于 `packages/core/config/settings.<env>.yaml`：

```yaml
# 示例配置
performance:
  queue_size: 10000
  max_workers: 32
  batch_size: 100

database:
  host: localhost
  port: 5432
  name: deepsearch
```

## 开发指南

### 代码质量

```powershell
# 一键检查
uv run python scripts/run_all_tests.py

# 单元测试
uv run pytest tests/unit -n auto

# 类型检查
uv run mypy packages/core

# 代码格式
uv run ruff check packages/core apps
```

### 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat: 新功能`
- `fix: 修复`
- `docs: 文档`
- `refactor: 重构`

## 架构约束

⚠️ **重要限制**：

1. **单机部署**：禁止引入分布式架构
2. **依赖注入**：新组件必须通过 DI 容器注册
3. **分层架构**：遵守六边形架构，禁止跨层调用
4. **AmazingData 优先**：默认数据源，配置可降级

## 文档导航

| 文档 | 说明 |
|------|------|
| `docs/architecture/` | 架构设计 |
| `docs/development/` | 开发指南 |
| `docs/datasources/` | 数据源接入 |
| `docs/operations/` | 运维手册 |

## 许可证

MIT License

## 联系方式

- GitHub Issues: <https://github.com/BaHb/deepsearch/issues>
