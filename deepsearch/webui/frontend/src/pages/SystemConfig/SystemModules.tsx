import React from 'react'
import type { ModuleLog } from '@/types/systemConfig'
import type { SystemModule } from '@/api/config/modules'
import type { Key } from 'react'
import type { ColumnsType } from 'antd/es/table'
import {
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  message,
  Progress,
  Row,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Timeline,
  Tooltip
} from 'antd'
import {
  AppstoreOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
  SyncOutlined,
  WarningOutlined
} from '@ant-design/icons'
import { useAsyncData } from '@/hooks'
import {
  batchModuleOperation,
  fetchModuleLogs,
  fetchSystemModules,
  restartModule,
  setModuleAutoStart,
  startModule,
  stopModule
} from '@/api/config/modules'

interface ModuleDetailDrawerProps {
  module: SystemModule | null
  visible: boolean
  onClose: () => void
}

/**
 * 模块详情抽屉组件
 */
const ModuleDetailDrawer: React.FC<ModuleDetailDrawerProps> = ({ module, visible, onClose }) => {
  const { data: logs } = useAsyncData<ModuleLog[]>(
    () => (module ? fetchModuleLogs(module.id, { limit: 50 }) as Promise<ModuleLog[]> : Promise.resolve([])),
    {
      immediate: !!module,
      showError: false
    }
  )

  if (!module) return null

  return (
    <Drawer
      title={`模块详情 - ${module.name}`}
      placement="right"
      width={600}
      open={visible}
      onClose={onClose}
    >
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="模块ID">{module.id}</Descriptions.Item>
        <Descriptions.Item label="描述">{module.description}</Descriptions.Item>
        <Descriptions.Item label="版本">{module.version || '-'}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <Badge
            status={
              module.status === 'running' ? 'success' :
                module.status === 'error' ? 'error' :
                  module.status === 'starting' ? 'processing' :
                    module.status === 'stopping' ? 'warning' : 'default'
            }
            text={
              module.status === 'running' ? '运行中' :
                module.status === 'stopped' ? '已停止' :
                  module.status === 'error' ? '错误' :
                    module.status === 'starting' ? '启动中' :
                      module.status === 'stopping' ? '停止中' : module.status
            }
          />
        </Descriptions.Item>
        <Descriptions.Item label="运行时长">
          {module.uptime ? `${Math.floor(module.uptime / 3600)}小时` : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="CPU使用">
          {module.cpu !== undefined ? (
            <Progress
              percent={module.cpu}
              size="small"
              status={module.cpu > 80 ? 'exception' : 'normal'}
            />
          ) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="内存使用">
          {module.memory !== undefined ? (
            <Progress
              percent={module.memory}
              size="small"
              status={module.memory > 80 ? 'exception' : 'normal'}
            />
          ) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="错误计数">
          {module.errorCount || 0}
        </Descriptions.Item>
        <Descriptions.Item label="依赖模块">
          {module.dependencies?.length ? (
            <Space wrap>
              {module.dependencies.map(dep => (
                <Tag key={dep}>{dep}</Tag>
              ))}
            </Space>
          ) : '-'}
        </Descriptions.Item>
      </Descriptions>

      <Card title="运行日志" size="small" style={{ marginTop: 16 }}>
        <Timeline mode="left">
          {(logs ?? []).map((log: ModuleLog, index: number) => (
            <Timeline.Item
              key={index}
              color={
                log.level === 'error' ? 'red' :
                  log.level === 'warning' ? 'orange' : 'green'
              }
              label={log.timestamp}
            >
              <Tag color={
                log.level === 'error' ? 'error' :
                  log.level === 'warning' ? 'warning' : 'success'
              }>
                {log.level.toUpperCase()}
              </Tag>
              {log.message}
            </Timeline.Item>
          ))}
        </Timeline>
      </Card>
    </Drawer>
  )
}

/**
 * 系统模块管理组件
 */
const SystemModules = () => {
  const [selectedRowKeys, setSelectedRowKeys] = React.useState<Key[]>([])
  const [detailModule, setDetailModule] = React.useState<SystemModule | null>(null)
  const [detailVisible, setDetailVisible] = React.useState(false)

  const {
    data: modules,
    loading,
    refresh
  } = useAsyncData(
    fetchSystemModules,
    {
      immediate: true,
      showError: false,
      pollingInterval: 10000 // 10秒轮询
    }
  )

  const handleStart = async (moduleId: string) => {
    try {
      await startModule(moduleId)
      message.success('模块启动成功')
      refresh()
    } catch (error) {
      message.error('启动失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleStop = async (moduleId: string) => {
    try {
      await stopModule(moduleId)
      message.success('模块停止成功')
      refresh()
    } catch (error) {
      message.error('停止失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleRestart = async (moduleId: string) => {
    try {
      await restartModule(moduleId)
      message.success('模块重启成功')
      refresh()
    } catch (error) {
      message.error('重启失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleAutoStart = async (moduleId: string, autoStart: boolean) => {
    try {
      await setModuleAutoStart(moduleId, autoStart)
      message.success(autoStart ? '已设置自动启动' : '已取消自动启动')
      refresh()
    } catch (error) {
      message.error('设置失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleBatchOperation = async (action: 'start' | 'stop' | 'restart') => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择模块')
      return
    }

    try {
      await batchModuleOperation(action, selectedRowKeys as string[])
      message.success(`批量${action === 'start' ? '启动' :
        action === 'stop' ? '停止' : '重启'
        }成功`)
      setSelectedRowKeys([])
      refresh()
    } catch (error) {
      message.error('批量操作失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const showModuleDetail = (module: SystemModule) => {
    setDetailModule(module)
    setDetailVisible(true)
  }

  const columns: ColumnsType<SystemModule> = [
    {
      title: '模块名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: SystemModule) => (
        <Space>
          <AppstoreOutlined />
          <a onClick={() => showModuleDetail(record)}>{text}</a>
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: SystemModule['status']) => {
        const statusMap: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
          running: { color: 'green', icon: <CheckCircleOutlined />, text: '运行中' },
          stopped: { color: 'default', icon: <CloseCircleOutlined />, text: '已停止' },
          error: { color: 'red', icon: <WarningOutlined />, text: '错误' },
          starting: { color: 'blue', icon: <SyncOutlined spin />, text: '启动中' },
          stopping: { color: 'orange', icon: <SyncOutlined spin />, text: '停止中' }
        }
        const config = statusMap[status] || { color: 'default', icon: null, text: status }
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.text}
          </Tag>
        )
      }
    },
    {
      title: '资源使用',
      key: 'resources',
      render: (_: unknown, record: SystemModule) => (
        <Space size="small">
          {record.cpu !== undefined && (
            <Tooltip title={`CPU: ${record.cpu}%`}>
              <Progress
                type="circle"
                percent={record.cpu}
                width={40}
                strokeColor={record.cpu > 80 ? '#ff4d4f' : '#52c41a'}
                format={() => `${record.cpu}%`}
              />
            </Tooltip>
          )}
          {record.memory !== undefined && (
            <Tooltip title={`内存: ${record.memory}%`}>
              <Progress
                type="circle"
                percent={record.memory}
                width={40}
                strokeColor={record.memory > 80 ? '#ff4d4f' : '#1890ff'}
                format={() => `${record.memory}%`}
              />
            </Tooltip>
          )}
        </Space>
      )
    },
    {
      title: '自动启动',
      dataIndex: 'autoStart',
      key: 'autoStart',
      render: (autoStart: boolean, record: SystemModule) => (
        <Switch
          checked={autoStart}
          onChange={(checked) => handleAutoStart(record.id, checked)}
          checkedChildren="是"
          unCheckedChildren="否"
        />
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: SystemModule) => (
        <Space size="small">
          {record.status === 'stopped' ? (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleStart(record.id)}
            >
              启动
            </Button>
          ) : (
            <Button
              type="link"
              size="small"
              icon={<PauseCircleOutlined />}
              onClick={() => handleStop(record.id)}
              danger
            >
              停止
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => handleRestart(record.id)}
          >
            重启
          </Button>
          <Button
            type="link"
            size="small"
            icon={<SettingOutlined />}
            onClick={() => showModuleDetail(record)}
          >
            详情
          </Button>
        </Space>
      )
    }
  ]

  // 统计信息
  const stats = React.useMemo(() => {
    if (!modules) return { total: 0, running: 0, stopped: 0, error: 0 }
    return {
      total: modules.length,
      running: modules.filter(m => m.status === 'running').length,
      stopped: modules.filter(m => m.status === 'stopped').length,
      error: modules.filter(m => m.status === 'error').length
    }
  }, [modules])

  return (
    <>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总模块数"
              value={stats.total}
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="运行中"
              value={stats.running}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已停止"
              value={stats.stopped}
              valueStyle={{ color: '#999' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="错误"
              value={stats.error}
              valueStyle={{ color: '#cf1322' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="系统模块管理"
        extra={
          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => handleBatchOperation('start')}
              disabled={selectedRowKeys.length === 0}
            >
              批量启动
            </Button>
            <Button
              icon={<PauseCircleOutlined />}
              onClick={() => handleBatchOperation('stop')}
              disabled={selectedRowKeys.length === 0}
            >
              批量停止
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => handleBatchOperation('restart')}
              disabled={selectedRowKeys.length === 0}
            >
              批量重启
            </Button>
            <Button
              icon={<SyncOutlined />}
              onClick={refresh}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: (keys: Key[]) => setSelectedRowKeys(keys)
          }}
          columns={columns}
          dataSource={modules || []}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <ModuleDetailDrawer
        module={detailModule}
        visible={detailVisible}
        onClose={() => setDetailVisible(false)}
      />
    </>
  )
}

export default SystemModules
