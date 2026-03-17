import { createElement, type ReactNode } from 'react'
import {
  CodeOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FlagOutlined,
  LineChartOutlined,
  SettingOutlined,
} from '@ant-design/icons'

export const APP_PATHS = {
  root: '/',
  dashboard: '/dashboard',
  events: '/events',
  market: '/market',
  aliasMarket: '/02',
  aliasScreener: '/03',
  strategy: '/strategy',
  strategyManager: '/strategy/manager',
  strategyComposite: '/strategy/composite',
  strategyScreener: '/strategy/screener',
  strategyTTrading: '/strategy/ttrading',
  strategyBacktest: '/strategy/backtest',
  strategyGeneratorLegacy: '/strategy/generator',
  monitor: '/monitor',
  monitorMarket: '/monitor/market',
  monitorDataSource: '/monitor/datasource',
  monitorCache: '/monitor/cache',
  monitorPerformance: '/monitor/performance',
  monitorAlert: '/monitor/alert',
  monitorComponent: '/monitor/component',
  monitorConcept: '/monitor/concept',
  system: '/system',
  systemConfig: '/system/config',
  systemNotificationCenter: '/system/notification-center',
  systemLogs: '/system/logs',
  systemMemory: '/system/memory',
  dataSource: '/datasource',
  dataSourceExplorer: '/datasource/explorer',
  dataSourceMatrix: '/datasource/matrix',
  dev: '/dev',
  devPlayground: '/dev/playground',
  devTTradingLegacy: '/dev/ttrading-legacy',
  devAmazingDataLegacy: '/dev/amazingdata',
  devMiniQmtLegacy: '/dev/miniqmt',
} as const

export const DEFAULT_HOME_PATH = APP_PATHS.dashboard

export type RouteComponentKey =
  | 'dashboard'
  | 'events'
  | 'market'
  | 'strategy_generator'
  | 'strategy_screener'
  | 'strategy_ttrading'
  | 'monitor_market'
  | 'monitor_datasource'
  | 'monitor_cache'
  | 'monitor_performance'
  | 'monitor_alert'
  | 'monitor_component'
  | 'monitor_concept'
  | 'system_config'
  | 'notification_center'
  | 'system_logs'
  | 'system_memory'
  | 'datasource_explorer'
  | 'datasource_matrix'
  | 'dev_playground'
  | 'ttrading_legacy'

export type MenuGroupKey = 'overview' | 'market' | 'strategy' | 'monitor' | 'system' | 'dev'

type IconKey =
  | 'dashboard'
  | 'market'
  | 'strategy'
  | 'monitor'
  | 'system'
  | 'dev'
  | 'logs'

interface MenuRouteMeta {
  group: MenuGroupKey
  title: string
  order: number
  iconKey?: IconKey
}

interface BaseRouteDefinition {
  id: string
  path: string
  wildcard?: boolean
  menu?: MenuRouteMeta
}

export interface PageRouteDefinition extends BaseRouteDefinition {
  type: 'page'
  component: RouteComponentKey
}

export interface RedirectRouteDefinition extends BaseRouteDefinition {
  type: 'redirect'
  redirectTo: string
  legacy?: boolean
}

export type AppRouteDefinition = PageRouteDefinition | RedirectRouteDefinition

interface MenuGroupDefinition {
  id: MenuGroupKey
  name: string
  path: string
  order: number
  iconKey: IconKey
  standalone?: boolean
}

const MENU_GROUPS: MenuGroupDefinition[] = [
  {
    id: 'overview',
    name: '实时总览',
    path: APP_PATHS.dashboard,
    order: 10,
    iconKey: 'dashboard',
    standalone: true,
  },
  {
    id: 'market',
    name: '行情',
    path: APP_PATHS.market,
    order: 20,
    iconKey: 'market',
  },
  {
    id: 'strategy',
    name: '策略',
    path: APP_PATHS.strategy,
    order: 30,
    iconKey: 'strategy',
  },
  {
    id: 'monitor',
    name: '监控',
    path: APP_PATHS.monitor,
    order: 40,
    iconKey: 'monitor',
  },
  {
    id: 'system',
    name: '系统',
    path: APP_PATHS.system,
    order: 50,
    iconKey: 'system',
  },
  {
    id: 'dev',
    name: '开发工具',
    path: APP_PATHS.dev,
    order: 60,
    iconKey: 'dev',
  },
]

export const APP_ROUTE_DEFINITIONS: AppRouteDefinition[] = [
  {
    id: 'dashboard',
    type: 'page',
    path: APP_PATHS.dashboard,
    component: 'dashboard',
    menu: { group: 'overview', title: '实时总览', order: 10 },
  },
  {
    id: 'events',
    type: 'page',
    path: APP_PATHS.events,
    component: 'events',
    menu: { group: 'monitor', title: '事件系统', order: 20 },
  },
  {
    id: 'market',
    type: 'page',
    path: APP_PATHS.market,
    wildcard: true,
    component: 'market',
    menu: { group: 'market', title: '行情看盘', order: 10 },
  },
  {
    id: 'strategy_manager',
    type: 'page',
    path: APP_PATHS.strategyManager,
    component: 'strategy_generator',
    menu: { group: 'strategy', title: '策略管理', order: 10 },
  },
  {
    id: 'strategy_composite',
    type: 'page',
    path: APP_PATHS.strategyComposite,
    component: 'strategy_generator',
    menu: { group: 'strategy', title: '策略组合', order: 20 },
  },
  {
    id: 'strategy_screener',
    type: 'page',
    path: APP_PATHS.strategyScreener,
    component: 'strategy_screener',
    menu: { group: 'strategy', title: '智能选股', order: 30 },
  },
  {
    id: 'strategy_ttrading',
    type: 'page',
    path: APP_PATHS.strategyTTrading,
    component: 'strategy_ttrading',
    menu: { group: 'strategy', title: '日内做T', order: 40 },
  },
  {
    id: 'strategy_backtest',
    type: 'page',
    path: APP_PATHS.strategyBacktest,
    component: 'strategy_generator',
    menu: { group: 'strategy', title: '策略回测', order: 50 },
  },
  {
    id: 'monitor_market',
    type: 'page',
    path: APP_PATHS.monitorMarket,
    component: 'monitor_market',
    menu: { group: 'market', title: '市场监控', order: 20 },
  },
  {
    id: 'monitor_datasource',
    type: 'page',
    path: APP_PATHS.monitorDataSource,
    component: 'monitor_datasource',
    menu: { group: 'monitor', title: '数据源监控', order: 10 },
  },
  {
    id: 'monitor_cache',
    type: 'page',
    path: APP_PATHS.monitorCache,
    component: 'monitor_cache',
    menu: { group: 'monitor', title: '缓存系统', order: 30 },
  },
  {
    id: 'monitor_performance',
    type: 'page',
    path: APP_PATHS.monitorPerformance,
    component: 'monitor_performance',
    menu: { group: 'monitor', title: '性能分析', order: 40 },
  },
  {
    id: 'monitor_alert',
    type: 'page',
    path: APP_PATHS.monitorAlert,
    component: 'monitor_alert',
    menu: { group: 'monitor', title: '告警管理', order: 50 },
  },
  {
    id: 'monitor_component',
    type: 'page',
    path: APP_PATHS.monitorComponent,
    component: 'monitor_component',
    menu: { group: 'monitor', title: '组件管理', order: 60 },
  },
  {
    id: 'monitor_concept',
    type: 'page',
    path: APP_PATHS.monitorConcept,
    component: 'monitor_concept',
    menu: { group: 'monitor', title: '概念监控', order: 25 },
  },
  {
    id: 'system_config',
    type: 'page',
    path: APP_PATHS.systemConfig,
    component: 'system_config',
    menu: { group: 'system', title: '系统配置', order: 10 },
  },
  {
    id: 'datasource_explorer',
    type: 'page',
    path: APP_PATHS.dataSourceExplorer,
    component: 'datasource_explorer',
    menu: { group: 'system', title: '数据源浏览器', order: 20 },
  },
  {
    id: 'datasource_matrix',
    type: 'page',
    path: APP_PATHS.dataSourceMatrix,
    component: 'datasource_matrix',
    menu: { group: 'system', title: '能力矩阵对比', order: 30 },
  },
  {
    id: 'system_notification_center',
    type: 'page',
    path: APP_PATHS.systemNotificationCenter,
    component: 'notification_center',
    menu: { group: 'system', title: '通知中心', order: 35 },
  },
  {
    id: 'system_logs',
    type: 'page',
    path: APP_PATHS.systemLogs,
    component: 'system_logs',
    menu: { group: 'system', title: '日志查看', order: 40, iconKey: 'logs' },
  },
  {
    id: 'system_memory',
    type: 'page',
    path: APP_PATHS.systemMemory,
    component: 'system_memory',
    menu: { group: 'system', title: '内存管理', order: 50 },
  },
  {
    id: 'dev_playground',
    type: 'page',
    path: APP_PATHS.devPlayground,
    component: 'dev_playground',
    menu: { group: 'dev', title: '数据调试台', order: 10 },
  },
  {
    id: 'dev_ttrading_legacy',
    type: 'page',
    path: APP_PATHS.devTTradingLegacy,
    component: 'ttrading_legacy',
    menu: { group: 'dev', title: '做T旧版', order: 20 },
  },
  {
    id: 'alias_02',
    type: 'redirect',
    path: APP_PATHS.aliasMarket,
    redirectTo: APP_PATHS.market,
    legacy: true,
  },
  {
    id: 'alias_03',
    type: 'redirect',
    path: APP_PATHS.aliasScreener,
    redirectTo: APP_PATHS.strategyScreener,
    legacy: true,
  },
  {
    id: 'strategy_root_redirect',
    type: 'redirect',
    path: APP_PATHS.strategy,
    redirectTo: APP_PATHS.strategyScreener,
  },
  {
    id: 'strategy_generator_legacy_redirect',
    type: 'redirect',
    path: APP_PATHS.strategyGeneratorLegacy,
    redirectTo: APP_PATHS.strategyBacktest,
    legacy: true,
  },
  {
    id: 'monitor_root_redirect',
    type: 'redirect',
    path: APP_PATHS.monitor,
    redirectTo: APP_PATHS.monitorMarket,
  },
  {
    id: 'system_root_redirect',
    type: 'redirect',
    path: APP_PATHS.system,
    redirectTo: APP_PATHS.systemConfig,
  },
  {
    id: 'datasource_root_redirect',
    type: 'redirect',
    path: APP_PATHS.dataSource,
    redirectTo: APP_PATHS.dataSourceExplorer,
  },
  {
    id: 'dev_root_redirect',
    type: 'redirect',
    path: APP_PATHS.dev,
    redirectTo: APP_PATHS.devPlayground,
  },
  {
    id: 'dev_amazing_legacy_redirect',
    type: 'redirect',
    path: APP_PATHS.devAmazingDataLegacy,
    redirectTo: APP_PATHS.devPlayground,
    legacy: true,
  },
  {
    id: 'dev_miniqmt_legacy_redirect',
    type: 'redirect',
    path: APP_PATHS.devMiniQmtLegacy,
    redirectTo: APP_PATHS.devPlayground,
    legacy: true,
  },
]

export const PAGE_ROUTE_DEFINITIONS: PageRouteDefinition[] = APP_ROUTE_DEFINITIONS.filter(
  (route): route is PageRouteDefinition => route.type === 'page'
)

export const REDIRECT_ROUTE_DEFINITIONS: RedirectRouteDefinition[] = APP_ROUTE_DEFINITIONS.filter(
  (route): route is RedirectRouteDefinition => route.type === 'redirect'
)

export function toChildRoutePath(path: string, wildcard = false): string {
  const normalized = path.startsWith('/') ? path.slice(1) : path
  if (!normalized) return normalized
  return wildcard ? `${normalized}/*` : normalized
}

function resolveIcon(iconKey: IconKey): ReactNode {
  switch (iconKey) {
    case 'dashboard':
      return createElement(DashboardOutlined)
    case 'market':
      return createElement(LineChartOutlined)
    case 'strategy':
      return createElement(FlagOutlined)
    case 'monitor':
      return createElement(DatabaseOutlined)
    case 'system':
      return createElement(SettingOutlined)
    case 'dev':
      return createElement(CodeOutlined)
    case 'logs':
      return createElement(FileTextOutlined)
    default:
      return undefined
  }
}

interface MenuRouteNode {
  path: string
  name: string
  icon?: ReactNode
  routes?: MenuRouteNode[]
}

interface MenuRouteTree {
  path: string
  routes: MenuRouteNode[]
}

export function buildMenuRouteTree(): MenuRouteTree {
  const menuPages = PAGE_ROUTE_DEFINITIONS
    .filter((route) => route.menu)
    .map((route) => ({
      path: route.path,
      title: route.menu!.title,
      group: route.menu!.group,
      order: route.menu!.order,
      iconKey: route.menu!.iconKey,
    }))

  const grouped = new Map<MenuGroupKey, typeof menuPages>()
  menuPages.forEach((entry) => {
    const entries = grouped.get(entry.group) ?? []
    entries.push(entry)
    grouped.set(entry.group, entries)
  })

  const routes: MenuRouteNode[] = []
  MENU_GROUPS
    .slice()
    .sort((a, b) => a.order - b.order)
    .forEach((group) => {
      const entries = (grouped.get(group.id) ?? []).slice().sort((a, b) => a.order - b.order)
      if (!entries.length) return

      if (group.standalone) {
        const landing = entries.find((entry) => entry.path === group.path) ?? entries[0]
        routes.push({
          path: landing.path,
          name: landing.title,
          icon: resolveIcon(group.iconKey),
        })
        return
      }

      const children = entries
        .filter((entry) => entry.path !== group.path)
        .map((entry) => ({
          path: entry.path,
          name: entry.title,
          icon: entry.iconKey ? resolveIcon(entry.iconKey) : undefined,
        }))

      routes.push({
        path: group.path,
        name: group.name,
        icon: resolveIcon(group.iconKey),
        routes: children.length ? children : undefined,
      })
    })

  return {
    path: APP_PATHS.root,
    routes,
  }
}
