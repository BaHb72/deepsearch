import React, { Suspense, lazy, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin, App as AntApp } from 'antd'
import MainLayout from './layouts/MainLayout'
import messageManager from './utils/messageManager'

// 懒加载页面组件
const Dashboard = lazy(() => import('./pages/Dashboard'))
const EventSystem = lazy(() => import('./pages/EventSystem'))
const MarketData = lazy(() => import('./pages/MarketData'))
const LogCenter = lazy(() => import('./pages/LogCenter'))
// const SystemConfig = lazy(() => import('./pages/SystemConfigEnhanced')) // 旧版本
const SystemConfig = lazy(() => import('./pages/SystemConfig')) // 使用重构后的模块化版本

// 监控管理页面
const DataSourceMonitor = lazy(() => import('./pages/DataSourceMonitor'))
const CacheSystem = lazy(() => import('./pages/CacheSystem'))
const PerformanceAnalytics = lazy(() => import('./pages/PerformanceAnalytics'))
const AlertManager = lazy(() => import('./pages/AlertManager'))
const ComponentManager = lazy(() => import('./pages/ComponentManager'))


// 加载组件
const Loading = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh' 
  }}>
    <Spin size="large" />
  </div>
)

// 主应用组件
function App() {
  // 获取 App 实例中的 message API
  const { message } = AntApp.useApp()
  
  // 设置全局 message 管理器
  useEffect(() => {
    messageManager.setMessageApi(message)
  }, [message])
  
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/*" element={
          <MainLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/events" element={<EventSystem />} />
              <Route path="/market/*" element={<MarketData />} />
              <Route path="/system/logs" element={<LogCenter />} />
              <Route path="/system/config" element={<SystemConfig />} />

              {/* 监控管理路由 */}
              <Route path="/monitor/datasource" element={<DataSourceMonitor />} />
              <Route path="/monitor/cache" element={<CacheSystem />} />
              <Route path="/monitor/performance" element={<PerformanceAnalytics />} />
              <Route path="/monitor/alert" element={<AlertManager />} />
              <Route path="/monitor/component" element={<ComponentManager />} />


              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </MainLayout>
        } />
      </Routes>
    </Suspense>
  )
}

export default App
