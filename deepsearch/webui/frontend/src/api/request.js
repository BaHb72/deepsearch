import axios from 'axios'
import messageManager from '@/utils/messageManager'
import {logApiError} from '@/utils/errorTracker'
import backendStatus from '@/utils/backendStatus'
import {clearPortCache} from '@/utils/portDetector'
import {debugAxiosInstance} from '@/utils/debugApi'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[request.js ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #e6a23c; font-weight: bold;', data)
}

const describeBackendIssue = () => {
    let status = null
    try {
        status = backendStatus.getLastStatus ? backendStatus.getLastStatus() : null
    } catch (err) {
        status = backendStatus.lastStatus || null
    }

    if (!status || typeof status !== 'object') {
        return '后端服务不可用'
    }

    if (status.ready === true) {
        return '后端服务不可用'
    }

    const market = status.market_data || {}
    if (market.provider && market.provider.connected === false) {
        return '后端服务不可用：数据源登录中或连接失败'
    }
    if (market.boards && market.boards.ready === false) {
        return '后端服务不可用：板块成分尚未加载'
    }
    const runtime = market.runtime || {}
    if (runtime.runner && runtime.runner !== 'active') {
        return '后端服务不可用：实时刷新任务未启动'
    }
    if (market.cache && market.cache.available === false) {
        return '后端服务不可用：缓存未就绪'
    }
    return '后端服务初始化中'
}

// 创建 axios 实例（初始不设置baseURL，由动态端口决定）
debugLog('INIT', '创建axios实例', {timeout: 30000})
const request = axios.create({
    timeout: 30000,  // 增加到30秒，适应后端优化后的响应时间
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'  // 明确要求JSON响应
    }
})

// 启用调试
debugAxiosInstance(request)

// 立即设置默认的baseURL（不等待异步检测）
request.defaults.baseURL = '/api'
debugLog('INIT', `设置默认baseURL: ${request.defaults.baseURL}`)

// 初始化动态baseURL
let currentBackendUrl = null

// 异步设置baseURL（保持使用相对路径）
async function ensureBackendUrl() {
    // 始终使用相对路径，不进行动态更新
    // 这样可以确保通过Vite代理工作，避免跨域问题
    if (!request.defaults.baseURL) {
        request.defaults.baseURL = '/api'
        debugLog('BACKEND_URL', '确保使用相对路径: /api')
    }
    return ''  // 返回空字符串表示使用代理
}

// 导出初始化函数，用于应用启动时的配置
export async function setupRequest() {
    try {
        debugLog('SETUP', '开始初始化 axios 实例')

        // 始终使用相对路径，通过 Vite 代理转发到后端
        // 这样可以避免跨域问题
        request.defaults.baseURL = '/api'
        debugLog('SETUP', '使用代理配置: /api -> http://localhost:8000')

        // 不再进行端口探测，避免设置完整URL导致跨域
        // 端口探测逻辑已被禁用

        return null
    } catch (error) {
        debugLog('SETUP_ERROR', '初始化失败', error)
        // 即使失败也使用默认配置
        request.defaults.baseURL = '/api'
        return null
    }
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

            const error = new Error(describeBackendIssue())
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
        
        // 记录请求成功，用于智能恢复机制
        backendStatus.recordSuccess()
        
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
        
        let errorMessage = '请求失败'
        let showError = true
        
        if (error.response) {
            switch (error.response.status) {
                case 400:
                    errorMessage = '请求参数错误'
                    break
                case 401:
                    errorMessage = '未授权，请登录'
                    break
                case 403:
                    errorMessage = '拒绝访问'
                    break
                case 404:
                    errorMessage = '请求地址不存在'
                    break
                case 422: {
                    // FastAPI的ValidationError返回422状态码
                    const validationDetail = error.response.data?.detail
                    errorMessage = typeof validationDetail === 'string'
                        ? validationDetail
                        : '请求参数验证失败'
                    break
                }
                case 500:
                    errorMessage = '服务器内部错误'
                    break
                case 503:
                    errorMessage = '服务不可用'
                    break
                default: {
                    // 处理可能是对象的detail字段（如FastAPI的ValidationError）
                    const detail = error.response.data?.detail
                    if (typeof detail === 'object' && detail !== null) {
                        // 如果detail是对象，尝试提取有意义的错误信息
                        if (Array.isArray(detail)) {
                            // 如果是数组（多个验证错误）
                            errorMessage = detail.map(item => {
                                if (typeof item === 'string') {
                                    return item
                                } else if (item.msg) {
                                    // FastAPI ValidationError格式
                                    return item.msg
                                } else {
                                    return JSON.stringify(item)
                                }
                            }).join('; ')
                        } else if (detail.msg) {
                            // 单个ValidationError对象
                            errorMessage = detail.msg
                        } else if (detail.error) {
                            // 自定义错误格式
                            errorMessage = detail.error
                        } else {
                            // 未知格式，转换为字符串
                            errorMessage = JSON.stringify(detail)
                        }
                    } else {
                        // detail是字符串或不存在
                        errorMessage = detail || error.response.data?.message || '请求失败'
                    }
                    break
                }
            }
            // 记录HTTP错误也算失败
            backendStatus.recordFailure()
        } else if (error.request) {
            // 网络错误（包括后端未启动）
            errorMessage = '无法连接到后端服务，请确保后端已启动'

            // 记录请求失败，用于智能恢复机制
            backendStatus.recordFailure()

            // 更新后端状态（仅对状态检查请求）
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
            errorMessage = describeBackendIssue()
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
            debugLog('USER_NOTIFICATION', `#${requestId} 显示错误消息: ${errorMessage}`)
            messageManager.error(errorMessage, 3)
        }
        
        return Promise.reject(error)
    }
)

export default request
