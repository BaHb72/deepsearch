import {createApp} from 'vue'
import {createPinia} from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
// import TestApp from './TestApp.vue'
import router from './router'

// 导入全局样式
import './assets/styles/global.scss'

// 导入错误追踪器
import {errorTracker} from './utils/errorTracker'

// 导入端口探测器
import {configureAxiosWithDynamicPort, detectBackendPort} from './utils/portDetector'
import axios from 'axios'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[main.js ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #67c23a; font-weight: bold;', data)
}

debugLog('START', '开始初始化Vue应用')

// 创建应用（包装成异步函数）
async function initApp() {
    debugLog('APP', '创建Vue应用实例')
    const appStartTime = Date.now()

    try {
        // 在创建应用前，先探测后端端口
        debugLog('BACKEND', '开始探测后端服务端口...')
        const backendPort = await detectBackendPort()
        debugLog('BACKEND', `后端服务运行在端口: ${backendPort}`)

        // 配置全局axios实例
        await configureAxiosWithDynamicPort(axios)
        debugLog('BACKEND', 'Axios已配置动态端口')
    
    const app = createApp(App)
    // const app = createApp(TestApp)
    debugLog('APP', 'Vue应用实例创建成功', {duration: `${Date.now() - appStartTime}ms`})

    // 使用 Pinia
    debugLog('PLUGIN', '安装Pinia状态管理')
    app.use(createPinia())

    // 使用路由
    debugLog('PLUGIN', '安装Vue Router')
    app.use(router)
    debugLog('PLUGIN', '当前路由', {path: router.currentRoute.value.path})

    // 使用 Element Plus
    debugLog('PLUGIN', '安装Element Plus')
    app.use(ElementPlus, {
        locale: zhCn,
    })

    // 注册所有图标
    debugLog('ICONS', '开始注册Element Plus图标')
    const iconCount = Object.keys(ElementPlusIconsVue).length
    for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
        app.component(key, component)
    }
    debugLog('ICONS', `注册了${iconCount}个图标组件`)

    // 初始化错误追踪器
    debugLog('ERROR_TRACKER', '初始化错误追踪器')
    errorTracker.init(app)

    // 添加全局错误处理
    app.config.errorHandler = (err, instance, info) => {
        debugLog('ERROR', '捕获到Vue全局错误', {
            error: err.message,
            stack: err.stack,
            info: info,
            component: instance?.$options?.name || 'Unknown'
        })
        console.error('Vue错误:', err)
    }

    // 添加未处理的Promise拒绝处理
    window.addEventListener('unhandledrejection', event => {
        debugLog('ERROR', '捕获到未处理的Promise拒绝', {
            reason: event.reason,
            promise: event.promise
        })
        console.error('未处理的Promise拒绝:', event.reason)
    })

    // 挂载应用
    debugLog('MOUNT', '开始挂载Vue应用到#app')
    const mountStartTime = Date.now()

    const mountResult = app.mount('#app')

    debugLog('MOUNT', 'Vue应用挂载成功', {
        duration: `${Date.now() - mountStartTime}ms`,
        totalDuration: `${Date.now() - appStartTime}ms`
    })

    // 检查挂载结果
    if (mountResult) {
        debugLog('SUCCESS', '应用初始化完成')
    } else {
        debugLog('WARNING', '应用挂载返回空结果')
    }

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