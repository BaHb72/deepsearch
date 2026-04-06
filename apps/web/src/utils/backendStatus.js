/**
 * 后端状态管理器
 * 统一管理后端可用性与最近状态快照
 */

import logger from '@/utils/logger'

const backendLogger = logger.child('utils:backend-status')
const DEFAULT_PROXY_TARGET = (import.meta.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000').trim()

class BackendStatusManager {
    constructor() {
        this.availabilityState = 'unknown' // unknown | unavailable | available
        this.isAvailable = null // 兼容旧调用: true | false | null
        this.lastStatus = null
        this.lastReason = ''

        this.lastCheckTime = 0
        this.checkInterval = 10000 // 10秒
        this.listeners = new Set()
        this.isChecking = false

        this.consecutiveFailures = 0
        this.maxConsecutiveFailures = 3

        this.recoveryAttempts = 0
        this.maxRecoveryAttempts = 5
        this.recoveryInterval = 5000
        this.recoveryTimer = null

        this.successfulRequests = 0
        this.failedRequests = 0

        this.statusHistory = []
        this.maxHistoryLength = 20
        this.backendTarget = DEFAULT_PROXY_TARGET
    }

    getAvailabilityState() {
        return this.availabilityState
    }

    isBackendReady() {
        return this.availabilityState === 'available'
    }

    getBackendTarget() {
        return this.backendTarget
    }

    setUnknown(reason = '') {
        this._setAvailabilityState('unknown', reason)
    }

    setAvailable(available, reason = '') {
        this._setAvailabilityState(available ? 'available' : 'unavailable', reason)
    }

    _setAvailabilityState(nextState, reason = '') {
        const prevState = this.availabilityState
        const changed = prevState !== nextState

        this.availabilityState = nextState
        this.lastReason = reason || this.lastReason

        if (nextState === 'available') {
            this.isAvailable = true
        } else if (nextState === 'unavailable') {
            this.isAvailable = false
        } else {
            this.isAvailable = null
        }

        if (!changed) {
            if (nextState === 'available' && this.consecutiveFailures > 0) {
                this.consecutiveFailures = 0
            }
            if (
                nextState === 'unavailable' &&
                this.consecutiveFailures >= this.maxConsecutiveFailures
            ) {
                this.startRecoveryProcess()
            }
            return
        }

        this.recordStatusHistory()
        this.notifyListeners(this.isAvailable === true)

        if (nextState === 'available') {
            backendLogger.info('[BackendStatus] 后端可用')
            this.stopRecoveryProcess()
            this.consecutiveFailures = 0
            this.recoveryAttempts = 0
            return
        }

        if (nextState === 'unavailable') {
            backendLogger.warn(`[BackendStatus] 后端不可用: ${reason || 'unknown'}`)
            if (this.consecutiveFailures >= this.maxConsecutiveFailures) {
                this.startRecoveryProcess()
            }
            return
        }

        backendLogger.debug('[BackendStatus] 后端状态未知')
    }

    recordStatusHistory() {
        this.statusHistory.push({
            timestamp: Date.now(),
            state: this.availabilityState,
            available: this.isAvailable,
            reason: this.lastReason || null,
            status: this.lastStatus ? { ...this.lastStatus } : null,
        })
        if (this.statusHistory.length > this.maxHistoryLength) {
            this.statusHistory.shift()
        }
    }

    _extractStatusPayload(payload) {
        if (!payload || typeof payload !== 'object') {
            return null
        }
        const envelope = payload
        if (envelope.data && typeof envelope.data === 'object') {
            return envelope.data
        }
        return envelope
    }

    _extractReadyFlag(statusPayload) {
        return Boolean(
            statusPayload &&
            typeof statusPayload === 'object' &&
            statusPayload.ready === true
        )
    }
    async checkStatus(force = false) {
        if (this.isChecking) {
            return this.isBackendReady()
        }

        const now = Date.now()
        if (!force && now - this.lastCheckTime < this.checkInterval) {
            return this.isBackendReady()
        }

        this.isChecking = true
        this.lastCheckTime = now

        try {
            const response = await fetch('/api/system/status', {
                method: 'GET',
                signal: AbortSignal.timeout(5000),
            })

            if (response.ok) {
                const payload = await response.json().catch(() => null)
                const statusPayload = this._extractStatusPayload(payload)
                this.lastStatus = statusPayload
                const ready = this._extractReadyFlag(statusPayload)

                if (ready) {
                    this.consecutiveFailures = 0
                    this.setAvailable(true, 'status_ready')
                } else {
                    this.handleFailure('not_ready', 'ready_false')
                }
            } else {
                this.handleFailure('server_error', `http_${response.status}`)
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            backendLogger.debug(`[BackendStatus] 健康检查异常: ${message}`)
            if (message.includes('import') || message.includes('Cannot read')) {
                this.handleFailure('not_ready', 'module_not_ready')
            } else {
                this.handleFailure('connection_failed', message)
            }
        } finally {
            this.isChecking = false
        }

        return this.isBackendReady()
    }

    handleFailure(errorType = 'unknown', reason = '') {
        if (errorType === 'server_error' || errorType === 'connection_failed' || errorType === 'not_ready') {
            this.consecutiveFailures += 1
            backendLogger.debug(
                `[BackendStatus] 连续失败: ${this.consecutiveFailures}/${this.maxConsecutiveFailures} reason=${reason || errorType}`
            )
            if (this.availabilityState === 'unknown') {
                this.setAvailable(false, reason || errorType)
                return
            }
            if (this.consecutiveFailures >= this.maxConsecutiveFailures) {
                this.setAvailable(false, reason || errorType)
            }
            return
        }
        backendLogger.debug(`[BackendStatus] 忽略错误类型: ${errorType}`)
    }

    startRecoveryProcess() {
        if (this.recoveryTimer) {
            return
        }

        backendLogger.info('[BackendStatus] 启动恢复检测')
        this.recoveryAttempts = 0

        this.recoveryTimer = setInterval(async () => {
            this.recoveryAttempts += 1
            backendLogger.info(
                `[BackendStatus] 尝试恢复 (${this.recoveryAttempts}/${this.maxRecoveryAttempts})`
            )

            const ready = await this.checkStatus(true)
            if (ready) {
                backendLogger.info('[BackendStatus] 恢复成功')
                this.stopRecoveryProcess()
                return
            }

            if (this.recoveryAttempts >= this.maxRecoveryAttempts) {
                backendLogger.warn('[BackendStatus] 达到最大恢复次数，30秒后重试')
                this.stopRecoveryProcess()
                setTimeout(() => {
                    if (!this.isBackendReady()) {
                        this.startRecoveryProcess()
                    }
                }, 30000)
            }
        }, this.recoveryInterval)
    }

    stopRecoveryProcess() {
        if (!this.recoveryTimer) {
            return
        }
        clearInterval(this.recoveryTimer)
        this.recoveryTimer = null
        backendLogger.info('[BackendStatus] 停止恢复检测')
    }

    addListener(callback) {
        this.listeners.add(callback)
    }

    removeListener(callback) {
        this.listeners.delete(callback)
    }

    notifyListeners(available) {
        this.listeners.forEach((callback) => {
            try {
                callback(available)
            } catch (error) {
                backendLogger.error('后端状态监听器执行失败:', error)
            }
        })
    }

    recordSuccess() {
        this.successfulRequests += 1
        this.failedRequests = Math.max(0, this.failedRequests - 1)

        if (!this.isBackendReady() && this.successfulRequests > 2) {
            this.setAvailable(true, 'traffic_recovered')
            this.successfulRequests = 0
        }

        if (this.consecutiveFailures > 0) {
            this.consecutiveFailures = 0
        }
    }

    recordFailure() {
        this.failedRequests += 1
        this.successfulRequests = Math.max(0, this.successfulRequests - 1)
        const netFailures = this.failedRequests - this.successfulRequests
        if (this.isBackendReady() && netFailures > 5) {
            backendLogger.info(`[BackendStatus] 检测到净失败数过多(${netFailures})，触发探测`)
            this.checkStatus().catch(() => undefined)
        }
    }

    getStatistics() {
        return {
            state: this.availabilityState,
            isAvailable: this.isAvailable,
            consecutiveFailures: this.consecutiveFailures,
            successfulRequests: this.successfulRequests,
            failedRequests: this.failedRequests,
            recoveryAttempts: this.recoveryAttempts,
            statusHistory: this.statusHistory,
            lastReason: this.lastReason,
            backendTarget: this.backendTarget,
        }
    }

    async manualRecovery() {
        backendLogger.info('[BackendStatus] 手动恢复触发')
        this.consecutiveFailures = 0
        this.failedRequests = 0
        this.successfulRequests = 0
        this.recoveryAttempts = 0

        const ready = await this.checkStatus(true)
        if (!ready) {
            this.startRecoveryProcess()
        }
        return this.isBackendReady()
    }

    resetCounters() {
        this.consecutiveFailures = 0
        this.successfulRequests = 0
        this.failedRequests = 0
        this.recoveryAttempts = 0
        backendLogger.info('[BackendStatus] 计数器已重置')
    }

    getLastStatus() {
        return this.lastStatus
    }

    startPeriodicCheck() {
        setTimeout(() => {
            this.checkStatus(true).catch(() => undefined)
        }, 1000)

        setInterval(() => {
            const netFailures = this.failedRequests - this.successfulRequests
            const shouldCheck =
                !this.isBackendReady() ||
                Date.now() - this.lastCheckTime > this.checkInterval * 2 ||
                netFailures > 3

            if (shouldCheck) {
                this.checkStatus().catch(() => undefined)
            }
        }, this.checkInterval)
    }
}

export const backendStatus = new BackendStatusManager()

if (typeof window !== 'undefined') {
    backendStatus.startPeriodicCheck()
}

export default backendStatus
