/**
 * QMT数据API接口
 */

import request from './request'

/**
 * 获取QMT连接状态
 */
export function getQmtStatus() {
    return request({
        url: '/qmt/status',
        method: 'get'
    })
}

/**
 * 订阅股票行情
 * @param {Array<string>} symbols - 股票代码列表
 */
export function subscribeSymbols(symbols) {
    return request({
        url: '/qmt/subscribe',
        method: 'post',
        data: symbols
    })
}

/**
 * 取消订阅股票行情
 * @param {Array<string>} symbols - 股票代码列表
 */
export function unsubscribeSymbols(symbols) {
    return request({
        url: '/qmt/unsubscribe',
        method: 'post',
        data: symbols
    })
}

/**
 * 获取已订阅的股票列表
 */
export function getSubscribedSymbols() {
    return request({
        url: '/qmt/subscribed',
        method: 'get'
    })
}

/**
 * 获取最新的Tick数据
 * @param {string} symbol - 股票代码
 */
export function getLatestTick(symbol) {
    return request({
        url: `/qmt/tick/${symbol}`,
        method: 'get'
    })
}

/**
 * 获取最新的盘口数据
 * @param {string} symbol - 股票代码
 */
export function getLatestOrderbook(symbol) {
    return request({
        url: `/qmt/orderbook/${symbol}`,
        method: 'get'
    })
}

/**
 * 获取连接的QMT客户端信息
 */
export function getConnectedClients() {
    return request({
        url: '/qmt/clients',
        method: 'get'
    })
}

/**
 * 获取交易明细
 * @param {string} symbol - 股票代码
 * @param {number} limit - 返回条数，默认20
 */
export function getTradeDetails(symbol, limit = 20) {
    return request({
        url: `/qmt/trades/${symbol}`,
        method: 'get',
        params: {limit}
    })
}

/**
 * 获取QMT数据统计信息
 */
export function getQmtStatistics() {
    return request({
        url: '/qmt/statistics',
        method: 'get'
    })
}

/**
 * QMT WebSocket连接类
 */
export class QmtWebSocket {
    constructor(url = null) {
        this.url = url || this._getWebSocketUrl()
        this.ws = null
        this.subscriptions = new Set()
        this.callbacks = {
            onTick: null,
            onOrderbook: null,
            onTrade: null,
            onConnected: null,
            onDisconnected: null,
            onError: null
        }
        this.reconnectTimeout = null
        this.reconnectDelay = 5000
        this.isManualClose = false
    }

    _getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        return `${protocol}//${host}/api/qmt/ws`
    }

    /**
     * 连接WebSocket
     */
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('QMT WebSocket already connected')
            return
        }

        this.isManualClose = false
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
            console.log('QMT WebSocket connected')
            if (this.callbacks.onConnected) {
                this.callbacks.onConnected()
            }

            // 重新订阅之前的股票
            if (this.subscriptions.size > 0) {
                this.subscribe(Array.from(this.subscriptions))
            }
        }

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                this._handleMessage(data)
            } catch (error) {
                console.error('Failed to parse QMT WebSocket message:', error)
            }
        }

        this.ws.onerror = (error) => {
            console.error('QMT WebSocket error:', error)
            if (this.callbacks.onError) {
                this.callbacks.onError(error)
            }
        }

        this.ws.onclose = () => {
            console.log('QMT WebSocket disconnected')
            if (this.callbacks.onDisconnected) {
                this.callbacks.onDisconnected()
            }

            // 自动重连
            if (!this.isManualClose) {
                this._scheduleReconnect()
            }
        }
    }

    /**
     * 断开WebSocket连接
     */
    disconnect() {
        this.isManualClose = true
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout)
            this.reconnectTimeout = null
        }
        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
    }

    /**
     * 订阅股票
     * @param {Array<string>} symbols - 股票代码列表
     */
    subscribe(symbols) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('QMT WebSocket not connected')
            return
        }

        symbols.forEach(symbol => this.subscriptions.add(symbol))

        this.ws.send(JSON.stringify({
            action: 'subscribe',
            symbols: symbols
        }))
    }

    /**
     * 取消订阅股票
     * @param {Array<string>} symbols - 股票代码列表
     */
    unsubscribe(symbols) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('QMT WebSocket not connected')
            return
        }

        symbols.forEach(symbol => this.subscriptions.delete(symbol))

        this.ws.send(JSON.stringify({
            action: 'unsubscribe',
            symbols: symbols
        }))
    }

    /**
     * 发送心跳
     */
    ping() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                action: 'ping'
            }))
        }
    }

    /**
     * 设置回调函数
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    on(event, callback) {
        if (event in this.callbacks) {
            this.callbacks[event] = callback
        }
    }

    /**
     * 处理接收到的消息
     * @private
     */
    _handleMessage(data) {
        switch (data.type) {
            case 'connected':
                console.log('QMT WebSocket connected:', data.data)
                break

            case 'tick':
                if (this.callbacks.onTick) {
                    this.callbacks.onTick(data.data)
                }
                break

            case 'orderbook':
                if (this.callbacks.onOrderbook) {
                    this.callbacks.onOrderbook(data.data)
                }
                break

            case 'trade':
                if (this.callbacks.onTrade) {
                    this.callbacks.onTrade(data.data)
                }
                break

            case 'subscribed':
                console.log('Subscribed to symbols:', data.data)
                break

            case 'unsubscribed':
                console.log('Unsubscribed from symbols:', data.data)
                break

            case 'pong':
                // 心跳响应
                break

            case 'error':
                console.error('QMT WebSocket error:', data.message)
                if (this.callbacks.onError) {
                    this.callbacks.onError(new Error(data.message))
                }
                break

            default:
                console.log('Unknown QMT message type:', data.type)
        }
    }

    /**
     * 安排重连
     * @private
     */
    _scheduleReconnect() {
        if (this.reconnectTimeout) {
            return
        }

        console.log(`Reconnecting QMT WebSocket in ${this.reconnectDelay}ms...`)
        this.reconnectTimeout = setTimeout(() => {
            this.reconnectTimeout = null
            this.connect()
        }, this.reconnectDelay)
    }
}

// 导出API
export const qmtApi = {
    getStatus: getQmtStatus,
    subscribe: subscribeSymbols,
    unsubscribe: unsubscribeSymbols,
    getSubscribed: getSubscribedSymbols,
    getTick: getLatestTick,
    getOrderbook: getLatestOrderbook,
    getClients: getConnectedClients,
    getStatistics: getQmtStatistics,
    WebSocket: QmtWebSocket
}