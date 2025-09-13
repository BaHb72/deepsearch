import { useEffect, useRef, useState, useCallback } from 'react'
import { WebSocketClient, WebSocketState } from '@/services/websocket/WebSocketClient'
import { WSMessage, WSMessageType } from '@/types'

export interface UseWebSocketOptions {
  url: string
  autoConnect?: boolean
  reconnect?: boolean
  reconnectInterval?: number
  reconnectAttempts?: number
  heartbeatInterval?: number
  onOpen?: () => void
  onClose?: (event: CloseEvent) => void
  onError?: (error: Error) => void
  onMessage?: (message: WSMessage) => void
  debug?: boolean
}

export interface UseWebSocketReturn {
  client: WebSocketClient | null
  connected: boolean
  connecting: boolean
  error: Error | null
  connect: () => Promise<void>
  disconnect: () => void
  send: (message: WSMessage) => void
  subscribe: (topics: string | string[]) => void
  unsubscribe: (topics: string | string[]) => void
  on: (event: string, handler: (...args: any[]) => void) => void
  off: (event: string, handler: (...args: any[]) => void) => void
}

export const useWebSocket = (options: UseWebSocketOptions): UseWebSocketReturn => {
  const {
    url,
    autoConnect = true,
    reconnect = true,
    reconnectInterval = 5000,
    reconnectAttempts = 5,
    heartbeatInterval = 30000,
    onOpen,
    onClose,
    onError,
    onMessage,
    debug = false,
  } = options

  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  
  const clientRef = useRef<WebSocketClient | null>(null)
  const mountedRef = useRef(true)

  // 初始化 WebSocket 客户端
  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = new WebSocketClient({
        url,
        reconnect,
        reconnectInterval,
        reconnectAttempts,
        heartbeatInterval,
        debug,
      })

      // 绑定事件
      clientRef.current.on('open', () => {
        if (mountedRef.current) {
          setConnected(true)
          setConnecting(false)
          setError(null)
          onOpen?.()
        }
      })

      clientRef.current.on('close', (event: CloseEvent) => {
        if (mountedRef.current) {
          setConnected(false)
          setConnecting(false)
          onClose?.(event)
        }
      })

      clientRef.current.on('error', (err: Error) => {
        if (mountedRef.current) {
          setError(err)
          setConnecting(false)
          onError?.(err)
        }
      })

      clientRef.current.on('message', (msg: WSMessage) => {
        if (mountedRef.current) {
          onMessage?.(msg)
        }
      })

      clientRef.current.on('reconnect_failed', () => {
        if (mountedRef.current) {
          setError(new Error('Failed to reconnect after maximum attempts'))
        }
      })
    }

    return () => {
      mountedRef.current = false
    }
  }, [url, reconnect, reconnectInterval, reconnectAttempts, heartbeatInterval, debug])

  // 自动连接
  useEffect(() => {
    if (autoConnect && clientRef.current) {
      connect()
    }

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect()
        clientRef.current.removeAllListeners()
        clientRef.current = null
      }
    }
  }, [autoConnect])

  // 连接
  const connect = useCallback(async () => {
    if (!clientRef.current || connecting || connected) return

    setConnecting(true)
    setError(null)

    try {
      await clientRef.current.connect()
    } catch (err) {
      if (mountedRef.current) {
        setError(err as Error)
        setConnecting(false)
      }
    }
  }, [connecting, connected])

  // 断开连接
  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect()
      setConnected(false)
      setConnecting(false)
    }
  }, [])

  // 发送消息
  const send = useCallback((message: WSMessage) => {
    if (clientRef.current) {
      clientRef.current.send(message)
    }
  }, [])

  // 订阅
  const subscribe = useCallback((topics: string | string[]) => {
    if (clientRef.current) {
      clientRef.current.subscribe(topics)
    }
  }, [])

  // 取消订阅
  const unsubscribe = useCallback((topics: string | string[]) => {
    if (clientRef.current) {
      clientRef.current.unsubscribe(topics)
    }
  }, [])

  // 监听事件
  const on = useCallback((event: string, handler: (...args: any[]) => void) => {
    if (clientRef.current) {
      clientRef.current.on(event, handler)
    }
  }, [])

  // 取消监听
  const off = useCallback((event: string, handler: (...args: any[]) => void) => {
    if (clientRef.current) {
      clientRef.current.off(event, handler)
    }
  }, [])

  return {
    client: clientRef.current,
    connected,
    connecting,
    error,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    on,
    off,
  }
}

// 实时行情 Hook
export const useMarketData = (symbols: string[]) => {
  const [quotes, setQuotes] = useState<Record<string, any>>({})
  const [trades, setTrades] = useState<Record<string, any[]>>({})
  const [orderbooks, setOrderbooks] = useState<Record<string, any>>({})

  const ws = useWebSocket({
    url: process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
    onMessage: (message) => {
      switch (message.type) {
        case WSMessageType.QUOTE:
          setQuotes(prev => ({
            ...prev,
            [message.data.symbol]: message.data,
          }))
          break
        
        case WSMessageType.TRADE:
          setTrades(prev => ({
            ...prev,
            [message.data.symbol]: [
              message.data,
              ...(prev[message.data.symbol] || []).slice(0, 99),
            ],
          }))
          break
        
        case WSMessageType.ORDERBOOK:
          setOrderbooks(prev => ({
            ...prev,
            [message.data.symbol]: message.data,
          }))
          break
      }
    },
  })

  useEffect(() => {
    if (ws.connected && symbols.length > 0) {
      ws.subscribe(symbols.map(s => `quote:${s}`))
      ws.subscribe(symbols.map(s => `trade:${s}`))
      ws.subscribe(symbols.map(s => `orderbook:${s}`))
    }

    return () => {
      if (ws.connected && symbols.length > 0) {
        ws.unsubscribe(symbols.map(s => `quote:${s}`))
        ws.unsubscribe(symbols.map(s => `trade:${s}`))
        ws.unsubscribe(symbols.map(s => `orderbook:${s}`))
      }
    }
  }, [ws.connected, symbols])

  return {
    quotes,
    trades,
    orderbooks,
    ...ws,
  }
}

// 系统状态 Hook
export const useSystemWebSocket = () => {
  const [systemStatus, setSystemStatus] = useState<any>(null)
  const [components, setComponents] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])

  const ws = useWebSocket({
    url: process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
    onMessage: (message) => {
      switch (message.type) {
        case WSMessageType.SYSTEM_STATUS:
          setSystemStatus(message.data)
          break
        
        case WSMessageType.COMPONENT_UPDATE:
          setComponents(message.data)
          break
        
        case WSMessageType.ALERT:
          setAlerts(prev => [message.data, ...prev].slice(0, 50))
          break
      }
    },
  })

  useEffect(() => {
    if (ws.connected) {
      ws.subscribe(['system:status', 'system:components', 'system:alerts'])
    }

    return () => {
      if (ws.connected) {
        ws.unsubscribe(['system:status', 'system:components', 'system:alerts'])
      }
    }
  }, [ws.connected])

  return {
    systemStatus,
    components,
    alerts,
    ...ws,
  }
}