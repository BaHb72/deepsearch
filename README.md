# DeepSearch

高性能量化交易事件系统

## 项目结构

```
deepsearch/
├── config/                 # 配置文件
│   ├── settings.yaml      # 基础配置
│   ├── settings.dev.yaml  # 开发环境配置
│   └── settings.prod.yaml # 生产环境配置
├── deepsearch/            # 源代码
│   ├── __init__.py
│   ├── config/            # 配置管理
│   ├── core/              # 核心工具
│   ├── event/             # 事件系统
│   ├── gateway/           # 交易网关
│   ├── observability/     # 日志监控
│   ├── storage/           # 数据存储
│   └── trader/            # 交易逻辑
├── docs/                  # 文档
├── examples/              # 示例代码
├── tests/                 # 测试
├── main.py               # 主入口
├── pyproject.toml        # 项目配置
├── requirements.txt      # 依赖
└── README.md            # 本文件
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
# 运行系统
python main.py

# 或安装后运行
deepsearch
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

## License

MIT License