# CLAUDE.md

**最后更新时间**: 2025-09-20 (UTC+8)

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

⚠️ **重要提示**: 项目已完成基础架构重构，所有数据提供者、数据库和存储相关代码已迁移到`infrastructure/`目录下。请使用新的路径结构。

## 📚 目录

- [⚠️ CRITICAL: API接口管理](#️-critical-api接口管理)
- [Project Overview](#project-overview)
- [⚠️ CRITICAL: Development Requirements](#️-critical-development-requirements)
- [⚠️ CRITICAL: Architecture Requirements](#️-critical-architecture-requirements)
- [⚠️ CRITICAL: QMT Scripts Encoding](#️-critical-qmt-scripts-encoding-requirement)
- [Recent Updates](#recent-updates-2025-08-22)
- [Common Development Commands](#common-development-commands)
- [Architecture Overview](#architecture-overview)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Testing Strategy](#testing-strategy)
- [Monitoring and Observability](#monitoring-and-observability)

## ⚠️ CRITICAL: API接口管理

### 📌 所有API接口统一文档位置
**所有API接口都记录在以下统一文档中，每次修改API前后必须读取和更新这些文档：**
- 📄 **完整API列表**: `docs/api/README.md` - 包含所有前后端API接口的完整清单（265个端点）
- 📄 **前端API定义**: `docs/api/FRONTEND_API_REGISTRY.md` - 前端调用的API列表
- 📄 **后端API定义**: `docs/api/BACKEND_API_REGISTRY.md` - 后端提供的API路由
- 📄 **接口映射关系**: `docs/api/API_MAPPING.md` - 前后端API对应关系
- 📄 **数据源API**: `docs/api/datasource_api.md` - 数据源管理相关API文档

### 重要：修改API前必读
在修改任何API接口前，**必须**先执行以下步骤：

1. **读取接口文档**：
   - 先读取 `docs/api/README.md` 了解全局API结构
   - 查看相关的前端和后端API定义文档
   - 确认接口的映射关系

2. **检查影响范围**：
   - 确认修改的接口被哪些组件使用
   - 检查是否有相关的测试需要更新

3. **更新文档**：
   - 每次修改后立即运行 `python tools/generate_api_documentation.py` 更新文档
   - 记录修改时间、修改内容、修改原因
   - 确保 README.md 始终保持最新

### API文档生成工具使用说明
**自动化API文档生成器** (`tools/generate_api_documentation.py`)：
- **功能**：扫描前后端代码，自动生成完整的API文档
- **使用方法**：`python tools/generate_api_documentation.py`
- **输出位置**：`docs/api/` 目录
- **生成内容**：
  - 前端API调用列表 (`FRONTEND_API_REGISTRY.md`)
  - 后端API路由列表 (`BACKEND_API_REGISTRY.md`)
  - 前后端API映射关系 (`API_MAPPING.md`)
  - 按分类组织的API文档（市场数据、监控、系统管理等）
  - API统计信息和未匹配接口报告
- **使用时机**：
  - 添加新API接口后
  - 修改API路径或参数后
  - 定期检查前后端API一致性

### 架构优化文档
**系统架构优化策略** (`docs/ARCHITECTURE_OPTIMIZATION_STRATEGY.md`)：
- **功能**：规划架构目标形态与各阶段优化路线
- **更新时间**：2025-09-17
- **内容**：覆盖性能、可靠性、团队协作三大方向的行动清单

### AmazingData 集成资料
**综合方案** (`docs/AMAZINGDATA_COMPREHENSIVE_SOLUTION.md`)：
- **范围**：涵盖接入流程、隔离策略与关键 API 封装
- **同步**：结合 SDK 隔离设计与技术实现文档一并维护
- **建议**：落地变更时对照 `AMAZINGDATA_SDK_ISOLATION_*` 系列文档核查

### API接口规范
- 前端请求路径：相对路径，如 `/database/status`
- axios baseURL 设置：`/api`（通过 request.js 自动添加）
- 实际请求路径：`/api/database/status`
- 后端路由前缀：在 server.py 中通过 `prefix="/api/database"` 设置
- Vite代理配置：将 `/api` 请求代理到 `http://localhost:8000`

### 配置自检
- **模板**：`deepsearch/config/settings.template.yaml` 提供基础结构，修改后务必保留占位符
- **示例**：`.env.example` 列出所有环境变量，请复制为本地私有文件使用
- **校验**：运行 `python tools/validate_config.py` 自动检查必填项与敏感字段配置

## Project Overview

DeepSearch is a high-performance quantitative trading event system built with Python. It features an event-driven architecture, flexible message bus, comprehensive monitoring, and a web UI for real-time management.

## ⚠️ CRITICAL: Development Requirements

### NO MOCK DATA IN PRODUCTION CODE
**Mock数据仅限单元测试使用：**
- ❌ **生产代码严禁**硬编码假数据或Mock判断
- ❌ **API业务逻辑严禁**包含环境判断来返回不同数据
- ✅ 生产和开发环境必须连接真实数据源
- ✅ 如果主数据源不可用，必须降级到其他真实数据源
- ✅ 单元测试通过 pytest fixtures 和 mocking 实现，不需要环境配置

**环境配置：**
- 通过 `config.app.env` 判断当前环境
- `prod`: 生产环境 - 使用真实数据源
- `dev`: 开发环境 - 使用真实数据源进行开发

**真实数据源降级优先级：**
1. AmazingData（银河证券星耀数智）- **默认主数据源**
2. AkShare Proxy（CloudFlare代理）
3. AkShare Direct（直连）
4. QMT（量化终端）
5. 返回明确的错误信息（不返回Mock）

**⚠️ AmazingData API使用注意事项：**
- **实时数据获取**：必须使用订阅模式（onSnapshot系列），不存在 `get_market_realtime()` 方法
- **订阅接口**：通过 `SubscribeData` 对象和 `@register` 装饰器实现
- **测试连接**：可使用 `BaseData.get_code_info()` 或 `get_calendar()` 验证连接
- **代码格式**：需要市场前缀，如 `SH.600000`、`SZ.000001`

**⚠️ 重要说明：数据源API使用规范**
- **优先通过 AmazingData API 获取数据**：本项目默认使用银河证券的 AmazingData（星耀数智）接口，在可用范围内尽量通过该渠道完成需求
- **通过 AmazingData 调用**：业务仅通过 AmazingData SDK 暴露的 API 访问数据，底层 TGW 组件随 SDK 一同交付，无需手动接入
- **必要时使用 AkShare**：当 AmazingData 无法使用或无法提供特定数据时，可启用 AkShare（含 CloudFlare 代理）作为备选数据源，并在变更记录中说明原因
- **避免直接调用 TGW**：禁止在业务代码中直接 import TGW 或操作其底层接口，避免破坏 AmazingData SDK 的封装
- **实现位置**：AmazingData 实现代码位于 `infrastructure/providers/implementations/amazingdata/`

### 单元测试 Mock 实现规范

**使用 pytest fixtures 和 mocking：**
```python
# ✅ 正确的 Mock 实现（仅在测试文件中）
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_data_provider():
    """Fixture for mocking data provider in tests."""
    provider = Mock()
    provider.get_data.return_value = {"test": "data"}
    return provider

def test_with_mock_provider(mock_data_provider):
    # 使用 mock provider 进行测试
    result = mock_data_provider.get_data()
    assert result["test"] == "data"
```

**配置文件：**
- `settings.dev.yaml`: 开发环境配置
- `settings.prod.yaml`: 生产环境配置
- 测试环境不需要单独配置文件，使用 pytest fixtures

## ⚠️ CRITICAL: Architecture Requirements

### NO DISTRIBUTED SYSTEMS
**This project is designed as a SINGLE-MACHINE system. DO NOT implement or suggest:**
- ❌ Distributed caching (Redis Cluster, Memcached clusters)
- ❌ Distributed message queues (Kafka, RabbitMQ clusters)
- ❌ Microservices architecture
- ❌ Container orchestration (Kubernetes, Docker Swarm)
- ❌ Distributed databases (Cassandra, MongoDB clusters)
- ❌ Service mesh (Istio, Linkerd)

**Acceptable optimizations:**
- ✅ Single Redis instance for caching
- ✅ Single PostgreSQL/DuckDB for storage
- ✅ In-process message bus (ZeroMQ)
- ✅ Thread/Process pooling on single machine
- ✅ Single-node performance optimizations
- ✅ Local file caching
- ✅ Memory optimization techniques

## ⚠️ CRITICAL: Configuration File Management

### 配置文件安全规范
**永远不要提交包含真实密码的配置文件！**

1. **配置文件处理流程**：
   - 真实配置文件（如 `settings.dev.yaml`）必须加入 `.gitignore`
   - 每次修改配置结构后，创建脱敏的 example 文件（如 `settings.dev.yaml.example`）
   - 只提交 example 文件到Git仓库
   - example 文件中的密码字段使用占位符，如：`your_database_password`

2. **开发者使用流程**：
   - 克隆仓库后，复制 `settings.dev.yaml.example` 为 `settings.dev.yaml`
   - 在本地 `settings.dev.yaml` 中填写真实凭据
   - 本地配置文件永远不会被提交

3. **配置文件命名规范**：
   - 模板文件：`settings.template.yaml` - 包含所有配置项的完整模板
   - 示例文件：`settings.{env}.yaml.example` - 特定环境的示例配置
   - 实际文件：`settings.{env}.yaml` - 包含真实凭据的本地配置（不提交）

4. **敏感信息检查**：
   - 提交前必须执行：`git grep -i "password\|secret\|token" -- ':(exclude)*.example'`
   - 确保没有真实密码被跟踪

## ⚠️ CRITICAL: QMT Scripts Encoding Requirement

**ALL Python scripts in `deepsearch/infrastructure/providers/datafeed/qmt/scripts/` MUST use GBK encoding!**

This is mandatory because QMT terminal only supports GBK. Using UTF-8 will cause Chinese characters to display as garbage.

When modifying QMT scripts:
1. Always save with GBK encoding
2. First line must be: `# encoding:gbk`
3. Read with: `open(file, 'r', encoding='gbk')`
4. Write with: `open(file, 'w', encoding='gbk')`

## Recent Updates (2025-01-21)

### 配置文件安全管理 (Current)
- **实施内容**：
  - 从Git移除所有包含真实密码的配置文件
  - 创建脱敏的 example 配置文件供开发者参考
  - 更新 .gitignore 确保敏感配置不被跟踪
  - 修改代码从配置文件动态读取凭据，移除硬编码密码

### AmazingData SDK进程隔离架构 (已完成)
- **核心改进**：通过进程池隔离SDK，防止其崩溃影响主服务
- **技术文档**：`docs/DATASOURCE_PROCESS_POOL_ARCHITECTURE.md`
- **关键特性**：30秒进程复用窗口，智能故障恢复，健康检查API


## Recent Updates (2025-09-17)

### 基础架构重构完成
- **Infrastructure层引入**: 完成项目基础架构重构，所有基础设施代码迁移到`infrastructure/`目录
- **目录结构调整**:
  - `data_providers/` → `infrastructure/providers/`
  - `services/` → 功能分散到其他模块
  - `database/` → `infrastructure/persistence/`
  - `storage/` → `infrastructure/persistence/`
- **QMT路径更新**: QMT脚本路径从`datafeed/qmt/scripts/`更新为`infrastructure/providers/datafeed/qmt/scripts/`

### API文档自动化工具
- **新增工具**：`tools/generate_api_documentation.py` API文档自动生成器
- **功能特性**：自动扫描前后端代码，生成完整的API文档
- **文档位置**：生成的文档保存在 `docs/api/` 目录，主文档为`README.md`
- **使用建议**：每次修改API后立即运行，确保文档同步

## Recent Updates (2025-08-22)

### Backend Performance Optimization
- **Singleton Data Providers**: Implemented factory pattern in `webui/api/providers.py` to ensure single instances
- **Request Deduplication**: Added middleware in `webui/api/middleware/deduplication.py` to merge identical concurrent requests
- **Unified Cache Layer**: Created multi-tier caching in `webui/api/cache/unified.py` (L1 Memory + L2 Redis)
- **Performance Gains**: 40-60% faster API responses, 30% less memory usage, 90% request deduplication rate
- **Note**: All optimizations are single-machine focused, no distributed systems

## Recent Updates (2025-08-21)

### Data Source Architecture Refactoring
- **Unified Data Source Manager**: Created `infrastructure/providers/managers/data_source_manager.py` for centralized data provider management
- **Priority-based Selection**: Implemented automatic failover with configurable priorities (AmazingData > CloudFlare > QMT)
- **Circuit Breaker Pattern**: Added fault tolerance with automatic recovery
- **Multi-tier Caching**: L1 (Memory) → L2 (Redis) → L3 (DuckDB/PostgreSQL)
- **Request Optimization**: Added rate limiting and deduplication middleware in `webui/api/middleware/`
- **CloudFlare Workers Integration**: Enabled proxy for AKShare API to improve reliability
- **Database Connection Pooling**: Implemented high-performance pool in `infrastructure/persistence/pool.py`

### Infrastructure Layer Structure
完整的基础设施层包含以下模块：
- `infrastructure/cache/` - 缓存提供者实现
- `infrastructure/caching/` - 缓存策略和管理
- `infrastructure/data/` - 数据分析和处理
- `infrastructure/database/` - 数据库基础设施
- `infrastructure/di/` - 依赖注入容器
- `infrastructure/messaging/` - 消息传递基础设施
- `infrastructure/monitoring/` - 监控和可观测性
- `infrastructure/persistence/` - 持久化层（包含原storage和database功能）
- `infrastructure/providers/` - 数据提供者（原data_providers）
- `infrastructure/repositories/` - 仓储模式实现

## Recent Updates (2025-08-18)

### QMT Integration Fixes
- Fixed authentication message sending in `qmt_collector.py`
- Special handling for AUTH messages in `send_message()` function
- Consolidated multiple QMT scripts into production and test versions
- Ensured all QMT scripts use GBK encoding

## Recent Updates (2025-08-17)

### Professional Trading View Features
1. ✅ **ElCol Flickering Fixed**: Implemented RAF batching and stable keys for order book updates
2. ✅ **MA Lines Continuous Display**: Set showSymbol=false, disabled smooth curves for accurate financial data
3. ✅ **K-line Hollow/Solid Toggle**: Added isHollowCandle switch in toolbar with dynamic itemStyle
4. ✅ **Indicator Switching Fixed**: Proper chart disposal and container management
5. ✅ **Chip Distribution Mouse Tracking**: Real-time updates following crosshair with date-specific API
6. ✅ **Date Formatting**: Daily K-lines now show YYYY-MM-DD without time component
7. ✅ **Chip Y-axis Alignment**: Synchronized price ranges between main and chip charts
8. ✅ **Adjust Factors**: Implemented forward/backward/no adjustment with AkShare integration
9. ✅ **Volume & Sub-indicators**: Added volume bars, MACD, RSI, KDJ with chart synchronization

### Data Source Architecture (已重构到Infrastructure层)
- Implemented dependency inversion principle with IDataSource interface
- Created DataSourceAdapter with circuit breaker pattern (现位于 `infrastructure/providers/`)
- Built AggregatedDataSource for intelligent routing and failover
- Modified StockInfoService to use dependency injection
- **注意**: 原`data_providers/`、`services/`、`database/`、`storage/`目录已迁移到`infrastructure/`层

## Common Development Commands

### Package Management (UV)

**This project uses UV for package management instead of pip.**

```bash
# Install UV (if not already installed)
pip install uv

# Create virtual environment (requires Python >= 3.13)
uv venv --python 3.13

# Install all dependencies (including dev)
uv sync --all-extras

# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --group dev package-name

# Update dependencies
uv lock --update

# Show installed packages
uv pip list
```

### Running the System

**Note: Frontend and backend are now started separately by default.**

```bash
# Run backend system (without frontend)
uv run python -m deepsearch run

# Run backend with explicit no-frontend flag (same as above)
uv run python -m deepsearch run --no-frontend

# Start frontend separately (in another terminal)
cd deepsearch/webui/frontend
npm run dev

# Run with specific mode
uv run python -m deepsearch run --mode engine  # Engine only
uv run python -m deepsearch run --mode webui   # WebUI only

# Check port configuration
uv run python -m deepsearch check-ports
```

### Development Setup

```bash
# Run tests
uv run pytest
uv run pytest tests/test_event.py -v  # Run specific test

# Code formatting
uv run black deepsearch tests
uv run isort deepsearch tests

# Type checking
uv run mypy deepsearch
```

### Configuration Management

The system uses YAML configuration files located in `deepsearch/config/`:
- `settings.dev.yaml` - Development environment
- `settings.prod.yaml` - Production environment

Environment variables override config using double underscore notation:
```bash
LOG__LEVEL=DEBUG
WEBUI__BACKEND_PORT=8080
MESSAGE_BUS__BUSES__ZMQ__CONFIG__HOST=10.0.0.5
```

## Architecture Overview

### Core Components

1. **MainEngine** (`core/runtime/engine.py`): System lifecycle orchestrator
2. **Event System** (`event/`): High-performance event processing with Pydantic validation
3. **Message Bus** (`messaging/`): ZeroMQ-based inter-process communication
4. **WebUI** (`webui/`): FastAPI backend + React frontend
5. **Component System** (`core/managers/component_manager.py`): Standardized component lifecycle
6. **Data Source Management** (`infrastructure/providers/`): Unified interface with automatic failover (AmazingData > CloudFlare > AKShare > QMT)
7. **Database Layer** (`infrastructure/persistence/`): Multi-tier caching (Memory → Redis → DuckDB/PostgreSQL)
8. **Infrastructure Layer** (`infrastructure/`): 新增基础设施层，包含所有数据提供者、持久化、缓存等基础功能

### Key Design Patterns

- **Singleton Pattern**: Used for global managers (ConfigManager, ComponentManager)
- **Observer Pattern**: Event system for decoupled communication
- **Decorator Pattern**: Event handlers and monitoring decorators
- **Factory Pattern**: Message bus implementation selection

### Port Configuration

All service ports are managed through configuration files:
- WebUI Backend: 8000 (default)
- WebUI Frontend: 3000 (default)
- ZeroMQ Pub: 5556
- ZeroMQ Sub: 5557

Port conflicts are automatically detected on startup using `PortChecker` utility.

### Common Issues and Solutions

1. **Circular Import**: The codebase uses delayed imports in several places to avoid circular dependencies. When adding new imports, especially in `__init__.py` files, use delayed imports within functions when necessary.

2. **Windows Process Cleanup**: The system includes special handling for Windows process cleanup in `engine.py` and `runner.py` to ensure ports are properly released.

3. **Configuration Loading**: Use `from deepsearch.config import get_config` to get the global configuration object. The function returns a `Settings` instance with all configuration values.

4. **React Performance Issues**: Use `React.memo` and `useMemo` for optimization. Implement RAF batching for high-frequency updates to avoid flickering.

5. **ResizeObserver Warnings**: Always use debounce wrapper for resize handlers to avoid "loop completed with undelivered notifications" warnings.

6. **ECharts Performance**: Disable animation, use `showSymbol: false` for line series, and connect charts for synchronized zooming.

### Testing Strategy

- Unit tests for individual components in `tests/`
- Integration tests for message bus and event system
- Use pytest fixtures for common test setup
- Mock external dependencies (Redis, etc.) in tests

### Monitoring and Observability

- Loguru for structured logging with pretty formatting
- Custom `MonitorAPI` for system metrics
- WebSocket endpoints for real-time monitoring
- Health check endpoints at `/api/health`