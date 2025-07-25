# DeepSearch Web UI

DeepSearch 量化交易系统的 Web 用户界面。

## 功能特性

- 📊 **实时监控仪表板** - 系统状态、事件处理、性能指标的实时展示
- 📈 **事件监控** - 事件流查看、类型统计、慢事件追踪
- ⚙️ **系统配置** - 在线查看和管理系统配置
- 📝 **日志查看** - 实时日志流、级别过滤、搜索功能
- 💹 **交易监控** - 持仓、订单、策略性能展示

## 技术栈

### 后端

- FastAPI - 现代、高性能的 Python Web 框架
- uvicorn - ASGI 服务器
- WebSocket - 实时数据推送

### 前端

- Vue 3 - 渐进式 JavaScript 框架
- Element Plus - 基于 Vue 3 的组件库
- ECharts - 强大的图表库
- Vite - 下一代前端构建工具

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd deepsearch/webui/frontend
npm install
```

### 2. 开发模式运行

#### 启动后端服务器

```bash
# 在项目根目录
python -m deepsearch.webui.server
```

服务器将在 http://localhost:8000 启动

#### 启动前端开发服务器

```bash
# 在 frontend 目录
cd deepsearch/webui/frontend
npm run dev
```

前端开发服务器将在 http://localhost:3000 启动

### 3. 生产构建

```bash
# 在 frontend 目录
npm run build
```

构建产物将输出到 `deepsearch/webui/static` 目录

### 4. 生产部署

```bash
# 使用 uvicorn 启动
uvicorn deepsearch.webui.server:app --host 0.0.0.0 --port 8000

# 或使用 gunicorn (需要安装)
gunicorn deepsearch.webui.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API 文档

FastAPI 自动生成的 API 文档可通过以下地址访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 目录结构

```
webui/
├── __init__.py          # 模块初始化
├── server.py            # FastAPI 主应用
├── api/                 # API 路由
│   ├── monitor.py       # 监控相关接口
│   ├── config.py        # 配置相关接口
│   └── system.py        # 系统控制接口
├── frontend/            # Vue 前端项目
│   ├── src/
│   │   ├── views/       # 页面组件
│   │   ├── components/  # 通用组件
│   │   ├── api/         # API 调用
│   │   ├── stores/      # Pinia 状态管理
│   │   └── utils/       # 工具函数
│   └── package.json     # 前端依赖
└── static/              # 前端构建输出

```

## 配置说明

### 后端配置

后端配置通过 DeepSearch 主配置文件管理，监控相关配置在 `monitoring` 节点下。

### 前端配置

前端开发配置在 `vite.config.js` 中，包括：

- 开发服务器端口
- API 代理配置
- 构建输出目录

## 开发指南

### 添加新页面

1. 在 `frontend/src/views/` 创建新的 Vue 组件
2. 在 `frontend/src/router/index.js` 添加路由
3. 在 `frontend/src/App.vue` 添加菜单项

### 添加新 API

1. 在 `api/` 目录创建新的路由模块
2. 在 `server.py` 中导入并注册路由
3. 在前端 `src/api/` 添加对应的 API 调用

### WebSocket 通信

- 后端通过 `ConnectionManager` 管理 WebSocket 连接
- 前端在需要实时数据的组件中连接 WebSocket
- 支持自动重连机制

## 注意事项

1. 生产环境应该限制 CORS 允许的域名
2. 考虑添加认证机制保护 API
3. 大量数据展示时注意分页和性能优化
4. WebSocket 连接数限制和资源管理