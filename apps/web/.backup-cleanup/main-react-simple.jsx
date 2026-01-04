import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, Layout, Menu, Card, Typography, Space, Button, message } from 'antd'
import { DashboardOutlined, SettingOutlined, LineChartOutlined } from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'
import 'antd/dist/reset.css'

const { Header, Sider, Content } = Layout
const { Title, Text } = Typography

function App() {
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
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.08)'
          }}>
            <Title level={4} style={{ margin: 0 }}>
              DeepSearch React版本
            </Title>
            <Space>
              <Text type="secondary">React 18 + Ant Design 5</Text>
              <Button type="primary" onClick={() => window.location.reload()}>
                刷新
              </Button>
            </Space>
          </Header>
          <Content style={{ margin: '24px 16px' }}>
            <Card
              title="🎉 React版本成功运行！"
              style={{ maxWidth: 800, margin: '0 auto' }}
            >
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <div>
                  <Title level={3}>系统信息</Title>
                  <Text>这是一个使用React + Ant Design构建的量化交易系统前端。</Text>
                </div>

                <div>
                  <Title level={4}>技术栈</Title>
                  <ul>
                    <li>React 18 - 用户界面库</li>
                    <li>Ant Design 5 - UI组件库</li>
                    <li>Vite - 构建工具</li>
                    <li>Zustand - 状态管理</li>
                    <li>Axios - HTTP客户端</li>
                  </ul>
                </div>

                <div>
                  <Title level={4}>当前页面: {selectedKey}</Title>
                  <Text type="secondary">点击左侧菜单切换页面</Text>
                </div>

                <div>
                  <Title level={4}>访问地址</Title>
                  <Space>
                    <Text code>http://localhost:3003</Text>
                    <Button size="small" onClick={() => {
                      navigator.clipboard.writeText('http://localhost:3003')
                      message.success('已复制到剪贴板')
                    }}>
                      复制地址
                    </Button>
                  </Space>
                </div>
              </Space>
            </Card>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}

// 渲染应用
const container = document.getElementById('root')
if (container) {
  const root = ReactDOM.createRoot(container)
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
  console.log('✅ React应用已启动')
} else {
  console.error('❌ 找不到根元素 #root')
}
