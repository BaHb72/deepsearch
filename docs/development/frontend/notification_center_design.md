# 通知中心前端模块设计

## 背景与目标
- 当前通知配置入口嵌在系统配置页，功能混杂，难以集中管理。
- 微信推送存在 32 字标题限制，需要前端显式提示，避免被动截断。
- 目标是提供一站式的通知配置、测试与额度监控能力，降低运维同学使用成本。

## 页面信息架构
页面划分为四个主要模块，可通过 Tabs 或 Anchor 切换：
1. **概览与状态**：展示服务启用状态、默认渠道、最近一次推送结果、快速入口（查看日志、刷新额度）。
2. **格式与模板**：编辑标题、正文模板，说明可用占位符；实时校验微信标题长度、空值等。
3. **推送测试**：输入标题/正文/渠道/分类，一键触发 `POST /api/notification/send`，记录测试结果列表。
4. **额度监控**：调用 `GET /api/notification/quotas`，以表格 + 进度条方式展示各分类额度，支持 `POST /api/notification/quotas/reset`。
5. **凭据与基础配置**：管理微信/Bark Token、默认渠道、重试策略等基础参数。

> 若沿用现有系统配置页，可把该页面作为独立路由（例如 `/system/notifications`），保持原地址跳转。

## 组件拆分
- `NotificationCenter/index.tsx`：页面骨架，负责布局与状态管理容器。
- `OverviewCard.tsx`：汇总信息卡片，订阅最新测试结果与额度状态。
- `FormatSection.tsx`：模板编辑表单，包含标题/正文、即时预览；复用 Ant Form。
- `TestSection.tsx`：测试推送表单 + 历史表格；支持本地缓存最近 20 条记录。
- `QuotaSection.tsx`：额度表格组件，支持刷新、重置按钮；显示剩余额度进度。
- `CredentialsSection.tsx`：Token 配置卡片，使用弹窗修改并提示遮盖。
- `useNotificationConfig` hook：封装获取/保存配置逻辑，提供字段校验。
- `useNotificationQuota` hook：统一处理额度获取、刷新、重置。
- `useNotificationTest` hook：负责发送测试请求、记录结果、错误提示。

## 交互与校验细节
- 标题长度：前端在 `FormatSection` 与 `TestSection` 中同步校验 `<= 32`，与后端 `NotificationValidationError` 保持一致；超过限制时禁用提交，并提示“微信推送标题长度需不超过 32 个字符”。
- 正文模板：支持占位符（如 `{symbol}`、`{price}`）。保存时仅校验非空；未来可扩展占位符提示。
- Token 管理：展示已配置状态（***），点击“更新”后输入新 Token，可选“清除”操作。
- 测试历史：成功失败都记录，展示时间、渠道、分类、状态码、错误信息；可清空记录。
- 限额表格：列包含分类、渠道、已用次数、剩余额度、窗口秒数、预计重置时间；显示 0 剩余时高亮。
- 全局状态：若通知服务未启用，除凭据配置外其他模块灰化并提示需先启用。

## 后端接口对接
- `GET /api/notification/config`：加载初始配置。
- `PUT /api/notification/config`：保存模板、凭据、开关等；需要在请求体中补充新字段（若新增模板字段需同步后端模型）。
- `POST /api/notification/send`：用于测试推送；捕获 400 错误展示后端返回信息。
- `GET /api/notification/quotas` / `POST /api/notification/quotas/reset`：额度展示与重置。
- 可选：若要持久化测试历史，新增 `GET /api/notification/tests`（未来迭代）。

## 状态管理方案
- 使用 React Query 或自研 hook 缓存配置、额度数据；提交成功后执行 `invalidate`。
- 测试历史可存放在组件 state，也可利用浏览器 LocalStorage 持久化。
- 标题/正文模板可使用 Form 控制；保存时统一调用 `updateNotificationConfig`。

## UI 与可用性细节
- 顶部提供“复制模板”、“恢复默认”按钮，方便快速回滚。
- 测试按钮旁增加“填入默认模板”快捷填充。
- 限额表格支持自动刷新（间隔可配置，如 60s），并提供手动刷新。
- 所有关键操作（保存、测试、重置）使用 Ant Message/Notification 给出反馈。

## 验收与测试
- 单元测试：前端为 hooks/组件写基础测试（位于 `src/pages/NotificationCenter/__tests__/`），覆盖校验逻辑与状态变化。
- 手工验证：
  1. 启用服务，配置 Token，保存成功。
  2. 输入超长标题，阻止提交并提示。
  3. 正常标题发送成功，额度表同步更新。
  4. 重置额度后，表格恢复初始状态。
  5. 服务禁用时页面提示受限。
- 后端接口已在 `tests/api/test_notification_api.py` 覆盖；若新增字段需同步更新。

## 后续迭代留白
- 增加通知模板预览（Markdown 渲染）。
- 支持批量测试不同渠道。
- 增加历史推送查询（与日志/数据库联动）。
- 集成权限控制，限制敏感操作（如重置额度）。
