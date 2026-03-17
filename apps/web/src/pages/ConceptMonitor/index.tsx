import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { PageContainer, ProCard } from '@ant-design/pro-components'
import { Alert, Button, Empty, Segmented, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined } from '@ant-design/icons'

import request from '@/api/request'
import { marketDataLiveApi, type ConceptFlowPeriod } from '@/api/marketDataLive'

const { Text } = Typography

interface ConceptBoardRow {
  key: string
  concept_name: string
  concept_code: string
  leading_stock: string
  change_pct: number | null
  main_net_inflow: number | null
  flow_speed: number | null
}

interface ConceptStockRow {
  key: string
  symbol: string
  name: string
  change_pct: number | null
  price: number | null
  amount: number | null
}

interface ConceptFlowMeta {
  dataSource: string
  stale: boolean
  retrievedAt: string
  diagnosis: string
}

const PERIOD_OPTIONS: Array<{ label: string; value: ConceptFlowPeriod }> = [
  { label: '实时', value: 'realtime' },
  { label: '今日', value: 'today' },
  { label: '周(5日)', value: 'week' },
]

const REFRESH_INTERVAL_MS: Record<ConceptFlowPeriod, number> = {
  realtime: 10000,
  today: 30000,
  week: 60000,
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

function pickText(...values: unknown[]): string {
  for (const value of values) {
    if (value === null || value === undefined) {
      continue
    }
    const text = String(value).trim()
    if (!text || text === '--' || text === '-') {
      continue
    }
    return text
  }
  return ''
}

function formatAmount(value: number | null): string {
  if (value === null) {
    return '--'
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
    return '--'
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function trendColor(value: number | null): string {
  if (value === null || value === 0) {
    return '#595959'
  }
  return value > 0 ? '#cf1322' : '#389e0d'
}

function normalizeBoardRows(items: unknown): ConceptBoardRow[] {
  if (!Array.isArray(items)) {
    return []
  }
  const rows = items
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item, index) => {
      const conceptName = String(
        item.concept_name ?? item.board ?? item.name ?? item['板块名称'] ?? item['概念名称'] ?? ''
      )
      const conceptCode = String(item.concept_code ?? item.code ?? item['板块代码'] ?? '')
      const leadingStock = String(item.leading_stock ?? item.lead_stock ?? item['今日主力净流入最大股'] ?? '')
      const changePct = toPercent(item.change_pct ?? item.lead_change)
      const mainNetInflow = toNumber(item.main_net_inflow ?? item.velocity)
      const flowSpeed = toNumber(item.flow_speed ?? item.velocity ?? item.main_net_inflow)
      const key = `${conceptCode || conceptName || index}`
      return {
        key,
        concept_name: conceptName,
        concept_code: conceptCode,
        leading_stock: leadingStock,
        change_pct: changePct,
        main_net_inflow: mainNetInflow,
        flow_speed: flowSpeed,
      }
    })
    .filter((item) => item.concept_name || item.concept_code)
  rows.sort((a, b) => (b.main_net_inflow ?? 0) - (a.main_net_inflow ?? 0))
  return rows
}

function buildFlowDiagnosis(
  payload: Record<string, unknown>,
  rowCount: number,
  period: ConceptFlowPeriod
): string {
  const detail = payload.detail
  if (!detail || typeof detail !== 'object') {
    return rowCount === 0 ? `${period === 'week' ? '周' : period === 'today' ? '今日' : '实时'}概念数据为空。` : ''
  }

  const detailObj = detail as Record<string, unknown>
  const code = typeof detailObj.code === 'string' ? detailObj.code : ''
  const message = typeof detailObj.message === 'string' ? detailObj.message : ''
  const reason = typeof detailObj.reason === 'string' ? detailObj.reason : ''
  const fallback = detailObj.fallback

  const parts: string[] = []
  if (message) {
    parts.push(message)
  }
  if (reason) {
    parts.push(`原因: ${reason}`)
  }
  if (fallback && typeof fallback === 'object') {
    const from = typeof (fallback as Record<string, unknown>).from === 'string'
      ? String((fallback as Record<string, unknown>).from)
      : ''
    const to = typeof (fallback as Record<string, unknown>).to === 'string'
      ? String((fallback as Record<string, unknown>).to)
      : ''
    if (from || to) {
      parts.push(`回退链路: ${from || '-'} -> ${to || '-'}`)
    }
  }
  if (code) {
    parts.push(`状态码: ${code}`)
  }
  if (parts.length === 0 && rowCount === 0) {
    parts.push('概念数据为空，可能由上游数据源波动导致。')
  }
  return parts.join('；')
}

function normalizeConstituentRows(payload: unknown): ConceptStockRow[] {
  let rows: unknown[] = []
  if (Array.isArray(payload)) {
    rows = payload
  } else if (payload && typeof payload === 'object') {
    const body = payload as Record<string, unknown>
    if (Array.isArray(body.data)) {
      rows = body.data
    }
  }

  return rows
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item, index) => {
      const symbol = pickText(item.symbol, item.code, item['代码'], item['股票代码'])
      const name = pickText(
        item.name,
        item.stock_name,
        item['名称'],
        item['股票简称'],
        item['龙头股'],
        item['概念名称'],
        item['板块名称']
      )
      const changePct = toPercent(item.change_pct ?? item['涨跌幅'] ?? item['龙头股涨跌幅'])
      const price = toNumber(item.price ?? item.latest ?? item['最新价'])
      const amount = toNumber(item.amount ?? item.turnover ?? item['成交额'] ?? item['成分股数量'])
      return {
        key: `${symbol || name || index}`,
        symbol,
        name,
        change_pct: changePct,
        price,
        amount,
      }
    })
    .filter((item) => item.symbol || item.name)
}

const ConceptMonitor: React.FC = () => {
  const [period, setPeriod] = useState<ConceptFlowPeriod>('today')
  const [loadingBoards, setLoadingBoards] = useState(false)
  const [boards, setBoards] = useState<ConceptBoardRow[]>([])
  const [selectedBoard, setSelectedBoard] = useState<ConceptBoardRow | null>(null)
  const [flowMeta, setFlowMeta] = useState<ConceptFlowMeta>({
    dataSource: '',
    stale: false,
    retrievedAt: '',
    diagnosis: '',
  })
  const [boardError, setBoardError] = useState('')

  const [loadingStocks, setLoadingStocks] = useState(false)
  const [stocks, setStocks] = useState<ConceptStockRow[]>([])
  const [stockSource, setStockSource] = useState('')
  const [stockHint, setStockHint] = useState('')

  const fetchBoards = useCallback(async () => {
    setLoadingBoards(true)
    try {
      const payload = (await marketDataLiveApi.getConceptFlow({
        period,
        limit: 80,
      })) as unknown as Record<string, unknown>

      const rows = normalizeBoardRows(payload.items)
      setBoards(rows)
      setFlowMeta({
        dataSource: typeof payload.data_source === 'string' ? payload.data_source : '',
        stale: Boolean(payload.stale),
        retrievedAt: typeof payload.retrieved_at === 'string' ? payload.retrieved_at : '',
        diagnosis: buildFlowDiagnosis(payload, rows.length, period),
      })
      setBoardError('')
      setSelectedBoard((prev) => {
        if (rows.length === 0) {
          return null
        }
        if (prev) {
          const matched = rows.find((item) => item.key === prev.key)
          if (matched) {
            return matched
          }
        }
        return rows[0]
      })
    } catch (error) {
      const text = error instanceof Error ? error.message : '概念板块数据获取失败'
      setBoardError(text)
      setBoards([])
      setSelectedBoard(null)
    } finally {
      setLoadingBoards(false)
    }
  }, [period])

  const fetchStocks = useCallback(async (board: ConceptBoardRow | null) => {
    if (!board || !board.concept_name) {
      setStocks([])
      setStockHint('请先从左侧选择概念板块。')
      setStockSource('')
      return
    }

    setLoadingStocks(true)
    try {
      const encodedName = encodeURIComponent(board.concept_name)
      const payload = await request.get<unknown>(`/trading/market/concept-ths/${encodedName}/constituents`)
      const rows = normalizeConstituentRows(payload)
      const payloadObj = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
      const source = typeof payloadObj._data_source === 'string'
        ? payloadObj._data_source
        : typeof payloadObj.source === 'string'
          ? payloadObj.source
          : 'trading.market'
      const note = typeof payloadObj.note === 'string' ? payloadObj.note : ''
      setStocks(rows)
      setStockSource(source)
      if (rows.length > 0) {
        setStockHint(note || '')
      } else {
        const defaultHint = '该概念暂未返回成分股数据，可能是上游数据源波动或概念映射为空。'
        setStockHint(note ? `${note}；${defaultHint}` : defaultHint)
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : '概念成分股查询失败'
      setStocks([])
      setStockSource('trading.market')
      setStockHint(text)
    } finally {
      setLoadingStocks(false)
    }
  }, [])

  useEffect(() => {
    void fetchBoards()
    const timer = window.setInterval(() => {
      void fetchBoards()
    }, REFRESH_INTERVAL_MS[period])
    return () => window.clearInterval(timer)
  }, [period, fetchBoards])

  useEffect(() => {
    void fetchStocks(selectedBoard)
  }, [selectedBoard, fetchStocks])

  const boardColumns: ColumnsType<ConceptBoardRow> = useMemo(
    () => [
      {
        title: '概念',
        dataIndex: 'concept_name',
        key: 'concept_name',
        render: (value: string, row) => (
          <Space direction="vertical" size={0}>
            <Text strong>{value || row.concept_code || '--'}</Text>
            {row.concept_code ? <Text type="secondary">{row.concept_code}</Text> : null}
          </Space>
        ),
      },
      {
        title: '领涨股',
        dataIndex: 'leading_stock',
        key: 'leading_stock',
        render: (value: string) => value || '--',
      },
      {
        title: '板块涨跌',
        dataIndex: 'change_pct',
        key: 'change_pct',
        render: (value: number | null) => (
          <Text style={{ color: trendColor(value), fontFamily: 'Consolas, monospace' }}>
            {formatPercent(value)}
          </Text>
        ),
      },
      {
        title: '主力净流入',
        dataIndex: 'main_net_inflow',
        key: 'main_net_inflow',
        render: (value: number | null) => (
          <Text style={{ color: trendColor(value), fontFamily: 'Consolas, monospace' }}>
            {formatAmount(value)}
          </Text>
        ),
      },
    ],
    []
  )

  const stockColumns: ColumnsType<ConceptStockRow> = useMemo(
    () => [
      {
        title: '代码',
        dataIndex: 'symbol',
        key: 'symbol',
        width: 120,
        render: (value: string) => <Text strong>{value || '--'}</Text>,
      },
      {
        title: '名称',
        dataIndex: 'name',
        key: 'name',
        render: (value: string) => value || '--',
      },
      {
        title: '涨跌幅',
        dataIndex: 'change_pct',
        key: 'change_pct',
        width: 120,
        render: (value: number | null) => (
          <Text style={{ color: trendColor(value), fontFamily: 'Consolas, monospace' }}>
            {formatPercent(value)}
          </Text>
        ),
      },
      {
        title: '最新价',
        dataIndex: 'price',
        key: 'price',
        width: 120,
        render: (value: number | null) => (value === null ? '--' : value.toFixed(2)),
      },
      {
        title: '成交额',
        dataIndex: 'amount',
        key: 'amount',
        width: 140,
        render: (value: number | null) => formatAmount(value),
      },
    ],
    []
  )

  return (
    <PageContainer
      header={{
        title: '概念联动监控',
        ghost: true,
        extra: [
          <Segmented
            key="period"
            options={PERIOD_OPTIONS}
            value={period}
            onChange={(value) => setPeriod(value as ConceptFlowPeriod)}
          />,
          <Button key="refresh" icon={<ReloadOutlined />} onClick={() => void fetchBoards()}>
            刷新
          </Button>,
        ],
      }}
    >
      {boardError ? (
        <Alert type="error" showIcon message="概念数据获取失败" description={boardError} style={{ marginBottom: 16 }} />
      ) : null}
      {flowMeta.diagnosis ? (
        <Alert
          type={flowMeta.stale ? 'warning' : 'info'}
          showIcon
          message="概念资金流说明"
          description={
            <>
              <div>{flowMeta.diagnosis}</div>
              <div style={{ marginTop: 4 }}>
                数据源: {flowMeta.dataSource || '--'}；更新时间: {flowMeta.retrievedAt || '--'}
              </div>
            </>
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <ProCard ghost gutter={[16, 16]}>
        <ProCard colSpan={{ xs: 24, lg: 12 }} title="板块概览" bordered headerBordered boxShadow>
          <Table<ConceptBoardRow>
            rowKey="key"
            columns={boardColumns}
            dataSource={boards}
            loading={loadingBoards}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            rowSelection={{
              type: 'radio',
              selectedRowKeys: selectedBoard ? [selectedBoard.key] : [],
              onChange: (_keys, rows) => setSelectedBoard(rows[0] ?? null),
            }}
            onRow={(record) => ({
              onClick: () => setSelectedBoard(record),
            })}
            locale={{ emptyText: <Empty description="暂无概念板块数据" /> }}
            size="small"
          />
        </ProCard>

        <ProCard
          colSpan={{ xs: 24, lg: 12 }}
          title={selectedBoard ? `${selectedBoard.concept_name || selectedBoard.concept_code} 成分股` : '成分股'}
          bordered
          headerBordered
          boxShadow
          extra={stockSource ? <Tag color="processing">来源: {stockSource}</Tag> : null}
        >
          {stockHint ? (
            <Alert
              type={stocks.length > 0 ? 'warning' : 'info'}
              showIcon
              style={{ marginBottom: 8 }}
              message="成分股说明"
              description={stockHint}
            />
          ) : null}
          <Table<ConceptStockRow>
            rowKey="key"
            columns={stockColumns}
            dataSource={stocks}
            loading={loadingStocks}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            locale={{ emptyText: <Empty description="暂无概念成分股数据" /> }}
            size="small"
          />
        </ProCard>
      </ProCard>
    </PageContainer>
  )
}

export default ConceptMonitor
