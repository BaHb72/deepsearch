import React, {useCallback, useMemo} from 'react'
import {Outlet, useLocation, useNavigate} from 'react-router-dom'
import {App as AntApp, Badge, Button, Dropdown, Space, Switch, Tag, Tooltip,} from 'antd'
import {
    BellOutlined,
    DashboardOutlined,
    DatabaseOutlined,
    FileTextOutlined,
    LineChartOutlined,
    LogoutOutlined,
    MoonOutlined,
    ReloadOutlined,
    SettingOutlined,
    SunOutlined,
    TransactionOutlined,
    UserOutlined,
} from '@ant-design/icons'
import {ProLayout} from '@ant-design/pro-components'
import {useTheme} from '@/contexts/ThemeContext'
import {useSystemStore} from '@/stores'
import DataSourceSwitch from '@/components/common/DataSourceSwitch'
import {useRealtimeSource} from '@/contexts/RealtimeSourceContext'
import {formatDataSourceLabel} from '@/utils/dataSource'
import JobStatusIndicator from '@/components/common/JobStatusIndicator'
import './index.scss'

const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { toggleTheme, isDark } = useTheme()
  const systemStore = useSystemStore()
  const realtimeSource = useRealtimeSource()
  const { message } = AntApp.useApp()



  const route = useMemo(() => ({
    path: '/',
    routes: [
      {
        path: '/',
        name: '实时总览',
        icon: <DashboardOutlined />,
      },
      {
        path: '/market',
        name: '行情数据',
        icon: <LineChartOutlined />,
      },
      {
        path: '/events',
        name: '事件管理',
        icon: <TransactionOutlined />,
      },
      {
        path: '/monitor',
        name: '系统监控',
        icon: <DatabaseOutlined />,
        routes: [
          {
            path: '/monitor/datasource',
            name: '数据源监控',
          },
          {
            path: '/monitor/cache',
            name: '缓存系统',
          },
          {
            path: '/monitor/performance',
            name: '性能分析',
          },
          {
            path: '/monitor/alert',
            name: '告警管理',
          },
          {
            path: '/monitor/component',
            name: '组件管理',
          },
        ],
      },
      {
        path: '/system',
        name: '系统管理',
        icon: <SettingOutlined />,
        routes: [
          {
            path: '/system/config',
            name: '系统配置',
          },
          {
            path: '/system/logs',
            name: '日志查看',
            icon: <FileTextOutlined />,
          },
        ]
      },
    ],
  }), [])

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
    },
  ]

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      console.log('Logout')
    }
  }

  const handleRefreshRealtimeSource = useCallback(async () => {
    try {
      await realtimeSource.refreshStatus()
      message.success('已刷新数据源状态')
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error)
      message.error(text || '刷新数据源状态失败')
    }
  }, [message, realtimeSource])

  const handleGlobalSourceChange = useCallback(
    (next: string) => {
      realtimeSource.switchSource(next).catch(() => undefined)
    },
    [realtimeSource],
  )

  return (
    <div
      id="deepsearch-pro-layout"
      style={{
        height: '100vh',
      }}
    >
      <ProLayout
        title="DeepSearch"
        logo={null} // You can add a logo image here if available
        route={route}
        location={location}
        onMenuHeaderClick={() => navigate('/')}
        menuItemRender={(item, dom) => (
          <div
            onClick={() => {
              navigate(item.path || '/')
            }}
          >
            {dom}
          </div>
        )}
        avatarProps={{
          icon: <UserOutlined />,
          title: '管理员',
          render: (_, dom) => (
            <Dropdown
              menu={{
                items: userMenuItems,
                onClick: handleUserMenuClick,
              }}
            >
              {dom}
            </Dropdown>
          ),
        }}
        actionsRender={(props) => {
          if (props.isMobile) return []
          return [
            <Space key="source-control" size={8} style={{ marginRight: 16 }}>
              <Tooltip title="当前实时数据源">
                <Tag color="blue" style={{ margin: 0 }}>{formatDataSourceLabel(realtimeSource.activeSource)}</Tag>
              </Tooltip>
              <DataSourceSwitch
                size="small"
                sources={realtimeSource.availableSources}
                value={realtimeSource.activeSource}
                loading={realtimeSource.loading || realtimeSource.switching}
                onChange={handleGlobalSourceChange}
              />
              <Tooltip title="刷新数据源状态">
                <Button
                  type="text"
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={handleRefreshRealtimeSource}
                  loading={realtimeSource.loading}
                />
              </Tooltip>
            </Space>,
            <JobStatusIndicator key="job-status" />,
            <Switch
              key="theme-switch"
              checkedChildren={<MoonOutlined />}
              unCheckedChildren={<SunOutlined />}
              checked={isDark}
              onChange={(checked) => toggleTheme(checked)}
              style={{ marginLeft: 8 }}
            />,
            <Badge key="alerts" count={systemStore.alerts?.length || 0} size="small" style={{ marginLeft: 8 }}>
              <Button
                type="text"
                icon={<BellOutlined />}
                onClick={() => navigate('/system/logs')}
              />
            </Badge>,
          ]
        }}
        token={{
            header: {
                colorBgHeader: 'rgba(255, 255, 255, 0.8)',
                colorHeaderTitle: '#1f1f1f',
                heightLayoutHeader: 56,
            },
            sider: {
                colorMenuBackground: '#ffffff',
                colorMenuItemDivider: '#f0f0f0',
                colorTextMenu: '#595959',
                colorTextMenuSelected: '#3e79f7',
                colorBgMenuItemSelected: 'rgba(62, 121, 247, 0.08)',
                colorBgMenuItemHover: 'rgba(0, 0, 0, 0.03)',
            },
            bgLayout: '#f4f6f9',
        }}
        fixSiderbar
        layout="mix"
        splitMenus={false}
      >
          <div style={{padding: 24, minHeight: '100%'}}>
              <Outlet/>
          </div>
      </ProLayout>
    </div>
  )
}

export default MainLayout
