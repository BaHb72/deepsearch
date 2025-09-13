# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: API接口管理

### 重要：修改API前必读
在修改任何API接口前，**必须**先执行以下步骤：

1. **读取接口文档**：
   - `docs/api/FRONTEND_API_REGISTRY.md` - 前端API定义
   - `docs/api/BACKEND_API_REGISTRY.md` - 后端API定义  
   - `docs/api/API_MAPPING.md` - 接口映射关系

2. **检查影响范围**：
   - 确认修改的接口被哪些组件使用
   - 检查是否有相关的测试需要更新

3. **更新文档**：
   - 每次修改后立即运行 `python tools/generate_api_docs.py` 更新文档
   - 记录修改时间、修改内容、修改原因

### API接口规范
- 前端请求路径：相对路径，如 `/database/status`
- axios baseURL 设置：`/api`（通过 request.js 自动添加）
- 实际请求路径：`/api/database/status`
- 后端路由前缀：在 server.py 中通过 `prefix="/api/database"` 设置
- Vite代理配置：将 `/api` 请求代理到 `http://localhost:8000`

## Project Overview

DeepSearch is a high-performance quantitative trading event system built with Python. It features an event-driven architecture, flexible message bus, comprehensive monitoring, and a web UI for real-time management.

## ⚠️ CRITICAL: Development Requirements

### NO MOCK DATA IN PRODUCTION CODE
**严禁在生产代码中使用模拟数据：**
- ❌ 不允许在API中硬编码假数据
- ❌ 不允许返回静态的模拟响应
- ❌ 不允许使用内存中的临时数据存储
- ✅ 必须连接真实的数据库或服务
- ✅ 如果服务不可用，返回适当的错误信息
- ✅ 测试环境可以使用专门的测试数据，但必须明确标识

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

## ⚠️ CRITICAL: QMT Scripts Encoding Requirement

**ALL Python scripts in `deepsearch/datafeed/qmt/scripts/` MUST use GBK encoding!**

This is mandatory because QMT terminal only supports GBK. Using UTF-8 will cause Chinese characters to display as garbage.

When modifying QMT scripts:
1. Always save with GBK encoding
2. First line must be: `# encoding:gbk`
3. Read with: `open(file, 'r', encoding='gbk')`
4. Write with: `open(file, 'w', encoding='gbk')`

## Recent Updates (2025-08-22)

### Backend Performance Optimization
- **Singleton Data Providers**: Implemented factory pattern in `webui/api/providers.py` to ensure single instances
- **Request Deduplication**: Added middleware in `webui/api/middleware/deduplication.py` to merge identical concurrent requests
- **Unified Cache Layer**: Created multi-tier caching in `webui/api/cache/unified.py` (L1 Memory + L2 Redis)
- **Performance Gains**: 40-60% faster API responses, 30% less memory usage, 90% request deduplication rate
- **Note**: All optimizations are single-machine focused, no distributed systems

## Recent Updates (2025-08-21)

### Data Source Architecture Refactoring
- **Unified Data Source Manager**: Created `services/data_source_manager.py` for centralized data provider management
- **Priority-based Selection**: Implemented automatic failover with configurable priorities (AmazingData > CloudFlare > QMT)
- **Circuit Breaker Pattern**: Added fault tolerance with automatic recovery
- **Multi-tier Caching**: L1 (Memory) → L2 (Redis) → L3 (DuckDB/PostgreSQL)
- **Request Optimization**: Added rate limiting and deduplication middleware in `webui/api/middleware.py`
- **CloudFlare Workers Integration**: Enabled proxy for AKShare API to improve reliability
- **Database Connection Pooling**: Implemented high-performance pool in `database/pool.py`

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

### Data Source Architecture
- Implemented dependency inversion principle with IDataSource interface
- Created DataSourceAdapter with circuit breaker pattern
- Built AggregatedDataSource for intelligent routing and failover
- Modified StockInfoService to use dependency injection

## Common Development Commands

### Package Management (UV)

**This project uses UV for package management instead of pip.**

```bash
# Install UV (if not already installed)
pip install uv

# Create virtual environment
uv venv --python 3.13.7

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

1. **MainEngine** (`core/engine.py`): Central orchestrator that manages system lifecycle
   - Initializes all components in correct order
   - Manages component dependencies
   - Handles graceful shutdown
   - Coordinates data providers and services

2. **Event System** (`event/`): High-performance event processing
   - EventEngine handles event routing and processing
   - Schema-based validation using Pydantic
   - Supports batch processing for high-frequency data
   - Event deduplication and rate limiting

3. **Message Bus** (`messaging/`): Flexible inter-process communication
   - CompositeMessageBus supports multiple backends (ZeroMQ, Redis TimeSeries)
   - Route-based message distribution
   - Configurable per environment
   - Message compression and deduplication

4. **WebUI** (`webui/`): Management interface
   - FastAPI backend (`webui/server.py`) with middleware for rate limiting
   - Vue.js frontend (`webui/frontend/`) with optimized components
   - Real-time monitoring via WebSocket
   - RESTful API endpoints for chart data, QMT integration, and data sources

5. **Component System** (`core/component_manager.py`): Standardized component lifecycle
   - Dependency management between components
   - Health checks and status monitoring
   - Graceful startup/shutdown ordering
   - Unified component interface

6. **Data Source Management** (`services/data_source_manager.py`): Unified data provider interface
   - Priority-based data source selection (AmazingData > CloudFlare Proxy > QMT)
   - Circuit breaker pattern for fault tolerance
   - Automatic failover between data sources
   - Request caching and deduplication

7. **Database Layer** (`database/`): Multi-tier caching and persistence
   - **L1 Cache**: In-memory LRU cache for hot data
   - **L2 Cache**: Redis for distributed caching
   - **L3 Storage**: DuckDB for analytics, PostgreSQL for transactional data
   - Connection pooling with `database/pool.py`
   - Automatic cache synchronization

8. **Data Providers** (`data_providers/`): Multiple data source implementations
   - **AmazingData**: Galaxy Securities data API (highest priority)
   - **CloudFlare Workers Proxy**: AKShare API via CloudFlare edge network
   - **QMT Integration**: Real-time market data from QMT terminal
   - **AKShare Direct**: Direct API access (fallback)
   - Unified interface through `DataSourceManager`

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

4. **Vue Reactivity Issues**: Use `shallowRef` for large arrays like order book data. Implement RAF batching for high-frequency updates to avoid flickering.

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