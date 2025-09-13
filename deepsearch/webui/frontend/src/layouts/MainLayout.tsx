import React, { useState } from 'react'
import { ProLayout } from '@ant-design/pro-components'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  SettingOutlined,
  FileTextOutlined,
  LineChartOutlined,
  DatabaseOutlined,
  ApiOutlined,
  EyeOutlined,
  FundOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  SyncOutlined,
  UserOutlined,
  GithubOutlined
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
      routes: [
        {
          path: '/market/overview',
          name: '市场总览',
          icon: <AreaChartOutlined />,
        },
        {
          path: '/market/realtime',
          name: '实时行情',
          icon: <BarChartOutlined />,
        },
        {
          path: '/market/analysis',
          name: '技术分析',
          icon: <LineChartOutlined />,
        },
      ],
    },
    {
      path: '/trading',
      name: '交易管理',
      icon: <LineChartOutlined />,
      routes: [
        {
          path: '/trading/strategies',
          name: '策略管理',
        },
        {
          path: '/trading/backtest',
          name: '策略回测',
        },
        {
          path: '/trading/positions',
          name: '持仓管理',
        },
        {
          path: '/trading/orders',
          name: '订单管理',
        },
      ],
    },
    {
      path: '/data',
      name: '数据管理',
      icon: <DatabaseOutlined />,
      routes: [
        {
          path: '/data-source',
          name: '数据源配置',
          icon: <ApiOutlined />,
        },
        {
          path: '/data-source-monitor',
          name: '数据源监控',
          icon: <EyeOutlined />,
        },
        {
          path: '/data/sync',
          name: '数据同步',
          icon: <SyncOutlined />,
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
        {
          path: '/system/users',
          name: '用户管理',
          icon: <UserOutlined />,
        },
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
            DeepSearch ©2025 | <GithubOutlined /> GitHub
          </div>
        )}
      >
        {children || <Outlet />}
      </ProLayout>
    </ConfigProvider>
  )
}

export default React.memo(MainLayout)