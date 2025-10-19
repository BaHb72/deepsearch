/**
 * 数据库配置管理 - 使用 Zustand Store 版本
 */

import React from 'react'
import {
    Button,
    Card,
    Empty,
    Form,
    Input,
    InputNumber,
    Modal,
    Popconfirm,
    Select,
    Space,
    Spin,
    Switch,
    Table,
    Tag
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
import {useDatabaseStore} from '@/stores'
import type {CreateConnectionDTO, DatabaseConnection} from '@/stores/types'

const { Option } = Select

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

  // Modal 状态
  const [editModal, setEditModal] = React.useState({
    visible: false,
    isEdit: false,
    editingId: null as number | null
  })

  const [testModal, setTestModal] = React.useState({
    visible: false,
    testing: false,
    result: null as any
  })

    const [toggleLoading, setToggleLoading] = React.useState<Record<number, boolean>>({})

  const [form] = Form.useForm()

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
      // 编辑模式
      form.setFieldsValue(record)
      setEditModal({
        visible: true,
        isEdit: true,
        editingId: record.id
      })
    } else {
      // 新建模式
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

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (editModal.isEdit && editModal.editingId) {
        // 更新
        await updateConnection(editModal.editingId, values)
      } else {
        // 创建
        await createConnection(values as CreateConnectionDTO)
      }

      closeEditModal()
    } catch (error) {
      console.error('提交失败:', error)
    }
  }

  // 删除连接
  const handleDelete = async (id: number) => {
    try {
      await deleteConnection(id)
    } catch (error) {
      console.error('删除失败:', error)
    }
  }

  // 测试连接
  const handleTest = async (record: DatabaseConnection) => {
    setTestModal({
      visible: true,
      testing: true,
      result: null
    })

    try {
      const result = await testConnection(record.id)
      setTestModal({
        visible: true,
        testing: false,
        result
      })
    } catch (error) {
      setTestModal({
        visible: true,
        testing: false,
        result: {
          success: false,
          message: error instanceof Error ? error.message : '测试失败'
        }
      })
    }
  }

  // 表格列定义
    const handleToggle = async (record: DatabaseConnection, enabled: boolean) => {
        if (!record || typeof record.id !== 'number') {
            return
        }
        const key = record.id
        setToggleLoading(prev => ({...prev, [key]: true}))
        try {
            if (enabled) {
                await activateConnection(record.id, {connectImmediately: false})
            } else {
                await deactivateConnection(record.id, {disconnect: true})
            }
        } catch (error) {
            console.error('启用状态切换失败:', error)
        } finally {
            setToggleLoading(prev => {
                const next = {...prev}
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
        <span>
          {record.host ? `${record.host}:${record.port}` : record.database}
        </span>
      )
    },
    {
        title: '启用状态',
        dataIndex: 'enabled',
        key: 'enabled',
        render: (_: any, record: DatabaseConnection) => {
            const isEnabled = record.activation?.enabled ?? record.enabled ?? false
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
              const isEnabled = record.activation?.enabled ?? record.enabled ?? false
              const connectivityState = record.connectivity?.state ?? (isEnabled ? 'unknown' : 'inactive')

              if (!isEnabled) {
                  return (
                      <Tag icon={<CloseCircleOutlined/>} color="default">
                          未启用
                      </Tag>
                  )
              }

              if (connectivityState === 'connected') {
                  return (
                      <Tag icon={<CheckCircleOutlined/>} color="success">
                          已连接
                      </Tag>
                  )
              }

              if (connectivityState === 'connecting' || connectivityState === 'pending') {
                  return (
                      <Tag icon={<SyncOutlined spin/>} color="processing">
                          连接中...
                      </Tag>
                  )
              }

              if (connectivityState === 'error') {
                  return (
                      <Tag icon={<CloseCircleOutlined/>} color="error">
                          连接失败
                      </Tag>
                  )
              }

              return (
                  <Tag icon={<CloseCircleOutlined/>} color="default">
                      未连接
                  </Tag>
              )
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
            okText="保存"
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

  // 渲染错误状态
  if (error && !loading && connections.length === 0) {
    return (
      <Card title="数据库连接管理">
        <Empty
          description={
            <div>
              <p>{error.message}</p>
              <Button onClick={() => fetchConnections(true)} style={{ marginTop: 16 }}>
                重试
              </Button>
            </div>
          }
        />
      </Card>
    )
  }

  return (
    <>
      <Card
        title="数据库连接管理"
        extra={
          <Space>
            <Button
              icon={<SyncOutlined />}
              onClick={() => fetchConnections(true)}
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
        />
      </Card>

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

          <Form.Item
            label="设为默认"
            name="isDefault"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 测试结果弹窗 */}
      <Modal
        title="连接测试"
        open={testModal.visible}
        onCancel={() => setTestModal({ visible: false, testing: false, result: null })}
        footer={[
          <Button
            key="close"
            onClick={() => setTestModal({ visible: false, testing: false, result: null })}
          >
            关闭
          </Button>
        ]}
      >
        {testModal.testing ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <p style={{ marginTop: '16px' }}>正在测试连接...</p>
          </div>
        ) : testModal.result ? (
          <div>
            <p>
              <strong>测试结果：</strong>
              <Tag color={testModal.result.success ? 'success' : 'error'}>
                {testModal.result.success ? '成功' : '失败'}
              </Tag>
            </p>
            <p><strong>消息：</strong>{testModal.result.message}</p>
            {testModal.result.latency && (
              <p><strong>延迟：</strong>{testModal.result.latency}ms</p>
            )}
            {testModal.result.error && (
              <p style={{ color: 'red' }}><strong>错误：</strong>{testModal.result.error}</p>
            )}
          </div>
        ) : null}
      </Modal>
    </>
  )
}

export default DatabaseConfigWithStore
