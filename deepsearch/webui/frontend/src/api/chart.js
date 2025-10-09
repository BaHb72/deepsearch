import request from './request'

// 获取K线数据序列
export function getSeries(params) {
    return request({
        url: '/chart/series',
        method: 'get',
        params: {
            symbol: params.symbol,
            timeframe: params.timeframe || '1d',
            start: params.start,
            end: params.end,
            limit: params.limit || 500,
            adjust: params.adjust || 'none',
            session_split: params.session_split !== false,
            provider: params.provider
        }
    })
}

// 计算技术指标
export function calculateIndicators(data) {
    return request({
        url: '/chart/indicators',
        method: 'post',
        data: {
            symbol: data.symbol,
            timeframe: data.timeframe || '1d',
            adjust: data.adjust || 'none',
            indicators: data.indicators || []
        }
    })
}

// 获取可用指标列表
export function getIndicatorList() {
    return request({
        url: '/chart/indicator-list',
        method: 'get'
    })
}

// 获取实时快照
export function getSnapshot(symbol) {
    return request({
        url: '/chart/snap',
        method: 'get',
        params: {symbol}
    })
}

// 获取股票信息
export function getStockInfo(symbol) {
    return request({
        url: '/chart/stock-info',
        method: 'get',
        params: {symbol}
    })
}

// 获取股票列表
export function getStockList(keyword) {
    return request({
        url: '/chart/stock-list',
        method: 'get',
        params: keyword ? {keyword} : {}
    })
}

// 获取可用的数据提供者列表
export function getProviders() {
    return request({
        url: '/chart/providers',
        method: 'get'
    })
}

// 获取筹码分布数据
export function getChipDistribution(symbol, lookbackDays = 120, priceBins = 100, targetDate = null) {
    const params = {
        symbol,
        lookback_days: lookbackDays,
        price_bins: priceBins
    }

    // 如果指定了日期，添加到参数中
    if (targetDate) {
        params.target_date = targetDate
    }

    return request({
        url: '/chart/chip-distribution',
        method: 'get',
        params
    })
}

// 获取信号检测
export function getSignals(symbol, timeframe = '1d') {
    return request({
        url: '/chart/signals',
        method: 'get',
        params: {symbol, timeframe}
    })
}

// 获取图表服务统计
export function getChartStats() {
    return request({
        url: '/chart/stats',
        method: 'get'
    })
}

// 订阅实时数据（REST方式，用于测试）
export function subscribeData(symbol, timeframe = '1m') {
    return request({
        url: '/chart/subscribe',
        method: 'post',
        params: {symbol, timeframe}
    })
}

// 取消订阅
export function unsubscribeData(subscriptionId) {
    return request({
        url: `/chart/subscribe/${subscriptionId}`,
        method: 'delete'
    })
}

// 导出chart API对象
export const chartApi = {
    getSeries,
    calculateIndicators,
    getIndicatorList,
    getSnapshot,
    getStockInfo,
    getStockList,
    getProviders,
    getChipDistribution,
    getSignals,
    getChartStats,
    subscribeData,
    unsubscribeData
}

// WebSocket管理类
export class ChartWebSocket {
    constructor(url = null) {
        this.url = url || this._getWebSocketUrl()
        this.ws = null
        this.subscriptions = new Map()
        this.callbacks = new Map()
        this.reconnectAttempts = 0
        this.maxReconnectAttempts = 5
        this.reconnectInterval = 3000
        this.heartbeatInterval = null
    }

    _getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        return `${protocol}//${host}/api/chart/ws`
    }

    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url)

                this.ws.onopen = () => {
                    console.log('Chart WebSocket connected')
                    this.reconnectAttempts = 0
                    this._startHeartbeat()

                    // 重新订阅之前的订阅
                    this.subscriptions.forEach((config, subscriptionId) => {
                        this._sendSubscribe(config.symbol, config.timeframe)
                    })

                    resolve()
                }

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data)
                        this._handleMessage(data)
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error)
                    }
                }

                this.ws.onerror = (error) => {
                    console.error('Chart WebSocket error:', error)
                    reject(error)
                }

                this.ws.onclose = () => {
                    console.log('Chart WebSocket closed')
                    this._stopHeartbeat()
                    this._attemptReconnect()
                }

            } catch (error) {
                reject(error)
            }
        })
    }

    disconnect() {
        this._stopHeartbeat()
        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
        this.subscriptions.clear()
        this.callbacks.clear()
    }

    subscribe(symbol, timeframe = '1m', callback) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected')
            return null
        }

        const subscriptionId = `${symbol}_${timeframe}_${Date.now()}`

        this.subscriptions.set(subscriptionId, {symbol, timeframe})
        if (callback) {
            this.callbacks.set(subscriptionId, callback)
        }

        this._sendSubscribe(symbol, timeframe)

        return subscriptionId
    }

    unsubscribe(subscriptionId) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected')
            return
        }

        this.subscriptions.delete(subscriptionId)
        this.callbacks.delete(subscriptionId)

        this.ws.send(JSON.stringify({
            action: 'unsubscribe',
            subscription_id: subscriptionId
        }))
    }

    getIndicators(symbol, timeframe, indicators) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected')
            return
        }

        this.ws.send(JSON.stringify({
            action: 'get_indicators',
            symbol,
            timeframe,
            indicators
        }))
    }

    _sendSubscribe(symbol, timeframe) {
        this.ws.send(JSON.stringify({
            action: 'subscribe',
            symbol,
            timeframe
        }))
    }

    _handleMessage(data) {
        const {type} = data

        switch (type) {
            case 'pong':
                // Heartbeat response
                break

            case 'subscribed':
                console.log('Subscribed:', data)
                break

            case 'unsubscribed':
                console.log('Unsubscribed:', data)
                break

            case 'bar_update':
                // K线更新
                this._notifyCallbacks(data)
                break

            case 'indicators':
                // 指标数据
                this._notifyCallbacks(data)
                break

            case 'error':
                console.error('Chart WebSocket error:', data.message)
                break

            default:
                console.log('Unknown message type:', type, data)
        }
    }

    _notifyCallbacks(data) {
        // 通知所有相关的回调
        this.callbacks.forEach((callback, subscriptionId) => {
            const config = this.subscriptions.get(subscriptionId)
            if (config && config.symbol === data.symbol) {
                callback(data)
            }
        })
    }

    _startHeartbeat() {
        this._stopHeartbeat()
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({action: 'ping'}))
            }
        }, 30000) // 30秒心跳
    }

    _stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval)
            this.heartbeatInterval = null
        }
    }

    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached')
            return
        }

        this.reconnectAttempts++
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)

        setTimeout(() => {
            this.connect().catch(error => {
                console.error('Reconnection failed:', error)
            })
        }, this.reconnectInterval)
    }
}