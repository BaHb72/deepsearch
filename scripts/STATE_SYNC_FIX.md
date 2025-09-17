# 组件状态同步修复说明

## 修复的问题
组件在后端恢复后不会自动刷新，需要手动点击"重试"按钮。

## 根本原因
1. **组件未监听后端状态变化**：useAsyncData 和 DatabaseConfig 都没有监听 backendStatus 的变化
2. **请求被永久拒绝**：当 backendStatus.isAvailable = false 时，request.js 直接拒绝请求
3. **状态不同步**：后端恢复后，组件仍停留在错误状态

## 解决方案
实施了方案一：在 useAsyncData 中添加 backendStatus 监听器

## 修改的文件

### 1. `hooks/useAsyncData.ts`
- 导入 backendStatus
- 添加 useEffect 监听后端状态变化
- 当后端恢复且错误是 BACKEND_UNAVAILABLE 时，自动调用 refresh()

```typescript
// 监听后端状态变化
useEffect(() => {
  const handleBackendStatusChange = (available: boolean) => {
    if (available && state.error) {
      const isBackendError = // 检查是否是后端错误
      if (isBackendError) {
        console.log('[useAsyncData] 后端已恢复，自动重试...')
        refresh()
      }
    }
  }
  backendStatus.addListener(handleBackendStatusChange)
  return () => backendStatus.removeListener(handleBackendStatusChange)
}, [state.error, refresh])
```

### 2. `pages/SystemConfig/DatabaseConfig.tsx`
- 导入 Spin 和 LoadingOutlined 组件
- 改进错误显示逻辑
- 当错误是"后端服务不可用"时，显示等待动画和提示

```tsx
{error.message?.includes('后端服务不可用') ? (
  <>
    <Spin indicator={<LoadingOutlined />} />
    <p>正在等待后端服务恢复...</p>
    <p>系统将在后端恢复后自动刷新</p>
  </>
) : (
  // 其他错误显示
)}
```

## 工作流程

### 之前的流程
1. 后端不可用 → 请求被拒绝
2. 组件显示错误
3. 后端恢复
4. 组件不知道，继续显示错误 ❌
5. 用户必须手动点击"重试"

### 修复后的流程
1. 后端不可用 → 请求被拒绝
2. 组件显示"正在等待后端服务恢复..."
3. useAsyncData 添加监听器
4. 后端恢复 → 触发监听器
5. 自动调用 refresh() ✅
6. 组件自动更新，无需手动操作

## 测试方法

### 1. 使用测试脚本
在浏览器控制台执行：
```javascript
// 复制 scripts/test_state_sync.js 的内容
```

### 2. 手动测试
```javascript
// 设置后端不可用
testStateSync.setBackendUnavailable()

// 等待几秒，观察组件显示

// 设置后端可用
testStateSync.setBackendAvailable()

// 组件应该自动刷新
```

### 3. 验证点
- ✅ 后端不可用时显示等待动画
- ✅ 后端恢复后自动刷新
- ✅ 无需手动点击"重试"
- ✅ 控制台显示"[useAsyncData] 后端已恢复，自动重试..."

## 优势
1. **更好的用户体验**：无需手动干预
2. **实时响应**：后端恢复立即刷新
3. **清晰的状态提示**：用户知道系统在等待
4. **减少困惑**：避免用户不知道该做什么

## 潜在优化
如果需要进一步优化，可以考虑：
1. 添加重试次数限制
2. 实现指数退避算法
3. 在 request.js 中添加短暂等待
4. 提供手动强制刷新选项