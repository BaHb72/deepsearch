/**
 * 后端状态管理器
 * 统一管理后端服务的可用性状态
 */

import logger from '@/utils/logger'

const backendLogger = logger.child('utils:backend-status')

class BackendStatusManager {
    constructor() {
        this.isAvailable = true  // 默认假设后端可用，避免一开始就阻止所有请求
        this.lastCheckTime = 0
        this.checkInterval = 10000 // 10秒检查一次
        this.listeners = new Set()
        this.isChecking = false
        this.consecutiveFailures = 0
        this.maxConsecutiveFailures = 3
        
        // 新增：恢复机制相关
        this.recoveryAttempts = 0
        this.maxRecoveryAttempts = 5
        this.recoveryInterval = 5000 // 5秒尝试恢复一次
        this.recoveryTimer = null
        
        // 新增：请求成功计数（用于自动恢复）
        this.successfulRequests = 0
        this.failedRequests = 0
        
        // 新增：状态历史记录
        this.statusHistory = []
        this.maxHistoryLength = 10
    }

    /**
     * 检查后端状态
     */
    async checkStatus() {
        if (this.isChecking) {
            return this.isAvailable
        }

        const now = Date.now()
        if (now - this.lastCheckTime < this.checkInterval) {
            return this.isAvailable
        }

        this.isChecking = true
        this.lastCheckTime = now

        try {
            // 使用 fetch 进行健康检查
            const response = await fetch('/api/system/status', {
                method: 'GET',
                signal: AbortSignal.timeout(5000) // 5秒超时
            })

            if (response.ok) {
                this.setAvailable(true)
                this.consecutiveFailures = 0
            } else {
                this.handleFailure('server_error')
            }
        } catch (error) {
            // 区分不同类型的错误
            backendLogger.debug('[BackendStatus] 健康检查异常:', error.message)

            // 模块导入错误 - 不算作后端不可用
            if (error.message?.includes('import') || error.message?.includes('Cannot read')) {
                backendLogger.debug('[BackendStatus] API模块尚未就绪，稍后重试')
                // 不调用 handleFailure，保持当前状态
            }
            // 网络连接错误或服务器错误 - 真正的后端问题
            else if (error.response?.status >= 500 || error.code === 'ECONNREFUSED' || error.message?.includes('503')) {
                backendLogger.warn('[BackendStatus] 后端服务错误:', error.response?.status || error.code)
                this.handleFailure('server_error')
            }
            // 其他错误 - 记录但不判定为不可用
            else {
                backendLogger.debug('[BackendStatus] 其他错误，不影响后端状态判断')
            }
        } finally {
            this.isChecking = false
        }

        return this.isAvailable
    }

    /**
     * 处理检查失败
     * @param {string} errorType - 错误类型：server_error, connection_failed, unknown
     */
    handleFailure(errorType = 'unknown') {
        // 只有真正的服务器错误才累计失败次数
        if (errorType === 'server_error' || errorType === 'connection_failed') {
            this.consecutiveFailures++
            backendLogger.debug(`[BackendStatus] 服务器错误累计: ${this.consecutiveFailures}/${this.maxConsecutiveFailures}`)

            if (this.consecutiveFailures >= this.maxConsecutiveFailures) {
                this.setAvailable(false)
            }
        } else {
            backendLogger.debug(`[BackendStatus] 错误类型 ${errorType} 不影响失败计数`)
        }
    }

    /**
     * 设置可用性状态
     */
    setAvailable(available) {        
        if (this.isAvailable !== available) {
            this.isAvailable = available
            
            // 记录状态历史
            this.recordStatusHistory(available)
            
            // 通知监听器
            this.notifyListeners(available)

            if (!available) {
                if (this.consecutiveFailures >= this.maxConsecutiveFailures) {
                    backendLogger.error(`[BackendStatus] 后端服务确认不可用 (连续${this.consecutiveFailures}次失败)`)
                    // 启动恢复机制
                    this.startRecoveryProcess()
                }
            } else {
                backendLogger.info('[BackendStatus] ✅ 后端服务正常')
                // 停止恢复机制
                this.stopRecoveryProcess()
                // 重置计数器
                this.consecutiveFailures = 0
                this.recoveryAttempts = 0
            }
        }
        
        // 即使状态没变化，如果是从失败恢复，也要重置失败计数
        if (available && this.consecutiveFailures > 0) {
            this.consecutiveFailures = 0
        }
    }
    
    /**
     * 记录状态历史
     */
    recordStatusHistory(available) {
        this.statusHistory.push({
            timestamp: Date.now(),
            available
        })
        
        // 限制历史记录长度
        if (this.statusHistory.length > this.maxHistoryLength) {
            this.statusHistory.shift()
        }
    }
    
    /**
     * 启动恢复进程
     */
    startRecoveryProcess() {
        // 如果已经在恢复中，不重复启动
        if (this.recoveryTimer) {
            return
        }
        
        backendLogger.info('启动后端恢复进程...')
        this.recoveryAttempts = 0
        
        this.recoveryTimer = setInterval(async () => {
            this.recoveryAttempts++
            backendLogger.info(`尝试恢复后端连接 (${this.recoveryAttempts}/${this.maxRecoveryAttempts})`)
            
            try {
                const response = await fetch('/api/system/status', {
                    method: 'GET',
                    signal: AbortSignal.timeout(3000) // 恢复时使用更短的超时
                })
                
                if (response.ok) {
                    backendLogger.info('后端恢复成功！')
                    this.setAvailable(true)
                    this.stopRecoveryProcess()
                }
            } catch (error) {
                // 恢复失败，继续尝试
                backendLogger.debug('恢复尝试失败，将继续尝试...')
            }
            
            // 达到最大尝试次数后，延长检查间隔
            if (this.recoveryAttempts >= this.maxRecoveryAttempts) {
                backendLogger.info('达到最大恢复尝试次数，延长检查间隔')
                this.stopRecoveryProcess()
                // 30秒后再次尝试
                setTimeout(() => {
                    if (!this.isAvailable) {
                        this.startRecoveryProcess()
                    }
                }, 30000)
            }
        }, this.recoveryInterval)
    }
    
    /**
     * 停止恢复进程
     */
    stopRecoveryProcess() {
        if (this.recoveryTimer) {
            clearInterval(this.recoveryTimer)
            this.recoveryTimer = null
            backendLogger.info('停止后端恢复进程')
        }
    }

    /**
     * 添加状态变化监听器
     */
    addListener(callback) {
        this.listeners.add(callback)
    }

    /**
     * 移除监听器
     */
    removeListener(callback) {
        this.listeners.delete(callback)
    }

    /**
     * 通知所有监听器
     */
    notifyListeners(available) {
        this.listeners.forEach(callback => {
            try {
                callback(available)
            } catch (error) {
                backendLogger.error('后端状态监听器执行失败:', error)
            }
        })
    }

    /**
     * 记录请求成功
     * 由request.js在响应成功时调用
     */
    recordSuccess() {
        this.successfulRequests++
        this.failedRequests = Math.max(0, this.failedRequests - 1) // 成功时减少失败计数
        
        // 如果后端被标记为不可用，但有请求成功，可能后端已恢复
        if (!this.isAvailable && this.successfulRequests > 2) {
            backendLogger.info('检测到请求成功，尝试恢复后端状态')
            this.setAvailable(true) // 直接设置为可用，不需要再次检查
            this.successfulRequests = 0 // 重置计数
        }
        
        // 重置连续失败计数
        if (this.consecutiveFailures > 0) {
            this.consecutiveFailures = 0
        }
    }
    
    /**
     * 记录请求失败
     * 由request.js在响应失败时调用
     */
    recordFailure() {
        this.failedRequests++
        this.successfulRequests = Math.max(0, this.successfulRequests - 1) // 失败时减少成功计数
        
        // 不要因为单个请求失败就标记后端不可用
        // 只有在明显失败多于成功时才检查状态
        const netFailures = this.failedRequests - this.successfulRequests
        if (this.isAvailable && netFailures > 5) {
            backendLogger.info(`检测到净失败数过多(${netFailures})，检查后端状态`)
            this.checkStatus()
        }
    }
    
    /**
     * 获取状态统计信息
     */
    getStatistics() {
        return {
            isAvailable: this.isAvailable,
            consecutiveFailures: this.consecutiveFailures,
            successfulRequests: this.successfulRequests,
            failedRequests: this.failedRequests,
            recoveryAttempts: this.recoveryAttempts,
            statusHistory: this.statusHistory
        }
    }
    
    /**
     * 手动触发恢复尝试
     * 可以由用户界面或其他组件调用
     */
    async manualRecovery() {
        backendLogger.info('手动触发后端恢复尝试')
        this.consecutiveFailures = 0
        this.failedRequests = 0
        this.successfulRequests = 0
        this.recoveryAttempts = 0
        
        // 直接尝试检查状态
        const wasAvailable = this.isAvailable
        await this.checkStatus()
        
        if (!this.isAvailable && wasAvailable) {
            // 如果检查后仍然不可用，启动恢复进程
            this.startRecoveryProcess()
        }
        
        return this.isAvailable
    }
    
    /**
     * 重置所有计数器
     */
    resetCounters() {
        this.consecutiveFailures = 0
        this.successfulRequests = 0
        this.failedRequests = 0
        this.recoveryAttempts = 0
        backendLogger.info('重置所有计数器')
    }
    
    /**
     * 启动定期检查
     */
    startPeriodicCheck() {
        // 初始检查
        setTimeout(() => this.checkStatus(), 1000) // 延迟1秒后首次检查
        
        setInterval(() => {
            // 只有在必要时才检查，避免频繁检查
            const netFailures = this.failedRequests - this.successfulRequests
            const shouldCheck = 
                !this.isAvailable || // 后端不可用时需要检查
                (Date.now() - this.lastCheckTime > this.checkInterval * 2) || // 超过2倍检查间隔
                (netFailures > 3) // 净失败数超过阈值
            
            if (shouldCheck) {
                this.checkStatus()
            }
        }, this.checkInterval)
    }
}

// 创建单例
export const backendStatus = new BackendStatusManager()

// 自动启动检查
if (typeof window !== 'undefined') {
    backendStatus.startPeriodicCheck()
}

export default backendStatus

