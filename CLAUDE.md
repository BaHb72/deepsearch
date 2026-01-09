# CLAUDE.md

**最后更新时间**: 2026-01-09 (UTC+8)

Claude Code 指导文档。

## 项目概述

DeepSearch 是一个高性能量化交易系统，采用 Python Monorepo 架构。

## 目录结构

```text
deepsearch/
├── packages/
│   ├── core/                    # 核心库
│   │   ├── config/              # 配置文件 (settings.*.yaml)
│   │   ├── infrastructure/      # 基础设施层
│   │   │   ├── providers/       # 数据提供者 (AmazingData, MiniQMT, AkShare)
│   │   │   ├── persistence/     # 持久化层 (DuckDB, PostgreSQL)
│   │   │   ├── cache/           # 缓存
│   │   │   └── messaging/       # 消息传递
│   │   ├── core/                # 运行时、引擎
│   │   ├── domain/              # 领域模型
│   │   └── cli/                 # 命令行入口
│   └── data/                    # 数据处理包
├── apps/
│   ├── api/                     # FastAPI 后端
│   │   ├── api/endpoints/       # API 路由
│   │   ├── server.py            # 服务器主文件
│   │   └── runner.py            # 运行器
│   └── web/                     # React 前端 (Ant Design Pro)
├── tests/                       # 测试
├── tools/                       # 开发工具
└── docs/                        # 文档
```

## 开发命令

### 包管理 (UV)

```bash
uv sync --all-extras          # 安装所有依赖
uv add package-name           # 添加依赖
uv add --group dev pkg        # 添加开发依赖
```

### 运行系统

```bash
# 后端
uv run deepsearch run dev     # 开发环境
uv run deepsearch run prod    # 生产环境
uv run deepsearch run --mode webui  # 仅 WebUI

# 前端 (在 apps/web/ 目录)
npm run dev:react             # 开发模式
npm run build:react           # 生产构建
```

### 开发工具

```bash
uv run pytest                 # 运行测试
uv run mypy packages/core     # 类型检查
uv run ruff check .           # 代码检查
```

## 关键约束

### 1. 禁止生产代码中的 Mock 数据

- 生产代码严禁硬编码假数据
- 单元测试使用 pytest fixtures 实现 mocking

### 2. 计算架构

- **Dask** - 分布式计算框架
- **RabbitMQ** - 消息队列
- **Redis** - 缓存
- **PostgreSQL/DuckDB** - 持久化

### 3. 数据源优先级

1. **AmazingData** (银河证券) - 主数据源
2. **MiniQMT** (迅投) - 量化终端
3. **AkShare** - 开源数据

### 4. 凭据安全规范

**严禁硬编码密码！** 所有敏感信息必须从配置文件读取。

```python
# ❌ 错误 - 硬编码密码
USERNAME = "your_username"
PASSWORD = "your_password"
sdk.login(USERNAME, PASSWORD, HOST, PORT)

# ✅ 正确 - 从配置读取
from core.config import get_config
config = get_config()
ad = config.amazingdata.connection
sdk.login(ad.username, ad.password, ad.host, ad.port)
```

**不提交到 Git 的文件：**

- `settings.*.yaml` - 含数据库密码
- `data_sources.yaml` - 含数据源凭据
- `scripts/test_*.py` 等临时脚本

**脚本中读取凭据：**

```python
# 使用 scripts/utils/credentials.py
from scripts.utils import get_amazingdata_credentials
creds = get_amazingdata_credentials()
```

## 配置文件位置

```text
packages/core/config/
├── settings.dev.yaml          # 开发配置 (不提交)
├── settings.prod.yaml         # 生产配置 (不提交)
├── data_sources.yaml          # 数据源配置 (不提交)
├── settings.dev.yaml.example  # 开发模板
├── data_sources.yaml.example  # 数据源模板
└── settings.template.yaml     # 完整模板
```

## 端口配置

| 服务            | 默认端口 |
| --------------- | -------- |
| WebUI Backend   | 8000     |
| WebUI Frontend  | 3000     |

## Git 提交规范

- **不添加 Co-Authored-By** - 提交信息中不要添加 `Co-Authored-By: Claude` 署名
- 提交信息使用中文，格式遵循 Conventional Commits
- 示例: `fix(mypy): 修复类型检查错误`

## 常见问题

1. **循环导入**: 使用函数内延迟导入
2. **配置加载**: `from core.config import get_config`
3. **端口冲突**: `uv run deepsearch check-ports`
