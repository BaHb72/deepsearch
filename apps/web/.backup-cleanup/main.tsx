import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { initPerformanceMonitor } from '@/utils/performance'

// 初始化性能监控
if (process.env.NODE_ENV === 'production') {
  initPerformanceMonitor({
    reportCallback: (data) => {
      // 发送性能数据到后端
      fetch('/api/performance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }).catch(console.error)
    },
    debug: false
  })
}

// 开发环境调试
if (process.env.NODE_ENV === 'development') {
  initPerformanceMonitor({ debug: true })
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
