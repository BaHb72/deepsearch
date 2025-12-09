import React, { lazy, Suspense, useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { App as AntApp, Spin } from 'antd'

import MainLayout from './layouts/MainLayout'
import messageManager from './utils/messageManager'

const Dashboard = lazy(() => import('./pages/dashboard'))
const EventSystem = lazy(() => import('./pages/EventSystem'))
const MarketData = lazy(() => import('./pages/market'))
const LogCenter = lazy(() => import('./pages/System/LogCenter'))
const SystemConfig = lazy(() => import('./pages/SystemConfig'))
const DataSourceMonitor = lazy(() => import('./pages/Monitor/DataSourceMonitor'))
const CacheSystem = lazy(() => import('./pages/Monitor/CacheSystem'))
const PerformanceAnalytics = lazy(() => import('./pages/Monitor/PerformanceAnalytics'))
const AlertManager = lazy(() => import('./pages/Monitor/AlertManager'))
const ComponentManager = lazy(() => import('./pages/Monitor/ComponentManager'))

const Loading: React.FC = () => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
    }}
  >
    <Spin size="large" />
  </div>
)

const App: React.FC = () => {
  const { message } = AntApp.useApp()

  useEffect(() => {
    messageManager.setMessageApi(message)
  }, [message])

  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="events" element={<EventSystem />} />
          <Route path="market/*" element={<MarketData />} />
          <Route path="system/logs" element={<LogCenter />} />
          <Route path="system/config" element={<SystemConfig />} />

          <Route path="monitor/datasource" element={<DataSourceMonitor />} />
          <Route path="monitor/cache" element={<CacheSystem />} />
          <Route path="monitor/performance" element={<PerformanceAnalytics />} />
          <Route path="monitor/alert" element={<AlertManager />} />
          <Route path="monitor/component" element={<ComponentManager />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App
