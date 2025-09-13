import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import App from '../App-react'

// 懒加载组件
const Dashboard = lazy(() => import('../views/react/Dashboard'))
const Events = lazy(() => import('../views/react/Events'))
const Config = lazy(() => import('../views/react/Config'))
const Logs = lazy(() => import('../views/react/Logs'))
const Trading = lazy(() => import('../views/react/Trading'))
const DataManagement = lazy(() => import('../views/react/DataManagement'))
const DataSource = lazy(() => import('../views/react/DataSource'))
const DataSourceMonitor = lazy(() => import('../views/react/DataSourceMonitor'))
const Market = lazy(() => import('../views/react/Market'))
const MarketOverview = lazy(() => import('../views/react/MarketOverview'))
const ProfessionalTradingView = lazy(() => import('../views/react/ProfessionalTradingView'))
const WorkersProxy = lazy(() => import('../views/react/WorkersProxy'))
const SystemConfig = lazy(() => import('../pages/SystemConfig'))

// Loading 组件
const PageLoading = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh' 
  }}>
    <Spin size="large" tip="加载中..." />
  </div>
)

// 路由懒加载包装器
const LazyRoute = ({ Component }) => (
  <Suspense fallback={<PageLoading />}>
    <Component />
  </Suspense>
)

// 路由配置
export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <LazyRoute Component={Dashboard} />
      },
      {
        path: 'events',
        element: <LazyRoute Component={Events} />
      },
      {
        path: 'config',
        element: <LazyRoute Component={Config} />
      },
      {
        path: 'logs',
        element: <LazyRoute Component={Logs} />
      },
      {
        path: 'trading',
        element: <LazyRoute Component={Trading} />
      },
      {
        path: 'data',
        element: <LazyRoute Component={DataManagement} />
      },
      {
        path: 'data-source',
        element: <LazyRoute Component={DataSource} />
      },
      {
        path: 'data-source-monitor',
        element: <LazyRoute Component={DataSourceMonitor} />
      },
      {
        path: 'market',
        element: <LazyRoute Component={Market} />
      },
      {
        path: 'market-overview',
        element: <LazyRoute Component={MarketOverview} />
      },
      {
        path: 'pro-trading',
        element: <LazyRoute Component={ProfessionalTradingView} />
      },
      {
        path: 'workers-proxy',
        element: <LazyRoute Component={WorkersProxy} />
      },
      {
        path: 'system',
        children: [
          {
            path: 'config',
            element: <LazyRoute Component={SystemConfig} />
          }
        ]
      },
      {
        path: '*',
        element: <Navigate to="/" replace />
      }
    ]
  }
])

export default router