# AI 分析服务接入 - Phase 1 RAG 模式

**日期**: 2026-01-31
**模块**: ai, config, api
**类型**: feature
**状态**: 已完成

## 背景

为决策者提供基于本地 DeepSeek 模型（通过 Ollama）的智能分析能力，解读投资者互动问答和时事新闻。

## 设计决策

### 为什么选择 Ollama + 本地模型

- 数据不出本机，符合金融数据安全要求
- 无 API 调用费用，适合高频分析场景
- DeepSeek 开源模型质量足够，中文理解能力强

### 为什么完全独立模块

- `ai.enabled=false` 时零开销，不影响现有系统启动
- 健康检查失败仅 warning，不阻塞其他服务
- 所有代码在 `packages/core/infrastructure/ai/` 和 `apps/api/api/endpoints/ai/` 下，无侵入修改

### 配置加载方式

沿用项目已有的分层配置模式（`infrastructure.{env}.yaml`、`market_data.{env}.yaml`），新增 `ai.{env}.yaml`，通过 `loader.py` 中的 `_load_ai_config` 函数合并到主配置。

### SSE 流式设计

Ollama `/api/chat` 的 `stream=true` 模式返回 NDJSON（每行一个 JSON），通过 httpx 的 `aiter_lines()` 逐行解析，包装为标准 SSE `data:` 格式。前端可用 `EventSource` 或 `fetch` + `ReadableStream` 消费。

## 实施进度

### 已完成

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| 1 | 配置模型 | `packages/core/config/models/ai.py` | 已完成 |
| 2 | 开发环境配置 | `packages/core/config/ai.dev.yaml` | 已完成 |
| 3 | 生产环境配置 | `packages/core/config/ai.prod.yaml` | 已完成 |
| 4 | 配置模型导出 | `packages/core/config/models/__init__.py` | 已修改 |
| 5 | Settings 集成 | `packages/core/config/settings.py` | 已修改 (新增 `ai: Optional[AiConfig]`) |
| 6 | 配置加载器 | `packages/core/config/loader.py` | 已修改 (新增 `_load_ai_config`) |
| 7 | Ollama 客户端 | `packages/core/infrastructure/ai/ai_client.py` | 已完成 |
| 8 | Prompt 模板 | `packages/core/infrastructure/ai/prompt_templates.py` | 已完成 |
| 9 | 分析服务 | `packages/core/infrastructure/ai/ai_analysis_service.py` | 已完成 |
| 10 | API 端点 | `apps/api/api/endpoints/ai/analyze.py` | 已完成 |
| 11 | API 路由 | `apps/api/api/endpoints/ai/router.py` | 已完成 |
| 12 | 服务器集成 | `apps/api/server.py` | 已修改 (lifespan init/shutdown + 路由注册) |

### 验证结果

- 模块导入测试通过：`AiConfig`、`AiClient`、`AiAnalysisService` 均可正常导入
- 路由注册验证通过：4 个端点路径正确注册

### API 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ai/analyze/investor-qa` | 投资者互问解读（支持 `stream=true`） |
| POST | `/api/ai/analyze/news` | 时事新闻分析（支持 `stream=true`） |
| POST | `/api/ai/analyze/stream` | 通用流式分析（SSE） |
| GET | `/api/ai/health` | AI 服务健康状态 |

## 待办 (Phase 2)

- [ ] MCP Server 实现：让 DeepSeek 模型主动查询 DeepSearch 数据
- [ ] 接入 DataAccessProxy 自动获取投资者互问数据（当前由调用方提供 `qa_data`）
- [ ] 接入新闻数据源自动获取时事新闻
- [ ] 对话历史管理（多轮对话）
- [ ] 响应缓存（相似问题去重）

## 文件变更汇总

### 新增文件 (10个)

```
packages/core/config/models/ai.py
packages/core/config/ai.dev.yaml
packages/core/config/ai.prod.yaml
packages/core/infrastructure/ai/__init__.py
packages/core/infrastructure/ai/ai_client.py
packages/core/infrastructure/ai/ai_analysis_service.py
packages/core/infrastructure/ai/prompt_templates.py
apps/api/api/endpoints/ai/__init__.py
apps/api/api/endpoints/ai/router.py
apps/api/api/endpoints/ai/analyze.py
```

### 修改文件 (4个)

```
packages/core/config/models/__init__.py   - 导出 AiConfig
packages/core/config/settings.py          - 新增 ai 字段
packages/core/config/loader.py            - 新增 _load_ai_config
apps/api/server.py                        - lifespan + 路由注册
```
