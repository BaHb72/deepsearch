import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouteObject } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import ErrorBoundary from '@/components/common/ErrorBoundary'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const EventSystem = lazy(() => import('@/pages/EventSystem'))
const MarketData = lazy(() => import('@/pages/MarketData'))
const LogCenter = lazy(() => import('@/pages/LogCenter'))
const SystemConfig = lazy(() => import('@/pages/SystemConfig'))
const DataSourceMonitor = lazy(() => import('@/pages/DataSourceMonitor'))
const CacheSystem = lazy(() => import('@/pages/CacheSystem'))
const PerformanceAnalytics = lazy(() => import('@/pages/PerformanceAnalytics'))
const AlertManager = lazy(() => import('@/pages/AlertManager'))
const ComponentManager = lazy(() => import('@/pages/ComponentManager'))
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
        path: '*',
        element: <RouteWrapper element={NotFound} />
      }
    ]
  }
]

const router = createBrowserRouter(routes)

export default router
