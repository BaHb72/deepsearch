import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

// 导入样式
import './styles/variables.css'
import './styles/global.css'
import 'antd/dist/reset.css'

// 导入端口探测器和axios配置
import { configureAxiosWithDynamicPort, detectBackendPort } from './utils/portDetector'
import axios from 'axios'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[main.jsx ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #1890ff; font-weight: bold;', data)
}

debugLog('START', '开始初始化React应用')

// 初始化应用
async function initApp() {
    debugLog('APP', '开始初始化React应用')
    const appStartTime = Date.now()

    try {
        // 探测后端端口
        debugLog('BACKEND', '开始探测后端服务端口...')
        const backendPort = await detectBackendPort()
        debugLog('BACKEND', `后端服务运行在端口: ${backendPort}`)

        // 配置axios
        await configureAxiosWithDynamicPort(axios)
        debugLog('BACKEND', 'Axios已配置动态端口')

        // 创建React根节点
        debugLog('MOUNT', '开始挂载React应用到#app')
        const root = ReactDOM.createRoot(document.getElementById('app'))

        root.render(
            <React.StrictMode>
                <BrowserRouter>
                    <App />
                </BrowserRouter>
            </React.StrictMode>
        )

        debugLog('SUCCESS', '应用初始化完成', {
            duration: `${Date.now() - appStartTime}ms`
        })

    } catch (error) {
        debugLog('ERROR', '应用初始化失败', {
            error: error.message,
            stack: error.stack
        })
        console.error('应用初始化失败:', error)

        // 显示错误提示
        document.getElementById('app').innerHTML = `
            <div style="text-align: center; padding: 50px; color: #f56c6c;">
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
    document.getElementById('app').innerHTML = `
        <div style="text-align: center; padding: 50px; color: #f56c6c;">
            <h1>应用启动失败</h1>
            <p>${error.message}</p>
            <p>请确保后端服务已启动</p>
        </div>
    `
})
