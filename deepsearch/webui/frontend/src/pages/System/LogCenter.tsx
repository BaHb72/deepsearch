// @ts-nocheck

import React, {Fragment, useCallback, useEffect, useMemo, useRef, useState} from 'react'
import {
    Alert,
    Badge,
    Button,
    Card,
    Col,
    Collapse,
    DatePicker,
    Divider,
    Empty,
    Input,
    List,
    message as antdMessage,
    Progress,
    Row,
    Segmented,
    Select,
    Space,
    Spin,
    Statistic,
    Switch,
    Table,
    Tabs,
    Tag,
    Timeline,
    Tooltip,
    Typography
} from 'antd'
import {
    AlertOutlined,
    CloudDownloadOutlined,
    FileTextOutlined,
    FireOutlined,
    LinkOutlined,
    PauseCircleOutlined,
    PlayCircleOutlined,
    ReloadOutlined,
    SearchOutlined,
    ThunderboltOutlined
} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
import type {SegmentedValue} from 'antd/es/segmented'
import {Column, type ColumnConfig, Tiny, type TinyAreaConfig} from '@ant-design/charts'
import dayjs, {Dayjs} from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import advancedFormat from 'dayjs/plugin/advancedFormat'
import durationPlugin from 'dayjs/plugin/duration'

const { Paragraph, Text, Title } = Typography
const { RangePicker } = DatePicker
const { Panel } = Collapse

dayjs.extend(relativeTime)
dayjs.extend(advancedFormat)
dayjs.extend(durationPlugin)

const { Area: TinyArea } = Tiny

type LogLevel = 'TRACE' | 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'FATAL' | 'UNKNOWN'
type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'error'
type RangeKey = '5m' | '30m' | '4h' | '24h' | 'all' | 'custom'

interface LogEntry {
  id: string
  rawId?: number
  timestamp: string
  level: LogLevel
  message: string
  service?: string
  location?: string
  processInfo?: string
  durationMs?: number
  statusCode?: number
  traceId?: string
  host?: string
  context?: string[]
  original: Record<string, any>
}

interface LogFileSummary {
  name: string
  path: string
  size: number
  modified: string
  created: string
}

interface TimelineBucket {
  key: number
  label: string
  error: number
  warn: number
  info: number
  total: number
}

const MAX_LOGS = 2000

const LEVEL_COLORS: Record<LogLevel, string> = {
  TRACE: '#909399',
  DEBUG: '#409EFF',
  INFO: '#36cfc9',
  WARN: '#faad14',
  ERROR: '#ff4d4f',
  FATAL: '#722ED1',
  UNKNOWN: '#595959'
}

const LEVEL_ORDER: LogLevel[] = ['FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'TRACE', 'UNKNOWN']

const CONNECTION_BADGE: Record<ConnectionState, { status: 'success' | 'processing' | 'error' | 'warning'; text: string }> = {
  connected: { status: 'success', text: '实时连接正常' },
  connecting: { status: 'processing', text: '正在连接日志流' },
  reconnecting: { status: 'processing', text: '连接断开，正在重试' },
  error: { status: 'error', text: '连接失败' }
}

const QUICK_RANGE_OPTIONS: Array<{ label: string; value: RangeKey }> = [
  { label: '5分钟', value: '5m' },
  { label: '30分钟', value: '30m' },
  { label: '4小时', value: '4h' },
  { label: '24小时', value: '24h' },
  { label: '全部', value: 'all' },
  { label: '自定义', value: 'custom' }
]

const levelOptions = LEVEL_ORDER.filter(level => level !== 'UNKNOWN').map(level => ({
  label: level,
  value: level
}))

const isErrorLevel = (level: LogLevel) => level === 'ERROR' || level === 'FATAL'
const isWarnLevel = (level: LogLevel) => level === 'WARN'

const hashCode = (input: string): string => {
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash).toString(36)
}

const normalizeLevel = (level?: string): LogLevel => {
  if (!level) {
    return 'UNKNOWN'
  }
  const upper = level.toUpperCase()
  if (upper.includes('TRACE')) return 'TRACE'
  if (upper.includes('DEBUG')) return 'DEBUG'
  if (upper.includes('WARN')) return 'WARN'
  if (upper.includes('ERROR')) return 'ERROR'
  if (upper.includes('FATAL') || upper.includes('CRITICAL')) return 'FATAL'
  if (upper.includes('INFO')) return 'INFO'
  return 'UNKNOWN'
}

const extractDuration = (message?: string, rawDuration?: unknown, rawDurationMs?: unknown): number | undefined => {
  if (typeof rawDuration === 'number' && !Number.isNaN(rawDuration)) {
    return rawDuration
  }
  if (typeof rawDurationMs === 'number' && !Number.isNaN(rawDurationMs)) {
    return rawDurationMs
  }
  if (!message) {
    return undefined
  }
  const match = message.match(/(?:duration|耗时|time taken|took)\s*[=:]\s*(\d+(?:\.\d+)?)(?:\s*(ms|毫秒|s|秒))?/i)
  if (!match) {
    return undefined
  }
  const value = Number(match[1])
  const unit = match[2]?.toLowerCase()
  if (Number.isNaN(value)) {
    return undefined
  }
  if (!unit || unit === 'ms' || unit === '毫秒') {
    return value
  }
  if (unit === 's' || unit === '秒') {
    return value * 1000
  }
  return value
}

const extractStatusCode = (message?: string, rawStatus?: unknown): number | undefined => {
  if (typeof rawStatus === 'number') {
    return rawStatus
  }
  if (!message) {
    return undefined
  }
  const match = message.match(/(?:status(?:_code)?|状态码|code)[\s=:]+(\d{3})/i)
  if (!match) {
    return undefined
  }
  return Number(match[1])
}

const extractTraceId = (message?: string, rawTrace?: unknown): string | undefined => {
  if (typeof rawTrace === 'string') {
    return rawTrace
  }
  if (!message) {
    return undefined
  }
  const match = message.match(/(?:trace[_-]?id|request[_-]?id|traceId)[\s=:]+([A-Za-z0-9-]+)/i)
  if (!match) {
    return undefined
  }
  return match[1]
}

const extractServiceFromProcess = (processInfo?: string): string | undefined => {
  if (!processInfo) {
    return undefined
  }
  const match = processInfo.match(/([A-Za-z0-9_.-]+)\s*\(/)
  return match?.[1]
}

const extractServiceFromLocation = (location?: string): string | undefined => {
  if (!location) {
    return undefined
  }
  const parts = location.split(':')
  if (parts.length > 1) {
    return parts[0]
  }
  return undefined
}

const createLogEntry = (raw: Record<string, any>): LogEntry => {
  const timestamp: string = raw.timestamp || raw.time || new Date().toISOString()
  const level = normalizeLevel(raw.level || raw.log_level || raw.severity)
  const baseMessage = typeof raw.message === 'string' ? raw.message : JSON.stringify(raw.message)
  const durationMs = extractDuration(baseMessage, raw.duration, raw.duration_ms)
  const statusCode = extractStatusCode(baseMessage, raw.status || raw.status_code)
  const traceId = extractTraceId(baseMessage, raw.trace_id || raw.traceId)

  const service = raw.service || raw.module || raw.source || extractServiceFromProcess(raw.process_info) || extractServiceFromLocation(raw.location)

  const idSeed = `${raw.id ?? ''}|${timestamp}|${baseMessage.slice(0, 128)}`
  const entry: LogEntry = {
    id: `log-${hashCode(idSeed)}`,
    rawId: typeof raw.id === 'number' ? raw.id : undefined,
    timestamp,
    level,
    message: baseMessage,
    service,
    location: raw.location,
    processInfo: raw.process_info,
    durationMs,
    statusCode,
    traceId,
    host: raw.host || raw.hostname,
    context: Array.isArray(raw.context) ? raw.context : undefined,
    original: raw
  }

  return entry
}

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const highlightKeyword = (text: string, keyword: string) => {
  if (!keyword.trim()) {
    return text
  }
  const escaped = escapeRegExp(keyword)
  const regex = new RegExp(`(${escaped})`, 'gi')
  const segments = text.split(regex)

  return (
    <>
      {segments.map((segment, index) => (
        index % 2 === 1 ? (
          <Text mark key={`${segment}-${index}`}>
            {segment}
          </Text>
        ) : (
          <Fragment key={`${segment}-${index}`}>
            {segment}
          </Fragment>
        )
      ))}
    </>
  )
}

const formatDuration = (value?: number): string => {
  if (!value && value !== 0) {
    return '--'
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`
  }
  return `${(value / 1000).toFixed(2)} s`
}

const percentile = (values: number[], p: number): number | undefined => {
  if (!values.length) {
    return undefined
  }
  const sorted = [...values].sort((a, b) => a - b)
  const rank = p * (sorted.length - 1)
  const lower = Math.floor(rank)
  const upper = Math.ceil(rank)
  if (lower === upper) {
    return sorted[lower]
  }
  const weight = rank - lower
  return sorted[lower] * (1 - weight) + sorted[upper] * weight
}

const formatBytes = (bytes: number): string => {
  if (Number.isNaN(bytes)) {
    return '--'
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

const LogCenter: React.FC = () => {
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const [rawLogs, setRawLogs] = useState<LogEntry[]>([])
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'table' | 'realtime' | 'timeline'>('table')
  const [rangeKey, setRangeKey] = useState<RangeKey>('30m')
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [levelFilter, setLevelFilter] = useState<LogLevel[]>(['ERROR', 'WARN', 'INFO'])
  const [serviceFilter, setServiceFilter] = useState<string[]>([])
  const [keyword, setKeyword] = useState('')
  const [traceIdFilter, setTraceIdFilter] = useState('')
  const [autoScrollRealtime, setAutoScrollRealtime] = useState(true)
  const [streamPaused, setStreamPaused] = useState(false)
  const [pendingRealtimeCount, setPendingRealtimeCount] = useState(0)
  const [logFiles, setLogFiles] = useState<LogFileSummary[]>([])
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [filesError, setFilesError] = useState<string | null>(null)
  const [lastLogTime, setLastLogTime] = useState<Dayjs | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number>()
  const manualCloseRef = useRef(false)
  const pingTimerRef = useRef<number>()
  const bufferRef = useRef<LogEntry[]>([])
  const realtimeListRef = useRef<HTMLDivElement | null>(null)
  const [connectSeq, setConnectSeq] = useState(0)

  const scheduleReconnect = useCallback(() => {
    window.clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = window.setTimeout(() => {
      setConnectSeq(prev => prev + 1)
    }, 3000)
  }, [])

  const handleLogAppend = useCallback((entry: LogEntry) => {
    if (streamPaused) {
      bufferRef.current.push(entry)
      setPendingRealtimeCount(prev => prev + 1)
      return
    }
    setRawLogs(prev => {
      const next = [...prev, entry]
      if (next.length > MAX_LOGS) {
        next.splice(0, next.length - MAX_LOGS)
      }
      return next
    })
    setPendingRealtimeCount(0)
    setLastLogTime(dayjs(entry.timestamp))
  }, [streamPaused])

  const setupWebSocket = useCallback(() => {
    if (wsRef.current) {
      manualCloseRef.current = true
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/api/system/logs/ws`

    setConnectionState(prev => (prev === 'error' ? 'reconnecting' : 'connecting'))
    manualCloseRef.current = false

    try {
      const socket = new WebSocket(wsUrl)
      wsRef.current = socket

      socket.onopen = () => {
        window.clearTimeout(reconnectTimerRef.current)
        setConnectionState('connected')
      }

      socket.onerror = () => {
        setConnectionState('error')
      }

      socket.onclose = () => {
        wsRef.current = null
        if (!manualCloseRef.current) {
          setConnectionState('reconnecting')
          scheduleReconnect()
        }
      }

      socket.onmessage = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'initial' && Array.isArray(payload.logs)) {
            const initial = payload.logs.map((item: Record<string, any>) => createLogEntry(item))
            setRawLogs(() => {
              const limited = initial.slice(-MAX_LOGS)
              if (limited.length) {
                setLastLogTime(dayjs(limited[limited.length - 1].timestamp))
              }
              return limited
            })
            if (initial.length) {
              setSelectedLogId(initial[initial.length - 1].id)
            }
            setPendingRealtimeCount(0)
            bufferRef.current = []
          }
          if (payload.type === 'update' && payload.log) {
            const entry = createLogEntry(payload.log)
            handleLogAppend(entry)
          }
          if (payload.type === 'error' && payload.message) {
            setConnectionState('error')
            antdMessage.error(`日志流错误：${payload.message}`)
          }
        } catch (error) {
          console.error('解析日志流失败', error)
        }
      }
    } catch (error) {
      console.error('无法建立日志 WebSocket 连接', error)
      setConnectionState('error')
      scheduleReconnect()
    }
  }, [handleLogAppend, scheduleReconnect])

  useEffect(() => {
    setupWebSocket()
    return () => {
      manualCloseRef.current = true
      window.clearTimeout(reconnectTimerRef.current)
      window.clearInterval(pingTimerRef.current)
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close()
      }
    }
  }, [setupWebSocket, connectSeq])

  useEffect(() => {
    window.clearInterval(pingTimerRef.current)
    if (connectionState === 'connected' && wsRef.current) {
      pingTimerRef.current = window.setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send('ping')
        }
      }, 15000)
    }
    return () => {
      window.clearInterval(pingTimerRef.current)
    }
  }, [connectionState])

  useEffect(() => {
    if (!streamPaused && bufferRef.current.length) {
      setRawLogs(prev => {
        const next = [...prev, ...bufferRef.current]
        if (next.length > MAX_LOGS) {
          next.splice(0, next.length - MAX_LOGS)
        }
        return next
      })
      const lastBuffered = bufferRef.current[bufferRef.current.length - 1]
      if (lastBuffered) {
        setLastLogTime(dayjs(lastBuffered.timestamp))
      }
      bufferRef.current = []
      setPendingRealtimeCount(0)
    }
  }, [streamPaused])

  const fetchLogFiles = useCallback(async () => {
    setLoadingFiles(true)
    setFilesError(null)
    try {
      const response = await fetch('/api/system/logs/files')
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }
      const data = await response.json()
      if (data.status === 'success' && Array.isArray(data.files)) {
        setLogFiles(data.files as LogFileSummary[])
      } else {
        throw new Error(data.message || '未能获取日志文件列表')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFilesError(message)
    } finally {
      setLoadingFiles(false)
    }
  }, [])

  useEffect(() => {
    fetchLogFiles()
  }, [fetchLogFiles])

  const computedRange = useMemo(() => {
    if (rangeKey === 'custom') {
      return customRange
    }
    const now = dayjs()
    switch (rangeKey) {
      case '5m':
        return [now.subtract(5, 'minute'), now] as [Dayjs, Dayjs]
      case '30m':
        return [now.subtract(30, 'minute'), now] as [Dayjs, Dayjs]
      case '4h':
        return [now.subtract(4, 'hour'), now] as [Dayjs, Dayjs]
      case '24h':
        return [now.subtract(24, 'hour'), now] as [Dayjs, Dayjs]
      case 'all':
        return null
      default:
        return [now.subtract(30, 'minute'), now] as [Dayjs, Dayjs]
    }
  }, [rangeKey, customRange])

  const filteredLogs = useMemo(() => {
    const range = computedRange
    return rawLogs.filter(log => {
      if (levelFilter.length && !levelFilter.includes(log.level)) {
        return false
      }
      if (serviceFilter.length) {
        if (!log.service || !serviceFilter.includes(log.service)) {
          return false
        }
      }
      if (traceIdFilter && !(log.traceId || '').includes(traceIdFilter.trim())) {
        return false
      }
      if (keyword.trim()) {
        const needle = keyword.trim().toLowerCase()
        const haystack = [
          log.message,
          log.service,
          log.location,
          log.processInfo,
          log.traceId
        ].filter(Boolean).join(' ').toLowerCase()
        if (!haystack.includes(needle)) {
          return false
        }
      }
      if (range) {
        const ts = dayjs(log.timestamp)
        if (!ts.isValid() || ts.isBefore(range[0]) || ts.isAfter(range[1])) {
          return false
        }
      }
      return true
    })
  }, [rawLogs, computedRange, levelFilter, serviceFilter, keyword, traceIdFilter])

  const sortedLogs = useMemo(() => {
    return [...filteredLogs].sort((a, b) => dayjs(b.timestamp).valueOf() - dayjs(a.timestamp).valueOf())
  }, [filteredLogs])

  useEffect(() => {
    if (!selectedLogId && sortedLogs.length) {
      setSelectedLogId(sortedLogs[0].id)
    }
  }, [sortedLogs, selectedLogId])

  const selectedLog = useMemo(() => {
    if (!selectedLogId) {
      return null
    }
    return rawLogs.find(item => item.id === selectedLogId) || null
  }, [rawLogs, selectedLogId])

  const serviceOptions = useMemo(() => {
    const counter = new Map<string, number>()
    rawLogs.forEach(log => {
      if (log.service) {
        counter.set(log.service, (counter.get(log.service) ?? 0) + 1)
      }
    })
    return Array.from(counter.entries()).map(([value, count]) => ({
      label: `${value} (${count})`,
      value
    }))
  }, [rawLogs])

  const metrics = useMemo(() => {
    const total = filteredLogs.length
    let error = 0
    let warn = 0
    let info = 0
    const durations: number[] = []
    const statusCounter: Record<string, number> = { '2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0 }
    const serviceCounter = new Map<string, number>()
    const errorMessageCounter = new Map<string, number>()
    const bucketMap = new Map<number, TimelineBucket>()

    filteredLogs.forEach(log => {
      if (isErrorLevel(log.level)) {
        error += 1
        errorMessageCounter.set(log.message, (errorMessageCounter.get(log.message) ?? 0) + 1)
      } else if (isWarnLevel(log.level)) {
        warn += 1
      } else if (log.level === 'INFO') {
        info += 1
      }
      if (typeof log.durationMs === 'number') {
        durations.push(log.durationMs)
      }
      if (typeof log.statusCode === 'number') {
        const group = `${Math.floor(log.statusCode / 100)}xx`
        statusCounter[group] = (statusCounter[group] ?? 0) + 1
      }
      if (log.service) {
        serviceCounter.set(log.service, (serviceCounter.get(log.service) ?? 0) + 1)
      }
      const minuteKey = dayjs(log.timestamp).startOf('minute').valueOf()
      const bucket = bucketMap.get(minuteKey) ?? {
        key: minuteKey,
        label: dayjs(minuteKey).format('HH:mm'),
        error: 0,
        warn: 0,
        info: 0,
        total: 0
      }
      bucket.total += 1
      if (isErrorLevel(log.level)) {
        bucket.error += 1
      } else if (isWarnLevel(log.level)) {
        bucket.warn += 1
      } else {
        bucket.info += 1
      }
      bucketMap.set(minuteKey, bucket)
    })

    const timeline = Array.from(bucketMap.values()).sort((a, b) => a.key - b.key)
    const durationAvg = durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : undefined
    const durationP95 = percentile(durations, 0.95)
    const durationP99 = percentile(durations, 0.99)

    const services = Array.from(serviceCounter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6)
    const topErrors = Array.from(errorMessageCounter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 5)

    return {
      total,
      error,
      warn,
      info,
      timeline,
      durationAvg,
      durationP95,
      durationP99,
      statusCounter,
      services,
      topErrors
    }
  }, [filteredLogs])

  const realtimeLogs = useMemo(() => {
    return rawLogs.slice(-200)
  }, [rawLogs])

  useEffect(() => {
    if (activeTab === 'realtime' && autoScrollRealtime) {
      const container = realtimeListRef.current
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    }
  }, [realtimeLogs, activeTab, autoScrollRealtime])

  const handleManualRefresh = () => {
    setStreamPaused(false)
    bufferRef.current = []
    setPendingRealtimeCount(0)
    setConnectSeq(prev => prev + 1)
    fetchLogFiles()
  }

  const handleDownloadLatest = () => {
    const latest = logFiles[0]
    if (!latest) {
      antdMessage.warning('暂无可下载的日志文件')
      return
    }
    const link = document.createElement('a')
    link.href = `/api/system/logs/download/${encodeURIComponent(latest.name)}`
    link.download = latest.name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const columns: ColumnsType<LogEntry> = useMemo(() => [
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 160,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss.SSS')
    },
    {
      title: '级别',
      dataIndex: 'level',
      width: 100,
      filters: LEVEL_ORDER.map(level => ({ text: level, value: level })),
      onFilter: (value, record) => record.level === value,
      render: (value: LogLevel) => (
        <Tag color={LEVEL_COLORS[value]}>{value}</Tag>
      )
    },
    {
      title: '服务 / 模块',
      dataIndex: 'service',
      width: 180,
      render: (value?: string) => value || <Text type="secondary">未标识</Text>
    },
    {
      title: '位置',
      dataIndex: 'location',
      width: 200,
      render: (value?: string) => value || <Text type="secondary">--</Text>
    },
    {
      title: '摘要',
      dataIndex: 'message',
      ellipsis: true,
      render: (value: string) => (
        <Tooltip placement="topLeft" title={value}>
          <span>{highlightKeyword(value, keyword)}</span>
        </Tooltip>
      )
    },
    {
      title: '耗时',
      dataIndex: 'durationMs',
      width: 110,
      sorter: (a, b) => (a.durationMs || 0) - (b.durationMs || 0),
      render: (value?: number) => formatDuration(value)
    },
    {
      title: '状态码',
      dataIndex: 'statusCode',
      width: 110,
      render: (value?: number) => value ?? '--'
    },
    {
      title: 'Trace ID',
      dataIndex: 'traceId',
      width: 220,
      render: (value?: string) => value || <Text type="secondary">--</Text>
    }
  ], [keyword])

  const timelineChartConfig: ColumnConfig = useMemo(() => ({
    data: metrics.timeline.flatMap(bucket => ([
      { 时间: bucket.label, 类型: '错误', 数量: bucket.error },
      { 时间: bucket.label, 类型: '警告', 数量: bucket.warn },
      { 时间: bucket.label, 类型: '信息', 数量: bucket.info }
    ])),
    xField: '时间',
    yField: '数量',
    seriesField: '类型',
    isStack: true,
    height: 260,
    legend: {
      position: 'top'
    },
    animation: false,
    scrollbar: metrics.timeline.length > 24 ? { type: 'horizontal' } : undefined,
    tooltip: {
      showMarkers: false
    }
  }), [metrics.timeline])

  const errorTrendConfig: TinyAreaConfig = useMemo(() => ({
    data: metrics.timeline.map(bucket => bucket.error),
    smooth: true,
    height: 60,
    autoFit: true,
    areaStyle: { fill: 'l(270) 0:#ffccc7 1:#ffa39e' }
  }), [metrics.timeline])

  const warnTrendConfig: TinyAreaConfig = useMemo(() => ({
    data: metrics.timeline.map(bucket => bucket.warn),
    smooth: true,
    height: 60,
    autoFit: true,
    areaStyle: { fill: 'l(270) 0:#fff7e6 1:#ffe7ba' }
  }), [metrics.timeline])

  const infoTrendConfig: TinyAreaConfig = useMemo(() => ({
    data: metrics.timeline.map(bucket => bucket.info),
    smooth: true,
    height: 60,
    autoFit: true,
    areaStyle: { fill: 'l(270) 0:#e6fffb 1:#b5f5ec' }
  }), [metrics.timeline])

  return (
    <div style={{ padding: 24, background: '#f5f7fa', minHeight: '100%' }}>
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <Card variant="borderless" style={{ boxShadow: '0 4px 16px rgba(15, 23, 42, 0.06)' }}>
          <Row justify="space-between" align="middle">
            <Col>
              <Space size={16} align="center">
                <FileTextOutlined style={{ fontSize: 28, color: '#1677ff' }} />
                <div>
                  <Title level={3} style={{ marginBottom: 0 }}>
                    系统日志中心
                  </Title>
                  <Text type="secondary">
                    一站式实时监控、检索与洞察
                  </Text>
                </div>
                <Badge status={CONNECTION_BADGE[connectionState].status} text={CONNECTION_BADGE[connectionState].text} />
                {lastLogTime && (
                  <Tooltip title={lastLogTime.format('YYYY-MM-DD HH:mm:ss')}>
                    <Text type="secondary">
                      最近日志 {lastLogTime.fromNow()}
                    </Text>
                  </Tooltip>
                )}
              </Space>
            </Col>
            <Col>
              <Space size={12}>
                {pendingRealtimeCount > 0 && (
                  <Badge count={pendingRealtimeCount} style={{ backgroundColor: '#ff4d4f' }}>
                    <Button type="link" onClick={() => setStreamPaused(false)}>
                      有新日志，点击恢复
                    </Button>
                  </Badge>
                )}
                <Tooltip title={streamPaused ? '恢复实时流' : '暂停追加新日志'}>
                  <Switch
                    checkedChildren={<PlayCircleOutlined />}
                    unCheckedChildren={<PauseCircleOutlined />}
                    checked={!streamPaused}
                    onChange={(checked: boolean) => {
                      setStreamPaused(!checked)
                      if (checked) {
                        setPendingRealtimeCount(0)
                      }
                    }}
                  />
                </Tooltip>
                <Tooltip title="手动刷新日志列表">
                  <Button icon={<ReloadOutlined />} onClick={handleManualRefresh} />
                </Tooltip>
                <Tooltip title="下载最新日志文件">
                  <Button icon={<CloudDownloadOutlined />} onClick={handleDownloadLatest}>
                    下载日志
                  </Button>
                </Tooltip>
              </Space>
            </Col>
          </Row>
          {connectionState === 'error' && (
            <Alert
              style={{ marginTop: 16 }}
              type="error"
              message="无法连接日志流"
              description="请检查后端服务是否启动，或稍后重试。"
              showIcon
            />
          )}
        </Card>

        <Row gutter={16}>
          <Col span={8}>
            <Card>
              <Space align="start" size={16}>
                <FireOutlined style={{ fontSize: 28, color: '#ff4d4f' }} />
                <div>
                  <Statistic title="错误日志" value={metrics.error} suffix={`/ ${metrics.total}`} valueStyle={{ color: '#ff4d4f' }} />
                  <div style={{ marginTop: 12 }}>
                    <TinyArea {...errorTrendConfig} />
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Space align="start" size={16}>
                <AlertOutlined style={{ fontSize: 28, color: '#faad14' }} />
                <div>
                  <Statistic title="警告日志" value={metrics.warn} suffix={`/ ${metrics.total}`} valueStyle={{ color: '#faad14' }} />
                  <div style={{ marginTop: 12 }}>
                    <TinyArea {...warnTrendConfig} />
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Space align="start" size={16}>
                <ThunderboltOutlined style={{ fontSize: 28, color: '#36cfc9' }} />
                <div>
                  <Statistic
                    title="平均处理耗时"
                    value={metrics.durationAvg ? Math.round(metrics.durationAvg) : '--'}
                    suffix={metrics.durationAvg ? ' ms' : ''}
                  />
                  <Space size={12} style={{ marginTop: 8 }}>
                    <Tag color="blue">P95 {formatDuration(metrics.durationP95)}</Tag>
                    <Tag color="purple">P99 {formatDuration(metrics.durationP99)}</Tag>
                  </Space>
                  <div style={{ marginTop: 12 }}>
                    <TinyArea {...infoTrendConfig} />
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
        </Row>

        <Card>
          <Collapse defaultActiveKey={['filters']} ghost>
            <Panel header="检索条件" key="filters">
              <Space wrap size={16}>
                <div>
                  <Text type="secondary">时间范围</Text>
                  <div style={{ marginTop: 8 }}>
                    <Segmented
                      options={QUICK_RANGE_OPTIONS}
                      value={rangeKey}
                      onChange={(value: SegmentedValue) => {
                        setRangeKey(value as RangeKey)
                        if (value !== 'custom') {
                          setCustomRange(null)
                        }
                      }}
                    />
                  </div>
                </div>
                {rangeKey === 'custom' && (
                  <RangePicker
                    showTime
                    value={customRange}
                    onChange={(values) => {
                      if (values) {
                        setCustomRange(values as [Dayjs, Dayjs])
                      } else {
                        setCustomRange(null)
                      }
                    }}
                  />
                )}
                <div>
                  <Text type="secondary">日志级别</Text>
                  <Select
                    mode="multiple"
                    allowClear
                    placeholder="选择级别"
                    value={levelFilter}
                    options={levelOptions}
                    onChange={(values) => setLevelFilter(values as LogLevel[])}
                    style={{ minWidth: 220, marginTop: 8 }}
                  />
                </div>
                <div>
                  <Text type="secondary">服务模块</Text>
                  <Select
                    mode="multiple"
                    allowClear
                    placeholder="筛选服务"
                    value={serviceFilter}
                    options={serviceOptions}
                    onChange={(values) => setServiceFilter(values as string[])}
                    style={{ minWidth: 240, marginTop: 8 }}
                  />
                </div>
                <div>
                  <Text type="secondary">关键字</Text>
                  <Input
                    allowClear
                    prefix={<SearchOutlined />}
                    placeholder="请输入关键词"
                    value={keyword}
                    onChange={(event) => setKeyword(event.target.value)}
                    style={{ width: 240, marginTop: 8 }}
                  />
                </div>
                <div>
                  <Text type="secondary">Trace ID / Request ID</Text>
                  <Input
                    allowClear
                    prefix={<LinkOutlined />}
                    placeholder="输入 Trace ID"
                    value={traceIdFilter}
                    onChange={(event) => setTraceIdFilter(event.target.value)}
                    style={{ width: 240, marginTop: 8 }}
                  />
                </div>
              </Space>
            </Panel>
          </Collapse>
        </Card>

        <Row gutter={24}>
          <Col span={16}>
            <Card style={{ minHeight: 680 }}>
              <Tabs
                activeKey={activeTab}
                onChange={(key) => setActiveTab(key as 'table' | 'realtime' | 'timeline')}
                items={[
                  {
                    key: 'table',
                    label: '列表视图',
                    children: (
                      <Table
                        rowKey="id"
                        columns={columns}
                        dataSource={sortedLogs}
                        size="middle"
                        pagination={{
                          pageSize: 30,
                          showSizeChanger: true,
                          pageSizeOptions: ['20', '30', '50', '100']
                        }}
                        scroll={{ y: 460 }}
                        onRow={record => ({
                          onClick: () => setSelectedLogId(record.id),
                          style: record.id === selectedLogId ? { backgroundColor: 'rgba(22, 119, 255, 0.12)' } : undefined
                        })}
                        locale={{
                          emptyText: (
                            <Empty
                              description={(
                                <span>
                                  暂无匹配日志
                                  {keyword && <span>，请尝试调整关键字</span>}
                                </span>
                              )}
                            />
                          )
                        }}
                      />
                    )
                  },
                  {
                    key: 'realtime',
                    label: '实时流',
                    children: (
                      <div>
                        <Space style={{ marginBottom: 12 }}>
                          <Switch
                            checkedChildren="自动滚动"
                            unCheckedChildren="手动滚动"
                            checked={autoScrollRealtime}
                            onChange={setAutoScrollRealtime}
                          />
                          <Text type="secondary">展示最近 200 条日志</Text>
                        </Space>
                        <div
                          ref={realtimeListRef}
                          style={{
                            maxHeight: 480,
                            overflowY: 'auto',
                            background: '#0f172a',
                            color: '#e2e8f0',
                            padding: '12px 16px',
                            borderRadius: 8,
                            fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                          }}
                        >
                          {realtimeLogs.map(log => (
                            <div key={log.id} style={{ marginBottom: 12, opacity: selectedLogId === log.id ? 1 : 0.85 }}>
                              <Space align="start" size={12}>
                                <Text style={{ color: '#94a3b8' }}>{dayjs(log.timestamp).format('HH:mm:ss')}</Text>
                                <Tag color={LEVEL_COLORS[log.level]}>{log.level}</Tag>
                                <Text style={{ color: '#38bdf8' }}>{log.service || 'unknown'}</Text>
                                <Text style={{ color: '#e2e8f0' }}>{highlightKeyword(log.message, keyword)}</Text>
                              </Space>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  },
                  {
                    key: 'timeline',
                    label: '时间线视图',
                    children: (
                      <div>
                        {metrics.timeline.length ? (
                          <Column {...timelineChartConfig} />
                        ) : (
                          <Empty description="当前筛选下暂无时间线数据" />
                        )}
                        <Divider />
                        <Timeline mode="left" style={{ maxHeight: 360, overflowY: 'auto', paddingRight: 12 }}>
                          {sortedLogs
                            .filter(log => isErrorLevel(log.level) || isWarnLevel(log.level))
                            .slice(0, 30)
                            .reverse()
                            .map(log => (
                              <Timeline.Item
                                key={log.id}
                                color={isErrorLevel(log.level) ? 'red' : 'orange'}
                                dot={<AlertOutlined />}
                              >
                                <Space direction="vertical" size={4}>
                                  <Text strong>{dayjs(log.timestamp).format('HH:mm:ss')}</Text>
                                  <Text type="secondary">{log.service || 'unknown'} / {log.location || '---'}</Text>
                                  <Text>{log.message}</Text>
                                </Space>
                              </Timeline.Item>
                            ))}
                        </Timeline>
                      </div>
                    )
                  }
                ]}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card title="日志详情" style={{ minHeight: 220 }}>
                {selectedLog ? (
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <Space size={12}>
                      <Tag color={LEVEL_COLORS[selectedLog.level]}>{selectedLog.level}</Tag>
                      <Text type="secondary">{dayjs(selectedLog.timestamp).format('YYYY-MM-DD HH:mm:ss.SSS')}</Text>
                    </Space>
                    <Row gutter={[8, 8]}>
                      <Col span={12}>
                        <Text type="secondary">服务模块</Text>
                        <div>{selectedLog.service || '--'}</div>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary">Trace ID</Text>
                        <div>{selectedLog.traceId || '--'}</div>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary">调用位置</Text>
                        <div>{selectedLog.location || '--'}</div>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary">耗时 / 状态</Text>
                        <div>
                          {formatDuration(selectedLog.durationMs)}
                          {' '}
                          {selectedLog.statusCode ? ` / ${selectedLog.statusCode}` : ''}
                        </div>
                      </Col>
                    </Row>
                    <Divider style={{ margin: '8px 0' }} />
                    <Paragraph
                      style={{ marginBottom: 0 }}
                      copyable={{ text: selectedLog.message }}
                      ellipsis={{ rows: 6, expandable: true, symbol: '展开全文' }}
                    >
                      {highlightKeyword(selectedLog.message, keyword)}
                    </Paragraph>
                  </Space>
                ) : (
                  <Empty description="请选择一条日志" />
                )}
              </Card>

              <Card title="智能洞察">
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Text strong>状态分布</Text>
                  <Space size={8}>
                    {Object.entries(metrics.statusCounter).map(([status, count]) => (
                      <Tag key={status} color={status.startsWith('5') ? 'red' : status.startsWith('4') ? 'orange' : 'blue'}>
                        {status.toUpperCase()} {count}
                      </Tag>
                    ))}
                  </Space>
                  <Divider style={{ margin: '12px 0' }} />
                  <Text strong>高频错误</Text>
                  {metrics.topErrors.length ? (
                    <List
                      size="small"
                      dataSource={metrics.topErrors}
                      renderItem={([message, count]) => (
                        <List.Item>
                          <Space align="start" size={8}>
                            <Badge color="#ff4d4f" />
                            <div>
                              <Text>{message}</Text>
                              <div style={{ color: '#8c8c8c' }}>{count} 次</div>
                            </div>
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Text type="secondary">暂无明显异常模式</Text>
                  )}
                </Space>
              </Card>

              <Card title="日志文件">
                {loadingFiles ? (
                  <Spin />
                ) : filesError ? (
                  <Alert type="error" message={filesError} showIcon action={<Button size="small" onClick={fetchLogFiles}>重试</Button>} />
                ) : logFiles.length ? (
                  <List
                    size="small"
                    dataSource={logFiles.slice(0, 6)}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Button
                            key="download"
                            type="link"
                            icon={<CloudDownloadOutlined />}
                            onClick={() => {
                              const link = document.createElement('a')
                              link.href = `/api/system/logs/download/${encodeURIComponent(item.name)}`
                              link.download = item.name
                              document.body.appendChild(link)
                              link.click()
                              document.body.removeChild(link)
                            }}
                          >
                            下载
                          </Button>
                        ]}
                      >
                        <List.Item.Meta
                          title={item.name}
                          description={(
                            <Space size={16}>
                              <span>{formatBytes(item.size)}</span>
                              <span>更新 {dayjs(item.modified).fromNow()}</span>
                            </Space>
                          )}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无日志文件" />
                )}
                <Divider style={{ margin: '12px 0' }} />
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Text strong>高频服务</Text>
                  {metrics.services.length ? (
                    metrics.services.map(([name, count]) => (
                      <Space key={name} style={{ width: '100%' }}>
                        <Text style={{ flex: 1 }}>{name}</Text>
                        <Progress percent={Math.min(100, Number(((count / Math.max(1, metrics.total)) * 100).toFixed(1)))} showInfo={false} style={{ flex: 2 }} />
                        <Text type="secondary">{count}</Text>
                      </Space>
                    ))
                  ) : (
                    <Text type="secondary">暂无服务分布数据</Text>
                  )}
                </Space>
              </Card>
            </Space>
          </Col>
        </Row>
      </Space>
    </div>
  )
}

export default LogCenter

