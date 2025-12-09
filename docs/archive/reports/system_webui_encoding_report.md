# System WebUI 编码巡检报告

## 背景

根据最新指令，对 System WebUI 前端模块进行中文编码与日志文案巡检，同时梳理与编码相关的 TODO。巡检范围覆盖 React 入口、主布局、API
客户端与监控模块，目标是彻底清除乱码、统一中文提示并补齐缺失的类型约束。

## 已完成的优化

### 入口与布局

- `src/main-react.tsx`：重写启动流程，统一中文日志与异常提示，并按需惰性加载主题配置。
- `src/layouts/MainLayout/index.tsx`：整理嵌套路由与菜单文案，修复历史遗留乱码，确保侧边导航完全采用 UTF-8。
- `src/utils/performance.ts`：新增定时采样守护，保证性能日志为可读中文。

### API 核心模块

- `src/api/core/types.ts` 与 `src/types/axios.d.ts`：补齐 `RequestMetadata` 类型扩展，确保 Axios 客户端可以识别请求元数据。
- `src/api/core/client.ts`：合并 `mergeMetadata` 等辅助函数，规范请求/响应封装与错误处理，日志统一输出 UTF-8 中文。
- `src/api/core/logger.ts`：移除 emoji，补充分类字段，使所有日志在 GBK/UTF-8 环境下均可读。
- `src/api/core/monitor.ts`：重建采样与指标计算流程，支持全局/分类/端点维度的性能快照，并统一中文提示。

### 类型与上下文

- `src/components/ErrorBoundary.tsx`、`src/contexts/ThemeContext.tsx`、`src/hooks/useAsyncData.ts`、
  `src/hooks/useWebSocket.ts`：补齐类型、消除 `implicit any`，修复历史编码导致的错位文案。
- `src/utils/messageManager.ts`：迁移至 TypeScript，显式约束 antd 消息实例能力。
- `tsconfig.json`：限定编译范围至新 UI 目录，引入 `vite/client` 与 `node` 类型定义，规避旧目录编码污染。

## 校验

- `uv pip check --python ./.venv/Scripts/python.exe`
- 建议在 `deepsearch/webui/frontend` 执行 `npm ls --depth=0` 与 `npx tsc --noEmit` 对前端依赖与类型进行复验（当前环境未自动执行）。

## 待跟进事项

1. `src/pages` 与 `src/stores` 中仍存在大量 `// @ts-nocheck`，需逐步补充类型后移除。
2. `src/api/core/monitor.ts` 尚留请求采集落地与历史指标整合 TODO，需继续推进。
3. AmazingData 数据源尚未全面接入（Chart/Market/Cache 接口仍返回模拟数据），需按计划替换为真实数据。
4. 旧文档残留的 GBK 片段应陆续转存为 UTF-8，避免再次出现乱码。

## 影响范围

- `src/main-react.tsx`
- `src/layouts/MainLayout/index.tsx`
- `src/components/ErrorBoundary.tsx`
- `src/contexts/ThemeContext.tsx`
- `src/hooks/useAsyncData.ts`
- `src/hooks/useWebSocket.ts`
- `src/api/core/client.ts`
- `src/api/core/monitor.ts`
- `src/utils/messageManager.ts`
- `tsconfig.json`
