import React, { useMemo } from 'react'
import { PageContainer, ProCard } from '@ant-design/pro-components'
import { Alert, Empty, Space, Statistic, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useDataSourceMonitor } from '@/hooks/queries/useDataSourceQueries'
import type {
  DataSource,
  DataSourceMonitorAlert,
  DataSourceMonitorTimelineItem,
} from '@/api/dataSource'
import { getDataSourceStatusMeta } from '@/utils/dataSourceStatus'

const { Text } = Typography

function formatRate(value?: number | null): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  const normalized = value > 1 ? value : value * 100
  return `${normalized.toFixed(1)}%`
}

function formatLatency(value?: number | null): string {
  if (typeof value !== 'number' || Number.isNaN(value) || value < 0) {
    return '--'
  }
  return `${value.toFixed(1)} ms`
}

const DataSourceMonitor: React.FC = () => {
  const { data, isLoading, error } = useDataSourceMonitor({
    refetchInterval: 15000,
    staleTime: 10000,
  })

  const overview = data?.overview
  const sources = Array.isArray(data?.sources) ? data.sources : []
  const timeline = Array.isArray(data?.timeline) ? data.timeline : []
  const alerts = Array.isArray(data?.alerts) ? data.alerts : []

  const sourceColumns: ColumnsType<DataSource> = useMemo(
    () => [
      {
        title: '数据源',
        dataIndex: 'name',
        key: 'name',
        render: (_: unknown, record: DataSource) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.name}</Text>
            <Text type="secondary">{record.type}</Text>
          </Space>
        ),
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        render: (value: string) => {
          const meta = getDataSourceStatusMeta(value)
          return <Tag color={meta.tagColor}>{meta.text}</Tag>
        },
      },
      {
        title: '可用',
        dataIndex: 'available',
        key: 'available',
        render: (_: unknown, record: DataSource) => {
          const available =
            typeof record.available === 'boolean'
              ? record.available
              : typeof record.is_available === 'boolean'
                ? record.is_available
                : false
          return <Tag color={available ? 'success' : 'error'}>{available ? '是' : '否'}</Tag>
        },
      },
      {
        title: '请求数',
        dataIndex: 'metrics',
        key: 'totalRequests',
        render: (_: unknown, record: DataSource) => Number(record.metrics?.totalRequests ?? 0),
      },
      {
        title: '成功率',
        dataIndex: 'metrics',
        key: 'successRate',
        render: (_: unknown, record: DataSource) =>
          formatRate(record.metrics?.successRate),
      },
      {
        title: '平均延迟',
        dataIndex: 'metrics',
        key: 'avgLatency',
        render: (_: unknown, record: DataSource) =>
          formatLatency(record.metrics?.avgLatency ?? record.latency),
      },
      {
        title: '最近检测',
        dataIndex: 'lastTestTime',
        key: 'lastTestTime',
        render: (value: string) => value || '--',
      },
    ],
    []
  )

  const timelineColumns: ColumnsType<DataSourceMonitorTimelineItem> = useMemo(
    () => [
      {
        title: '时间',
        dataIndex: 'time',
        key: 'time',
        width: 220,
      },
      {
        title: '来源',
        dataIndex: 'source',
        key: 'source',
        render: (value: string) => value || '--',
      },
      {
        title: '访问类型',
        dataIndex: 'accessType',
        key: 'accessType',
        render: (value: string) => value || '--',
      },
      {
        title: '请求',
        dataIndex: 'requests',
        key: 'requests',
      },
      {
        title: '延迟',
        dataIndex: 'latency',
        key: 'latency',
        render: (value: number | null) => formatLatency(value),
      },
      {
        title: '结果',
        dataIndex: 'success',
        key: 'success',
        render: (value: boolean | undefined) =>
          value === undefined ? '--' : value ? <Tag color="success">成功</Tag> : <Tag color="error">失败</Tag>,
      },
    ],
    []
  )

  const alertColumns: ColumnsType<DataSourceMonitorAlert> = useMemo(
    () => [
      {
        title: '级别',
        dataIndex: 'level',
        key: 'level',
        render: (value: string) => {
          if (value === 'error') return <Tag color="error">错误</Tag>
          if (value === 'warning') return <Tag color="warning">告警</Tag>
          return <Tag color="processing">提示</Tag>
        },
      },
      {
        title: '来源',
        dataIndex: 'source',
        key: 'source',
        render: (value: string) => value || '--',
      },
      {
        title: '消息',
        dataIndex: 'message',
        key: 'message',
      },
      {
        title: '时间',
        dataIndex: 'timestamp',
        key: 'timestamp',
        width: 220,
        render: (value: string | null | undefined) => value || '--',
      },
    ],
    []
  )

  const errorText = error instanceof Error ? error.message : ''

  return (
    <PageContainer
      header={{
        title: '数据源监控',
        ghost: true,
      }}
    >
      {errorText ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="监控数据拉取失败"
          description={errorText}
        />
      ) : null}

      <ProCard ghost gutter={[16, 16]}>
        <ProCard colSpan={{ xs: 24, md: 6 }}>
          <Statistic title="数据源总数" value={Number(overview?.total ?? sources.length)} />
        </ProCard>
        <ProCard colSpan={{ xs: 24, md: 6 }}>
          <Statistic title="可用数据源" value={Number(overview?.available ?? 0)} />
        </ProCard>
        <ProCard colSpan={{ xs: 24, md: 6 }}>
          <Statistic title="总请求数" value={Number(overview?.totalRequests ?? 0)} />
        </ProCard>
        <ProCard colSpan={{ xs: 24, md: 6 }}>
          <Statistic title="平均延迟" value={formatLatency(Number(overview?.avgLatency ?? 0))} />
        </ProCard>
      </ProCard>

      <ProCard
        style={{ marginTop: 16 }}
        title="数据源状态"
        bordered
        headerBordered
        boxShadow
      >
        <Table<DataSource>
          rowKey={(record) => record.id ?? record.name}
          columns={sourceColumns}
          dataSource={sources}
          loading={isLoading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无数据源状态数据" /> }}
          size="small"
        />
      </ProCard>

      <ProCard
        style={{ marginTop: 16 }}
        title="访问时间线"
        bordered
        headerBordered
        boxShadow
      >
        <Table<DataSourceMonitorTimelineItem>
          rowKey={(record, index) => `${record.time}-${record.source ?? ''}-${index}`}
          columns={timelineColumns}
          dataSource={timeline}
          loading={isLoading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          locale={{ emptyText: <Empty description="暂无访问时间线数据" /> }}
          size="small"
        />
      </ProCard>

      <ProCard
        style={{ marginTop: 16 }}
        title="告警列表"
        bordered
        headerBordered
        boxShadow
      >
        <Table<DataSourceMonitorAlert>
          rowKey={(record, index) => `${record.timestamp ?? ''}-${record.message}-${index}`}
          columns={alertColumns}
          dataSource={alerts}
          loading={isLoading}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          locale={{ emptyText: <Empty description="暂无告警" /> }}
          size="small"
        />
      </ProCard>
    </PageContainer>
  )
}

export default DataSourceMonitor
