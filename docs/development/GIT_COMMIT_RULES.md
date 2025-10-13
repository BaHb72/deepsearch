# DeepSearch 仓库 Git 提交规则总则

## 1. 文档目的
- 为全体协作者提供统一的 Git 版本管理准则，保证任意一次提交都能完整复现 DeepSearch 系统能力。
- 明确必须纳入版本控制的关键资产与禁止提交的临时文件，防止仓库被冗余或敏感数据污染。
- 将提交规范、质量校验与审批流程固化，减少回滚成本。

## 2. 适用范围
- 适用于 DeepSearch 仓库的所有分支、所有开发角色（后端、前端、基础设施、文档、测试）。
- 适用于本地提交、CI 自动提交（如有）与热修复分支；Fork 仓库贡献者亦需遵守。

## 3. 基础提交规范
- **提交粒度**：一次提交仅解决一个清晰的问题或功能点，禁止将不相关改动混入同一 commit。
- **提交信息**：严格遵循 Conventional Commits（例如 `feat(engine): 支持策略回放`），必要时在正文中说明背景、影响面、回滚策略。
- **变更覆盖**：提交前确认新增文件不会遗漏系统运行必需的依赖、脚本、迁移文件，保证部署即刻可用。
- **质量校验**：在 Windows PowerShell 环境中执行 `uv sync --all-extras`（首次）后，至少运行以下命令：
  - `uv run pre-commit run --all-files`
  - `uv run pytest --quick` 或 `python scripts/run_all_tests.py --quick`
  - 与改动相关的专用检查（如 `ruff check`、`mypy deepsearch`、`npm run lint`）。
- **敏感信息**：真实密钥、账号、密码一律不得提交，仅提交 `settings.{env}.yaml.example` 等模板并写明占位符。

## 4. 文件收录策略（必须纳入 Git）
- **核心代码**：`deepsearch/` 下的所有源码、工厂与配置模型；新增模块需同步相关 `__init__.py` 与依赖注入配置。
- **测试资产**：`tests/` 下的单元、集成、API 测试及基准数据（体积可控、脱敏）。
- **文档资料**：`docs/`、`README.md`、`CHANGELOG.md`、`CLAUDE.md` 等开发、运维、架构文档；新增规范需建立索引入口。
- **构建与自动化**：`.github/` 工作流、`scripts/`、`tools/`、`third_party/` 中的可复现脚本；若依赖外部工具需写明使用说明。
- **配置模板**：`.env.example`、`settings.{env}.yaml.example`、`deepsearch/config/settings.template.yaml`、`pyproject.toml`、`uv.lock`、`requirements*.txt` 等确保环境可还原的文件。
- **前端资源**：`deepsearch/webui/frontend` 的源码、配置与公共资源（`src/`、`public/`、`package.json` 等）。
- **运维支持**：`docs/operations/`、`docs/solutions/` 等面向部署或故障排查的指南；新增运维脚本需附自检步骤。
- **占位文件**：需要保留空目录时使用 `.gitkeep` 或仓库既有的占位文件，严禁提交空目录。

## 5. 文件排除策略（禁止提交）
- **运行时环境**：`.venv/`、`venv/`、`runtime/interpreters/`、`__pycache__/`、`*.py[cod]`、`*.so`、`*.dll`。
- **构建产物**：`build/`、`dist/`、`wheels/`、`download/`、`deepsearch/webui/frontend/dist/`、`deepsearch/webui/static/assets/`。
- **缓存与覆盖率**：`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.benchmarks/`、`htmlcov/`、`.coverage`、`coverage.xml`。
- **日志与诊断**：`*.log`、`logs/`、`diagnostic_*.json`、`reports/test_reports/`、`runs/`、`tmp/`、`worker/`、`tgw.log`。
- **数据文件**：`data/` 及子目录（除 `.gitkeep`）、`deepsearch/data/`、`deepsearch/infrastructure/data/**/*.duckdb.wal`、`monitoring_data/`，禁止提交真实业务数据或隐私数据。
- **本地配置**：`settings.local.yaml`、`settings.*.local.yaml`、`deepsearch/config/settings.local.yaml`、`deepsearch/config/database_connections.*.yaml`、`*.env`、`cloudflare-deploy/*.toml`。
- **前端临时文件**：`deepsearch/webui/frontend/node_modules/`、`package-lock.json`、`.vite/`、`src/.trash/`、`.husky/`、`.backup` 类目录。
- **垃圾与临时脚本**：`.trash/`（任意层级）、`*_old.py`、`temp_*.txt`、`cleanup_*.py`、`2025-*.txt`、`*-think.txt` 等临时或实验文件。
- **操作系统与编辑器**：`.DS_Store`、`Thumbs.db`、`.idea/`、`.vscode/`、`*.swp`、`*~`。
- **敏感配置**：`config/.crypto_key`、`.crypto_key`、任何真实密钥或证书；如需示例，使用占位符并放入 `.example` 文件。

## 6. 条件性提交与特别约定
- **依赖锁文件**：修改 Python 依赖时同步更新 `uv.lock`；前端依赖变更需更新 `package.json`，并确保 `packageManager` 字段标明所用 npm 版本，锁文件仍遵循仓库禁用 `package-lock.json` 的约定。
- **迁移脚本**：新增数据库或数据结构迁移脚本必须纳入版本库，并在文档中标记执行顺序。
- **示例与数据**：示例数据需确保脱敏且体积小于 1 MB，可放置在 `examples/` 或 `tests/fixtures/`；真实行情或交易数据不得入库。
- **QMT 脚本**：`deepsearch/infrastructure/providers/datafeed/qmt/scripts/` 下脚本需保持 GBK 编码，提交前人工校验编码声明 `# encoding:gbk` 是否存在。
- **临时需求**：遇到需保留的调试输出或一次性脚本，请移入 `docs/journals/`（记录策略）或 `scripts/experiments/` 并说明用途，禁止散落在根目录。
- **忽略规则更新**：若现有 `.gitignore` 无法覆盖的新增类型，应在提交中同步更新并说明原因。

## 7. 提交前检查清单
1. 执行 `git status` 确认未包含禁止提交的文件或目录。
2. 检查新增文件是否都位于允许路径、是否包含必要的 `__init__.py`、配置模板及测试。
3. 运行预设的质量检查（见第 3 节），确保无 lint、格式、类型错误。
4. 若涉及接口或配置变更，补充 `docs/api/` 或 `settings.{env}.yaml.example`，并运行 `python tools/generate_api_documentation.py`。
5. 对有风险的删除操作保留回滚方案（例如在 PR 描述中附上备份路径或迁移说明）。
6. 更新 PR 描述：概述变更、列出测试结果、关联 issue 或工单。

## 8. 例外处理与审批
- 需要短暂提交日志或调试文件时，必须先征得仓库管理员批准，并在提交后立即清理。
- 对于临时大文件（>5 MB）或无法脱敏的数据，建议使用内部制品库或对象存储，并在文档中提供下载指引。
- 若自动化工具生成的文件必须提交（例如 schema 快照），需在提交信息中解释生成方式及验证步骤。

## 9. 违例处理
- 被发现提交了禁止文件或敏感信息时，需立即创建修复提交清理历史，并在团队通报防止扩散。
- 屡次违反规则者需要重新审阅本指南并补充培训；严重情况将限制其写入权限。

## 10. 维护与更新
- 本文由仓库管理员维护，重大调整需在 `CHANGELOG.md` 中记录，并在团队会议中同步。
- 如遇特殊场景或新模块，请在 PR 中讨论并更新本指南后方可执行。

