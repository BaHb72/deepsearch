import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouteObject } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import ErrorBoundary from '@/components/common/ErrorBoundary'

// 懒加载页面组件
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Market = lazy(() => import('@/pages/Market'))
const Trading = lazy(() => import('@/pages/Trading'))
const DataSource = lazy(() => import('@/pages/DataSource'))
const Config = lazy(() => import('@/pages/Config'))
const Logs = lazy(() => import('@/pages/Logs'))
const NotFound = lazy(() => import('@/pages/NotFound'))

// 加载中组件
const PageLoading: React.FC = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh' 
  }}>
    <Spin size="large" tip="加载中..." />
  </div>
)

// 路由包装器，添加错误边界和懒加载
const RouteWrapper: React.FC<{ element: React.LazyExoticComponent<any> }> = ({ element: Element }) => (
  <ErrorBoundary>
    <Suspense fallback={<PageLoading />}>
      <Element />
    </Suspense>
  </ErrorBoundary>
)

// 路由配置
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
        path: 'market',
        element: <RouteWrapper element={Market} />
      },
      {
        path: 'trading',
        element: <RouteWrapper element={Trading} />
      },
      {
        path: 'data-source',
        element: <RouteWrapper element={DataSource} />
      },
      {
        path: 'config',
        element: <RouteWrapper element={Config} />
      },
      {
        path: 'logs',
        element: <RouteWrapper element={Logs} />
      },
      {
        path: '*',
        element: <RouteWrapper element={NotFound} />
      }
    ]
  }
]

// 创建路由器
const router = createBrowserRouter(routes)

export default router