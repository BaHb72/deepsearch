import {Alert, Button, Card, Progress, Space, Switch, Table, Tag, Typography} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import dayjs from 'dayjs'
import type {QuotaRow} from './useNotificationQuota'

const CHANNEL_LABEL_MAP: Record<string, string> = {
  wechat: '微信',
  bark: 'Bark',
}

interface QuotaSectionProps {
  quotas: QuotaRow[]
  loading: boolean
  disabled: boolean
  autoRefresh: boolean
  lastUpdated?: number
  onAutoRefreshChange: (value: boolean) => void
  onRefresh: () => void
  onReset: () => void
}

const columns: ColumnsType<QuotaRow> = [
  {
    title: '限额类型',
    dataIndex: 'category',
    key: 'category',
    render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
  },
  {
    title: '渠道',
    dataIndex: 'channel',
    key: 'channel',
    render: (value: QuotaRow['channel']) => CHANNEL_LABEL_MAP[value] || value,
  },
  {
    title: '已使用',
    dataIndex: 'current',
    key: 'current',
  },
  {
    title: '最大值',
    dataIndex: 'max',
    key: 'max',
    render: (value: number | null | undefined) => (value ?? '无限制'),
  },
  {
    title: '剩余额度',
    key: 'remaining',
    render: (_, record) => {
      if (record.max === null || record.max === undefined || record.max <= 0) {
        return <Tag color="blue">无限制</Tag>
      }
      const percent = Math.max(0, Math.min(100, ((record.remaining ?? 0) / record.max) * 100))
      const status = (record.remaining ?? 0) <= 0 ? 'exception' : 'normal'
      return (
        <Progress
          percent={Number.isFinite(percent) ? Number(percent.toFixed(0)) : 0}
          status={status}
          size="small"
        />
      )
    },
  },
  {
    title: '时间窗口 / 秒',
    dataIndex: 'windowSeconds',
    key: 'windowSeconds',
    render: (value?: number) => value ?? '-',
  },
  {
    title: '预计重置时间',
    dataIndex: 'resetEta',
    key: 'resetEta',
    render: (value: string | null | undefined, record: QuotaRow) => {
      if (value) {
        return value
      }
      if (record.resetSeconds) {
        return `${record.resetSeconds}s 后`
      }
      return '—'
    },
  },
]

const QuotaSection = ({
  quotas,
  loading,
  disabled,
  autoRefresh,
  lastUpdated,
  onAutoRefreshChange,
  onRefresh,
  onReset,
}: QuotaSectionProps) => (
  <Card
    title="额度监控"
    variant="borderless"
    extra={
      <Space>
        <Switch
          checked={autoRefresh}
          onChange={onAutoRefreshChange}
          disabled={disabled}
          checkedChildren="自动刷新"
          unCheckedChildren="手动"
        />
        <Button onClick={onRefresh} loading={loading} disabled={disabled}>
          刷新
        </Button>
        <Button danger onClick={onReset} loading={loading} disabled={disabled}>
          重置额度
        </Button>
      </Space>
    }
  >
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {disabled && (
        <Alert type="warning" showIcon message="通知渠道未启用，额度状态暂不可用" />
      )}
      {lastUpdated && (
        <Typography.Text type="secondary">
          最近更新时间：{dayjs(lastUpdated).format('YYYY-MM-DD HH:mm:ss')}
        </Typography.Text>
      )}
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={quotas}
        pagination={false}
        locale={{ emptyText: disabled ? '通知渠道未启用' : '暂无额度数据' }}
      />
    </Space>
  </Card>
)

export default QuotaSection
