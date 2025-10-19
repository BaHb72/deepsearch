# DeepSearch

DeepSearch 是一套面向 AmazingData 数据源的单机量化交易事件系统，聚焦实时行情处理、策略编排与诊断工具链。工程采用模块化设计，后端以 Python 3.13 + FastAPI 构建，前端提供 React 管理界面，并集成多级缓存、可观测性与自动化测试能力。

## 仓库结构

```text
deepsearch/
├── deepsearch/                    # 核心源代码
│   ├── cli/                       # CLI 命令与运行入口
│   ├── config/                    # Pydantic 设置模型与 settings.<env>.yaml
│   ├── core/                      # 事件引擎、组件生命周期与运行时
│   ├── infrastructure/            # 缓存、消息、监控、持久化、数据提供方等
│   │   ├── cache/                 # 本地/Redis/DuckDB 缓存实现
│   │   ├── messaging/             # 消息总线与总线工厂
│   │   ├── monitoring/            # 监控与指标采集
│   │   ├── providers/             # 数据源统一抽象（AmazingData 等）
│   │   └── persistence/           # PostgreSQL、DuckDB 管理
│   ├── messaging/                 # 高层消息与事件桥接
│   ├── observability/             # 日志、追踪、告警
│   ├── webui/                     # FastAPI 后端与 React 前端
│   │   ├── api/                   # WebUI API 分层
│   │   ├── runner.py              # WebUI 启动器
│   │   └── frontend/              # React + Ant Design 管理界面
│   ├── workers/                   # Worker 管理与进程隔离
│   └── utils/                     # 通用工具与系统脚手架
├── docs/                          # 文档中心（详见 docs/README.md）
├── scripts/                       # 常用脚本（run_all_tests.py 等）
├── tests/                         # 测试套件（unit/integration/api）
├── third_party/                   # AmazingData 离线包等第三方资源
├── tools/                         # 开发与诊断辅助工具
└── uv.lock / pyproject.toml       # UV 与依赖配置
```

> `.trash/` 为临时回收区，不应提交或依赖其中内容。

## 核心能力

- **事件驱动引擎**：`core/runtime/async_runner.py` 提供高并发事件循环，组件拓扑由 `core/components` 与 `core/managers` 管理，支持批量调度与健康检查。
- **数据源与缓存**：仅支持 AmazingData，统一由 `infrastructure/providers` 注册；多级缓存覆盖内存、Redis、DuckDB，保证断线重连与速率控制。
- **可观测性**：`observability` 集成结构化日志、性能统计与告警通道，配合 `tools/` 下的诊断脚本快速定位问题。
- **Web 管理界面**：FastAPI 暴露 `/api/*` 接口，React 前端（Ant Design Pro + Zustand + ECharts）提供监控、策略与事件视图。
- **自动化运维**：CLI 提供 `run`、`check-ports`、`check-amazingdata` 等命令，脚本目录覆盖一键测试与 Git Hooks 安装。

## 架构约束

- DeepSearch 仅支持单机部署，禁止引入分布式缓存、消息队列、微服务或容器调度等方案。
- 基础设施组件统一归类于 `deepsearch/infrastructure/`，新增能力需遵守现有分层与工厂/观察者等模式实现。
- AmazingData 为默认优先数据源，核心实现位于 `deepsearch/infrastructure/providers/implementations/amazingdata/`；按配置可降级至 AkShare、Cloudflare Worker 或 QMT 等实现，遵循现有优先级与故障切换策略。Mock 仅用于测试稳定性及回归验证，不向终端用户提供数据。
- QMT 历史脚本位于 `deepsearch/infrastructure/providers/datafeed/qmt/scripts/`，需使用 GBK 编码并在首行声明 `# encoding:gbk`。

## 环境准备

> ⚠️ 默认在 **Windows PowerShell/CMD** 中运行 `uv`、`python`、`npm` 等命令；WSL 仅允许只读操作（如查看文件、grep），所有依赖安装必须在 Windows 环境执行。

1. 克隆仓库并进入目录：
   ```powershell
   git clone https://github.com/BaHb/deepsearch.git
   cd deepsearch
   ```
2. 安装 [uv](https://github.com/astral-sh/uv)（尚未安装时）：
   ```powershell
   python -m pip install --upgrade uv
   ```
3. 创建或复用仓库虚拟环境（版本见 `.python-version`）：
   ```powershell
   uv venv --python (Get-Content .python-version)
   . .\.venv\Scripts\Activate.ps1
   ```
4. 安装后端依赖（含所有 extra）：
   ```powershell
   uv sync --all-extras
   ```
   > 📌 **提示**：默认 `uv sync` 仅安装基础依赖。若需运行单元测试或调试 CLI，请追加 `--dev` 以同步 `pytest`、`coverage` 等开发套件：
   > ```powershell
   > uv sync --all-extras --dev
   > ```
   > 若执行测试仍提示缺少 `pandas`、`pydantic`、`fastapi`、`psutil` 等模块，请确认是否遗漏以上同步步骤。仓库已在 `pyproject.toml` 中声明这些依赖，缺失通常意味着当前虚拟环境尚未安装。 
5. 安装 WebUI 依赖：
   ```powershell
   cd deepsearch/webui/frontend
   npm install
   cd ..\..\..
   ```
   > 📎 **注意**：仓库约定不提交 `package-lock.json`。在 Windows 终端执行 `npm install` 后，请确认未将该文件纳入提交；如已生成，请运行
   > `Remove-Item package-lock.json` 或手动删除。
6. AmazingData 运行在隔离解释器：按 `docs/datasources/amazingdata/` 指南配置 `runtime/interpreters/py39/`，并在 `settings.<env>.yaml` 中填写 `amazingdata.connection.python_interpreter_path`。

## 启动方式

### 后端引擎与 API

```powershell
# 生产配置（默认）
uv run deepsearch run

# 开发模式 + 前端另行启动
uv run deepsearch run dev --mode full --no-frontend

# 仅运行事件引擎
uv run deepsearch run dev --mode engine

# 仅运行 WebUI 后端（FastAPI）
uv run deepsearch run dev --mode webui

# 端口自检
uv run deepsearch check-ports

# AmazingData 连通性自检
uv run deepsearch check-amazingdata dev
```

### WebUI 前端

```powershell
cd deepsearch/webui/frontend
npm run dev          # 默认端口 3000
# 或构建生产包
npm run build
```

访问入口：
- WebUI（开发环境）：http://localhost:3000
- API 文档（FastAPI）：http://localhost:8000/docs

## 配置管理

- 所有环境配置存放于 `deepsearch/config/settings.<env>.yaml`，仓库提供 `.example` 与 `settings.template.yaml` 作为模板。
- 非必要情况下不要依赖环境变量覆盖配置，确需调整时务必同步更新示例文件并保持结构一致。
- 涉及敏感字段使用占位符（如 `your_database_password`），真实凭据仅保存在本地未纳入 Git。
- 提交前执行 `git grep -i "password\|secret\|token" -- ':(exclude)*.example'` 自检，确保未泄露真实凭据。

## API 管理

- API 文档集中于 `docs/api/`：
  - `docs/api/README.md` 总览
  - `docs/api/FRONTEND_API_REGISTRY.md` 前端调用列表
  - `docs/api/BACKEND_API_REGISTRY.md` 后端实现
  - `docs/api/API_MAPPING.md` 前后端映射
  - `docs/api/datasource_api.md` 数据源接口说明
- 调整接口后必须运行 `uv run python tools/generate_api_documentation.py` 更新 `docs/api/`，并在变更说明中记录时间、内容与原因。
- 前端统一使用 `/api` 作为 axios `baseURL`，后端在 FastAPI 中以 `prefix="/api/<domain>"` 注册路由。

## 开发流程与质量

- 遵循 PEP 8 四空格缩进，业务类名以领域结尾（如 `OrderEngine`），配置模型使用 `Settings` 后缀。
- 提交前依次运行 `ruff check`、`black`、`isort`，类型敏感模块执行 `mypy deepsearch`，安全相关代码运行 `bandit -r deepsearch`。
- 测试遵循失败→修复流程，保持整体覆盖率 ≥85%，必要时更新 `docs/testing` 记录；优先通过 pytest fixtures 与 `unittest.mock` 注入依赖。

```powershell
# 一键运行所有检查
uv run python scripts/run_all_tests.py

# 单元/集成测试
uv run pytest tests/unit -n auto
uv run pytest tests/integration

# 质量工具
uv run ruff check deepsearch tests
uv run black --check deepsearch tests
uv run isort --check-only deepsearch tests
uv run mypy deepsearch
uv run bandit -r deepsearch
```

测试覆盖率报告位于 `htmlcov/`，可通过 `htmlcov/index.html` 查看。

## 技术栈

- **后端**：Python 3.13、FastAPI、Pydantic、SQLAlchemy、AsyncIO、Redis、DuckDB、PostgreSQL、ZeroMQ、Twisted。
- **前端**：React 19、Ant Design Pro、Zustand、ECharts、Vite、TypeScript。
- **数据源**：AmazingData 官方 SDK（`third_party/amazingdata`）为默认优先；根据配置可切换至 AkShare、Cloudflare Worker 或 QMT 等数据源。Mock 仅用于测试稳定性与验证，不可向用户提供实时数据。

## 文档导航

- `docs/README.md`：文档索引与快速导航
- 架构说明：`docs/architecture/SYSTEM_ARCHITECTURE.md`、`docs/architecture/DEEPSEARCH_ARCH_IMPROVEMENT_PLAN.md`
- 开发与调试：`docs/development/BEST_PRACTICES.md`、`docs/development/DEBUG_FEATURES.md`、`docs/development/CODE_REVIEW.md`
- 数据源资料：`docs/datasources/`（含 AmazingData 快速开始与隔离方案）
- 运维与常见问题：`docs/operations/` 及 `docs/operations/runbooks/`
- 历史归档： `docs/archive/datasources/amazingdata/AmazingData_API.md` 记录 AmazingData 官方 API 摘要版本，供参考使用

## 贡献指南

- 提交信息遵循 Conventional Commits（如 `feat: ...`、`fix: ...`、`docs: ...`）。
- 涉及前端或可视化调整请在变更说明中附带效果描述；配置改动需同步更新示例文件与相关文档。
- PR 描述应概述变更、列出测试结果并关联对应 issue；提交前确保 pre-commit 钩子与所需检查全部通过。

## 许可证

本项目使用 MIT License。

## 联系方式

- GitHub Issues: https://github.com/BaHb/deepsearch/issues
- 团队邮箱（示例）：team@deepsearch.local


