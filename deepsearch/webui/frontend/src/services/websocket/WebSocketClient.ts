import { EventEmitter } from 'events'
import { message } from 'antd'
import { WSMessage, WSMessageType } from '@/types'

export interface WebSocketConfig {
  url: string
  reconnect?: boolean
  reconnectInterval?: number
  reconnectAttempts?: number
  heartbeatInterval?: number
  timeout?: number
  debug?: boolean
}

export enum WebSocketState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3,
}

export class WebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null
  private config: Required<WebSocketConfig>
  private reconnectAttempts = 0
  private reconnectTimer: NodeJS.Timeout | null = null
  private heartbeatTimer: NodeJS.Timeout | null = null
  private subscriptions = new Set<string>()
  private messageQueue: WSMessage[] = []
  private isReconnecting = false

  constructor(config: WebSocketConfig) {
    super()
    this.config = {
      reconnect: true,
      reconnectInterval: 5000,
      reconnectAttempts: 5,
      heartbeatInterval: 30000,
      timeout: 60000,
      debug: false,
      ...config,
    }
  }

  // 连接 WebSocket
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocketState.OPEN) {
        resolve()
        return
      }

      try {
        this.ws = new WebSocket(this.config.url)
        
        // 连接超时
        const timeout = setTimeout(() => {
          this.ws?.close()
          reject(new Error('WebSocket connection timeout'))
        }, this.config.timeout)

        this.ws.onopen = () => {
          clearTimeout(timeout)
          this.log('WebSocket connected')
          this.reconnectAttempts = 0
          this.isReconnecting = false
          
          // 发送缓存的消息
          this.flushMessageQueue()
          
          // 重新订阅
          this.resubscribe()
          
          // 启动心跳
          this.startHeartbeat()
          
          this.emit('open')
          resolve()
        }

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data)
        }

        this.ws.onerror = (error) => {
          clearTimeout(timeout)
          this.log('WebSocket error:', error)
          this.emit('error', error)
          reject(error)
        }

        this.ws.onclose = (event) => {
          clearTimeout(timeout)
          this.log('WebSocket closed:', event.code, event.reason)
          this.stopHeartbeat()
          this.emit('close', event)
          
          // 自动重连
          if (this.config.reconnect && !this.isReconnecting) {
            this.reconnect()
          }
        }
      } catch (error) {
        this.log('Failed to create WebSocket:', error)
        reject(error)
      }
    })
  }

  // 断开连接
  disconnect(): void {
    this.config.reconnect = false
    this.stopHeartbeat()
    this.clearReconnectTimer()
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
    
    this.subscriptions.clear()
    this.messageQueue = []
  }

  // 发送消息
  send(message: WSMessage): void {
    const data = JSON.stringify(message)
    
    if (this.ws && this.ws.readyState === WebSocketState.OPEN) {
      this.ws.send(data)
      this.log('Sent message:', message)
    } else {
      // 缓存消息
      this.messageQueue.push(message)
      this.log('Message queued:', message)
    }
  }

  // 订阅主题
  subscribe(topics: string | string[]): void {
    const topicList = Array.isArray(topics) ? topics : [topics]
    
    topicList.forEach(topic => {
      this.subscriptions.add(topic)
    })
    
    this.send({
      type: WSMessageType.SUBSCRIBE,
      data: { topics: topicList },
      timestamp: Date.now(),
    })
  }

  // 取消订阅
  unsubscribe(topics: string | string[]): void {
    const topicList = Array.isArray(topics) ? topics : [topics]
    
    topicList.forEach(topic => {
      this.subscriptions.delete(topic)
    })
    
    this.send({
      type: WSMessageType.UNSUBSCRIBE,
      data: { topics: topicList },
      timestamp: Date.now(),
    })
  }

  // 获取连接状态
  getState(): WebSocketState {
    return this.ws?.readyState ?? WebSocketState.CLOSED
  }

  // 是否已连接
  isConnected(): boolean {
    return this.ws?.readyState === WebSocketState.OPEN
  }

  // 处理消息
  private handleMessage(data: string): void {
    try {
      const message: WSMessage = JSON.parse(data)
      this.log('Received message:', message)
      
      // 处理不同类型的消息
      switch (message.type) {
        case WSMessageType.HEARTBEAT:
          // 响应心跳
          this.send({
            type: WSMessageType.HEARTBEAT,
            data: { pong: true },
            timestamp: Date.now(),
          })
          break
          
        case WSMessageType.ERROR:
          this.handleError(message.data)
          break
          
        case WSMessageType.NOTIFICATION:
          this.handleNotification(message.data)
          break
          
        default:
          // 触发消息事件
          this.emit('message', message)
          this.emit(message.type, message.data)
      }
    } catch (error) {
      this.log('Failed to parse message:', error)
      this.emit('error', error)
    }
  }

  // 处理错误消息
  private handleError(error: any): void {
    message.error(error.message || '服务器错误')
    this.emit('error', error)
  }

  // 处理通知消息
  private handleNotification(notification: any): void {
    const { type, title, message: msg } = notification
    
    switch (type) {
      case 'success':
        message.success(msg || title)
        break
      case 'warning':
        message.warning(msg || title)
        break
      case 'error':
        message.error(msg || title)
        break
      default:
        message.info(msg || title)
    }
    
    this.emit('notification', notification)
  }

  // 重连
  private reconnect(): void {
    if (this.isReconnecting) return
    
    this.isReconnecting = true
    this.reconnectAttempts++
    
    if (this.reconnectAttempts > this.config.reconnectAttempts) {
      this.log('Max reconnect attempts reached')
      this.emit('reconnect_failed')
      return
    }
    
    this.log(`Reconnecting... (${this.reconnectAttempts}/${this.config.reconnectAttempts})`)
    
    this.reconnectTimer = setTimeout(() => {
      this.connect().catch(error => {
        this.log('Reconnect failed:', error)
      })
    }, this.config.reconnectInterval)
  }

  // 清除重连定时器
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  // 启动心跳
  private startHeartbeat(): void {
    this.stopHeartbeat()
    
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.send({
          type: WSMessageType.HEARTBEAT,
          data: { ping: true },
          timestamp: Date.now(),
        })
      }
    }, this.config.heartbeatInterval)
  }

  // 停止心跳
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  // 重新订阅
  private resubscribe(): void {
    if (this.subscriptions.size > 0) {
      this.send({
        type: WSMessageType.SUBSCRIBE,
        data: { topics: Array.from(this.subscriptions) },
        timestamp: Date.now(),
      })
    }
  }

  // 发送缓存的消息
  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()
      if (message) {
        this.send(message)
      }
    }
  }

  // 日志
  private log(...args: any[]): void {
    if (this.config.debug) {
      console.log('[WebSocket]', ...args)
    }
  }
}

// 创建默认实例
let defaultClient: WebSocketClient | null = null

export const getWebSocketClient = (config?: WebSocketConfig): WebSocketClient => {
  if (!defaultClient && config) {
    defaultClient = new WebSocketClient(config)
  }
  
  if (!defaultClient) {
    throw new Error('WebSocket client not initialized')
  }
  
  return defaultClient
}

export const closeWebSocketClient = (): void => {
  if (defaultClient) {
    defaultClient.disconnect()
    defaultClient = null
  }
}