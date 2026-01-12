import {useCallback, useEffect, useRef, useState} from 'react'
import {WebSocketClient} from '@/services/websocket/WebSocketClient'
import {ComponentStatus, Notification, SystemStatus, WSMessage, WSMessageType,} from '@/types'

type EventHandler = (...args: unknown[]) => void

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
    onMessage?: (message: WSMessage<unknown>) => void
  debug?: boolean
}

export interface UseWebSocketReturn {
  client: WebSocketClient | null
  connected: boolean
  connecting: boolean
  error: Error | null
  connect: () => Promise<void>
  disconnect: () => void
    send: (message: WSMessage<unknown>) => void
  subscribe: (topics: string | string[]) => void
  unsubscribe: (topics: string | string[]) => void
    on: (event: string, handler: EventHandler) => void
    off: (event: string, handler: EventHandler) => void
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

    const initialiseClient = useCallback(() => {
        if (clientRef.current) {
            return clientRef.current
        }

        const client = new WebSocketClient({
            url,
            reconnect,
            reconnectInterval,
            reconnectAttempts,
            heartbeatInterval,
            debug,
        })

        client.on('open', () => {
            if (!mountedRef.current) {
                return
            }
            setConnected(true)
            setConnecting(false)
            setError(null)
            onOpen?.()
        })

        client.on('close', (event: CloseEvent) => {
            if (!mountedRef.current) {
                return
            }
            setConnected(false)
            setConnecting(false)
            onClose?.(event)
        })

        client.on('error', (err: Error) => {
            if (!mountedRef.current) {
                return
            }
            setError(err)
            setConnecting(false)
            onError?.(err)
        })

        client.on('message', (message: WSMessage<unknown>) => {
            if (!mountedRef.current) {
                return
            }
            onMessage?.(message)
        })

        client.on('reconnect_failed', () => {
            if (!mountedRef.current) {
                return
            }
            setError(new Error('WebSocket reconnect attempts exhausted'))
        })

        clientRef.current = client
        return client
    }, [
        debug,
        heartbeatInterval,
        onClose,
        onError,
        onMessage,
        onOpen,
        reconnect,
        reconnectAttempts,
        reconnectInterval,
        url,
    ])

  const connect = useCallback(async () => {
      const client = initialiseClient()
      if (!client || connecting || connected) {
          return
      }

    setConnecting(true)
    try {
        await client.connect()
    } catch (err) {
        const connectionError = err instanceof Error ? err : new Error(String(err))
        setError(connectionError)
        setConnecting(false)
        onError?.(connectionError)
    }
  }, [connected, connecting, initialiseClient, onError])

  const disconnect = useCallback(() => {
      if (!clientRef.current) {
          return
      }

      clientRef.current.disconnect()
      clientRef.current.removeAllListeners()
      clientRef.current = null
      setConnected(false)
      setConnecting(false)
  }, [])

    const send = useCallback((message: WSMessage<unknown>) => {
        clientRef.current?.send(message)
  }, [])

  const subscribe = useCallback((topics: string | string[]) => {
      if (!clientRef.current) {
          return
      }
      clientRef.current.subscribe(topics)
  }, [])

  const unsubscribe = useCallback((topics: string | string[]) => {
      if (!clientRef.current) {
          return
      }
      clientRef.current.unsubscribe(topics)
  }, [])

    const on = useCallback((event: string, handler: EventHandler) => {
        clientRef.current?.on(event, handler)
  }, [])

    const off = useCallback((event: string, handler: EventHandler) => {
        clientRef.current?.off(event, handler)
  }, [])

    useEffect(() => {
        initialiseClient()
        return () => {
            mountedRef.current = false
            disconnect()
        }
    }, [initialiseClient, disconnect])

    useEffect(() => {
        if (autoConnect) {
            void connect()
        }
    }, [autoConnect, connect])

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

type QuotePayload = Record<string, unknown> & { symbol?: string }
type TradePayload = Record<string, unknown> & { symbol?: string }
type OrderBookPayload = Record<string, unknown> & { symbol?: string }

interface MarketDataState {
    quotes: Record<string, QuotePayload>
    trades: Record<string, TradePayload[]>
    orderbooks: Record<string, OrderBookPayload>
}

const DEFAULT_WS_URL = (import.meta.env.VITE_WS_URL || '').trim() || 'ws://localhost:8000/ws'

export const useMarketData = (symbols: string[]): MarketDataState & UseWebSocketReturn => {
    const [quotes, setQuotes] = useState<Record<string, QuotePayload>>({})
    const [trades, setTrades] = useState<Record<string, TradePayload[]>>({})
    const [orderbooks, setOrderbooks] = useState<Record<string, OrderBookPayload>>({})

    const websocket = useWebSocket({
        url: DEFAULT_WS_URL,
    onMessage: (message) => {
        const payload = message.data as Record<string, unknown>
        const symbol = (payload?.symbol as string | undefined) ?? ''
        if (!symbol) {
            return
        }

      switch (message.type) {
        case WSMessageType.QUOTE:
            setQuotes((prev) => ({
            ...prev,
                [symbol]: payload,
          }))
          break
        case WSMessageType.TRADE:
            setTrades((prev) => ({
            ...prev,
                [symbol]: [payload, ...(prev[symbol] ?? []).slice(0, 99)],
          }))
          break
        case WSMessageType.ORDERBOOK:
            setOrderbooks((prev) => ({
            ...prev,
                [symbol]: payload,
          }))
            break
          default:
          break
      }
    },
  })

    const {connected, subscribe, unsubscribe, ...rest} = websocket

  useEffect(() => {
      if (!connected || symbols.length === 0) {
          return
    }

      const quoteTopics = symbols.map((symbol) => `quote:${symbol}`)
      const tradeTopics = symbols.map((symbol) => `trade:${symbol}`)
      const orderbookTopics = symbols.map((symbol) => `orderbook:${symbol}`)
      const topics = [...quoteTopics, ...tradeTopics, ...orderbookTopics]

      subscribe(topics)

    return () => {
        unsubscribe(topics)
    }
  }, [connected, subscribe, unsubscribe, symbols])

  return {
    quotes,
    trades,
    orderbooks,
      connected,
      subscribe,
      unsubscribe,
      ...rest,
  }
}

interface SystemWebSocketState {
    systemStatus: SystemStatus | null
    components: ComponentStatus[]
    alerts: Notification[]
}

export const useSystemWebSocket = (): SystemWebSocketState & UseWebSocketReturn => {
    const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
    const [components, setComponents] = useState<ComponentStatus[]>([])
    const [alerts, setAlerts] = useState<Notification[]>([])

    const websocket = useWebSocket({
        url: DEFAULT_WS_URL,
    onMessage: (message) => {
      switch (message.type) {
        case WSMessageType.SYSTEM_STATUS:
            setSystemStatus(message.data as SystemStatus)
          break
        case WSMessageType.COMPONENT_UPDATE:
            setComponents(message.data as ComponentStatus[])
          break
        case WSMessageType.ALERT:
            setAlerts((prev) => [message.data as Notification, ...prev].slice(0, 50))
            break
          default:
          break
      }
    },
  })

    const {connected, subscribe, unsubscribe, ...rest} = websocket

  useEffect(() => {
      if (!connected) {
          return
    }

      const topics = ['system:status', 'system:components', 'system:alerts']
      subscribe(topics)

    return () => {
        unsubscribe(topics)
    }
  }, [connected, subscribe, unsubscribe])

  return {
    systemStatus,
    components,
    alerts,
      connected,
      subscribe,
      unsubscribe,
      ...rest,
  }
}
