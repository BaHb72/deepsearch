import React, { useState } from 'react'
import { ProLayout } from '@ant-design/pro-components'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  SettingOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  FundOutlined,
  MonitorOutlined,
  CloudServerOutlined,
  AlertOutlined,
  AppstoreOutlined,
  CodeOutlined,
  BugOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'

// 路由配置
const routes = {
  path: '/',
  routes: [
    {
      path: '/',
      name: '监控仪表板',
      icon: <DashboardOutlined />,
    },
    {
      path: '/events',
      name: '事件监控',
      icon: <UnorderedListOutlined />,
    },
    {
      path: '/market',
      name: '市场数据',
      icon: <FundOutlined />,
      // TODO: 实现以下子菜单功能
      // routes: [
      //   {
      //     path: '/market/overview',
      //     name: '市场总览',
      //     icon: <AreaChartOutlined />,
      //   },
      //   {
      //     path: '/market/realtime',
      //     name: '实时行情',
      //     icon: <BarChartOutlined />,
      //   },
      //   {
      //     path: '/market/analysis',
      //     name: '技术分析',
      //     icon: <LineChartOutlined />,
      //   },
      // ],
    },
    // TODO: 实现交易管理功能
    // {
    //   path: '/trading',
    //   name: '交易管理',
    //   icon: <LineChartOutlined />,
    //   routes: [
    //     {
    //       path: '/trading/strategies',
    //       name: '策略管理',
    //     },
    //     {
    //       path: '/trading/backtest',
    //       name: '策略回测',
    //     },
    //     {
    //       path: '/trading/positions',
    //       name: '持仓管理',
    //     },
    //     {
    //       path: '/trading/orders',
    //       name: '订单管理',
    //     },
    //   ],
    // },
    {
      path: '/monitor',
      name: '监控管理',
      icon: <MonitorOutlined />,
      routes: [
        {
          path: '/monitor/datasource',
          name: '数据源监控',
          icon: <CloudServerOutlined />,
        },
        {
          path: '/monitor/cache',
          name: '缓存系统',
          icon: <DatabaseOutlined />,
        },
        {
          path: '/monitor/performance',
          name: '性能分析',
          icon: <ThunderboltOutlined />,
        },
        {
          path: '/monitor/alert',
          name: '告警管理',
          icon: <AlertOutlined />,
        },
        {
          path: '/monitor/component',
          name: '组件管理',
          icon: <AppstoreOutlined />,
        },
      ],
    },
    {
      path: '/dev',
      name: '开发者工具',
      icon: <CodeOutlined />,
      routes: [
        {
          path: '/dev/components',
          name: '组件展示',
          icon: <AppstoreOutlined />,
        },
        {
          path: '/dev/api-debug',
          name: 'API调试',
          icon: <BugOutlined />,
        },
      ],
    },
    {
      path: '/system',
      name: '系统设置',
      icon: <SettingOutlined />,
      routes: [
        {
          path: '/system/config',
          name: '系统配置',
        },
        {
          path: '/system/logs',
          name: '系统日志',
          icon: <FileTextOutlined />,
        },
        // TODO: 实现用户管理功能
        // {
        //   path: '/system/users',
        //   name: '用户管理',
        //   icon: <UserOutlined />,
        // },
      ],
    },
  ],
}

const MainLayout = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <ConfigProvider>
      <ProLayout
        title="DeepSearch"
        logo="https://gw.alipayobjects.com/zos/rmsportal/KDpgvguMpGfqaHPjicRK.svg"
        layout="side"
        fixSiderbar
        fixedHeader
        siderWidth={240}
        collapsed={collapsed}
        onCollapse={setCollapsed}
        route={routes}
        location={{
          pathname: location.pathname,
        }}
        menuProps={{
          onClick: ({ key }) => navigate(key),
        }}
        menuItemRender={(item, dom) => (
          <Link to={item.path || '/'}>
            {dom}
          </Link>
        )}
        rightContentRender={() => (
          <div>
            <span>DeepSearch v1.0.0</span>
          </div>
        )}
        footerRender={() => (
          <div style={{ textAlign: 'center', color: 'rgba(0,0,0,0.45)' }}>
            DeepSearch ©2025
          </div>
        )}
      >
        {children || <Outlet />}
      </ProLayout>
    </ConfigProvider>
  )
}

export default React.memo(MainLayout)