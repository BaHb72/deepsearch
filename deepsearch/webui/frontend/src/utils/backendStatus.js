/**
 * 后端状态管理器
 * 统一管理后端服务的可用性状态
 */

class BackendStatusManager {
    constructor() {
        this.isAvailable = false
        this.lastCheckTime = 0
        this.checkInterval = 10000 // 10秒检查一次
        this.listeners = new Set()
        this.isChecking = false
        this.consecutiveFailures = 0
        this.maxConsecutiveFailures = 3
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
            const response = await fetch('/api/system/status', {
                method: 'GET',
                signal: AbortSignal.timeout(5000) // 5秒超时
            })

            if (response.ok) {
                this.setAvailable(true)
                this.consecutiveFailures = 0
            } else {
                this.handleFailure()
            }
        } catch (error) {
            this.handleFailure()
        } finally {
            this.isChecking = false
        }

        return this.isAvailable
    }

    /**
     * 处理检查失败
     */
    handleFailure() {
        this.consecutiveFailures++
        if (this.consecutiveFailures >= this.maxConsecutiveFailures) {
            this.setAvailable(false)
        }
    }

    /**
     * 设置可用性状态
     */
    setAvailable(available) {
        if (this.isAvailable !== available) {
            this.isAvailable = available
            this.notifyListeners(available)

            if (!available) {
                console.warn('后端服务不可用')
            } else {
                console.info('后端服务已恢复')
            }
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
                console.error('后端状态监听器执行失败:', error)
            }
        })
    }

    /**
     * 启动定期检查
     */
    startPeriodicCheck() {
        this.checkStatus()
        setInterval(() => {
            this.checkStatus()
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