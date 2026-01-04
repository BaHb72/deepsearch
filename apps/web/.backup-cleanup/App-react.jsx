import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Layout, Menu, Space, Button, Tag, Switch, Modal, message, Spin } from 'antd'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
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
  LinkOutlined,
  MoonOutlined,
  SunOutlined
} from '@ant-design/icons'
import { useSystemStore } from './stores/systemStore'
import { startSystem, stopSystem, restartSystem } from './api/system'
import { storage, STORAGE_KEYS } from './utils/storage'
import ErrorMonitor from './components/react/ErrorMonitor'
import PageTransition from './components/react/PageTransition'
import backendStatus from './utils/backendStatus'
import './styles/app-react.scss'

const { Header, Sider, Content } = Layout

// 菜单项配置
const menuItems = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: '监控仪表板'
  },
  {
    key: '/events',
    icon: <UnorderedListOutlined />,
    label: '事件监控'
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
  },
  {
    key: '/trading',
    icon: <LineChartOutlined />,
    label: '策略回测'
  },
  {
    key: '/data',
    icon: <DatabaseOutlined />,
    label: '数据管理'
  },
  {
    key: '/data-source',
    icon: <ApiOutlined />,
    label: '数据源配置'
  },
  {
    key: '/data-source-monitor',
    icon: <EyeOutlined />,
    label: '数据源监控'
  },
  {
    key: '/market',
    icon: <FundOutlined />,
    label: '市场数据'
  },
  {
    key: '/market-overview',
    icon: <AreaChartOutlined />,
    label: '市场总貌'
  },
  {
    key: '/pro-trading',
    icon: <BarChartOutlined />,
    label: '市场行情'
  },
  {
    key: '/workers-proxy',
    icon: <LinkOutlined />,
    label: 'Workers 代理'
  }
]

// 页面标题映射
const pageTitles = {
  '/': '监控仪表板',
  '/events': '事件监控',
  '/config': '系统配置',
  '/logs': '日志查看',
  '/trading': '策略回测',
  '/pro-trading': '市场行情',
  '/market': '市场数据',
  '/market-overview': '市场总貌',
  '/data': '数据管理',
  '/data-source': '数据源监控',
  '/data-source-monitor': '数据源监控',
  '/workers-proxy': 'Workers 代理'
}

// 调试日志工具
const debugLog = (stage, message, data = null) => {
  const timestamp = new Date().toISOString()
  const logEntry = `[App-react.jsx ${timestamp}] ${stage}: ${message}`
  console.log('%c' + logEntry, 'color: #1890ff; font-weight: bold;', data)
}

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const systemStore = useSystemStore()

  // 状态
  const [collapsed, setCollapsed] = useState(false)
  const [isDark, setIsDark] = useState(false)
  const [systemLoading, setSystemLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [pauseStatusPolling, setPauseStatusPolling] = useState(false)

  // Refs
  const statusTimerRef = useRef(null)

  // 计算属性
  const activeMenu = location.pathname
  const pageTitle = pageTitles[location.pathname] || 'DeepSearch'

  const systemStatus = (() => {
    try {
      if (systemStore.status?.engine?.running) {
        return { type: 'success', text: '系统运行中', running: true }
      }
    } catch (e) {
      console.warn('获取系统状态失败:', e)
    }
    return { type: 'default', text: '系统已停止', running: false }
  })()

  // 切换主题
  const toggleTheme = useCallback((checked) => {
    setIsDark(checked)
    if (checked) {
      document.documentElement.classList.add('dark')
      storage.setItem(STORAGE_KEYS.THEME, 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      storage.setItem(STORAGE_KEYS.THEME, 'light')
    }
  }, [])

  // 启动系统
  const handleSystemStart = useCallback(async () => {
    if (!backendStatus.isAvailable) {
      message.error('后端服务不可用，请先启动后端服务')
      return
    }

    try {
      setSystemLoading(true)
      setPauseStatusPolling(true)
      const result = await startSystem()
      message.success(result.message || '系统启动成功')
      setTimeout(() => {
        setPauseStatusPolling(false)
        systemStore.fetchStatus()
      }, 1000)
    } catch (error) {
      message.error(error.message || '系统启动失败')
      setPauseStatusPolling(false)
    } finally {
      setSystemLoading(false)
    }
  }, [systemStore])

  // 停止系统
  const handleSystemStop = useCallback(async () => {
    if (!backendStatus.isAvailable) {
      message.error('后端服务不可用')
      return
    }

    Modal.confirm({
      title: '停止交易引擎',
      content: '确定要停止交易引擎吗？这将停止所有交易活动，但WebUI仍会继续运行。',
      okText: '确定',
      cancelText: '取消',
      type: 'warning',
      onOk: async () => {
        try {
          setSystemLoading(true)
          setPauseStatusPolling(true)
          const result = await stopSystem()
          message.success(result.message || '交易引擎已停止')
          setTimeout(() => {
            setPauseStatusPolling(false)
            systemStore.fetchStatus()
          }, 1000)
        } catch (error) {
          message.error(error.message || '系统停止失败')
          setPauseStatusPolling(false)
        } finally {
          setSystemLoading(false)
        }
      }
    })
  }, [systemStore])

  // 重启系统
  const handleSystemRestart = useCallback(async () => {
    if (!backendStatus.isAvailable) {
      message.error('后端服务不可用')
      return
    }

    Modal.confirm({
      title: '重启交易引擎',
      content: '确定要重启交易引擎吗？这将中断当前所有交易活动并重新启动。',
      okText: '确定',
      cancelText: '取消',
      type: 'warning',
      onOk: async () => {
        try {
          setSystemLoading(true)
          setPauseStatusPolling(true)
          const result = await restartSystem()
          message.success(result.message || '交易引擎重启成功')
          setTimeout(() => {
            setPauseStatusPolling(false)
            systemStore.fetchStatus()
          }, 2000)
        } catch (error) {
          message.error(error.message || '系统重启失败')
          setPauseStatusPolling(false)
        } finally {
          setSystemLoading(false)
        }
      }
    })
  }, [systemStore])

  // 菜单点击处理
  const handleMenuClick = useCallback(({ key }) => {
    navigate(key)
  }, [navigate])

  // 后端状态变化处理
  const handleBackendStatusChange = useCallback((available) => {
    debugLog('BACKEND', `Backend status changed: ${available ? 'available' : 'unavailable'}`)

    if (available && !pauseStatusPolling && !systemLoading) {
      systemStore.fetchStatus().catch(err => {
        debugLog('API', 'Status fetch failed after backend recovery', { error: err.message })
      })
    }
  }, [pauseStatusPolling, systemLoading, systemStore])

  // 初始化
  useEffect(() => {
    debugLog('LIFECYCLE', 'Component mounting')
    const mountStartTime = Date.now()

    const init = async () => {
      try {
        // 初始化主题
        debugLog('THEME', '初始化主题', { isDark })
        document.documentElement.classList.remove('dark')

        // 检查后端状态
        debugLog('API', '检查后端状态')
        const isBackendAvailable = await backendStatus.checkStatus()

        if (isBackendAvailable) {
          debugLog('API', '开始获取系统状态')
          const fetchStartTime = Date.now()

          try {
            await systemStore.fetchStatus()
            const fetchDuration = Date.now() - fetchStartTime
            debugLog('API', '系统状态获取成功', {
              duration: `${fetchDuration}ms`,
              status: systemStore.status
            })
          } catch (fetchError) {
            const fetchDuration = Date.now() - fetchStartTime
            debugLog('API', '系统状态获取失败', {
              duration: `${fetchDuration}ms`,
              error: fetchError.message
            })
            throw fetchError
          }
        } else {
          debugLog('API', '后端不可用，跳过状态获取')
        }

        // 延迟关闭loading
        setTimeout(() => {
          setLoading(false)
          debugLog('LOADING', 'Loading关闭成功')
        }, 300)

        const mountDuration = Date.now() - mountStartTime
        debugLog('LIFECYCLE', 'Component mounted', { totalDuration: `${mountDuration}ms` })

      } catch (err) {
        const mountDuration = Date.now() - mountStartTime
        debugLog('ERROR', 'Initialization error', {
          duration: `${mountDuration}ms`,
          error: err.message
        })
        console.warn('获取系统状态失败，将使用默认值:', err)
        setLoading(false)
      }
    }

    init()

    // 监听后端状态变化
    backendStatus.addListener(handleBackendStatusChange)

    // 启动状态轮询
    debugLog('POLLING', '启动状态轮询定时器', { interval: '5000ms' })
    statusTimerRef.current = setInterval(async () => {
      if (!pauseStatusPolling && !systemLoading && backendStatus.isAvailable) {
        debugLog('POLLING', '执行状态轮询')
        systemStore.fetchStatus().catch(err => {
          if (!systemLoading) {
            debugLog('POLLING', '状态轮询失败', { error: err.message })
            console.warn('更新系统状态失败:', err)
          }
        })
      }
    }, 5000)

    // 清理函数
    return () => {
      if (statusTimerRef.current) {
        clearInterval(statusTimerRef.current)
        statusTimerRef.current = null
      }
      backendStatus.removeListener(handleBackendStatusChange)
      debugLog('LIFECYCLE', 'Component unmounted - cleaned up resources')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="app-loading">
        <Spin size="large" tip="正在初始化 DeepSearch 系统..." />
      </div>
    )
  }

  return (
    <Layout className="app-layout">
      <Sider
        width={200}
        className="app-sider"
        collapsed={collapsed}
        onCollapse={setCollapsed}
      >
        <div className="logo">
          <h2>DeepSearch</h2>
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[activeMenu]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>

      <Layout>
        <Header className="app-header">
          <div className="header-left">
            <h3>{pageTitle}</h3>
          </div>
          <div className="header-right">
            <Space size="middle">
              {/* 系统状态指示器 */}
              <div className="system-status">
                <Tag color={systemStatus.type}>
                  <span className={systemStatus.running ? 'breathing status-indicator' : 'status-indicator'}>
                    ●
                  </span>
                  {systemStatus.text}
                </Tag>
              </div>

              {/* 系统控制按钮 */}
              <Space.Compact>
                {!systemStatus.running ? (
                  <Button
                    type="primary"
                    size="small"
                    loading={systemLoading}
                    onClick={handleSystemStart}
                  >
                    启动引擎
                  </Button>
                ) : (
                  <>
                    <Button
                      danger
                      size="small"
                      loading={systemLoading}
                      onClick={handleSystemStop}
                    >
                      停止引擎
                    </Button>
                    <Button
                      type="default"
                      size="small"
                      loading={systemLoading}
                      onClick={handleSystemRestart}
                    >
                      重启引擎
                    </Button>
                  </>
                )}
              </Space.Compact>

              {/* 主题切换 */}
              <Switch
                checked={isDark}
                onChange={toggleTheme}
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
              />
            </Space>
          </div>
        </Header>

        <Content className="app-content">
          <PageTransition>
            <Outlet />
          </PageTransition>
        </Content>
      </Layout>

      {/* 错误监控组件 */}
      <ErrorMonitor />
    </Layout>
  )
}

export default App
