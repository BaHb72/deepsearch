# 调试指南

## 问题描述
前端启动时显示"后端服务不可用"，但实际后端是正常的。

## 问题原因

### 1. **错误判断逻辑不准确**
- `backendStatus.js` 将所有异常都当作后端不可用
- 包括模块加载失败、JavaScript 错误等

### 2. **React.StrictMode 影响**
- 导致组件双重渲染
- 发送重复的 API 请求
- `useAsyncData` 可能执行多次

### 3. **时序问题**
- API 客户端还未初始化就进行健康检查
- 动态导入 `@/api/core` 可能失败

## 已修复内容

### 1. **优化 backendStatus.js**
- 区分不同错误类型（模块加载错误 vs 服务器错误）
- 只有真正的服务器错误才累计失败次数
- 改进日志输出，避免误导

### 2. **修复 useAsyncData**
- 使用空依赖数组，避免重复执行
- 确保只在组件挂载时执行一次

### 3. **修复 DatabaseConfig**
- 简化 Table 的 loading 逻辑
- 移除可能导致问题的条件判断

## 调试步骤

### 1. 启动调试后端
```bash
cd D:\Stock\code\deepsearch
python scripts/debug_backend.py
```
这会启动带详细日志的后端服务。

### 2. 启动前端
```bash
cd deepsearch/webui/frontend
npm run dev
```

### 3. 在浏览器中调试

打开 http://localhost:3000，然后：

1. 打开开发者工具 (F12)
2. 在控制台中执行调试脚本：
   ```javascript
   // 复制 scripts/browser_debug.js 的内容粘贴执行
   ```

### 4. 查看输出

调试脚本会检查：
- API 模块状态
- 后端连接
- BackendStatus 状态
- React 组件状态
- 网络请求

## 关键日志位置

### 前端日志
- `[BackendStatus]` - 后端状态检查
- `[DatabaseConfig]` - 数据库配置组件
- `[REQUEST]` / `[RESPONSE]` - API 请求响应

### 后端日志
- `[DEBUG] /system/status` - 系统状态端点
- `[REQUEST]` / `[RESPONSE]` - HTTP 请求跟踪

## 验证修复

修复后应该看到：
1. ✅ 不再显示"后端服务不可用"（除非真的不可用）
2. ✅ 组件正常加载，不再转圈
3. ✅ 日志中区分"模块加载错误"和"服务器错误"
4. ✅ 只有连续3次真正的服务器错误才标记为不可用

## 回滚方案

如果修改导致问题，可以回滚：
```bash
git checkout -- deepsearch/webui/frontend/src/utils/backendStatus.js
git checkout -- deepsearch/webui/frontend/src/hooks/useAsyncData.ts
git checkout -- deepsearch/webui/frontend/src/pages/SystemConfig/DatabaseConfig.tsx
```