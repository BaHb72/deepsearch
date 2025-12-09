import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App as AntApp } from 'antd'
import { StyleProvider } from '@ant-design/cssinjs'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

import App from './App'
import ErrorBoundary from './components/common/ErrorBoundary'
import './utils/errorHandler'
import './utils/debugApi'
import { setupRequest } from './api/request'
import { resolveThemeMode, type ThemeMode } from './theme/config'
import { ThemeProvider } from './contexts/ThemeContext'
import { RealtimeSourceProvider } from './contexts/RealtimeSourceContext'

import 'antd/dist/reset.css'
import './styles/index.scss'

dayjs.locale('zh-cn')

const debugLog = (stage: string, message: string, data: unknown = null) => {
    const timestamp = new Date().toISOString()
    const prefix = `[React ${timestamp}] ${stage}: ${message}`
    console.log('%c' + prefix, 'color: #1890ff; font-weight: bold;', data)
}

debugLog('START', '开始初始化 React 应用')

const ROOT_ELEMENT_ID = 'root'

const FatalErrorFallback: React.FC<{ message: string }> = ({ message }) => (
    <div style={{ textAlign: 'center', padding: 50, color: '#ff4d4f' }}>
        <h1>应用初始化失败</h1>
        <p>{message}</p>
        <p>请查看控制台获取详细信息</p>
    </div>
)

function mountApplication(root: ReturnType<typeof createRoot>, themeMode: ThemeMode) {
    debugLog('THEME', '已选择的主题模式', { themeMode })

    root.render(
        <React.StrictMode>
            <ErrorBoundary>
                <StyleProvider hashPriority="high">
                    <ThemeProvider>
                        <AntApp>
                            <RealtimeSourceProvider>
                                <BrowserRouter>
                                    <App />
                                </BrowserRouter>
                            </RealtimeSourceProvider>
                        </AntApp>
                    </ThemeProvider>
                </StyleProvider>
            </ErrorBoundary>
        </React.StrictMode>
    )
}

function setupPerformanceObserver() {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) {
        return
    }

    const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
            debugLog('PERFORMANCE', `${entry.name}: ${entry.duration.toFixed(2)}ms`)
        })
    })

    observer.observe({ entryTypes: ['measure', 'navigation'] })
}

async function initApp() {
    debugLog('APP', '开始创建 React 实例')
    const container = document.getElementById(ROOT_ELEMENT_ID)

    if (!container) {
        throw new Error('未找到容器 #root')
    }

    const root = createRoot(container)
    const appStartTime = Date.now()

    try {
        await setupRequest()
        debugLog('AXIOS', 'Axios 已初始化')

        const themeMode = resolveThemeMode()
        mountApplication(root, themeMode)

        debugLog('MOUNT', 'React 应用挂载成功', {
            duration: `${Date.now() - appStartTime}ms`,
            themeMode,
        })

        setupPerformanceObserver()
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        debugLog('ERROR', '应用加载失败', { error: message })
        console.error('应用加载失败:', error)
        root.render(<FatalErrorFallback message={message} />)
    }
}

initApp().catch((error) => {
    console.error('应用加载失败:', error)
    const container = document.getElementById(ROOT_ELEMENT_ID)
    if (!container) {
        return
    }

    const root = createRoot(container)
    const message = error instanceof Error ? error.message : String(error ?? '未知错误')
    root.render(<FatalErrorFallback message={message} />)
})
