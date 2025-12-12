// @ts-nocheck
import React, {Fragment, useCallback, useEffect, useMemo, useRef, useState} from 'react'
import {
    Badge,
    Button,
    Card,
    Collapse,
    DatePicker,
    Divider,
    Empty,
    Input,
    List,
    message as antdMessage,
    Select,
    Space,
    Switch,
    Table,
    Tag,
    theme,
    Tooltip,
    Typography
} from 'antd'
import {PageContainer, ProCard, StatisticCard} from '@ant-design/pro-components'
import {
    AlertOutlined,
    CloudDownloadOutlined,
    FireOutlined,
    LinkOutlined,
    PauseCircleOutlined,
    PlayCircleOutlined,
    ReloadOutlined,
    SearchOutlined,
    ThunderboltOutlined
} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
import {Column, Tiny} from '@ant-design/charts'
import dayjs, {Dayjs} from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import advancedFormat from 'dayjs/plugin/advancedFormat'
import durationPlugin from 'dayjs/plugin/duration'

const { Paragraph, Text, Title } = Typography
const { RangePicker } = DatePicker
const { Panel } = Collapse
const {Statistic} = StatisticCard

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
    const {token} = theme.useToken()
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const [rawLogs, setRawLogs] = useState<LogEntry[]>([])
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'table' | 'realtime' | 'timeline'>('table')
    const [rightPanelTab, setRightPanelTab] = useState<'details' | 'insights' | 'files'>('insights')
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
                const lastId = initial[initial.length - 1].id;
                // Don't auto-select to avoid jumping
                // setSelectedLogId(lastId)
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

    // --- Derived State ---

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
            log.message, log.service, log.location, log.processInfo, log.traceId
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

    // Auto switch right tab to Details when log selected
  useEffect(() => {
      if (selectedLogId) {
          setRightPanelTab('details');
    }
  }, [selectedLogId]);

  const selectedLog = useMemo(() => {
      if (!selectedLogId) return null
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
      // const durationP99 = percentile(durations, 0.99)
    const services = Array.from(serviceCounter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6)
    const topErrors = Array.from(errorMessageCounter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 5)

      return {total, error, warn, info, timeline, durationAvg, durationP95, statusCounter, services, topErrors}
  }, [filteredLogs])

    // Realtime scroll logic
    const realtimeLogs = useMemo(() => rawLogs.slice(-200), [rawLogs])
  useEffect(() => {
    if (activeTab === 'realtime' && autoScrollRealtime) {
      const container = realtimeListRef.current
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    }
  }, [realtimeLogs, activeTab, autoScrollRealtime])

    // Handlers
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

    // --- Render Components ---

  const columns: ColumnsType<LogEntry> = useMemo(() => [
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 160,
        render: (value: string) => dayjs(value).format('HH:mm:ss.SSS')
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
        title: '服务',
      dataIndex: 'service',
        width: 140,
        ellipsis: true,
        render: (value?: string) => value ? <Tag bordered={false}>{value}</Tag> : '-'
    },
    {
        title: '消息',
      dataIndex: 'message',
      ellipsis: true,
      render: (value: string) => (
        <Tooltip placement="topLeft" title={value}>
          <span>{highlightKeyword(value, keyword)}</span>
        </Tooltip>
      )
    },
    {
        title: 'TraceID',
      dataIndex: 'traceId',
        width: 180,
        ellipsis: true,
        render: (value?: string) => value ? <Text type="secondary" code>{value}</Text> : '-'
    },
      {
          title: '操作',
          key: 'action',
          width: 80,
          render: (_, record) => (
              <Button
                  type="link"
                  size="small"
                  onClick={(e) => {
                      e.stopPropagation();
                      setSelectedLogId(record.id);
                  }}
              >
                  详情
              </Button>
          )
    }
  ], [keyword])

    const timelineChartConfig = useMemo(() => ({
    data: metrics.timeline.flatMap(bucket => ([
        {time: bucket.label, type: 'Error', count: bucket.error},
        {time: bucket.label, type: 'Warn', count: bucket.warn},
        {time: bucket.label, type: 'Info', count: bucket.info}
    ])),
        xField: 'time',
        yField: 'count',
        seriesField: 'type',
    isStack: true,
        height: 200,
        color: {Error: '#ff4d4f', Warn: '#faad14', Info: '#36cfc9'},
        legend: {position: 'top'},
    animation: false,
    }), [metrics.timeline]);

  return (
      <PageContainer
          header={{
              title: '日志中心',
              subTitle: (
                  <Space>
                      <Badge status={CONNECTION_BADGE[connectionState].status}
                             text={CONNECTION_BADGE[connectionState].text}/>
                      {lastLogTime && <Text type="secondary"
                                            style={{fontSize: 12}}>最后更新: {lastLogTime.format('HH:mm:ss')}</Text>}
                  </Space>
              ),
              extra: [
                  <Space key="controls">
                      {pendingRealtimeCount > 0 && (
                          <Badge count={pendingRealtimeCount} style={{backgroundColor: '#ff4d4f'}}>
                              <Button type="primary" shape="round" onClick={() => setStreamPaused(false)}>
                                  有新日志
                              </Button>
                          </Badge>
                      )}
                      <Switch
                          checkedChildren={<PlayCircleOutlined/>}
                          unCheckedChildren={<PauseCircleOutlined/>}
                          checked={!streamPaused}
                          onChange={(checked) => {
                              setStreamPaused(!checked)
                              if (checked) setPendingRealtimeCount(0)
                          }}
                      />
                      <Button icon={<ReloadOutlined/>} onClick={handleManualRefresh}>刷新</Button>
                      <Button icon={<CloudDownloadOutlined/>} onClick={handleDownloadLatest}>下载</Button>
                  </Space>
              ]
          }}
      >
          <ProCard.Group direction="row" gutter={16} ghost title="实时概览">
              <StatisticCard
                  statistic={{
                      title: '错误 (Error)',
                      value: metrics.error,
                      icon: <FireOutlined style={{color: token.colorError}}/>,
                  }}
              />
              <StatisticCard
                  statistic={{
                      title: '警告 (Warn)',
                      value: metrics.warn,
                      icon: <AlertOutlined style={{color: token.colorWarning}}/>,
                  }}
              />
              <StatisticCard
                  statistic={{
                      title: '平均耗时',
                      value: metrics.durationAvg ? Math.round(metrics.durationAvg) : '--',
                      suffix: 'ms',
                      icon: <ThunderboltOutlined style={{color: token.colorPrimary}}/>,
                  }}
              />
          </ProCard.Group>

          <ProCard split="vertical" bordered headerBordered gutter={16} ghost style={{marginTop: 16}}>
              {/* Left: Main Content */}
              <ProCard colSpan="flex" ghost direction="column" gutter={[0, 16]}>

                  {/* Filter Bar */}
                  <ProCard bordered size="small" collapsible title="筛选" defaultCollapsed={false}>
                      <Space wrap size={16}>
                          <Select
                              popupMatchSelectWidth={false}
                              value={rangeKey}
                              options={QUICK_RANGE_OPTIONS}
                              onChange={v => {
                                  setRangeKey(v);
                                  if (v !== 'custom') setCustomRange(null);
                              }}
                              style={{width: 100}}
                          />
                          {rangeKey === 'custom' &&
                              <RangePicker showTime value={customRange} onChange={v => setCustomRange(v)}/>}
                          <Select
                              mode="multiple"
                              placeholder="日志级别"
                              allowClear
                              value={levelFilter}
                              options={levelOptions}
                              onChange={setLevelFilter}
                              style={{minWidth: 120}}
                          />
                          <Select
                              mode="multiple"
                              placeholder="服务模块"
                              allowClear
                              value={serviceFilter}
                              options={serviceOptions}
                              onChange={setServiceFilter}
                              style={{minWidth: 150}}
                          />
                          <Input
                              prefix={<SearchOutlined/>}
                              placeholder="关键字搜索..."
                              value={keyword}
                              onChange={e => setKeyword(e.target.value)}
                              style={{width: 200}}
                              allowClear
                          />
                          <Input
                              prefix={<LinkOutlined/>}
                              placeholder="TraceID"
                              value={traceIdFilter}
                              onChange={e => setTraceIdFilter(e.target.value)}
                              style={{width: 160}}
                              allowClear
                          />
                      </Space>
                  </ProCard>

                  {/* Content Tabs */}
                  <ProCard bordered tabs={{
                      activeKey: activeTab,
                      onChange: (key) => setActiveTab(key as any),
                      items: [
                          {
                              key: 'table',
                              label: '列表视图',
                              children: (
                                  <Table
                                      rowKey="id"
                                      columns={columns}
                                      dataSource={sortedLogs}
                                      size="small"
                                      pagination={{pageSize: 20, showSizeChanger: true}}
                                      scroll={{y: 600}}
                                      onRow={(record) => ({
                                          onClick: () => setSelectedLogId(record.id),
                                          style: {
                                              cursor: 'pointer',
                                              backgroundColor: record.id === selectedLogId ? token.colorPrimaryBg : undefined
                                          }
                                      })}
                                  />
                              )
                          },
                          {
                              key: 'realtime',
                              label: '实时流',
                              children: (
                                  <div style={{background: '#1e1e1e', borderRadius: 8, padding: 16}}>
                                      <Space style={{marginBottom: 12}}>
                                          <Switch checked={autoScrollRealtime} onChange={setAutoScrollRealtime}
                                                  checkedChildren="自动滚动" unCheckedChildren="停止"/>
                                          <Text style={{color: '#888'}}>显示最近 200 条</Text>
                                      </Space>
                                      <div
                                          ref={realtimeListRef}
                                          style={{
                                              height: 600,
                                              overflowY: 'auto',
                                              fontFamily: 'monospace',
                                              fontSize: 13
                                          }}
                                      >
                                          {realtimeLogs.map(log => (
                                              <div key={log.id}
                                                   style={{marginBottom: 4, lineHeight: '1.4', color: '#ccc'}}>
                                                  <span style={{
                                                      color: '#666',
                                                      marginRight: 8
                                                  }}>{dayjs(log.timestamp).format('HH:mm:ss')}</span>
                                                  <span style={{
                                                      color: LEVEL_COLORS[log.level],
                                                      marginRight: 8,
                                                      fontWeight: 'bold'
                                                  }}>[{log.level}]</span>
                                                  <span style={{color: '#569cd6', marginRight: 8}}>{log.service}:</span>
                                                  <span>{log.message}</span>
                                              </div>
                                          ))}
                                      </div>
                                  </div>
                              )
                          },
                          {
                              key: 'timeline',
                              label: '趋势分析',
                              children: <Column {...timelineChartConfig} />
                          }
                      ]
                  }}/>
              </ProCard>

              {/* Right: Sidebar */}
              <ProCard
                  title="详情与分析"
                  colSpan={8}
                  collapsible
                  bordered

                  tabs={{
                      activeKey: rightPanelTab,
                      onChange: (k) => setRightPanelTab(k as any),
                      items: [
                          {
                              key: 'details',
                              label: '详情',
                              children: selectedLog ? (
                                  <Space direction="vertical" style={{width: '100%'}}>
                                      <Space>
                      <Tag color={LEVEL_COLORS[selectedLog.level]}>{selectedLog.level}</Tag>
                      <Text type="secondary">{dayjs(selectedLog.timestamp).format('YYYY-MM-DD HH:mm:ss.SSS')}</Text>
                    </Space>
                                      <Divider style={{margin: '8px 0'}}/>
                                      <div style={{wordBreak: 'break-all', maxHeight: 400, overflow: 'auto'}}>
                                          <Text style={{fontSize: 13, fontFamily: 'monospace'}}>
                                              {highlightKeyword(selectedLog.message, keyword)}
                                          </Text>
                                      </div>
                                      <Divider style={{margin: '8px 0'}}/>
                                      <List size="small">
                                          <List.Item><Text type="secondary">Service:</Text> {selectedLog.service}
                                          </List.Item>
                                          <List.Item><Text type="secondary">TraceID:</Text> {selectedLog.traceId || '-'}
                                          </List.Item>
                                          <List.Item><Text
                                              type="secondary">Location:</Text> {selectedLog.location || '-'}
                                          </List.Item>
                                          <List.Item><Text
                                              type="secondary">StatusCode:</Text> {selectedLog.statusCode || '-'}
                                          </List.Item>
                                          <List.Item><Text
                                              type="secondary">Duration:</Text> {formatDuration(selectedLog.durationMs)}
                                          </List.Item>
                                      </List>
                  </Space>
                              ) : <Empty description="点击日志查看详情"/>
                          },
                          {
                              key: 'insights',
                              label: '洞察',
                              children: (
                                  <Space direction="vertical" style={{width: '100%'}}>
                                      <Card size="small" title="高频错误" bordered={false}>
                                          <List
                                              size="small"
                                              dataSource={metrics.topErrors}
                                              renderItem={([msg, count]) => (
                                                  <List.Item>
                                                      <Badge count={count} overflowCount={999}
                                                             style={{backgroundColor: '#f5222d'}}/>
                                                      <Text type="secondary" ellipsis
                                                            style={{marginLeft: 8, maxWidth: 200}}>{msg}</Text>
                                                  </List.Item>
                                              )}
                                          />
                                      </Card>
                                      <Card size="small" title="状态码分布" bordered={false}>
                                          <Space wrap>
                                              {Object.entries(metrics.statusCounter).map(([k, v]) => v > 0 &&
                                                  <Tag key={k}>{k}: {v}</Tag>)}
                                          </Space>
                                      </Card>
                                  </Space>
                              )
                          },
                          {
                              key: 'files',
                              label: '文件',
                              children: (
                  <List
                    size="small"
                    dataSource={logFiles}
                    renderItem={item => (
                        <List.Item actions={[<a onClick={() => {
                            const link = document.createElement('a')
                            link.href = `/api/system/logs/download/${encodeURIComponent(item.name)}`
                            link.download = item.name
                            link.click()
                        }}><CloudDownloadOutlined/></a>]}>
                        <List.Item.Meta
                            title={<Text ellipsis>{item.name}</Text>}
                            description={formatBytes(item.size)}
                        />
                      </List.Item>
                    )}
                  />
                              )
                          }
                      ]
                  }}
              />
          </ProCard>
      </PageContainer>
  )
}

export default LogCenter
