import { useEffect, useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { Alert, Empty, Segmented, Tooltip, message, Table, Tag, Tabs, Typography } from 'antd'
import { PageContainer, ProCard } from '@ant-design/pro-components'
import { DatabaseOutlined, FireOutlined, WarningOutlined } from '@ant-design/icons'
import request from '@/api/request'

const { Text } = Typography
const { TabPane } = Tabs

interface ZTStockItem {
  symbol: string
  name: string
  change_pct: number
  price: number
  seal_funds: number
  first_seal_time: string
  continuous_days: number
  industry: string
}

type ConceptFlowPeriod = 'realtime' | 'today' | 'week'

interface AnomalyItem {
  timestamp: string
  symbol: string
  name: string
  reason: string
  price: number
  change_pct: number
}

const marketAPI = {
  getZTPool: async (date?: string): Promise<ZTStockItem[]> =>
    request.get('/trading/market/zt-pool', { params: { date } }),

  getConceptFlow: async (params: { period: ConceptFlowPeriod; limit?: number }): Promise<unknown> =>
    request.get('/market/live/concept-flow', { params }),

  getAnomalies: async (): Promise<AnomalyItem[]> => request.get('/trading/market/anomalies'),
}

interface ConceptFlowItem {
  concept_name: string
  concept_code: string
  main_net_inflow: number | null
  main_net_inflow_pct: number | null
  change_pct: number | null
  leading_stock: string
  flow_speed: number | null
}

interface ConceptFlowPayload {
  items?: unknown
  data_source?: string
  stale?: boolean
  retrieved_at?: string
  detail?: Record<string, unknown>
  period?: string
  count?: number
}

const PERIOD_OPTIONS: { label: string; value: ConceptFlowPeriod }[] = [
  { label: '实时', value: 'realtime' },
  { label: '今日', value: 'today' },
  { label: '周(5日)', value: 'week' },
]

const PERIOD_REFRESH_MS: Record<ConceptFlowPeriod, number> = {
  realtime: 5000,
  today: 15000,
  week: 30000,
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

function toPercent(value: unknown): number | null {
  const num = toNumber(value)
  if (num === null) {
    return null
  }
  return Math.abs(num) <= 1 ? num * 100 : num
}

function normalizeConceptFlow(payload: unknown): ConceptFlowItem[] {
  const rows = (() => {
    if (payload && typeof payload === 'object') {
      const items = (payload as ConceptFlowPayload).items
      if (Array.isArray(items)) {
        return items
      }
    }
    if (Array.isArray(payload)) {
      return payload
    }
    return []
  })()

  const normalized = rows
    .filter((row): row is Record<string, unknown> => !!row && typeof row === 'object')
    .map((row) => {
      const conceptName =
        String(row.concept_name ?? row.board ?? row.name ?? row['板块名称'] ?? row['概念名称'] ?? '')
      const conceptCode = String(row.concept_code ?? row.code ?? row['板块代码'] ?? '')
      const mainNetInflow = toNumber(row.main_net_inflow) ?? toNumber(row.velocity)
      const mainNetInflowPct = toPercent(row.main_net_inflow_pct)
      const changePct = toPercent(row.change_pct ?? row.lead_change)
      const leadingStock = String(row.leading_stock ?? row.lead_stock ?? row['今日主力净流入最大股'] ?? '')
      const flowSpeed = toNumber(row.flow_speed) ?? toNumber(row.velocity) ?? mainNetInflow

      return {
        concept_name: conceptName,
        concept_code: conceptCode,
        main_net_inflow: mainNetInflow,
        main_net_inflow_pct: mainNetInflowPct,
        change_pct: changePct,
        leading_stock: leadingStock,
        flow_speed: flowSpeed,
      }
    })
    .filter((row) => row.concept_name || row.concept_code)

  normalized.sort((a, b) => (b.main_net_inflow ?? 0) - (a.main_net_inflow ?? 0))
  return normalized
}

function formatCapital(value: number | null): string {
  if (value === null) {
    return '-'
  }
  const abs = Math.abs(value)
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`
  }
  return value.toFixed(2)
}

function formatPercent(value: number | null): string {
  if (value === null) {
    return '-'
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

function formatAbsoluteTime(value: string): string {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const year = date.getFullYear()
  const month = pad2(date.getMonth() + 1)
  const day = pad2(date.getDate())
  const hours = pad2(date.getHours())
  const minutes = pad2(date.getMinutes())
  const seconds = pad2(date.getSeconds())
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

function formatRelativeTime(value: string): string {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '-'
  }
  const diffMs = Date.now() - date.getTime()
  if (diffMs < 0) {
    return '刚刚'
  }
  const diffSeconds = Math.floor(diffMs / 1000)
  if (diffSeconds < 10) {
    return '刚刚'
  }
  if (diffSeconds < 60) {
    return `${diffSeconds}秒前`
  }
  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) {
    return `${diffMinutes}分钟前`
  }
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) {
    return `${diffHours}小时前`
  }
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) {
    return '昨天'
  }
  if (diffDays < 7) {
    return `${diffDays}天前`
  }
  return formatAbsoluteTime(value)
}

function getTrendColor(value: number | null): string {
  if (value === null || value === 0) {
    return '#595959'
  }
  return value > 0 ? '#cf1322' : '#389e0d'
}

function buildConceptFlowDiagnosis(
  payload: ConceptFlowPayload | null,
  rows: ConceptFlowItem[],
  period: ConceptFlowPeriod,
): string {
  if (!payload) {
    return ''
  }
  const detail = payload.detail
  if (!detail || typeof detail !== 'object') {
    if (rows.length === 0) {
      return period === 'realtime'
        ? '实时概念资金流暂无数据。'
        : `${period === 'today' ? '今日' : '周'}概念资金流暂无数据。`
    }
    return ''
  }

  const code = typeof detail.code === 'string' ? detail.code : ''
  const message = typeof detail.message === 'string' ? detail.message : ''
  const reason = typeof detail.reason === 'string' ? detail.reason : ''
  const fallback = detail.fallback

  const parts: string[] = []
  if (message) {
    parts.push(message)
  }
  if (reason) {
    parts.push(`原因: ${reason}`)
  }
  if (fallback && typeof fallback === 'object') {
    const fallbackFrom =
      typeof (fallback as Record<string, unknown>).from === 'string'
        ? String((fallback as Record<string, unknown>).from)
        : ''
    const fallbackTo =
      typeof (fallback as Record<string, unknown>).to === 'string'
        ? String((fallback as Record<string, unknown>).to)
        : ''
    if (fallbackFrom || fallbackTo) {
      parts.push(`回退链路: ${fallbackFrom || '-'} -> ${fallbackTo || '-'}`)
    }
  }
  if (!parts.length && rows.length === 0) {
    parts.push('概念资金流接口返回空结果。')
  }
  if (code) {
    parts.push(`状态码: ${code}`)
  }
  return parts.join('；')
}

type RefreshState = 'idle' | 'refreshing' | 'success' | 'error'

const ZTPoolTable = () => {
  const [data, setData] = useState<ZTStockItem[]>([])
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await marketAPI.getZTPool()
      if (Array.isArray(res)) {
        setData(res)
      }
    } catch {
      message.error('获取涨停股池失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const columns: ColumnsType<ZTStockItem> = [
    { title: '代码', dataIndex: 'symbol', render: (t: string) => <Text strong>{t}</Text> },
    { title: '名称', dataIndex: 'name' },
    {
      title: '涨幅',
      dataIndex: 'change_pct',
      render: (t: number) => <Text type="danger">+{Number(t).toFixed(2)}%</Text>,
    },
    { title: '最新价', dataIndex: 'price' },
    { title: '封板资金', dataIndex: 'seal_funds', render: (t: number) => `${(t / 10000).toFixed(0)}万` },
    { title: '首次封板', dataIndex: 'first_seal_time' },
    { title: '连板数', dataIndex: 'continuous_days', render: (t: number) => <Tag color="red">{t}连板</Tag> },
    { title: '行业', dataIndex: 'industry' },
  ]

  return <Table dataSource={data} columns={columns} loading={loading} rowKey="symbol" size="small" />
}

const ConceptFlowPanel = () => {
  const [period, setPeriod] = useState<ConceptFlowPeriod>('realtime')
  const [data, setData] = useState<ConceptFlowItem[]>([])
  const [initialLoading, setInitialLoading] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [dataSource, setDataSource] = useState('')
  const [retrievedAt, setRetrievedAt] = useState('')
  const [stale, setStale] = useState(false)
  const [refreshState, setRefreshState] = useState<RefreshState>('idle')
  const [refreshError, setRefreshError] = useState('')
  const [diagnosis, setDiagnosis] = useState('')

  const fetchData = async (selectedPeriod: ConceptFlowPeriod, silent = false) => {
    const useRefreshMode = silent || data.length > 0
    if (useRefreshMode) {
      setIsRefreshing(true)
    } else {
      setInitialLoading(true)
    }
    setRefreshState('refreshing')
    try {
      const payload = (await marketAPI.getConceptFlow({ period: selectedPeriod, limit: 50 })) as ConceptFlowPayload
      const normalized = normalizeConceptFlow(payload)
      setData(normalized)
      setDataSource(String(payload?.data_source ?? ''))
      setRetrievedAt(String(payload?.retrieved_at ?? ''))
      setStale(Boolean(payload?.stale))
      setDiagnosis(buildConceptFlowDiagnosis(payload, normalized, selectedPeriod))
      setRefreshError('')
      setRefreshState('success')
    } catch (error) {
      const text = error instanceof Error ? error.message : '获取概念资金流失败'
      setRefreshState('error')
      setRefreshError(text)
      setDiagnosis(text)
      if (!silent) {
        message.error('获取概念资金流失败')
      }
      setStale(true)
    } finally {
      if (useRefreshMode) {
        setIsRefreshing(false)
      } else {
        setInitialLoading(false)
      }
    }
  }

  useEffect(() => {
    void fetchData(period, false)
    const timer = window.setInterval(() => {
      void fetchData(period, true)
    }, PERIOD_REFRESH_MS[period])
    return () => window.clearInterval(timer)
  }, [period])

  const hasInflowPctData = data.some((item) => item.main_net_inflow_pct !== null)
  const refreshStatusTag = (() => {
    if (refreshState === 'refreshing') {
      return <Tag color="processing">更新中</Tag>
    }
    if (refreshState === 'success') {
      return <Tag color="success">已更新</Tag>
    }
    if (refreshState === 'error') {
      return <Tag color="error" title={refreshError || '更新失败，已保留上次数据'}>更新失败</Tag>
    }
    return <Tag>待更新</Tag>
  })()

  const timeRelative = formatRelativeTime(retrievedAt)
  const timeAbsolute = formatAbsoluteTime(retrievedAt)

  const columns: ColumnsType<ConceptFlowItem> = [
    {
      title: '概念',
      dataIndex: 'concept_name',
      width: 170,
      render: (value: string, row) => (
        <Text strong>
          {value || row.concept_code || '-'}
        </Text>
      ),
    },
    {
      title: '领涨股',
      dataIndex: 'leading_stock',
      width: 130,
      render: (value: string) => value || '-',
    },
    {
      title: '板块涨跌',
      dataIndex: 'change_pct',
      width: 110,
      render: (value: number | null) => (
        <Text style={{ color: getTrendColor(value), fontFamily: 'Consolas, monospace' }}>
          {formatPercent(value)}
        </Text>
      ),
    },
    {
      title: '流速',
      dataIndex: 'flow_speed',
      width: 140,
      render: (value: number | null) => (
        <Text style={{ color: getTrendColor(value), fontFamily: 'Consolas, monospace' }}>
          {formatCapital(value)}
        </Text>
      ),
    },
    {
      title: '主力净流入',
      dataIndex: 'main_net_inflow',
      width: 150,
      sorter: (a, b) => (a.main_net_inflow ?? 0) - (b.main_net_inflow ?? 0),
      defaultSortOrder: 'descend',
      render: (value: number | null) => (
        <Text strong style={{ color: getTrendColor(value), fontFamily: 'Consolas, monospace' }}>
          {formatCapital(value)}
        </Text>
      ),
    },
    {
      title: (
        <Tooltip title="实时口径可能不提供该字段；日/周口径通常有值">
          <span>净流入占比</span>
        </Tooltip>
      ),
      dataIndex: 'main_net_inflow_pct',
      width: 120,
      render: (value: number | null) => (
        <Text style={{ color: getTrendColor(value), fontFamily: 'Consolas, monospace' }}>
          {formatPercent(value)}
        </Text>
      ),
    },
  ]

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <Segmented
          options={PERIOD_OPTIONS}
          value={period}
          onChange={(value) => setPeriod(value as ConceptFlowPeriod)}
        />
        <Text type="secondary">
          {dataSource ? `数据源: ${dataSource}` : ''}
          {retrievedAt ? `  更新时间: ${timeRelative} (${timeAbsolute})` : '  更新时间: -'}
          {isRefreshing ? '  刷新中' : ''}
          {stale ? '  (可能过期)' : ''}
        </Text>
        {refreshStatusTag}
      </div>
      {period === 'realtime' && !hasInflowPctData ? (
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">实时口径当前未返回净流入占比，日/周口径可查看该字段。</Text>
        </div>
      ) : null}
      {diagnosis ? (
        <Alert
          type={stale ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 8 }}
          message="数据说明"
          description={diagnosis}
        />
      ) : null}
      <Table
        dataSource={data}
        columns={columns}
        loading={initialLoading}
        rowKey={(row) => `${row.concept_code}-${row.concept_name}`}
        locale={{ emptyText: <Empty description="暂无概念资金流数据" /> }}
        size="small"
        pagination={{ pageSize: 15, showSizeChanger: false }}
      />
    </>
  )
}

const AnomaliesList = () => {
  const [data, setData] = useState<AnomalyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('')

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await marketAPI.getAnomalies()
      if (Array.isArray(res)) {
        setData(res)
        setHint(
          res.length === 0
            ? '当前未检测到异动记录，可能是市场平稳，或上游数据源暂未返回该指标。'
            : ''
        )
      }
    } catch {
      message.error('获取异动监控失败')
      setHint('异动数据获取失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchData()
    const timer = window.setInterval(() => {
      void fetchData()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [])

  const columns: ColumnsType<AnomalyItem> = [
    { title: '时间', dataIndex: 'timestamp' },
    {
      title: '股票',
      dataIndex: 'name',
      render: (t: string, r: AnomalyItem) => (
        <span>
          {t} ({r.symbol})
        </span>
      ),
    },
    { title: '异动原因', dataIndex: 'reason', render: (t: string) => <Tag color="orange">{t}</Tag> },
    { title: '价格', dataIndex: 'price' },
    {
      title: '涨幅',
      dataIndex: 'change_pct',
      render: (t: number) => <span style={{ color: t > 0 ? 'red' : 'green' }}>{Number(t).toFixed(2)}%</span>,
    },
  ]

  return (
    <>
      {hint ? (
        <Alert
          type={data.length === 0 ? 'info' : 'warning'}
          showIcon
          style={{ marginBottom: 8 }}
          message="异动监控说明"
          description={hint}
        />
      ) : null}
      <Table
        dataSource={data}
        columns={columns}
        loading={loading}
        rowKey={(r: AnomalyItem) => `${r.symbol}-${r.timestamp}`}
        locale={{ emptyText: <Empty description={hint || '暂无异动监控数据'} /> }}
        size="small"
      />
    </>
  )
}

const MarketMonitor = () => (
  <PageContainer
    header={{
      title: '市场全景监控',
      ghost: true,
    }}
  >
    <ProCard ghost gutter={[16, 16]}>
      <Tabs type="card" defaultActiveKey="zt_pool">
        <TabPane
          tab={
            <span>
              <FireOutlined />
              涨停股池
            </span>
          }
          key="zt_pool"
        >
          <ProCard>
            <ZTPoolTable />
          </ProCard>
        </TabPane>
        <TabPane
          tab={
            <span>
              <DatabaseOutlined />
              概念板块
            </span>
          }
          key="concepts"
        >
          <ProCard>
            <ConceptFlowPanel />
          </ProCard>
        </TabPane>
        <TabPane
          tab={
            <span>
              <WarningOutlined />
              异动监控
            </span>
          }
          key="anomalies"
        >
          <ProCard>
            <AnomaliesList />
          </ProCard>
        </TabPane>
      </Tabs>
    </ProCard>
  </PageContainer>
)

export default MarketMonitor
