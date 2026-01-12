# webui 模块实现说明

## 模块定位

`deepsearch.webui` 提供 DeepSearch 的可视化管理与交互界面，后端基于 FastAPI，前端为 Vite + React（位于 `webui/frontend`）。模块负责身份认证、API 路由、静态资源与前后端运行器管理。

## 目录结构

- `server.py`：FastAPI 应用入口，注册 `/api/<domain>` 路由与中间件。
- `runner.py`：封装命令行入口，区分 `engine` 与 `webui` 模式启动。
- `auth.py`：实现 JWT/Session 认证、权限校验与密码加密。
- `dependencies.py`：FastAPI 依赖注入，绑定数据库会话、消息总线、配置。
- `api/`：按领域划分的路由模块，与 `docs/api` 中的规范对应。
- `frontend/`：Vite 工程，组件/状态管理、API 调用集中于 `src/api`。
- `static/`：内置静态文件与 SPA 入口模板。

## 核心数据结构

- `UserSession`：登录态模型，包含角色、权限列表与过期时间。
- `ApiResponse[T]`：统一响应包装器，包含 `code`、`message`、`data` 字段。
- `WebUISettings`：读取 `settings.*.yaml` 中的 WebUI 配置。

## 关键流程

1. 启动时 `runner` 初始化配置、依赖注入并创建 FastAPI 应用。
2. 前端通过 `/api` 前缀访问，后端依赖 `dependencies` 注入资源。
3. 认证流程：登录请求 -> `auth.authenticate_user` -> 生成 Token -> 设置响应。
4. 所有接口遵循 `docs/api/API_MAPPING.md`，调用完成后记录审计日志。
5. 前端开发时执行 `npm run dev`，通过 Vite 代理到后端 `/api`。

## 扩展与集成

- 新增 API 前需更新 `docs/api/*` 并运行 `python tools/generate_api_documentation.py`。
- 若调整认证逻辑，注意同步修改前端的 token 管理与刷新流程。
- 支持自定义主题/组件，可在 `frontend/src` 中编写并与后端配置解耦。
- 部署在 Windows 环境时，使用提供的脚本启动，确保虚拟环境一致。
