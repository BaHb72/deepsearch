# WebUI 模块概览

## 模块定位

`deepsearch/webui` 提供 DeepSearch 的前后端一体化 Web 控制台。后端基于 FastAPI，负责数据服务、配置管理、缓存查询等接口；前端使用
React + Ant Design Pro 构建交互界面，最终打包为静态资源并由 FastAPI 提供。

## 后端结构

- `server.py`：创建 FastAPI 应用实例，加载路由、事件钩子、异常处理器，并集成跨域、认证中间件。
- `runner.py`：封装 `run_standalone` / `create_app`，供 CLI `webui` 模式或 gunicorn/uvicorn 启动使用。
- `server_manager.py`：管理 WebUI 服务进程（启动、健康检查、自动重启），在核心引擎“full”模式下由组件调用。
- `auth.py`：实现登录认证（JWT/Token）、权限校验；配合前端登录流程。
- `dependencies.py`：定义 FastAPI 依赖注入（数据库会话、数据源管理器、缓存适配器等），确保请求范围资源按需注入。
- `api/`：
  - `base.py`, `types.py`, `utils.py` 定义 API 响应模型、统一响应格式、分页工具。
  - `exception_handlers.py`, `errors.py` 统一异常映射；`common/response_format.py` 规范返回结构。
  - `cache/unified.py` 暴露缓存读写与状态查询接口。
  - `endpoints/` 子模块按业务拆分：
    - `market.py`, `chart.py`, `cache.py` 等提供市场行情、图表数据、缓存数据接口。
    - `amazingdata/`、`data/`、`providers/` 对接不同数据源 API（AmazingData、AkShare、统一数据服务）。
    - `database/`、`database_states.py` 处理数据库监控、运行状态查询。
    - `proxy.py`, `stock_comment.py` 等扩展接口。
  - `common`、`utils` 子目录包含响应包装、错误编码、路由适配器等通用逻辑。
- `dependencies.py`、`api/utils.py` 结合 `infrastructure.providers`、`persistence` 组件满足数据访问需求。
- 运行时产物如 `diagnostic_log.json` 用于记录后端诊断信息。

## 前端结构

- `frontend/`：React (TypeScript) 应用，采用 Ant Design Pro + Zustand 状态管理。
  - `src/api`：封装请求函数（使用 Axios），与后端接口对齐。
  - `src/components`：仪表盘、图表、卡片等 UI 组件；`modules` 下包含图表渲染、性能分析、日志中心等模块化视图。
  - `src/stores`：Zustand store 管理全局配置、市场数据、系统状态。
  - `src/layouts`, `pages`, `router`：路由与页面结构，包含 Dashboard、数据源监控、日志中心等页面。
  - `src/utils`：前端缓存、批量请求、性能监控、WebSocket 等辅助工具。
  - `src/theme`、`src/styles`：主题与样式定制。
  - `src/assets`：图标、字体等静态资源。
- 构建后的静态文件输出至 `static/`（`index.html`、打包的 JS/CSS）。

## 运行流程

1. CLI `deepsearch run --mode webui` 通过 `runner.run_standalone()` 启动 FastAPI，静态文件由后端直接服务或代理到独立前端进程。
2. 客户端登录后，前端调用 `api` 目录下的接口获取缓存、行情、数据源状态，并通过 WebSocket/轮询刷新。
3. 后端依赖 `dependencies.py` 注入的服务访问缓存、数据库、数据源，并返回标准化响应。
4. `server_manager` 在“full”模式下与核心引擎组件协同，确保 WebUI 与其他组件同步启动/停止。

## 扩展建议

- 新增 API 时，在 `api/endpoints/<domain>` 编写路由并更新前端 `src/api` 与对应页面。
- 与新数据源集成时，可在 `api/endpoints/data` 或 `providers` 子模块中增加路由，与配置模型联动。
- 前端改动后需运行 `npm run build` 更新 `static/`，或在开发模式下通过 `npm run dev` 启动独立前端并配置代理。
