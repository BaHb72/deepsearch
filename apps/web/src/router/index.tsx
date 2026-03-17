import React, { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouteObject } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import {
  DEFAULT_HOME_PATH,
  PAGE_ROUTE_DEFINITIONS,
  REDIRECT_ROUTE_DEFINITIONS,
  toChildRoutePath,
  type RouteComponentKey,
} from '@/router/manifest'

const Dashboard = lazy(() => import('@/pages/dashboard'))
const EventSystem = lazy(() => import('@/pages/EventSystem'))
const MarketData = lazy(() => import('@/pages/market'))
const StrategyGenerator = lazy(() => import('@/pages/Strategy/Generator'))
const StrategyScreener = lazy(() => import('@/pages/Strategy/Screener'))
const StrategyTTrading = lazy(() => import('@/pages/Strategy/TTrading'))
const LogCenter = lazy(() => import('@/pages/System/LogCenter'))
const MemoryManagement = lazy(() => import('@/pages/System/MemoryManagement'))
const SystemConfig = lazy(() => import('@/pages/SystemConfig'))
const NotificationCenter = lazy(() => import('@/pages/NotificationCenter'))
const MarketMonitor = lazy(() => import('@/pages/Monitor/MarketMonitor'))
const DataSourceMonitor = lazy(() => import('@/pages/Monitor/DataSourceMonitor'))
const CacheSystem = lazy(() => import('@/pages/Monitor/CacheSystem'))
const PerformanceAnalytics = lazy(() => import('@/pages/Monitor/PerformanceAnalytics'))
const AlertManager = lazy(() => import('@/pages/Monitor/AlertManager'))
const ComponentManager = lazy(() => import('@/pages/Monitor/ComponentManager'))
const ConceptMonitor = lazy(() => import('@/pages/ConceptMonitor'))
const DataExplorer = lazy(() => import('@/pages/DataSource/Explorer'))
const CapabilityMatrix = lazy(() => import('@/pages/DataSource/CapabilityMatrix'))
const DataPlayground = lazy(() => import('@/pages/Playground/DataPlayground'))
const TTradingLegacyPage = lazy(() => import('@/pages/Trading/TTradingPage'))
const NotFound = lazy(() => import('@/pages/NotFound'))

const COMPONENT_MAP: Record<RouteComponentKey, React.LazyExoticComponent<React.ComponentType<any>>> = {
  dashboard: Dashboard,
  events: EventSystem,
  market: MarketData,
  strategy_generator: StrategyGenerator,
  strategy_screener: StrategyScreener,
  strategy_ttrading: StrategyTTrading,
  monitor_market: MarketMonitor,
  monitor_datasource: DataSourceMonitor,
  monitor_cache: CacheSystem,
  monitor_performance: PerformanceAnalytics,
  monitor_alert: AlertManager,
  monitor_component: ComponentManager,
  monitor_concept: ConceptMonitor,
  system_config: SystemConfig,
  notification_center: NotificationCenter,
  system_logs: LogCenter,
  system_memory: MemoryManagement,
  datasource_explorer: DataExplorer,
  datasource_matrix: CapabilityMatrix,
  dev_playground: DataPlayground,
  ttrading_legacy: TTradingLegacyPage,
}

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

const children: RouteObject[] = [
  {
    index: true,
    element: <Navigate to={DEFAULT_HOME_PATH} replace />
  },
  ...PAGE_ROUTE_DEFINITIONS.map((route) => {
    const Component = COMPONENT_MAP[route.component]
    return {
      path: toChildRoutePath(route.path, route.wildcard),
      element: <RouteWrapper element={Component} />
    } satisfies RouteObject
  }),
  ...REDIRECT_ROUTE_DEFINITIONS.map((route) => ({
    path: toChildRoutePath(route.path),
    element: <Navigate to={route.redirectTo} replace />
  })),
  {
    path: '*',
    element: <RouteWrapper element={NotFound} />
  },
]

const routes: RouteObject[] = [
  {
    path: '/',
    element: <MainLayout />,
    children,
  }
]

const router = createBrowserRouter(routes)

export default router
