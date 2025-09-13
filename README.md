# DeepSearch

高性能量化交易事件系统

## 项目结构

```
deepsearch/
├── deepsearch/                    # 源代码
│   ├── __init__.py
│   ├── __main__.py                # CLI 入口
│   ├── cli.py                     # 命令行界面
│   ├── config/                    # 配置管理
│   │   ├── models/                # 配置模型
│   │   ├── manager.py             # 配置管理器
│   │   ├── settings.py            # 配置设置
│   │   ├── settings.dev.yaml      # 开发环境配置
│   │   └── settings.prod.yaml     # 生产环境配置
│   ├── constants/                 # 常量定义
│   ├── core/                      # 核心组件
│   │   ├── engine.py              # 主引擎（事件循环、组件管理）
│   │   ├── component_manager.py   # 组件生命周期管理
│   │   ├── unified_components.py  # 统一组件接口
│   │   └── interfaces.py          # 接口定义
│   ├── database/                  # 数据库层
│   │   ├── pool.py                # 连接池管理
│   │   ├── duckdb_manager.py      # DuckDB分析数据库
│   │   └── cache_manager.py       # 多级缓存管理
│   ├── data_providers/            # 数据提供者
│   │   ├── amazingdata.py         # 银河证券数据API（最高优先级）
│   │   ├── amazingdata_types.py   # AmazingData类型定义
│   │   ├── cloudflare_proxy.py    # CloudFlare Workers代理
│   │   ├── akshare_direct.py      # AkShare直连（备用）
│   │   ├── qmt_provider.py        # QMT实时数据
│   │   ├── capabilities.py        # 数据源能力矩阵
│   │   └── interfaces.py          # 统一接口定义
│   ├── datafeed/                  # 数据源集成
│   │   ├── qmt/                   # QMT数据源
│   │   │   └── scripts/           # QMT脚本（GBK编码）
│   │   └── akshare/                # AkShare数据源
│   ├── event/                     # 事件系统
│   │   ├── engine.py              # 事件引擎
│   │   ├── handler.py             # 事件处理器
│   │   └── schemas.py             # 事件模式定义
│   ├── gateway/                   # 交易网关
│   ├── messaging/                 # 消息系统
│   │   ├── bus.py                 # 消息总线
│   │   ├── zeromq_bus.py          # ZeroMQ实现
│   │   └── redis_bus.py           # Redis实现
│   ├── monitoring/                # 监控系统
│   │   └── data_source_monitor.py # 数据源监控
│   ├── observability/             # 日志监控
│   │   ├── logger.py              # 结构化日志
│   │   └── structured_logger.py   # 日志增强
│   ├── services/                  # 业务服务
│   │   ├── data_source_manager.py # 数据源统一管理（新增）
│   │   ├── kline_cache.py         # K线数据缓存（优化）
│   │   ├── chart_service.py       # 图表数据服务
│   │   ├── market_service.py      # 市场数据服务
│   │   ├── adjust_service.py      # 复权因子服务
│   │   └── stock_info_service.py  # 股票信息服务
│   ├── storage/                   # 数据存储
│   ├── trader/                    # 交易逻辑
│   ├── utils/                     # 工具类
│   └── webui/                     # Web UI
│       ├── api/                   # FastAPI 后端
│       │   ├── middleware.py      # 请求中间件（新增）
│       │   ├── chart.py           # 图表API
│       │   ├── qmt.py             # QMT API
│       │   └── market.py          # 市场数据API
│       ├── frontend/              # Vue 前端
│       │   ├── src/
│       │   │   ├── components/    # 组件
│       │   │   ├── stores/        # 状态管理
│       │   │   └── utils/         # 工具函数
│       │   └── package.json
│       └── server.py              # 服务器入口
├── docs/                          # 文档
│   ├── AMAZINGDATA_*.md           # AmazingData相关文档
│   ├── QMT_*.md                   # QMT相关文档
│   ├── DATA_PROVIDER_DESIGN.md    # 数据提供者设计
│   └── STRATEGY_ARCHITECTURE.md   # 策略架构
├── tests/                         # 测试
├── installer/                     # 安装包
│   └── AmazingData-*.whl          # AmazingData SDK
├── pyproject.toml                 # UV项目配置
├── uv.lock                        # UV锁文件
├── CLAUDE.md                      # Claude Code指南
└── README.md                      # 本文件
```

## 核心功能

### 1. 专业交易视图 (Professional Trading View)

- **K线图表**: 支持空心/实心K线切换，日线时间格式优化
- **技术指标**: MA均线连续显示，MACD/RSI/KDJ等多种指标
- **筹码分布**: 实时跟随鼠标显示，价格轴对齐
- **复权处理**: 支持前复权、后复权、不复权三种模式
- **成交量**: 红绿柱状图，与主图联动缩放
- **盘口数据**: RAF批处理优化，避免频繁渲染

### 2. 数据源架构

- **统一数据源管理**: DataSourceManager提供单一入口，自动选择最优数据源
- **优先级机制**: AmazingData > CloudFlare Proxy > QMT > AkShare Direct
- **断路器模式**: 故障隔离和自动恢复，避免级联失败
- **多级缓存**: L1内存 → L2 Redis → L3 DuckDB/PostgreSQL
- **请求优化**: 速率限制、请求去重、批处理

### 3. 事件驱动系统

- **高性能事件引擎**: 支持批处理和优先级调度
- **异步事件处理**: 基于asyncio的高并发处理
- **事件订阅**: 灵活的事件订阅和发布机制

### 4. 消息总线

- **多后端支持**: ZeroMQ、Redis TimeSeries
- **路由机制**: 基于主题的消息路由
- **持久化**: 支持消息持久化和重放

## 安装

本项目使用 UV 作为包管理工具，提供更快的依赖安装和更好的依赖解析。

```bash
# 克隆项目
git clone https://github.com/your-repo/deepsearch.git
cd deepsearch

# 安装 UV（如果未安装）
pip install uv

# 创建虚拟环境（使用Python 3.13）
uv venv --python 3.13

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装所有依赖（包括开发依赖）
uv sync --all-extras

# 安装前端依赖
cd deepsearch/webui/frontend
npm install
cd ../../..
```

## 使用

### 启动系统

```bash
# 使用UV启动后端系统（不含前端）
uv run python -m deepsearch run

# 单独启动前端（另一个终端）
cd deepsearch/webui/frontend
npm run dev

# 运行特定模式
uv run python -m deepsearch run --mode engine  # 仅引擎
uv run python -m deepsearch run --mode webui   # 仅WebUI

# 检查端口配置
uv run python -m deepsearch check-ports
```

### 访问界面

- WebUI: http://localhost:3000
- API文档: http://localhost:8000/docs
- 专业交易视图: http://localhost:3000/pro-trading

### CLI 命令

```bash
# 查看帮助
uv run python -m deepsearch --help

# 检查端口
uv run python -m deepsearch check-ports

# 运行特定模式
uv run python -m deepsearch run --mode engine  # 仅引擎
uv run python -m deepsearch run --mode webui   # 仅WebUI

# 添加新依赖
uv add package-name

# 添加开发依赖
uv add --group dev package-name

# 更新依赖
uv lock --update
```

## 配置

系统配置文件位于 `deepsearch/config/` 目录：

- `settings.dev.yaml` - 开发环境配置
- `settings.prod.yaml` - 生产环境配置

### 环境变量

使用双下划线分隔的环境变量覆盖配置：

```bash
export LOG__LEVEL=DEBUG
export WEBUI__BACKEND_PORT=8080
export MESSAGE_BUS__BUSES__ZMQ__CONFIG__HOST=10.0.0.5
```

## 开发

### 代码规范

```bash
# 代码格式化
black deepsearch tests
isort deepsearch tests

# 类型检查
mypy deepsearch

# 运行测试
pytest
pytest tests/test_event.py -v
```

### 构建前端

```bash
cd deepsearch/webui/frontend
npm run build
```

生成的文件将位于 `deepsearch/webui/static/` 目录。

## 技术栈

### 后端

- Python 3.13 - 主要开发语言
- UV - 现代Python包管理器
- FastAPI - 高性能Web框架
- AsyncIO - 异步编程
- Pydantic - 数据验证和设置管理
- SQLAlchemy - ORM
- DuckDB - 分析型数据库
- PostgreSQL - 事务型数据库
- Redis - 缓存和消息队列
- ZeroMQ - 高性能消息传输

### 前端

- Vue 3 - 前端框架
- Element Plus - UI组件库
- ECharts - 专业图表库
- Vite - 构建工具
- TypeScript - 类型支持

### 数据源

- AmazingData - 银河证券专业数据（最高优先级）
- CloudFlare Workers - AkShare API代理
- AkShare - A股数据
- QMT - 迅投量化实时数据
- 支持自定义数据源扩展

## 性能优化

- **requestAnimationFrame批处理**: 优化高频数据更新
- **防抖处理**: ResizeObserver和窗口resize事件
- **shallowRef**: Vue3响应式优化
- **虚拟滚动**: 大数据列表渲染
- **Web Workers**: CPU密集型计算隔离

## 许可证

MIT License

## 贡献

欢迎提交 Pull Request 和 Issue。

## 联系方式

- GitHub Issues: [提交问题](https://github.com/your-repo/deepsearch/issues)
- Email: your-email@example.com