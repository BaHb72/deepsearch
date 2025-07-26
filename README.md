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
│   │   ├── components.py  # 组件管理
│   │   └── interfaces.py  # 接口定义
│   ├── event/             # 事件系统
│   ├── gateway/           # 交易网关
│   ├── messaging/         # 消息系统
│   ├── monitoring/        # 监控系统
│   ├── observability/     # 日志监控
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

## 安装

```bash
# 克隆项目
git clone https://github.com/BaHb/deepsearch.git
cd deepsearch

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 开发模式安装
pip install -e .
```

## 使用

```bash
# 运行完整系统（前端+后端）
python -m deepsearch run

# 仅运行后端
python -m deepsearch run --no-frontend

# 使用启动脚本
scripts\start.bat          # 启动完整系统
scripts\start.bat backend  # 仅启动后端
scripts\start.bat frontend # 仅启动前端
```

## 开发

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest

# 格式化代码
black deepsearch tests
isort deepsearch tests
```

## 主要特性

- **事件驱动架构**: 高性能事件处理，支持百万级事件/秒
- **灵活的消息总线**: 支持 ZeroMQ、Redis TimeSeries 等多种后端
- **全面的监控**: 内置指标采集、健康检查和性能跟踪
- **Schema 验证**: 使用 Pydantic 进行类型安全的事件处理
- **批量处理**: 针对高频数据优化的批处理能力
- **开发友好**: 提供装饰器和工具函数快速开发
- **Web UI**: 内置 Web 管理界面，支持实时监控和系统管理
- **组件化架构**: 模块化设计，易于扩展和维护

## License

MIT License