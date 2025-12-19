/**
 * 数据库配置管理 - 使用 Zustand Store 版本
 */

import React from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  LoadingOutlined,
  PlusOutlined,
  SyncOutlined
} from '@ant-design/icons'

// 使用 Zustand Store
import { useDatabaseStore, useSelectedConnection } from '@/stores'
import type { CreateConnectionDTO, DatabaseConnection, TestResult } from '@/stores/types'

const { Option } = Select
const { Text } = Typography

type TestModalState = {
  visible: boolean
  testing: boolean
  result: TestResult | null
  target: DatabaseConnection | null
}

const formatTimestamp = (value?: number | string | null): string => {
  if (value === null || value === undefined) {
    return '未记录'
  }

  const date = typeof value === 'number' ? new Date(value) : new Date(String(value))
  if (Number.isNaN(date.getTime()) || date.getTime() <= 0) {
    return '未记录'
  }

  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

const formatConnectionAddress = (record: DatabaseConnection): string => {
  if (record.host) {
    return record.port ? `${record.host}:${record.port}` : record.host
  }

  if (record.database) {
    return record.database
  }

  return '未配置'
}

const resolveErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  if (typeof error === 'string' && error.trim()) {
    return error
  }

  return fallback
}

const DatabaseConfigWithStore: React.FC = () => {
  // 从 Store 获取状态和方法
  const {
    connections,
    loading,
    error,
    fetchConnections,
    createConnection,
    updateConnection,
    deleteConnection,
    testConnection,
    activateConnection,
    deactivateConnection
  } = useDatabaseStore()
  const { selectedConnection, selectConnection } = useSelectedConnection()

  // Modal 状态
  const [editModal, setEditModal] = React.useState({
    visible: false,
    isEdit: false,
    editingId: null as number | null
  })

  const [testModal, setTestModal] = React.useState<TestModalState>({
    visible: false,
    testing: false,
    result: null,
    target: null
  })

  const [toggleLoading, setToggleLoading] = React.useState<Record<number, boolean>>({})

  const [form] = Form.useForm()
  const currentType = Form.useWatch('type', form)
  const hostValue = Form.useWatch('host', form)
  const portValue = Form.useWatch('port', form)
  const databaseValue = Form.useWatch('database', form)
  const usernameValue = Form.useWatch('username', form)
  const passwordValue = Form.useWatch('password', form)
  const connectionPreview = React.useMemo(() => {
    if (!currentType) {
      return '选择数据库类型后将自动生成连接串预览'
    }

    if (currentType === 'sqlite' || currentType === 'duckdb') {
      if (!databaseValue) {
        return `${currentType}://<请填写文件路径>`
      }
      return `${currentType}://${databaseValue}`
    }

    const host = hostValue || '<主机>'
    const port = portValue ? `:${portValue}` : ''
    const database = databaseValue || '<数据库>'
    const credential = usernameValue ? `${usernameValue}${passwordValue ? ':***' : ''}@` : ''

    return `${currentType}://${credential}${host}${port}/${database}`
  }, [currentType, databaseValue, hostValue, passwordValue, portValue, usernameValue])
  const overviewMetrics = React.useMemo(() => {
    const enabled = connections.filter(item => item.activation?.enabled).length
    const connected = connections.filter(item => item.connectivity?.state === 'connected').length
    const failure = connections.filter(item => item.connectivity?.state === 'error').length
    const pending = connections.filter(item => item.connectivity?.state === 'connecting' || item.connectivity?.retrying).length

    return {
      total: connections.length,
      enabled,
      connected,
      failure,
      pending,
    }
  }, [connections])

  // 组件挂载时获取数据
  const hasRequestedRef = React.useRef(false)

  React.useEffect(() => {
    if (hasRequestedRef.current) {
      return
    }

    if (loading) {
      return
    }

    hasRequestedRef.current = true
    console.log('[DatabaseConfigWithStore] 组件挂载，获取数据')
    // Store 会自动处理缓存和去重，不用担心重复请求
    fetchConnections()
  }, [loading, fetchConnections])
  // 打开编辑弹窗
  const openEditModal = (record?: DatabaseConnection) => {
    if (record) {
      form.setFieldsValue(record)
      setEditModal({
        visible: true,
        isEdit: true,
        editingId: record.id
      })
    } else {
      form.resetFields()
      setEditModal({
        visible: true,
        isEdit: false,
        editingId: null
      })
    }
  }

  // 关闭编辑弹窗
  const closeEditModal = () => {
    setEditModal({
      visible: false,
      isEdit: false,
      editingId: null
    })
    form.resetFields()
  }

  const handleRefresh = React.useCallback(() => {
    void fetchConnections(true)
  }, [fetchConnections])

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (editModal.isEdit && editModal.editingId) {
        await updateConnection(editModal.editingId, values)
        message.success('数据库连接已更新')
      } else {
        await createConnection(values as CreateConnectionDTO)
        message.success('数据库连接已创建')
      }

      closeEditModal()
      await fetchConnections(true)
    } catch (error: any) {
      if (error?.errorFields) {
        return
      }

      const errorMessage = resolveErrorMessage(error, '提交失败，请稍后重试')
      message.error(errorMessage)
      console.error('提交失败:', error)
    }
  }

  // 删除连接
  const handleDelete = async (id: number) => {
    try {
      await deleteConnection(id)
      message.success('数据库连接已删除')

      if (selectedConnection?.id === id) {
        selectConnection(null)
      }

      await fetchConnections(true)
    } catch (error) {
      const errorMessage = resolveErrorMessage(error, '删除失败，请稍后重试')
      message.error(errorMessage)
      console.error('删除失败:', error)
    }
  }

  // 测试连接
  const handleTest = async (record: DatabaseConnection) => {
    setTestModal({
      visible: true,
      testing: true,
      result: null,
      target: record
    })

    try {
      const result = await testConnection(record.id)
      setTestModal({
        visible: true,
        testing: false,
        result,
        target: record
      })

      if (result.success) {
        message.success(result.message || '连接测试成功')
      } else {
        message.warning(result.message || '连接测试出现警告')
      }
    } catch (error) {
      const fallback = resolveErrorMessage(error, '连接测试失败')

      setTestModal({
        visible: true,
        testing: false,
        result: {
          success: false,
          message: fallback
        },
        target: record
      })
      message.error(fallback)
    }
  }

  const handleRetryTest = () => {
    if (testModal.target) {
      void handleTest(testModal.target)
    }
  }

  // 表格列定义
  const handleToggle = async (record: DatabaseConnection, enabled: boolean) => {
    if (!record || typeof record.id !== 'number') {
      return
    }

    const key = record.id
    setToggleLoading(prev => ({ ...prev, [key]: true }))

    try {
      if (enabled) {
        await activateConnection(record.id, { connectImmediately: false })
        message.success(`已启用连接：${record.name}`)
      } else {
        await deactivateConnection(record.id, { disconnect: true })
        message.success(`已停用连接：${record.name}`)
      }

      await fetchConnections(true)
    } catch (error) {
      const errorMessage = resolveErrorMessage(error, '启用状态切换失败，请稍后重试')
      message.error(errorMessage)
      console.error('启用状态切换失败:', error)
      await fetchConnections(true)
    } finally {
      setToggleLoading(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    }
  }

  const columns = [
    {
      title: '连接名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DatabaseConnection) => (
        <Space>
          <DatabaseOutlined />
          <span>{text}</span>
          {record.isDefault && <Tag color="blue">默认</Tag>}
          {record.activeConnection && <Tag color="green">在用</Tag>}
        </Space>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => (
        <Tag color="blue">{type.toUpperCase()}</Tag>
      )
    },
    {
      title: '连接地址',
      key: 'address',
      render: (_: any, record: DatabaseConnection) => (
        <div>
          <Text>{formatConnectionAddress(record)}</Text>
          {record.username && (
            <div>
              <Text type="secondary">用户：{record.username}</Text>
            </div>
          )}
        </div>
      )
    },
    {
      title: '启用状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (_: any, record: DatabaseConnection) => {
        const isEnabled = record.activation?.enabled ?? record.deprecated?.enabled ?? false
        return (
          <Switch
            checked={isEnabled}
            onChange={value => handleToggle(record, value)}
            loading={Boolean(toggleLoading[record.id])}
            disabled={Boolean(toggleLoading[record.id])}
            checkedChildren="启用"
            unCheckedChildren="禁用"
          />
        )
      }
    },
    {
      title: '状态',
      dataIndex: 'connected',
      key: 'connected',
      render: (_: boolean, record: DatabaseConnection) => {
        const isEnabled = record.activation?.enabled ?? record.deprecated?.enabled ?? false
        const connectivityState = record.connectivity?.state ?? (isEnabled ? 'unknown' : 'inactive')

        if (!isEnabled) {
          return (
            <Tag icon={<CloseCircleOutlined />} color="default">
              未启用
            </Tag>
          )
        }

        if (connectivityState === 'connected') {
          return (
            <Tag icon={<CheckCircleOutlined />} color="success">
              已连接
            </Tag>
          )
        }

        if (connectivityState === 'connecting') {
          return (
            <Tag icon={<SyncOutlined spin />} color="processing">
              连接中
            </Tag>
          )
        }

        if (connectivityState === 'error') {
          return (
            <Tag icon={<CloseCircleOutlined />} color="error">
              连接失败
            </Tag>
          )
        }

        return (
          <Tag icon={<CloseCircleOutlined />} color="default">
            未连接
          </Tag>
        )
      }
    },
    {
      title: '最近检查',
      key: 'lastCheck',
      render: (_: any, record: DatabaseConnection) => (
        <div>
          <Text>{formatTimestamp(record.connectivity?.lastSuccessAt ?? record.lastHealthCheck ?? null)}</Text>
          {record.activation?.updatedAt && (
            <div>
              <Text type="secondary">启用更新：{formatTimestamp(record.activation.updatedAt)}</Text>
            </div>
          )}
        </div>
      )
    },
    {
      title: '状态详情',
      dataIndex: 'statusDetail',
      key: 'statusDetail',
      ellipsis: true,
      render: (detail: string | undefined, record: DatabaseConnection) => {
        if (detail) {
          return <Text type="secondary">{detail}</Text>
        }

        if (record.error) {
          return <Text type="danger">{record.error}</Text>
        }

        if (record.connectivity?.lastError) {
          return <Text type="danger">{record.connectivity.lastError}</Text>
        }

        return <Text type="secondary">-</Text>
      }
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: DatabaseConnection) => (
        <Space size="middle">
          <Button
            size="small"
            onClick={() => handleTest(record)}
          >
            测试
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个连接吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  const overviewCards = [
    {
      key: 'total',
      title: '连接总数',
      value: overviewMetrics.total,
    },
    {
      key: 'enabled',
      title: '已启用',
      value: overviewMetrics.enabled,
    },
    {
      key: 'connected',
      title: '在线连接',
      value: overviewMetrics.connected,
    },
    {
      key: 'failure',
      title: '告警/失败',
      value: overviewMetrics.failure,
      valueStyle: overviewMetrics.failure > 0 ? { color: '#cf1322' } : undefined
    }
  ]

  const tableEmptyNode = error
    ? (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={error.message || '加载数据库连接失败'}
      >
        <Button icon={<SyncOutlined />} onClick={handleRefresh}>
          重新加载
        </Button>
      </Empty>
    )
    : (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无数据库连接"
      >
        <Button type="primary" onClick={() => openEditModal()}>
          新建连接
        </Button>
      </Empty>
    )

  const closeTestModal = () => {
    setTestModal({
      visible: false,
      testing: false,
      result: null,
      target: null
    })
  }
  const testModalFooter: React.ReactNode[] = []
  if (testModal.target) {
    testModalFooter.push(
      <Button
        key="retry"
        onClick={handleRetryTest}
        loading={testModal.testing}
        disabled={testModal.testing}
      >
        重新测试
      </Button>
    )
  }
  testModalFooter.push(
    <Button
      key="close"
      onClick={closeTestModal}
    >
      关闭
    </Button>
  )

  return (
    <>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Card title="运行概览">
          <Spin spinning={loading}>
            <Row gutter={[16, 16]}>
              {overviewCards.map(card => (
                <Col xs={12} sm={12} md={6} key={card.key}>
                  <Statistic
                    title={card.title}
                    value={card.value}
                    suffix="个"
                    valueStyle={card.valueStyle}
                  />
                </Col>
              ))}
            </Row>
            <Space size="small" wrap style={{ marginTop: 16 }}>
              <Tag color="processing">待联机 {overviewMetrics.pending}</Tag>
              <Tag color="success">已连接 {overviewMetrics.connected}</Tag>
              <Tag color="blue">已启用 {overviewMetrics.enabled}</Tag>
              {overviewMetrics.failure > 0 && (
                <Tag color="error">异常 {overviewMetrics.failure}</Tag>
              )}
            </Space>
          </Spin>
        </Card>
        {error && (
          <Alert
            type="error"
            showIcon
            message="数据库连接获取失败"
            description={
              <Space size="small">
                <span>{error.message}</span>
                <Button
                  size="small"
                  type="link"
                  onClick={handleRefresh}
                >
                  重新加载
                </Button>
              </Space>
            }
          />
        )}

        <Card
          title="数据库连接管理"
          extra={
            <Space>
              <Button
                icon={<SyncOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => openEditModal()}
              >
                新建连接
              </Button>
            </Space>
          }
        >
          <Table
            columns={columns}
            dataSource={connections}
            loading={loading}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: tableEmptyNode }}
            onRow={record => ({
              onClick: () => selectConnection(record.id),
              style: selectedConnection?.id === record.id
                ? { background: '#f6ffed', cursor: 'pointer' }
                : { cursor: 'pointer' }
            })}
          />
        </Card>
      </Space>

      <Drawer
        title={selectedConnection ? `连接详情：${selectedConnection.name}` : '连接详情'}
        placement="right"
        width={420}
        open={Boolean(selectedConnection)}
        onClose={() => selectConnection(null)}
      >
        {selectedConnection ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="数据库类型">
                {selectedConnection.type.toUpperCase()}
              </Descriptions.Item>
              <Descriptions.Item label="连接地址">
                {formatConnectionAddress(selectedConnection)}
              </Descriptions.Item>
              <Descriptions.Item label="当前状态">
                {selectedConnection.connectivity?.state ?? 'unknown'}
              </Descriptions.Item>
              <Descriptions.Item label="最后健康检查">
                {formatTimestamp(selectedConnection.connectivity?.lastSuccessAt ?? selectedConnection.lastHealthCheck ?? null)}
              </Descriptions.Item>
              <Descriptions.Item label="启用状态">
                {selectedConnection.activation?.enabled ? '已启用' : '未启用'}
              </Descriptions.Item>
              <Descriptions.Item label="错误信息">
                {selectedConnection.connectivity?.lastError || selectedConnection.error || '暂无'}
              </Descriptions.Item>
              <Descriptions.Item label="状态详情">
                {selectedConnection.statusDetail || '暂无'}
              </Descriptions.Item>
            </Descriptions>
            <Space>
              <Button
                icon={<SyncOutlined />}
                onClick={() => handleTest(selectedConnection)}
                loading={testModal.testing && testModal.target?.id === selectedConnection.id}
              >
                测试连接
              </Button>
              <Button
                icon={<EditOutlined />}
                onClick={() => openEditModal(selectedConnection)}
              >
                编辑配置
              </Button>
              <Popconfirm
                title="确定要删除这个连接吗？"
                onConfirm={() => handleDelete(selectedConnection.id)}
                okText="删除"
                cancelText="取消"
              >
                <Button icon={<DeleteOutlined />} danger>
                  删除
                </Button>
              </Popconfirm>
            </Space>
          </Space>
        ) : (
          <Empty description="请选择任意连接查看详情" />
        )}
      </Drawer>

      {/* 编辑/新建弹窗 */}
      <Modal
        title={editModal.isEdit ? '编辑连接' : '新建连接'}
        open={editModal.visible}
        onOk={handleSubmit}
        onCancel={closeEditModal}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            type: 'postgresql',
            port: 5432,
            isDefault: false
          }}
        >
          <Divider orientation="left">基础信息</Divider>
          <Form.Item
            label="连接名称"
            name="name"
            rules={[{ required: true, message: '请输入连接名称' }]}
          >
            <Input placeholder="例如：生产数据库" />
          </Form.Item>

          <Form.Item
            label="数据库类型"
            name="type"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="postgresql">PostgreSQL</Option>
              <Option value="mysql">MySQL</Option>
              <Option value="sqlite">SQLite</Option>
              <Option value="duckdb">DuckDB</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.type !== currentValues.type
            }
          >
            {({ getFieldValue }) => {
              const type = getFieldValue('type')
              if (type === 'sqlite' || type === 'duckdb') {
                return (
                  <Form.Item
                    label="数据库文件"
                    name="database"
                    rules={[{ required: true, message: '请输入数据库文件路径' }]}
                  >
                    <Input placeholder="例如：./data/deepsearch.db" />
                  </Form.Item>
                )
              }

              return (
                <>
                  <Form.Item
                    label="主机地址"
                    name="host"
                    rules={[{ required: true, message: '请输入主机地址' }]}
                  >
                    <Input placeholder="例如：localhost" />
                  </Form.Item>

                  <Form.Item
                    label="端口"
                    name="port"
                    rules={[{ required: true, message: '请输入端口' }]}
                  >
                    <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                  </Form.Item>

                  <Form.Item
                    label="数据库名"
                    name="database"
                    rules={[{ required: true, message: '请输入数据库名' }]}
                  >
                    <Input placeholder="例如：deepsearch" />
                  </Form.Item>

                  <Form.Item
                    label="用户名"
                    name="username"
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input placeholder="例如：postgres" />
                  </Form.Item>

                  <Form.Item
                    label="密码"
                    name="password"
                  >
                    <Input.Password placeholder="请输入密码" />
                  </Form.Item>
                </>
              )
            }}
          </Form.Item>

          <Form.Item label="连接串预览">
            <Space direction="vertical" size={4}>
              <Text code style={{ userSelect: 'all' }}>{connectionPreview}</Text>
              <Text type="secondary">密码仅用于测试与保存，不会在此处展示明文。</Text>
            </Space>
          </Form.Item>

          <Divider orientation="left">运行选项</Divider>

          <Form.Item
            label="设为默认"
            name="isDefault"
            valuePropName="checked"
            tooltip="默认连接将在需要数据库时优先使用"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 测试结果弹窗 */}
      <Modal
        title={testModal.target ? `连接测试：${testModal.target.name}` : '连接测试'}
        open={testModal.visible}
        onCancel={closeTestModal}
        footer={testModalFooter}
        width={520}
      >
        {testModal.testing ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <p style={{ marginTop: 16 }}>正在测试连接...</p>
          </div>
        ) : testModal.result ? (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="连接名称">
              {testModal.target?.name ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="测试结果">
              <Tag color={testModal.result.success ? 'success' : 'error'}>
                {testModal.result.success ? '成功' : '失败'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="消息">
              {testModal.result.message || '-'}
            </Descriptions.Item>
            {typeof testModal.result.latency === 'number' && (
              <Descriptions.Item label="延迟">
                {testModal.result.latency} ms
              </Descriptions.Item>
            )}
            {testModal.result.error && (
              <Descriptions.Item label="错误">
                <Text type="danger">{testModal.result.error}</Text>
              </Descriptions.Item>
            )}
            {testModal.result.details && (
              <Descriptions.Item label="详细信息">
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 4, margin: 0 }}>
                  {JSON.stringify(testModal.result.details, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Empty description="尚未执行测试" />
        )}
      </Modal>
    </>
  )
}

export default DatabaseConfigWithStore

