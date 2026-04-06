/**
 * 前端错误追踪系统
 * 捕获并上报所有前端错误，支持实时监控
 */

import logger from '@/utils/logger'
import backendStatus from '@/utils/backendStatus'

const errorTrackerLogger = logger.child('utils:error-tracker')

class ErrorTracker {
    constructor() {
        this.errors = []
        this.maxErrors = 100
        this.apiEndpoint = '/api/frontend/errors'
        this.listeners = new Set()
        this.errorId = 0
        this.reportQueue = []
        this.isReporting = false
        this.lastReportTime = 0
        this.reportInterval = 1000 // 最少1秒间隔
        this.maxReportQueueSize = 10
        this.errorSignatures = new Map() // 用于去重
        this.signatureTimeout = 5000 // 5秒内相同错误只记录一次

        backendStatus.addListener((available) => {
            if (available) {
                this.processReportQueue()
            }
        })
    }

    /**
     * 初始化错误追踪
     */
    init(app) {
        try {
        // Vue 错误处理器
        if (app) {
            app.config.errorHandler = (err, instance, info) => {
                this.captureError({
                    type: 'vue-error',
                    message: err.message,
                    stack: err.stack,
                    info,
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
                    trace,
                    level: 'warning'
                })
            }
        }

            // 全局错误处理（包括 JS 错误和资源加载错误）
        window.addEventListener('error', (event) => {
            // 资源加载错误
            if (event.target !== window) {
                this.captureError({
                    type: 'resource-error',
                    message: `Failed to load ${event.target.tagName}`,
                    source: event.target.src || event.target.href,
                    level: 'warning'
                })
            } else {
                // JavaScript 错误
                this.captureError({
                    type: 'javascript-error',
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    stack: event.error?.stack
                })
            }
        }, true)

        // Promise 拒绝处理
        window.addEventListener('unhandledrejection', (event) => {
            this.captureError({
                type: 'unhandled-promise',
                message: event.reason?.message || event.reason,
                stack: event.reason?.stack,
                promise: event.promise
            })
        })

        errorTrackerLogger.info('错误追踪系统已初始化')
        } catch (error) {
            errorTrackerLogger.error('错误追踪系统初始化失败:', error)
        }
    }

    /**
     * 生成错误签名用于去重
     */
    generateErrorSignature(errorInfo) {
        return `${errorInfo.type}-${errorInfo.message}-${errorInfo.filename || ''}-${errorInfo.lineno || ''}`
    }

    /**
     * 捕获错误
     */
    captureError(errorInfo) {
        try {
            // 生成错误签名
            const signature = this.generateErrorSignature(errorInfo)
            const now = Date.now()

            // 检查是否是重复错误
            const lastOccurrence = this.errorSignatures.get(signature)
            if (lastOccurrence && (now - lastOccurrence) < this.signatureTimeout) {
                // 相同错误在超时时间内，跳过
                return
            }

            // 更新错误签名时间
            this.errorSignatures.set(signature, now)

            // 清理过期的签名
            if (this.errorSignatures.size > 100) {
                for (const [sig, time] of this.errorSignatures) {
                    if (now - time > this.signatureTimeout) {
                        this.errorSignatures.delete(sig)
                    }
                }
            }

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

            // 添加到上报队列而不是直接上报
            this.addToReportQueue(error)

        // 在控制台输出（开发环境）
            if (import.meta.env.DEV && errorInfo.type !== 'api-error') {
            const summary = `[DEV][${error.level}] ${error.type}`
            const details = {
                message: error.message,
                timestamp: error.timestamp,
                url: error.url,
                component: error.component || 'N/A',
                stack: error.stack
            }
            errorTrackerLogger.error(summary, details)
        }
        } catch (error) {
            // 防止错误追踪器本身的错误影响应用
            errorTrackerLogger.error('错误追踪器内部错误:', error)
        }
    }

    /**
     * 添加错误到上报队列
     */
    addToReportQueue(error) {
        // 限制队列大小
        if (this.reportQueue.length >= this.maxReportQueueSize) {
            this.reportQueue.shift() // 移除最旧的
        }

        this.reportQueue.push(error)

        // 后端不可用时只缓存，不上报
        if (backendStatus.getAvailabilityState?.() !== 'available') {
            return
        }

        // 如果没有正在上报，开始处理队列
        if (!this.isReporting) {
            this.processReportQueue()
        }
    }

    /**
     * 处理上报队列
     */
    async processReportQueue() {
        if (this.isReporting || this.reportQueue.length === 0) {
            return
        }

        if (backendStatus.getAvailabilityState?.() !== 'available') {
            return
        }

        const now = Date.now()
        if (now - this.lastReportTime < this.reportInterval) {
            // 等待下一个间隔
            setTimeout(() => this.processReportQueue(), this.reportInterval - (now - this.lastReportTime))
            return
        }

        this.isReporting = true
        this.lastReportTime = now

        // 批量处理错误
        const batch = this.reportQueue.splice(0, Math.min(5, this.reportQueue.length))

        for (const error of batch) {
            await this.reportError(error)
        }

        this.isReporting = false

        // 如果还有错误待处理，继续
        if (this.reportQueue.length > 0) {
            setTimeout(() => this.processReportQueue(), this.reportInterval)
        }
    }

    /**
     * 上报错误到服务器
     */
    async reportError(error) {
        try {
            // 检查后端是否可用
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(error)
            })

            if (!response.ok) {
                // 如果是 404 或 503，说明后端可能还没启动，静默处理
                if (response.status === 404 || response.status === 503) {
                    return
                }
                // 只在开发环境下输出警告
                if (import.meta.env.DEV) {
                    errorTrackerLogger.warn('错误上报失败:', response.status, response.statusText)
                }
            }
        } catch (e) {
            // 完全静默处理网络错误
            // 不产生任何控制台输出，避免递归
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
                errorTrackerLogger.error('错误监听器执行失败:', e)
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
            message,
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
            const detailText = this.normalizeDetail(detail)

            if (detailText) {
                if (
                    detailText.includes('Redis') ||
                    detailText.includes('redis') ||
                    detailText.includes('健康检查')
                ) {
                    errorInfo.category = 'redis'
                }
                errorInfo.fullError = detailText
            } else {
                errorInfo.fullError = detail
            }
        }

        this.captureError(errorInfo)
    }

    /**
     * Normalize various detail payloads into readable text.
     */
    normalizeDetail(detail) {
        if (detail === null || detail === undefined) {
            return ''
        }

        if (typeof detail === 'string') {
            return detail
        }

        if (Array.isArray(detail)) {
            return detail
                .map((item) => this.normalizeDetail(item))
                .filter(Boolean)
                .join('; ')
        }

        if (typeof detail === 'object') {
            if (typeof detail.msg === 'string') {
                return detail.msg
            }

            if (typeof detail.message === 'string') {
                return detail.message
            }

            return Object.entries(detail)
                .map(([key, value]) => {
                    const valueText = this.normalizeDetail(value)
                    return valueText ? `${key}: ${valueText}` : ''
                })
                .filter(Boolean)
                .join(', ')
        }

        return String(detail)
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
