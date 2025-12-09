// @ts-nocheck
import React, { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Segmented,
  Space,
  Switch,
  Tooltip,
  Typography,
} from 'antd'
import {
  AlertOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  CloudServerOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FieldTimeOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'

import { useDashboardLogic, getRefreshIntervalByRange } from './dashboard/hooks/useDashboardLogic'
import StatusCard from './dashboard/components/StatusCard'
import QuickStats from './dashboard/components/QuickStats'
import ResourceUsage from './dashboard/components/ResourceUsage'
import IncidentList from './dashboard/components/IncidentList'
import DataSourceTable from './dashboard/components/DataSourceTable'
import { getRecommendationByStatus } from './dashboard/utils'

const { Title } = Typography

const TIME_RANGE_OPTIONS = [
  { label: '近15分钟', value: '15m' },
  { label: '近1小时', value: '1h' },
  { label: '近24小时', value: '24h' },
]

const Dashboard = () => {
  const [timeRange, setTimeRange] = useState<string>('15m')
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
  const refreshInterval = useMemo(() => getRefreshIntervalByRange(timeRange), [timeRange])

  const {
    loading,
    systemInfo,
    error,
    lastUpdated,
    dataSourceStatus,
    statusSummary,
    dataSourcesLoading,
    dataSourcesError,
    refresh,
    systemStatusDetails,
    incidents,
    healthScore,
    dependencyAvailability,
    averageSuccessRateValue,
  } = useDashboardLogic({ autoRefresh, refreshInterval })

  const criticalIncidentCount = incidents.filter((item) => item.level === 'critical').length

  const quickStatsData = [
    {
      key: 'health',
      title: '系统健康指数',
      icon: <CheckCircleOutlined />,
      color: '#52c41a',
      value: healthScore !== null ? healthScore : '--',
      suffix: healthScore !== null ? '%' : undefined,
      description:
        statusSummary.total > 0
          ? '可用 ' + statusSummary.availableCount + ' / 总计 ' + statusSummary.total
          : '暂无可用数据',
    },
    {
      key: 'success-rate',
      title: 'SLA 成功率',
      icon: <FieldTimeOutlined />,
      color: '#1890ff',
      value: averageSuccessRateValue !== null ? averageSuccessRateValue : '--',
      suffix: averageSuccessRateValue !== null ? '%' : undefined,
      description:
        averageSuccessRateValue !== null ? '根据数据源近期请求平均计算' : '暂无测试数据',
    },
    {
      key: 'incidents',
      title: '待处理事件',
      icon: <AlertOutlined />,
      color: incidents.length > 0 ? '#fa541c' : '#52c41a',
      value: incidents.length,
      suffix: '项',
      description:
        incidents.length > 0
          ? '严重 ' +
          criticalIncidentCount +
          ' 项 ｜ 提示 ' +
          (incidents.length - criticalIncidentCount) +
          ' 项'
          : '一切正常，未检测到异常事件',
    },
    {
      key: 'dependencies',
      title: '依赖可用率',
      icon: <DeploymentUnitOutlined />,
      color:
        dependencyAvailability !== null && dependencyAvailability < 90 ? '#faad14' : '#722ed1',
      value: dependencyAvailability !== null ? dependencyAvailability : '--',
      suffix: dependencyAvailability !== null ? '%' : undefined,
      description:
        statusSummary.total > 0
          ? '离线 ' + (statusSummary.counts.offline ?? 0) + ' 个'
          : '暂无依赖数据',
    },
  ]

  const resourceCards = [
    {
      key: 'cpu',
      title: 'CPU 使用率',
      value: Number.isFinite(systemInfo.cpu_usage)
        ? Number(systemInfo.cpu_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <DashboardOutlined style={{ color: '#3f8600' }} />,
      color: systemInfo.cpu_usage > 80 ? '#cf1322' : '#3f8600',
    },
    {
      key: 'memory',
      title: '内存使用率',
      value: Number.isFinite(systemInfo.memory_usage)
        ? Number(systemInfo.memory_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <CloudServerOutlined style={{ color: '#1890ff' }} />,
      color: systemInfo.memory_usage > 80 ? '#cf1322' : '#1890ff',
    },
    {
      key: 'disk',
      title: '存储使用率',
      value: Number.isFinite(systemInfo.disk_usage)
        ? Number(systemInfo.disk_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <DatabaseOutlined style={{ color: '#722ed1' }} />,
      color: systemInfo.disk_usage > 80 ? '#cf1322' : '#722ed1',
    },
    {
      key: 'network',
      title: '网络吞吐',
      icon: <ApiOutlined style={{ color: '#1890ff' }} />,
      inbound: Number.isFinite(systemInfo.network_in)
        ? Math.max(0, Math.round(systemInfo.network_in))
        : 0,
      outbound: Number.isFinite(systemInfo.network_out)
        ? Math.max(0, Math.round(systemInfo.network_out))
        : 0,
      color: '#1890ff',
    },
  ]

  const actionItems = useMemo(() => {
    return incidents.slice(0, 5).map((incident) => ({
      key: incident.key,
      name: incident.name,
      title: incident.level === 'critical' ? '立即处理' : '关注',
      reason: incident.reason,
      recommendation: getRecommendationByStatus(incident.status),
      level: incident.level,
    }))
  }, [incidents])

  const dataSourceErrorMessage = dataSourcesError?.message ?? null

  return (
    <ProCard direction="column" ghost gutter={[0, 16]} style={{ padding: 24 }}>
      {error && (
        <Alert
          message="系统状态获取失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}
      {dataSourceErrorMessage && (
        <Alert
          message="数据源状态获取失败"
          description={dataSourceErrorMessage}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      <ProCard ghost gutter={16}>
        <ProCard colSpan={16} direction="column" ghost gutter={[0, 16]}>
          <ProCard title="系统概览" extra={
            <Space>
              <Segmented
                options={TIME_RANGE_OPTIONS}
                value={timeRange}
                onChange={setTimeRange}
              />
              <Tooltip title="自动刷新">
                <Switch
                  checkedChildren="自动"
                  unCheckedChildren="手动"
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                />
              </Tooltip>
              <Button
                icon={<ReloadOutlined spin={loading} />}
                onClick={() => refresh(true)}
              >
                刷新
              </Button>
            </Space>
          }>
            <QuickStats stats={quickStatsData} />
          </ProCard>

          <ProCard title="资源监控">
            <ResourceUsage resources={resourceCards} />
          </ProCard>
        </ProCard>

        <ProCard colSpan={8} direction="column" ghost gutter={[0, 16]}>
          <ProCard>
            <StatusCard
              systemStatusDetails={systemStatusDetails}
              uptime={systemInfo.uptime}
              lastUpdated={lastUpdated}
            />
          </ProCard>
          <ProCard title="待处理事件">
            <IncidentList incidents={actionItems} />
          </ProCard>
        </ProCard>
      </ProCard>

      <ProCard title="数据源状态监控">
        <DataSourceTable
          dataSourceStatus={dataSourceStatus}
          loading={dataSourcesLoading && dataSourceStatus.length === 0}
        />
      </ProCard>
    </ProCard>
  )
}

export default Dashboard
