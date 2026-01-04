# WebUI 前端接入数据源后台任务（股票基础信息预取）指南

> 适用范围：DeepSearch WebUI（React / TSX 前端）
> 目标：在前端增加“预取股票基础信息”按钮与 Job 列表展示，调用后端
> `POST /api/data-sources/jobs/prefetch-stock-basics` / `GET /api/data-sources/jobs`

后端已经提供了一套完整的数据源后台作业 API，用于执行耗时的股票基础信息预取（`prefetch_stock_basics`）并落库到
`ingestion_jobs / ingestion_batches / market_snapshots` 等表。
本指南说明如何在前端集成这套能力：增加一个按钮触发预取、一个简单的 Job 列表/进度展示，并与现有行情页面协同。

---

## 1. 后端接口快速回顾

详见：`docs/operations/runbooks/data_source_persistence_akshare_and_amazingdata.md`

- `GET /api/data-sources/jobs?job_type=prefetch_stock_basics&limit=20`
  - 返回最近的后台作业列表。
- `POST /api/data-sources/jobs/prefetch-stock-basics`
  - Body: `{ "force": true | false }`
  - 创建 / 复用股票基础信息预取作业。
- `POST /api/data-sources/jobs/{job_id}/cancel`
  - 取消排队/运行中的作业。

前端只需用 `fetch`/`axios` 等调用上述接口，无需了解内部细节（AmazingData vs AkShare 等）。

---

## 2. 前端 API 封装建议

假设前端已有统一的 HTTP 工具（如 `src/utils/request.ts` 或基于 `fetch` 的封装），可以在
`src/api/` 下新增一个数据源后台作业 API 模块，例如：

文件建议：`deepsearch/webui/frontend/src/api/dataSourceJobs.ts`

```ts
export interface IngestionJobSummary {
  jobId: string;
  jobType: string;
  dataSource: string;
  accessType: string;
  status: string;
  queuedAt?: string;
  startedAt?: string;
  completedAt?: string;
  expiresAt?: string;
  recordCount?: number;
  errorMessage?: string;
}

export interface JobListResponse {
  jobs: IngestionJobSummary[];
}

export async function listStockPrefetchJobs(limit = 20): Promise<JobListResponse> {
  const resp = await fetch(
    `/api/data-sources/jobs?job_type=prefetch_stock_basics&limit=${limit}`,
  );
  if (!resp.ok) {
    throw new Error(`Failed to load jobs: ${resp.status}`);
  }
  return resp.json();
}

export async function triggerStockPrefetch(force: boolean): Promise<IngestionJobSummary> {
  const resp = await fetch(`/api/data-sources/jobs/prefetch-stock-basics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to trigger prefetch: ${resp.status}`);
  }
  return resp.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  const resp = await fetch(`/api/data-sources/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
  if (!resp.ok) {
    throw new Error(`Failed to cancel job: ${resp.status}`);
  }
}
```

> 注意：以上仅为结构示例，实际实现时请复用项目现有的请求封装（如带统一错误处理、鉴权头等）。

---

## 3. UI 集成示例：在行情页面添加“预取基础数据”按钮

### 3.1 使用位置建议

- 行情总览页：`deepsearch/webui/frontend/src/pages/MarketData.tsx`
  - 该页已经承载了市场实时强弱、板块概览等核心指标；
  - 适合放置一个“预取基础数据”的操作入口与 Job 状态展示。

### 3.2 最小可用交互设计

在页面右上角或设置区域增加：

- 一个按钮：
  - 文案：`预取股票基础信息`
  - 行为：调用 `triggerStockPrefetch(force=true)`；
- 一个 Job 列表（可折叠）：
  - 展示最近 N 条作业：
    - 状态：`queued / running / writing / succeeded / failed / cancelled`
    - 记录数：`recordCount`
    - 时间：`queuedAt / startedAt / completedAt`
  - 支持点击“取消”正在运行的作业。

示意（简化版）：在 `MarketData.tsx` 中使用 Hooks：

```tsx
import React, { useEffect, useState } from 'react';
import {
  listStockPrefetchJobs,
  triggerStockPrefetch,
  cancelJob,
  IngestionJobSummary,
} from '../api/dataSourceJobs';

export const MarketDataPage: React.FC = () => {
  const [jobs, setJobs] = useState<IngestionJobSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  async function reloadJobs() {
    setLoading(true);
    try {
      const resp = await listStockPrefetchJobs(10);
      setJobs(resp.jobs);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // 初次加载 + 简单轮询
    reloadJobs();
    const timer = setInterval(reloadJobs, 10000);
    return () => clearInterval(timer);
  }, []);

  async function handleTrigger(force: boolean) {
    setTriggering(true);
    try {
      await triggerStockPrefetch(force);
      await reloadJobs();
    } finally {
      setTriggering(false);
    }
  }

  async function handleCancel(jobId: string) {
    await cancelJob(jobId);
    await reloadJobs();
  }

  // ...原有行情组件渲染...
};
```

> 具体的 UI（按钮样式、表格组件、国际化文案）应遵循当前前端的设计系统（例如 Ant Design / 自定义组件库），这里只给出结构思路。

---

## 4. 与实时行情接口的协同策略

为了避免再次出现 `timeout of 8000ms exceeded` 的情况，前端在调用实时行情接口前，应优先检查：

1. 是否已经完成至少一次股票基础信息预取（后台 Job）；
2. 后端是否已经有可用的板块成分和股票列表。

建议：

- 当 Job 列表中存在最近一次 `succeeded` 且 `recordCount > 0` 的 `prefetch_stock_basics` 作业时：
  - 可以在行情页面上显示“基础数据已就绪”的提示；
  - 再发起 `/api/market/live/*` 请求。
- 当最近 Job 仍处于 `running` 状态时：
  - 行情页可以提示“基础数据预取中”，允许用户等待；
  - 或仅展示上一次预取时的缓存数据。
- 当 Job 多次 `failed` 时：
  - 建议引导用户查看后端日志（AmazingData 登录 / AkShare 网络）；
  - 或提供一个“切换数据源”的入口（例如尝试使用 AkShare 作为临时基础数据提供者）。

---

## 5. 后续扩展方向

1. **接入 UI 组件库的全量体验**
   - 用项目既有的 Button / Table / Tag / Message 组件包装上述交互；
   - 对 Job 状态使用颜色与图标区分（例如 `running` 显示为进行中、`failed` 显示为错误等）。
2. **与数据源切换面板集成**
   - 如果前端已有数据源选择器（例如在设置或工具栏里），可以在该区域增加“预取/刷新”按钮；
   - 不同数据源（AmazingData/AkShare）可单独维护各自的 Job 列表。
3. **异常可视化**
   - 在 Job 详情中展示 `errorMessage`、`recordCount` 与 `ingestion_batches` 的统计信息；
   - 结合后端的监控 API（数据源健康状态），给出“建议操作”（重试 / 切换备源等）。

---

通过上述步骤，前端可以在**不改动业务领域逻辑**的前提下：

- 显式触发并观察后台数据预取作业；
- 减少“大抓取”对实时接口的直接压力；
- 与 AkShare / AmazingData 的持久化链路协同工作，保障行情页面在基础数据可用的前提下运行。
