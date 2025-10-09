import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import { StyleProvider } from '@ant-design/cssinjs'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import './utils/errorHandler' // 初始化全局错误处理
import './utils/debugApi' // 启用API调试
// import { StoreProvider } from './stores/StoreProvider'
// import { ErrorBoundary } from './components/react/ErrorBoundary'
import { setupRequest } from './api/request'

// 导入样式
import 'antd/dist/reset.css'
// import './styles/global-react.scss'
// import './styles/antd-theme.less'

// 设置 dayjs 语言
dayjs.locale('zh-cn')

// 调试日志工具
const debugLog = (stage, message, data = null) => {
  const timestamp = new Date().toISOString()
  const logEntry = `[React ${timestamp}] ${stage}: ${message}`
  console.log('%c' + logEntry, 'color: #1890ff; font-weight: bold;', data)
}

debugLog('START', '开始初始化 React 应用')

// Ant Design 5.x 主题配置
const antdTheme = {
  token: {
    // 品牌色
    colorPrimary: '#1890ff',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#1890ff',
    
    // 中性色
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f0f2f5',
    colorBgSpotlight: '#ffffff',
    colorBorder: '#d9d9d9',
    colorBorderSecondary: '#f0f0f0',
    
    // 文字色
    colorText: 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: 'rgba(0, 0, 0, 0.65)',
    colorTextTertiary: 'rgba(0, 0, 0, 0.45)',
    colorTextQuaternary: 'rgba(0, 0, 0, 0.25)',
    
    // 尺寸
    borderRadius: 6,
    borderRadiusLG: 8,
    borderRadiusSM: 4,
    
    // 字体
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeSM: 12,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    
    // 间距
    marginXS: 8,
    marginSM: 12,
    margin: 16,
    marginMD: 20,
    marginLG: 24,
    marginXL: 32,
    
    // 阴影
    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
    boxShadowSecondary: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
    
    // 动画
    motionDurationFast: '0.1s',
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
    
    // 控件尺寸
    controlHeight: 32,
    controlHeightLG: 40,
    controlHeightSM: 24,
  },
  algorithm: theme.defaultAlgorithm,
  components: {
    Button: {
      colorPrimary: '#1890ff',
      algorithm: true,
    },
    Input: {
      colorPrimary: '#1890ff',
      algorithm: true,
    },
    Select: {
      colorPrimary: '#1890ff',
      algorithm: true,
    },
    Table: {
      headerBg: '#fafafa',
      headerColor: 'rgba(0, 0, 0, 0.88)',
      headerSortActiveBg: '#f0f0f0',
      bodySortBg: '#fafafa',
    },
    Layout: {
      bodyBg: '#f0f2f5',
      headerBg: '#ffffff',
      headerHeight: 64,
      headerPadding: '0 24px',
      headerColor: 'rgba(0, 0, 0, 0.88)',
      siderBg: '#ffffff',
      triggerBg: '#002140',
      triggerColor: '#ffffff',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(24, 144, 255, 0.1)',
      itemSelectedColor: '#1890ff',
      itemHoverBg: 'rgba(24, 144, 255, 0.05)',
      itemHoverColor: '#1890ff',
      itemActiveBg: 'rgba(24, 144, 255, 0.15)',
    },
    Card: {
      headerBg: '#ffffff',
      headerFontSize: 16,
      headerHeight: 48,
      actionsLiMargin: '12px 0',
      tabsMarginBottom: -17,
      extraColor: 'rgba(0, 0, 0, 0.88)',
    },
    Tabs: {
      inkBarColor: '#1890ff',
      itemSelectedColor: '#1890ff',
      itemHoverColor: '#40a9ff',
      itemActiveColor: '#096dd9',
      cardBg: '#f5f5f5',
    },
    Tag: {
      defaultBg: '#fafafa',
      defaultColor: 'rgba(0, 0, 0, 0.88)',
    },
    Modal: {
      headerBg: '#ffffff',
      titleFontSize: 16,
      titleLineHeight: 1.5,
    },
    Form: {
      labelColor: 'rgba(0, 0, 0, 0.88)',
      labelFontSize: 14,
      labelHeight: 32,
      labelColonMarginInlineStart: 2,
      labelColonMarginInlineEnd: 8,
      itemMarginBottom: 24,
    },
    DatePicker: {
      cellHoverBg: '#f5f5f5',
      cellActiveWithRangeBg: '#e6f4ff',
      cellHoverWithRangeBg: '#cfe8fc',
      cellRangeBorderColor: 'transparent',
      cellBgDisabled: 'rgba(0, 0, 0, 0.04)',
      cellWidth: 36,
      cellHeight: 24,
    },
    Drawer: {
      footerPaddingBlock: 8,
      footerPaddingInline: 16,
    },
  }
}

// 暗色主题配置
const darkTheme = {
  ...antdTheme,
  algorithm: theme.darkAlgorithm,
  token: {
    ...antdTheme.token,
    colorBgContainer: '#141414',
    colorBgElevated: '#1f1f1f',
    colorBgLayout: '#000000',
    colorBorder: '#434343',
    colorBorderSecondary: '#303030',
    colorText: 'rgba(255, 255, 255, 0.85)',
    colorTextSecondary: 'rgba(255, 255, 255, 0.65)',
    colorTextTertiary: 'rgba(255, 255, 255, 0.45)',
    colorTextQuaternary: 'rgba(255, 255, 255, 0.25)',
  }
}

// 初始化应用
async function initApp() {
  debugLog('APP', '创建 React 应用实例')
  const appStartTime = Date.now()

  try {
    // 配置 axios
    await setupRequest()
    debugLog('AXIOS', 'Axios 配置完成')

    // 获取根元素
    const container = document.getElementById('root')
    if (!container) {
      throw new Error('找不到根元素 #root')
    }

    // 获取主题设置
    const isDark = localStorage.getItem('theme') === 'dark'
    const currentTheme = isDark ? darkTheme : antdTheme

    // 创建 React 根
    const root = ReactDOM.createRoot(container)
    debugLog('ROOT', 'React 根节点创建成功')

    // 渲染应用（包裹错误边界）
    root.render(
      <React.StrictMode>
        <ErrorBoundary>
          <StyleProvider hashPriority="high">
            <ConfigProvider
              locale={zhCN}
              theme={currentTheme}
              componentSize="middle"
            >
              <AntApp>
                <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                  <App />
                </BrowserRouter>
              </AntApp>
            </ConfigProvider>
          </StyleProvider>
        </ErrorBoundary>
      </React.StrictMode>
    )

    debugLog('MOUNT', 'React 应用挂载成功', {
      duration: `${Date.now() - appStartTime}ms`
    })

    // 性能监控
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          debugLog('PERFORMANCE', `${entry.name}: ${entry.duration.toFixed(2)}ms`)
        })
      })
      observer.observe({ entryTypes: ['measure', 'navigation'] })
    }

  } catch (error) {
    debugLog('ERROR', '应用初始化失败', {
      error: error.message,
      stack: error.stack
    })
    console.error('应用初始化失败:', error)

    // 显示错误提示
    document.getElementById('root').innerHTML = `
      <div style="text-align: center; padding: 50px; color: #ff4d4f;">
        <h1>应用加载失败</h1>
        <p>${error.message}</p>
        <p>请查看控制台获取详细信息</p>
      </div>
    `
  }
}

// 启动应用
initApp().catch(error => {
  console.error('应用启动失败:', error)
  document.getElementById('root').innerHTML = `
    <div style="text-align: center; padding: 50px; color: #ff4d4f;">
      <h1>应用启动失败</h1>
      <p>${error.message}</p>
      <p>请确保所有依赖已正确安装</p>
    </div>
  `
})