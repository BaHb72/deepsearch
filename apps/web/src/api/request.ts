import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import messageManager from '@/utils/messageManager'
import { logApiError } from '@/utils/errorTracker'
import backendStatus from '@/utils/backendStatus'
import { clearPortCache } from '@/utils/portDetector'
import { debugAxiosInstance } from '@/utils/debugApi'

// ============ 类型定义 ============

// 扩展 axios 配置，添加自定义属性
interface CustomAxiosRequestConfig extends InternalAxiosRequestConfig {
    requestId?: number
    requestStartTime?: number
    skipBackendCheck?: boolean
}

// ============ 调试日志工具 ============

const debugLog = (stage: string, message: string, data: unknown = null): void => {
    const timestamp = new Date().toISOString()
    const logEntry = `[request.ts ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #e6a23c; font-weight: bold;', data)
}

// ============ 后端状态描述 ============

const describeBackendIssue = (): string => {
    let status: Record<string, unknown> | null = null
    try {
        status = (backendStatus as { getLastStatus?: () => Record<string, unknown> }).getLastStatus
            ? (backendStatus as { getLastStatus: () => Record<string, unknown> }).getLastStatus()
            : null
    } catch {
        status = (backendStatus as { lastStatus?: Record<string, unknown> }).lastStatus || null
    }

    if (!status || typeof status !== 'object') {
        return '后端服务不可用'
    }

    if ((status as { ready?: boolean }).ready === true) {
        return '后端服务不可用'
    }

    const market = (status.market_data || {}) as Record<string, unknown>
    if (market.provider && (market.provider as { connected?: boolean }).connected === false) {
        return '后端服务不可用：数据源登录中或连接失败'
    }
    if (market.boards && (market.boards as { ready?: boolean }).ready === false) {
        return '后端服务不可用：板块成分尚未加载'
    }
    const runtime = (market.runtime || {}) as Record<string, unknown>
    if (runtime.runner && runtime.runner !== 'active') {
        return '后端服务不可用：实时刷新任务未启动'
    }
    if (market.cache && (market.cache as { available?: boolean }).available === false) {
        return '后端服务不可用：缓存未就绪'
    }
    return '后端服务初始化中'
}

// ============ 创建 axios 实例 ============

debugLog('INIT', '创建axios实例', { timeout: 90000 })
const request: AxiosInstance = axios.create({
    timeout: 90000,
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
})

// 启用调试
debugAxiosInstance(request)

// 设置默认的baseURL
request.defaults.baseURL = '/api'
debugLog('INIT', `设置默认baseURL: ${request.defaults.baseURL}`)

// ============ 导出初始化函数 ============

export async function setupRequest(): Promise<null> {
    try {
        debugLog('SETUP', '开始初始化 axios 实例')
        request.defaults.baseURL = '/api'
        debugLog('SETUP', '使用代理配置: /api -> http://localhost:8000')

        // 从后端同步超时配置，确保前后端超时一致
        try {
            const response = await axios.get('/api/config/timeouts', { timeout: 5000 })
            if (response.data?.client_timeout_ms) {
                request.defaults.timeout = response.data.client_timeout_ms
                debugLog('SETUP', `超时配置已从后端同步: ${response.data.client_timeout_ms}ms`)
            }
        } catch {
            debugLog('SETUP', '后端超时配置同步失败，使用默认值 90000ms')
        }

        return null
    } catch (error) {
        debugLog('SETUP_ERROR', '初始化失败', error)
        request.defaults.baseURL = '/api'
        return null
    }
}

// ============ 请求计数器 ============

let requestCounter = 0

// ============ 请求拦截器 ============

request.interceptors.request.use(
    async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
        const customConfig = config as CustomAxiosRequestConfig
        const requestId = ++requestCounter
        customConfig.requestId = requestId
        customConfig.requestStartTime = Date.now()

        const isStatusCheck = config.url === '/system/status' && !customConfig.skipBackendCheck
        // 白名单：这些 URL 不受后端状态检查影响
        const bypassUrls = ['/notification/', '/system/config', '/log/']
        const shouldBypass = bypassUrls.some(url => config.url?.includes(url))

        if (!isStatusCheck && !shouldBypass && !(backendStatus as { isAvailable?: boolean }).isAvailable) {
            debugLog('REQUEST_BLOCKED', `#${requestId} 后端不可用，拒绝请求`, {
                url: config.url,
                backendAvailable: false
            })

            const error = new Error(describeBackendIssue()) as Error & { code?: string; config?: InternalAxiosRequestConfig }
            error.code = 'BACKEND_UNAVAILABLE'
            error.config = config
            return Promise.reject(error)
        }

        debugLog('REQUEST', `#${requestId} 发起请求`, {
            method: config.method?.toUpperCase(),
            url: config.url,
            baseURL: config.baseURL,
            fullURL: (config.baseURL || '') + (config.url || ''),
            params: config.params,
            data: config.data,
            headers: config.headers
        })

        return config
    },
    (error: AxiosError) => {
        debugLog('REQUEST_ERROR', '请求配置错误', {
            error: error.message,
            stack: error.stack
        })
        console.error('请求错误:', error)
        return Promise.reject(error)
    }
)

// ============ 响应拦截器 ============

request.interceptors.response.use(
    (response: AxiosResponse) => {
        const customConfig = response.config as CustomAxiosRequestConfig
        const requestId = customConfig.requestId
        const duration = Date.now() - (customConfig.requestStartTime || 0)

        debugLog('RESPONSE', `#${requestId} 请求成功`, {
            url: response.config.url,
            duration: `${duration}ms`,
            status: response.status,
            statusText: response.statusText,
            dataSize: JSON.stringify(response.data).length,
            data: response.data
        })

        // 记录请求成功
        const bs = backendStatus as { recordSuccess?: () => void }
        if (bs.recordSuccess) bs.recordSuccess()

        return response.data
    },
    (error: AxiosError) => {
        const customConfig = error.config as CustomAxiosRequestConfig | undefined
        const requestId = customConfig?.requestId || 'unknown'
        const duration = customConfig?.requestStartTime
            ? Date.now() - customConfig.requestStartTime
            : 'unknown'

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
            const responseData = error.response.data as Record<string, unknown> | undefined

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
                    const validationDetail = responseData?.detail
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
                    const detail = responseData?.detail
                    if (typeof detail === 'object' && detail !== null) {
                        if (Array.isArray(detail)) {
                            errorMessage = detail.map((item: unknown) => {
                                if (typeof item === 'string') {
                                    return item
                                } else if ((item as { msg?: string }).msg) {
                                    return (item as { msg: string }).msg
                                } else {
                                    return JSON.stringify(item)
                                }
                            }).join('; ')
                        } else if ((detail as { msg?: string }).msg) {
                            errorMessage = (detail as { msg: string }).msg
                        } else if ((detail as { error?: string }).error) {
                            errorMessage = (detail as { error: string }).error
                        } else {
                            errorMessage = JSON.stringify(detail)
                        }
                    } else {
                        errorMessage = (detail as string) || (responseData?.message as string) || '请求失败'
                    }
                    break
                }
            }
            // 记录HTTP错误
            const bsf = backendStatus as { recordFailure?: () => void }
            if (bsf.recordFailure) bsf.recordFailure()
        } else if (error.request) {
            errorMessage = '无法连接到后端服务，请确保后端已启动'
            const bsf2 = backendStatus as { recordFailure?: () => void }
            if (bsf2.recordFailure) bsf2.recordFailure()

            if (error.config?.url === '/system/status') {
                (backendStatus as { setAvailable?: (v: boolean) => void }).setAvailable?.(false)
            }

            if (error.code === 'ECONNREFUSED' || error.code === 'ECONNABORTED') {
                debugLog('PORT_RESET', '连接失败，清除端口缓存')
                clearPortCache()
            }

            // 静默处理周期性轮询请求的错误，避免频繁弹窗
            const silentUrls = ['/status', '/statistics', '/memory/', '/all-processes', '/jobs/']
            if (silentUrls.some(url => error.config?.url?.includes(url))) {
                showError = false
                debugLog('SILENT_ERROR', `#${requestId} 静默处理周期性请求错误`, {
                    url: error.config?.url
                })
                console.debug('后端服务未就绪')
            }
        } else if ((error as Error & { code?: string }).code === 'BACKEND_UNAVAILABLE') {
            errorMessage = describeBackendIssue()
            showError = false
        }

        // 记录到错误追踪系统
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
