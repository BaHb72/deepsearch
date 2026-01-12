/**
 * 优化的WebSocket连接管理器
 *
 * 功能特性：
 * - 连接池管理
 * - 自动重连
 * - 心跳检测
 * - 消息队列
 * - 压缩支持
 * - 批量消息处理
 */

import { reactive, getCurrentInstance, onUnmounted } from 'vue'
import logger from '@/utils/logger'

const wsLogger = logger.child('utils:websocket')

class WebSocketConnection {
  constructor({
    url,
    protocols = [],
    reconnectInterval = 5000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    messageQueueSize = 100,
    enableCompression = true,
    enableBatching = true,
    batchSize = 50,
    batchTimeout = 100
  }) {
    this.url = url
    this.protocols = protocols
    this.reconnectInterval = reconnectInterval
    this.maxReconnectAttempts = maxReconnectAttempts
    this.heartbeatInterval = heartbeatInterval
    this.messageQueueSize = messageQueueSize
    this.enableCompression = enableCompression
    this.enableBatching = enableBatching
    this.batchSize = batchSize
    this.batchTimeout = batchTimeout

    this.ws = null
    this.reconnectCount = 0
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.messageQueue = []
    this.pendingMessages = []
    this.batchTimer = null

    // 状态
    this.state = reactive({
      connected: false,
      connecting: false,
      reconnecting: false,
      error: null
    })

    // 事件处理器
    this.handlers = {
      open: [],
      close: [],
      error: [],
      message: new Map() // topic -> handlers
    }

    // 统计信息
    this.stats = reactive({
      messagesSent: 0,
      messagesReceived: 0,
      messagesCompressed: 0,
      batchesSent: 0,
      reconnects: 0,
      errors: 0,
      bytesReceived: 0,
      bytesSent: 0,
      latency: 0,
      lastMessageTime: null
    })
  }

  connect() {
    if (this.state.connected || this.state.connecting) return

    this.state.connecting = true
    this.state.error = null

    try {
      this.ws = new WebSocket(this.url, this.protocols)
      this.setupEventHandlers()
    } catch (error) {
      this.handleError(error)
    }
  }

  setupEventHandlers() {
    this.ws.onopen = (event) => {
      this.state.connected = true
      this.state.connecting = false
      this.state.reconnecting = false
      this.reconnectCount = 0

      // 启动心跳
      this.startHeartbeat()

      // 发送队列中的消息
      this.flushMessageQueue()

      // 触发open事件
      this.emit('open', event)
    }

    this.ws.onclose = (event) => {
      this.state.connected = false
      this.state.connecting = false

      // 停止心跳
      this.stopHeartbeat()

      // 触发close事件
      this.emit('close', event)

      // 自动重连
      if (!event.wasClean && this.reconnectCount < this.maxReconnectAttempts) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = (event) => {
      this.stats.errors++
      this.handleError(event)
    }

    this.ws.onmessage = async (event) => {
      this.stats.messagesReceived++
      this.stats.bytesReceived += event.data.length
      this.stats.lastMessageTime = new Date()

      try {
        let data = event.data

        // 解析消息
        if (typeof data === 'string') {
          data = JSON.parse(data)
        }

        // 处理压缩消息
        if (data.type === 'compressed' && this.enableCompression) {
          data = await this.decompressMessage(data)
          this.stats.messagesCompressed++
        }

        // 处理批量消息
        if (data.type === 'batch' && this.enableBatching) {
          this.handleBatchMessage(data)
        } else {
          this.handleMessage(data)
        }
      } catch (error) {
        wsLogger.error('[MESSAGE_PARSE_ERROR]', error)
      }
    }
  }

  handleMessage(data) {
    // 计算延迟
    if (data.timestamp) {
      const latency = Date.now() - new Date(data.timestamp).getTime()
      this.stats.latency = (this.stats.latency * 0.9) + (latency * 0.1) // 移动平均
    }

    // 分发消息
    const topic = data.topic || data.type || 'default'
    const handlers = this.handlers.message.get(topic) || []
    handlers.forEach(handler => {
      try {
        handler(data)
      } catch (error) {
        wsLogger.error(`[TOPIC_HANDLER_ERROR] ${topic}`, error)
      }
    })

    // 通用消息处理器
    const allHandlers = this.handlers.message.get('*') || []
    allHandlers.forEach(handler => {
      try {
        handler(data)
      } catch (error) {
        wsLogger.error('[UNIVERSAL_HANDLER_ERROR]', error)
      }
    })
  }

  handleBatchMessage(batch) {
    const messages = batch.messages || []
    messages.forEach(message => this.handleMessage(message))
  }

  async decompressMessage(data) {
    // 将十六进制字符串转换回压缩数据
    const compressed = new Uint8Array(
      data.data.match(/.{1,2}/g).map(byte => parseInt(byte, 16))
    )

    // 解压缩
    const decompressed = await this.decompress(compressed)
    return JSON.parse(decompressed)
  }

  async decompress(data) {
    const ds = new DecompressionStream('gzip')
    const blob = new Blob([data])
    const stream = blob.stream().pipeThrough(ds)
    const decompressed = await new Response(stream).text()
    return decompressed
  }

  send(data) {
    if (!this.state.connected) {
      // 添加到队列
      if (this.messageQueue.length < this.messageQueueSize) {
        this.messageQueue.push(data)
      }
      return false
    }

    // 批量发送逻辑
    if (this.enableBatching) {
      this.pendingMessages.push(data)

      if (this.pendingMessages.length >= this.batchSize) {
        this.flushPendingMessages()
      } else if (!this.batchTimer) {
        this.batchTimer = setTimeout(() => {
          this.flushPendingMessages()
        }, this.batchTimeout)
      }
    } else {
      this.sendImmediate(data)
    }

    return true
  }

  sendImmediate(data) {
    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      this.ws.send(message)
      this.stats.messagesSent++
      this.stats.bytesSent += message.length
    } catch (error) {
      wsLogger.error('[SEND_ERROR]', error)
      this.handleError(error)
    }
  }

  flushPendingMessages() {
    if (this.pendingMessages.length === 0) return

    if (this.batchTimer) {
      clearTimeout(this.batchTimer)
      this.batchTimer = null
    }

    const batch = {
      type: 'batch',
      messages: this.pendingMessages,
      count: this.pendingMessages.length,
      timestamp: new Date().toISOString()
    }

    this.sendImmediate(batch)
    this.stats.batchesSent++
    this.pendingMessages = []
  }

  flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.state.connected) {
      const message = this.messageQueue.shift()
      this.send(message)
    }
  }

  startHeartbeat() {
    this.stopHeartbeat()

    this.heartbeatTimer = setInterval(() => {
      if (this.state.connected) {
        this.send({ type: 'ping', timestamp: Date.now() })
      }
    }, this.heartbeatInterval)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return

    this.state.reconnecting = true
    this.reconnectCount++
    this.stats.reconnects++

    const delay = Math.min(
      this.reconnectInterval * Math.pow(1.5, this.reconnectCount - 1),
      30000
    )

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  handleError(error) {
    this.state.error = error
    this.emit('error', error)
  }

  on(event, handler) {
    if (event === 'message') {
      // message事件需要topic
      return this.subscribe('*', handler)
    }

    if (!this.handlers[event]) {
      this.handlers[event] = []
    }
    this.handlers[event].push(handler)

    return () => this.off(event, handler)
  }

  off(event, handler) {
    if (this.handlers[event]) {
      const index = this.handlers[event].indexOf(handler)
      if (index > -1) {
        this.handlers[event].splice(index, 1)
      }
    }
  }

  emit(event, data) {
    const handlers = this.handlers[event] || []
    handlers.forEach(handler => {
      try {
        handler(data)
      } catch (error) {
        wsLogger.error(`[EVENT_HANDLER_ERROR] ${event}`, error)
      }
    })
  }

  subscribe(topic, handler) {
    if (!this.handlers.message.has(topic)) {
      this.handlers.message.set(topic, [])
    }
    this.handlers.message.get(topic).push(handler)

    return () => this.unsubscribe(topic, handler)
  }

  unsubscribe(topic, handler) {
    const handlers = this.handlers.message.get(topic)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  close() {
    // 清理定时器
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.batchTimer) {
      clearTimeout(this.batchTimer)
      this.batchTimer = null
    }

    // 关闭连接
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.state.connected = false
    this.state.connecting = false
    this.state.reconnecting = false
  }

  getState() {
    return this.state
  }

  getStats() {
    return this.stats
  }
}

class WebSocketManager {
  constructor() {
    this.connections = new Map()
  }

  create(key, options) {
    if (this.connections.has(key)) {
      wsLogger.warn(`[DUPLICATE_CONNECTION] 已存在连接 ${key}`)
      return this.connections.get(key)
    }

    const connection = new WebSocketConnection(options)
    this.connections.set(key, connection)
    return connection
  }

  get(key) {
    return this.connections.get(key)
  }

  remove(key) {
    const connection = this.connections.get(key)
    if (connection) {
      connection.close()
      this.connections.delete(key)
    }
  }

  closeAll() {
    this.connections.forEach(connection => connection.close())
    this.connections.clear()
  }

  getStats() {
    const stats = {}
    this.connections.forEach((connection, key) => {
      stats[key] = connection.getStats()
    })
    return stats
  }
}

// 创建单例实例
const wsManager = new WebSocketManager()

// Vue 3 Composition API 集成
export function useWebSocket(key, options) {
  const connection = wsManager.create(key, options)

  // 组件卸载时自动清理
  if (typeof getCurrentInstance !== 'undefined') {
    const instance = getCurrentInstance()
    if (instance) {
      onUnmounted(() => {
        wsManager.remove(key)
      })
    }
  }

  return {
    connection,
    state: connection.getState(),
    stats: connection.getStats(),
    connect: () => connection.connect(),
    close: () => connection.close(),
    send: (data) => connection.send(data),
    subscribe: (topic, handler) => connection.subscribe(topic, handler),
    on: (event, handler) => connection.on(event, handler)
  }
}

export default wsManager
