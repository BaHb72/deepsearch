/**
 * 前端错误追踪系统
 * 捕获并上报所有前端错误，支持实时监控
 */

class ErrorTracker {
    constructor() {
        this.errors = []
        this.maxErrors = 100
        this.apiEndpoint = '/api/frontend/errors'
        this.listeners = new Set()
        this.errorId = 0
    }

    /**
     * 初始化错误追踪
     */
    init(app) {
        // Vue 错误处理器
        if (app) {
            app.config.errorHandler = (err, instance, info) => {
                this.captureError({
                    type: 'vue-error',
                    message: err.message,
                    stack: err.stack,
                    info: info,
                    component: instance?.$options.name || 'Unknown',
                    componentStack: instance?.$options.__file
                })
            }

            // Vue 警告处理器
            app.config.warnHandler = (msg, instance, trace) => {
                this.captureError({
                    type: 'vue-warning',
                    message: msg,
                    component: instance?.$options.name || 'Unknown',
                    trace: trace,
                    level: 'warning'
                })
            }
        }

        // 全局错误处理
        window.addEventListener('error', (event) => {
            this.captureError({
                type: 'javascript-error',
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                stack: event.error?.stack
            })
        })

        // Promise 拒绝处理
        window.addEventListener('unhandledrejection', (event) => {
            this.captureError({
                type: 'unhandled-promise',
                message: event.reason?.message || event.reason,
                stack: event.reason?.stack,
                promise: event.promise
            })
        })

        // 资源加载错误
        window.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.captureError({
                    type: 'resource-error',
                    message: `Failed to load ${event.target.tagName}`,
                    source: event.target.src || event.target.href,
                    level: 'warning'
                })
            }
        }, true)

        console.log('错误追踪系统已初始化')
    }

    /**
     * 捕获错误
     */
    captureError(errorInfo) {
        const error = {
            id: ++this.errorId,
            timestamp: new Date().toISOString(),
            url: window.location.href,
            userAgent: navigator.userAgent,
            level: errorInfo.level || 'error',
            ...errorInfo
        }

        // 添加到本地缓存
        this.errors.unshift(error)
        if (this.errors.length > this.maxErrors) {
            this.errors.pop()
        }

        // 通知监听器
        this.notifyListeners(error)

        // 上报到服务器
        this.reportError(error)

        // 在控制台输出（开发环境）
        if (import.meta.env.DEV) {
            console.group(`🚨 ${error.type} - ${error.level}`)
            console.error('错误信息:', error.message)
            if (error.stack) {
                console.error('堆栈:', error.stack)
            }
            console.table({
                时间: error.timestamp,
                类型: error.type,
                级别: error.level,
                URL: error.url,
                组件: error.component || 'N/A'
            })
            console.groupEnd()
        }
    }

    /**
     * 上报错误到服务器
     */
    async reportError(error) {
        try {
            await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(error)
            })
        } catch (e) {
            console.warn('错误上报失败:', e)
        }
    }

    /**
     * 添加错误监听器
     */
    addListener(callback) {
        this.listeners.add(callback)
    }

    /**
     * 移除错误监听器
     */
    removeListener(callback) {
        this.listeners.delete(callback)
    }

    /**
     * 通知所有监听器
     */
    notifyListeners(error) {
        this.listeners.forEach(callback => {
            try {
                callback(error)
            } catch (e) {
                console.error('错误监听器执行失败:', e)
            }
        })
    }

    /**
     * 获取所有错误
     */
    getErrors() {
        return [...this.errors]
    }

    /**
     * 清空错误
     */
    clearErrors() {
        this.errors = []
        this.notifyListeners({type: 'clear'})
    }

    /**
     * 手动记录错误
     */
    logError(message, extra = {}) {
        this.captureError({
            type: 'manual',
            message: message,
            ...extra
        })
    }

    /**
     * 记录 API 错误
     */
    logApiError(error, config) {
        const errorInfo = {
            type: 'api-error',
            message: error.message,
            url: config?.url,
            method: config?.method,
            params: config?.params,
            data: config?.data,
            status: error.response?.status,
            statusText: error.response?.statusText,
            responseData: error.response?.data
        }

        // 如果是 Redis 相关错误，添加特殊标记
        if (error.response?.data?.detail) {
            const detail = error.response.data.detail
            if (detail.includes('Redis') || detail.includes('redis') || detail.includes('健康检查')) {
                errorInfo.category = 'redis'
                errorInfo.fullError = detail
            }
        }

        this.captureError(errorInfo)
    }

    /**
     * 导出错误日志
     */
    exportErrors() {
        const data = JSON.stringify(this.errors, null, 2)
        const blob = new Blob([data], {type: 'application/json'})
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `error-log-${new Date().toISOString()}.json`
        a.click()
        URL.revokeObjectURL(url)
    }
}

// 创建单例实例
export const errorTracker = new ErrorTracker()

// 导出便捷方法
export const logError = (...args) => errorTracker.logError(...args)
export const logApiError = (...args) => errorTracker.logApiError(...args)