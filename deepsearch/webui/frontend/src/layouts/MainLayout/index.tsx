import React, { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Space, Dropdown, Avatar, Badge, Switch, Typography } from 'antd'
import {
  DashboardOutlined,
  LineChartOutlined,
  TransactionOutlined,
  DatabaseOutlined,
  SettingOutlined,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
  BellOutlined,
  MoonOutlined,
  SunOutlined
} from '@ant-design/icons'
import { useTheme } from '@/contexts/ThemeContext'
import { useSystemStore } from '@/stores/system'
import './index.scss'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme, isDark } = useTheme()
  const systemStore = useSystemStore()
  
  const [collapsed, setCollapsed] = useState(false)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])

  // 菜单配置
  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '监控仪表板'
    },
    {
      key: '/market',
      icon: <LineChartOutlined />,
      label: '市场行情'
    },
    {
      key: '/trading',
      icon: <TransactionOutlined />,
      label: '交易管理'
    },
    {
      key: '/data-source',
      icon: <DatabaseOutlined />,
      label: '数据源管理'
    },
    {
      key: '/config',
      icon: <SettingOutlined />,
      label: '系统配置'
    },
    {
      key: '/logs',
      icon: <FileTextOutlined />,
      label: '日志查看'
    }
  ]

  // 用户菜单
  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心'
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录'
    }
  ]

  // 监听路由变化
  useEffect(() => {
    setSelectedKeys([location.pathname])
  }, [location])

  // 菜单点击处理
  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  // 用户菜单点击
  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      // 处理退出逻辑
      console.log('Logout')
    }
  }

  return (
    <Layout className="main-layout">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        className="layout-sider"
        width={240}
      >
        <div className="logo">
          <Title level={4} style={{ margin: 0, color: '#fff' }}>
            {collapsed ? 'DS' : 'DeepSearch'}
          </Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      
      <Layout className="site-layout">
        <Header className="layout-header">
          <div className="header-left">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              className="trigger"
            />
          </div>
          
          <div className="header-right">
            <Space size="middle">
              {/* 主题切换 */}
              <Switch
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
                checked={isDark}
                onChange={toggleTheme}
              />
              
              {/* 通知 */}
              <Badge count={systemStore.alerts?.length || 0} size="small">
                <Button
                  type="text"
                  icon={<BellOutlined />}
                  onClick={() => navigate('/logs')}
                />
              </Badge>
              
              {/* 用户菜单 */}
              <Dropdown
                menu={{ 
                  items: userMenuItems,
                  onClick: handleUserMenuClick
                }}
                placement="bottomRight"
              >
                <Space className="user-menu">
                  <Avatar icon={<UserOutlined />} />
                  <span>管理员</span>
                </Space>
              </Dropdown>
            </Space>
          </div>
        </Header>
        
        <Content className="layout-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout