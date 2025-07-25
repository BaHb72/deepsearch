/**
 * WebSocket 连接管理器
 * 提供自动重连和错误处理
 */

export class WebSocketManager {
    constructor(url, options = {}) {
        this.url = url
        this.options = {
            reconnectInterval: 5000,
            maxReconnectAttempts: 10,
            heartbeatInterval: 30000,
            ...options
        }

        this.ws = null
        this.reconnectAttempts = 0
        this.isConnecting = false
        this.isConnected = false
        this.shouldReconnect = true
        this.heartbeatTimer = null
        this.reconnectTimer = null

        // 事件处理器
        this.handlers = {
            open: [],
            message: [],
            close: [],
            error: []
        }
    }

    /**
     * 连接 WebSocket
     */
    connect() {
        if (this.isConnecting || this.isConnected) {
            return
        }

        this.isConnecting = true

        // 只在第一次连接时显示日志
        if (this.reconnectAttempts === 0) {
            console.log('正在连接 WebSocket:', this.url)
        }

        try {
            this.ws = new WebSocket(this.url)
            this.setupEventHandlers()
        } catch (error) {
            // 静默处理连接失败
            this.isConnecting = false
            this.scheduleReconnect()
        }
    }

    /**
     * 设置事件处理器
     */
    setupEventHandlers() {
        this.ws.onopen = (event) => {
            console.log('WebSocket 已连接')
            this.isConnecting = false
            this.isConnected = true
            this.reconnectAttempts = 0
            this.startHeartbeat()
            this.emit('open', event)
        }

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                this.emit('message', data)
            } catch (error) {
                console.error('解析 WebSocket 消息失败:', error)
            }
        }

        this.ws.onclose = (event) => {
            // 静默处理关闭，避免控制台噪音
            this.cleanup()
            this.emit('close', event)

            if (this.shouldReconnect) {
                this.scheduleReconnect()
            }
        }

        this.ws.onerror = (event) => {
            // 静默处理错误，特别是连接失败的情况
            // 只在第一次连接失败时显示提示
            if (this.reconnectAttempts === 0) {
                console.debug('WebSocket 连接失败，将自动重试')
            }
            this.emit('error', event)
        }
    }

    /**
     * 发送消息
     */
    send(data) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            const message = typeof data === 'string' ? data : JSON.stringify(data)
            this.ws.send(message)
            return true
        }
        console.warn('WebSocket 未连接，无法发送消息')
        return false
    }

    /**
     * 断开连接
     */
    disconnect() {
        this.shouldReconnect = false
        this.cleanup()

        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
    }

    /**
     * 清理资源
     */
    cleanup() {
        this.isConnecting = false
        this.isConnected = false
        this.stopHeartbeat()

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer)
            this.reconnectTimer = null
        }
    }

    /**
     * 计划重连
     */
    scheduleReconnect() {
        if (!this.shouldReconnect || this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
                console.debug('WebSocket: 已达到最大重连次数')
            }
            return
        }

        this.reconnectAttempts++
        const delay = Math.min(this.options.reconnectInterval * this.reconnectAttempts, 30000)

        // 只在前几次重连时显示日志
        if (this.reconnectAttempts <= 3) {
            console.debug(`WebSocket: 将在 ${delay}ms 后重连`)
        }

        this.reconnectTimer = setTimeout(() => {
            this.connect()
        }, delay)
    }

    /**
     * 开始心跳
     */
    startHeartbeat() {
        this.stopHeartbeat()

        this.heartbeatTimer = setInterval(() => {
            this.send('ping')
        }, this.options.heartbeatInterval)
    }

    /**
     * 停止心跳
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer)
            this.heartbeatTimer = null
        }
    }

    /**
     * 注册事件处理器
     */
    on(event, handler) {
        if (this.handlers[event]) {
            this.handlers[event].push(handler)
        }
    }

    /**
     * 移除事件处理器
     */
    off(event, handler) {
        if (this.handlers[event]) {
            this.handlers[event] = this.handlers[event].filter(h => h !== handler)
        }
    }

    /**
     * 触发事件
     */
    emit(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(handler => {
                try {
                    handler(data)
                } catch (error) {
                    console.error(`事件处理器错误 (${event}):`, error)
                }
            })
        }
    }

    /**
     * 获取连接状态
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            reconnectAttempts: this.reconnectAttempts,
            url: this.url
        }
    }
}

// 创建默认的 WebSocket 管理器实例
export const wsManager = new WebSocketManager('/ws/monitor', {
    reconnectInterval: 3000,
    maxReconnectAttempts: 20
})