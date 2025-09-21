# DeepSearch 代理协作指南

## 关键提醒
- 仓库输出遵循“使用中文回显”，请保持答复与文档语言一致。
- 基础设施、数据库与存储模块已统一迁移至 `deepsearch/infrastructure/` 体系，引用旧路径（如 `data_providers/`、`storage/`）时必须同步修正。
- 统一使用 Python 3.13 + UV 工具链，首次进入项目请运行 `uv sync --all-extras` 安装依赖。
- 后端与前端分开启动：`uv run python -m deepsearch run` 负责事件引擎，`uv run python -m deepsearch run --mode webui` 仅启用可视化，前端在 `deepsearch/webui/frontend` 目录执行 `npm run dev`。
- `.trash/` 用于临时回收，是垃圾目录，不要提交或依赖其中文件；需要保留内容请移至正式路径。

## API 管理要求
- 所有 API 说明集中在 `docs/api/`，修改接口前需同步查阅：
  - `docs/api/README.md`（总览）、`docs/api/FRONTEND_API_REGISTRY.md`（前端调用）、`docs/api/BACKEND_API_REGISTRY.md`（后端实现）、`docs/api/API_MAPPING.md`（前后端映射）、`docs/api/datasource_api.md`（数据源接口说明）。
- 调整接口后必须运行 `python tools/generate_api_documentation.py` 生成新文档，并在变更说明中记录时间、内容与原因。
- 统一路由规范：前端使用 `/api` 作为 axios `baseURL`，后端在 FastAPI 中以 `prefix="/api/<domain>"` 注册路径，实际访问形如 `/api/database/status`，Vite 代理保持一致。

## 架构与实现约束
- DeepSearch 仅支持单机部署，严禁引入分布式缓存、消息队列、微服务、容器调度等方案；可以采用单实例 Redis、PostgreSQL/DuckDB、ZeroMQ、本地文件缓存及线程/进程池优化。
- `deepsearch/infrastructure/` 目录已按缓存、消息、监控、持久化、数据提供方等子模块拆分，新增组件时请遵守现有分层与工厂/观察者等模式实现。

## 配置文件与敏感信息
- 任何真实密钥都不得入库，仅提交 `settings.{env}.yaml.example` 等示例文件；本地配置从模板复制后自行填写。
- 修改配置结构时同步更新示例与模板，并以占位符描述敏感字段（如 `your_database_password`）。
- 提交前执行 `git grep -i "password\|secret\|token" -- ':(exclude)*.example'` 自检，确保未泄露真实凭据。

## QMT 脚本编码
- `deepsearch/infrastructure/providers/datafeed/qmt/scripts/` 下全部脚本必须使用 GBK 编码。
- 保存脚本时首行声明 `# encoding:gbk`，读写文件统一使用 `encoding='gbk'`，否则 QMT 终端将出现乱码。

## 数据源策略
- 当前仅允许接入 AmazingData API，禁止使用 TGW 及其他未批准的数据源（两者底层库不同且接口不兼容）。
- AmazingData 相关实现位于 `infrastructure/providers/implementations/amazingdata/`，扩展能力需遵守既有优先级与故障切换策略。

## 开发流程与质量控制
- 安装与环境：`uv venv --python 3.13`、`uv sync --all-extras`，新增依赖使用 `uv add`，升级依赖使用 `uv lock --update`。
- 常用运行命令：`uv run python -m deepsearch run`、`uv run python -m deepsearch run --mode engine`、`uv run python -m deepsearch run --mode webui`、`uv run python -m deepsearch check-ports`。
- 代码规范：遵循 PEP 8 四空格缩进，业务类名以领域结尾（如 `OrderEngine`），配置模型使用 `Settings` 后缀；提交前依次运行 `ruff check`、`black`、`isort`，类型敏感模块执行 `mypy deepsearch`，安全相关代码运行 `bandit -r deepsearch`。
- 测试策略：单元测试放在 `tests/unit/`，命名遵循 `test_<module>_<case>`；集成与 API 测试在 `tests/integration/` 与 `tests/api/`；建议先通过失败→修复流程并保持覆盖率 ≥85%，必要时更新 `docs/testing` 记录。
- 推荐命令：`python scripts/run_all_tests.py`（或加 `--quick`），`pytest tests/unit -n auto`，`pytest --cov=deepsearch --cov-report=html`，生成覆盖率后人工抽查 `htmlcov/index.html`。
- 测试中若需替换依赖，优先使用 pytest fixtures + `unittest.mock`；示例参见 `CLAUDE.md` 中的 mock 用法。

## 文档导航
- `docs/README.md` 汇总了架构、API、开发与运维文档入口，可作为快速索引。
- 架构说明：参考 `docs/architecture/SYSTEM_ARCHITECTURE.md`、`docs/ARCHITECTURE_OPTIMIZATION_STRATEGY.md`。
- 开发最佳实践与调试：见 `docs/development/BEST_PRACTICES.md`、`docs/development/DEBUG_FEATURES.md`、`docs/development/CODE_REVIEW.md`。
- API 方案与数据源分析：查阅 `docs/api-guides/` 与 `docs/api/` 下各专题文档。
- 运维与资源：位于 `docs/operations/`，常见问题解法在 `docs/solutions/`。

## 提交流程
- 按照 Conventional Commits 书写消息（如 `feat: ...`、`fix: ...`、`docs: ...`），PR 描述需概述变更、列出测试结果并关联对应 issue。
- 涉及前端或可视化效果的调整请附带截图，配置改动需同步更新相关文档（例如 `docs/operations/`）。
- 提交前确保 pre-commit 钩子通过并根据需要执行 `uv run pytest`、`uv run black` 等检查。
