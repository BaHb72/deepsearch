import axios from 'axios'
import {ElMessage} from 'element-plus'
import {logApiError} from '@/utils/errorTracker'
import backendStatus from '@/utils/backendStatus'
import {clearPortCache, getBackendUrl} from '@/utils/portDetector'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[request.js ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #e6a23c; font-weight: bold;', data)
}

// 创建 axios 实例（初始不设置baseURL，由动态端口决定）
debugLog('INIT', '创建axios实例', {timeout: 30000})
const request = axios.create({
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 初始化动态baseURL
let currentBackendUrl = null

// 异步设置baseURL
async function ensureBackendUrl() {
    if (!currentBackendUrl) {
        currentBackendUrl = await getBackendUrl()
        request.defaults.baseURL = currentBackendUrl + '/api'
        debugLog('BACKEND_URL', `设置后端URL: ${currentBackendUrl}`)
    }
    return currentBackendUrl
}

// 请求计数器
let requestCounter = 0

// 请求拦截器
request.interceptors.request.use(
    async config => {
        // 确保设置了后端URL
        await ensureBackendUrl()
        
        const requestId = ++requestCounter
        config.requestId = requestId
        config.requestStartTime = Date.now()

        // 检查是否是状态检查请求
        const isStatusCheck = config.url === '/system/status' && !config.skipBackendCheck

        // 如果不是状态检查请求，且后端不可用，直接拒绝
        if (!isStatusCheck && !backendStatus.isAvailable) {
            debugLog('REQUEST_BLOCKED', `#${requestId} 后端不可用，拒绝请求`, {
                url: config.url,
                backendAvailable: false
            })

            const error = new Error('后端服务不可用')
            error.code = 'BACKEND_UNAVAILABLE'
            error.config = config
            return Promise.reject(error)
        }

        debugLog('REQUEST', `#${requestId} 发起请求`, {
            method: config.method?.toUpperCase(),
            url: config.url,
            baseURL: config.baseURL,
            fullURL: config.baseURL + config.url,
            params: config.params,
            data: config.data,
            headers: config.headers
        })
        
        // 可以在这里添加认证 token
        // config.headers['Authorization'] = 'Bearer ' + getToken()
        return config
    },
    error => {
        debugLog('REQUEST_ERROR', '请求配置错误', {
            error: error.message,
            stack: error.stack
        })
        console.error('请求错误:', error)
        return Promise.reject(error)
    }
)

// 响应拦截器
request.interceptors.response.use(
    response => {
        const requestId = response.config.requestId
        const duration = Date.now() - response.config.requestStartTime

        debugLog('RESPONSE', `#${requestId} 请求成功`, {
            url: response.config.url,
            duration: `${duration}ms`,
            status: response.status,
            statusText: response.statusText,
            dataSize: JSON.stringify(response.data).length,
            data: response.data
        })
        
        const res = response.data
        return res
    },
    error => {
        const requestId = error.config?.requestId || 'unknown'
        const duration = error.config?.requestStartTime ? Date.now() - error.config.requestStartTime : 'unknown'

        // 详细错误日志
        debugLog('RESPONSE_ERROR', `#${requestId} 请求失败`, {
            url: error.config?.url,
            duration: duration === 'unknown' ? duration : `${duration}ms`,
            status: error.response?.status,
            statusText: error.response?.statusText,
            errorMessage: error.message,
            errorCode: error.code,
            responseData: error.response?.data,
            isNetworkError: !error.response,
            isTimeout: error.code === 'ECONNABORTED',
            stack: error.stack
        })
        
        let message = '请求失败'
        let showError = true
        
        if (error.response) {
            switch (error.response.status) {
                case 400:
                    message = '请求参数错误'
                    break
                case 401:
                    message = '未授权，请登录'
                    break
                case 403:
                    message = '拒绝访问'
                    break
                case 404:
                    message = '请求地址不存在'
                    break
                case 500:
                    message = '服务器内部错误'
                    break
                case 503:
                    message = '服务不可用'
                    break
                default:
                    message = error.response.data?.detail || error.response.data?.message || '请求失败'
            }
        } else if (error.request) {
            // 网络错误（包括后端未启动）
            message = '无法连接到后端服务，请确保后端已启动'

            // 更新后端状态
            if (error.config?.url === '/system/status') {
                backendStatus.setAvailable(false)
            }

            // 如果连接失败，清除端口缓存，下次请求会重新探测
            if (error.code === 'ECONNREFUSED' || error.code === 'ECONNABORTED') {
                debugLog('PORT_RESET', '连接失败，清除端口缓存')
                clearPortCache()
                currentBackendUrl = null
            }
            
            // 对于某些周期性请求（如状态轮询），不显示错误
            if (error.config?.url?.includes('/status') ||
                error.config?.url?.includes('/statistics')) {
                showError = false
                debugLog('SILENT_ERROR', `#${requestId} 静默处理周期性请求错误`, {
                    url: error.config?.url
                })
                console.debug('后端服务未就绪')
            }
        } else if (error.code === 'BACKEND_UNAVAILABLE') {
            // 后端不可用错误
            message = '后端服务不可用'
            showError = false // 不显示错误，因为用户已经知道
        }

        // 记录到错误追踪系统
        // 排除一些不需要记录的请求
        const skipUrls = ['/status', '/statistics', '/frontend/errors']
        const shouldLog = !skipUrls.some(url => error.config?.url?.includes(url))

        if (shouldLog) {
            debugLog('ERROR_TRACKING', `#${requestId} 记录到错误追踪系统`)
            logApiError(error, error.config)
        }

        if (showError) {
            debugLog('USER_NOTIFICATION', `#${requestId} 显示错误消息: ${message}`)
            ElMessage.error({
                message,
                duration: 3000,
                showClose: true
            })
        }
        
        return Promise.reject(error)
    }
)

export default request