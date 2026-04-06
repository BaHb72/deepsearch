import React, { useEffect, useMemo, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Alert, Badge, Button, Dropdown, Switch, } from 'antd'
import {
  BellOutlined,
  LogoutOutlined,
  MoonOutlined,
  SunOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { ProLayout } from '@ant-design/pro-components'
import { useTheme } from '@/contexts/ThemeContext'
import { useSystemStore } from '@/stores'
import { buildMenuRouteTree } from '@/router/manifest'
// import { useRealtimeSource } from '@/contexts/RealtimeSourceContext' // TODO: 准备用于数据源切换
import JobStatusIndicator from '@/components/common/JobStatusIndicator'
import backendStatus from '@/utils/backendStatus'
import './index.scss'

const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { toggleTheme, isDark } = useTheme()
  const systemStore = useSystemStore()
  const [backendAvailability, setBackendAvailability] = useState(
    backendStatus.getAvailabilityState?.() || 'unknown'
  )
  const [backendReason, setBackendReason] = useState('')
  // const realtimeSource = useRealtimeSource() // TODO: 准备用于数据源切换
  // const { message } = AntApp.useApp() // TODO: 准备用于数据源切换

  const route = useMemo(() => buildMenuRouteTree(), [])
  const backendTarget = backendStatus.getBackendTarget?.() || (import.meta.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000')

  useEffect(() => {
    const syncBackendState = () => {
      setBackendAvailability(backendStatus.getAvailabilityState?.() || 'unknown')
      const stats = backendStatus.getStatistics?.()
      setBackendReason(stats?.lastReason || '')
    }

    syncBackendState()
    const onBackendStatus = () => syncBackendState()
    backendStatus.addListener(onBackendStatus)
    const timer = window.setInterval(syncBackendState, 5000)

    return () => {
      backendStatus.removeListener(onBackendStatus)
      window.clearInterval(timer)
    }
  }, [])

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
  // TODO: 这些函数准备用于数据源切换功能，暂时注释
  // const handleRefreshRealtimeSource = useCallback(async () => {
  //   try {
  //     await realtimeSource.refreshStatus()
  //     message.success('已刷新数据源状态')
  //   } catch (error) {
  //     const text = error instanceof Error ? error.message : String(error)
  //     message.error(text || '刷新数据源状态失败')
  //   }
  // }, [message, realtimeSource])
  //
  // const handleGlobalSourceChange = useCallback(
  //   (next: string) => {
  //     realtimeSource.switchSource(next).catch(() => undefined)
  //   },
  //   [realtimeSource],
  // )

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
        <div style={{ padding: 24, minHeight: '100%' }}>
          {backendAvailability !== 'available' && (
            <Alert
              type="warning"
              showIcon
              banner
              style={{ marginBottom: 12 }}
              message={`后端未就绪（状态：${backendAvailability}）`}
              description={`代理目标 ${backendTarget}。请先启动后端：uv run deepsearch run dev --no-frontend${backendReason ? `；最近原因：${backendReason}` : ''}`}
            />
          )}
          <Outlet />
        </div>
      </ProLayout>
    </div>
  )
}

export default MainLayout
