# DeepSearch

高性能量化交易事件系统

## 项目结构

```
deepsearch/
├── configs/               # 配置文件目录
├── deepsearch/            # 源代码
│   ├── __init__.py
│   ├── __main__.py        # CLI 入口
│   ├── cli.py             # 命令行界面
│   ├── config/            # 配置管理
│   │   ├── models/        # 配置模型
│   │   ├── manager.py     # 配置管理器
│   │   └── settings.py    # 配置设置
│   ├── constants/         # 常量定义
│   ├── core/              # 核心组件
│   │   ├── engine.py      # 主引擎
│   │   ├── component_manager.py  # 组件管理
│   │   └── interfaces.py  # 接口定义
│   ├── datafeed/          # 数据源
│   │   ├── qmt/           # QMT数据源
│   │   └── akshare/       # AkShare数据源
│   ├── event/             # 事件系统
│   ├── gateway/           # 交易网关
│   ├── messaging/         # 消息系统
│   ├── monitoring/        # 监控系统
│   ├── observability/     # 日志监控
│   ├── services/          # 业务服务
│   │   ├── chart_service.py       # 图表数据服务
│   │   ├── stock_info_service.py  # 股票信息服务
│   │   ├── adjust_service.py      # 复权因子服务
│   │   ├── data_source_interface.py    # 数据源接口
│   │   ├── data_source_adapter.py      # 数据源适配器
│   │   └── aggregated_data_source.py   # 聚合数据源
│   ├── storage/           # 数据存储
│   ├── trader/            # 交易逻辑
│   ├── utils/             # 工具类
│   └── webui/             # Web UI
│       ├── api/           # FastAPI 后端
│       ├── frontend/      # Vue 前端
│       └── server.py      # 服务器入口
├── docs/                  # 文档
├── examples/              # 示例代码
├── scripts/               # 脚本文件
│   └── start.bat          # 启动脚本
├── tests/                 # 测试
├── tools/                 # 工具脚本
├── main.py                # 主入口
├── pyproject.toml         # 项目配置
├── requirements.txt       # 依赖
└── README.md              # 本文件
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

- **依赖倒置原则**: 数据源作为黑盒，支持热切换
- **适配器模式**: 统一不同数据源接口
- **断路器模式**: 故障隔离和自动恢复
- **聚合数据源**: 智能路由和负载均衡

### 3. 事件驱动系统

- **高性能事件引擎**: 支持批处理和优先级调度
- **异步事件处理**: 基于asyncio的高并发处理
- **事件订阅**: 灵活的事件订阅和发布机制

### 4. 消息总线

- **多后端支持**: ZeroMQ、Redis TimeSeries
- **路由机制**: 基于主题的消息路由
- **持久化**: 支持消息持久化和重放

## 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/deepsearch.git
cd deepsearch

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖

# 安装前端依赖
cd deepsearch/webui/frontend
npm install
cd ../../..
```

## 使用

### 启动系统

```bash
# 启动后端系统（不含前端）
python -m deepsearch run

# 单独启动前端（另一个终端）
cd deepsearch/webui/frontend
npm run dev

# 或使用脚本启动所有服务
./scripts/start.bat  # Windows
./scripts/start.sh   # Linux/Mac
```

### 访问界面

- WebUI: http://localhost:3000
- API文档: http://localhost:8000/docs
- 专业交易视图: http://localhost:3000/pro-trading

### CLI 命令

```bash
# 查看帮助
python -m deepsearch --help

# 检查端口
python -m deepsearch check-ports

# 运行特定模式
python -m deepsearch run --mode engine  # 仅引擎
python -m deepsearch run --mode webui   # 仅WebUI
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

- Python 3.10+
- FastAPI - Web框架
- AsyncIO - 异步编程
- Pydantic - 数据验证
- SQLAlchemy - ORM
- Redis - 缓存和消息队列
- ZeroMQ - 高性能消息传输

### 前端

- Vue 3 - 前端框架
- Element Plus - UI组件库
- ECharts - 图表库
- Vite - 构建工具
- TypeScript - 类型支持

### 数据源

- AkShare - A股数据
- QMT - 迅投量化数据
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