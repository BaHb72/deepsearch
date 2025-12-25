import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouteObject } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import ErrorBoundary from '@/components/common/ErrorBoundary'

const Dashboard = lazy(() => import('@/pages/dashboard'))
const EventSystem = lazy(() => import('@/pages/EventSystem'))
const MarketData = lazy(() => import('@/pages/market'))
const LogCenter = lazy(() => import('@/pages/System/LogCenter'))
const SystemConfig = lazy(() => import('@/pages/SystemConfig'))
const DataSourceMonitor = lazy(() => import('@/pages/Monitor/DataSourceMonitor'))
const CacheSystem = lazy(() => import('@/pages/Monitor/CacheSystem'))
const PerformanceAnalytics = lazy(() => import('@/pages/Monitor/PerformanceAnalytics'))
const AlertManager = lazy(() => import('@/pages/Monitor/AlertManager'))
const ComponentManager = lazy(() => import('@/pages/Monitor/ComponentManager'))
const DataExplorer = lazy(() => import('@/pages/DataSource/Explorer'))
const CapabilityMatrix = lazy(() => import('@/pages/DataSource/CapabilityMatrix'))
const DataPlayground = lazy(() => import('@/pages/Playground/DataPlayground'))
const NotFound = lazy(() => import('@/pages/NotFound'))

const PageLoading: React.FC = () => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh'
    }}
  >
    <Spin size="large" tip="加载中..." />
  </div>
)

const RouteWrapper: React.FC<{ element: React.LazyExoticComponent<React.ComponentType<any>> }> = ({ element: Element }) => (
  <ErrorBoundary>
    <Suspense fallback={<PageLoading />}>
      <Element />
    </Suspense>
  </ErrorBoundary>
)

const routes: RouteObject[] = [
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />
      },
      {
        path: 'dashboard',
        element: <RouteWrapper element={Dashboard} />
      },
      {
        path: 'events',
        element: <RouteWrapper element={EventSystem} />
      },
      {
        path: 'market',
        element: <RouteWrapper element={MarketData} />
      },
      {
        path: 'system/logs',
        element: <RouteWrapper element={LogCenter} />
      },
      {
        path: 'system/config',
        element: <RouteWrapper element={SystemConfig} />
      },
      {
        path: 'monitor/datasource',
        element: <RouteWrapper element={DataSourceMonitor} />
      },
      {
        path: 'monitor/cache',
        element: <RouteWrapper element={CacheSystem} />
      },
      {
        path: 'monitor/performance',
        element: <RouteWrapper element={PerformanceAnalytics} />
      },
      {
        path: 'monitor/alert',
        element: <RouteWrapper element={AlertManager} />
      },
      {
        path: 'monitor/component',
        element: <RouteWrapper element={ComponentManager} />
      },
      {
        path: 'datasource/explorer',
        element: <RouteWrapper element={DataExplorer} />
      },
      {
        path: 'datasource/matrix',
        element: <RouteWrapper element={CapabilityMatrix} />
      },
      {
        path: 'dev/playground',
        element: <RouteWrapper element={DataPlayground} />
      },
      {
        // 保留旧路由，重定向到统一入口
        path: 'dev/miniqmt',
        element: <Navigate to="/dev/playground" replace />
      },
      {
        path: 'dev/amazingdata',
        element: <Navigate to="/dev/playground" replace />
      },
      {
        path: '*',
        element: <RouteWrapper element={NotFound} />
      }
    ]
  }
]

const router = createBrowserRouter(routes)

export default router
