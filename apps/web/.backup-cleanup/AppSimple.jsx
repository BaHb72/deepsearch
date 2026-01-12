import React from 'react'
import { ConfigProvider, Layout, Menu, Card, Typography, Space, Button, message } from 'antd'
import { DashboardOutlined, SettingOutlined, LineChartOutlined } from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'
// import './styles/global-react.scss'

const { Header, Sider, Content } = Layout
const { Title, Text } = Typography

function AppSimple() {
  const [collapsed, setCollapsed] = React.useState(false)
  const [selectedKey, setSelectedKey] = React.useState('dashboard')

  const menuItems = [
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: '仪表板',
    },
    {
      key: 'market',
      icon: <LineChartOutlined />,
      label: '市场行情',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ]

  const handleMenuClick = ({ key }) => {
    setSelectedKey(key)
    message.info(`切换到: ${key}`)
  }

  return (
    <ConfigProvider locale={zhCN}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="dark"
        >
          <div style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 18,
            fontWeight: 'bold'
          }}>
            {collapsed ? 'DS' : 'DeepSearch'}
          </div>
          <Menu
            theme="dark"
            selectedKeys={[selectedKey]}
            mode="inline"
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>
        <Layout>
          <Header style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <Title level={4} style={{ margin: 0 }}>
              DeepSearch React版本
            </Title>
            <Space>
              <Text type="secondary">欢迎使用React版本</Text>
              <Button type="primary">刷新</Button>
            </Space>
          </Header>
          <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
            <Card title="欢迎使用DeepSearch React版本">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <div>
                  <Title level={3}>系统信息</Title>
                  <Text>这是一个使用React + Ant Design构建的量化交易系统前端。</Text>
                </div>

                <div>
                  <Title level={4}>技术栈</Title>
                  <ul>
                    <li>React 18</li>
                    <li>Ant Design 5</li>
                    <li>Vite</li>
                    <li>Zustand</li>
                  </ul>
                </div>

                <div>
                  <Title level={4}>当前页面: {selectedKey}</Title>
                  <Text type="secondary">点击左侧菜单切换页面</Text>
                </div>
              </Space>
            </Card>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}

export default AppSimple
