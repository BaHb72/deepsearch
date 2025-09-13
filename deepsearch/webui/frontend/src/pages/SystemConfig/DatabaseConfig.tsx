import React, { useEffect } from 'react'

/**
 * @typedef {import('@/types/systemConfig').DatabaseConnection} DatabaseConnection
 * @typedef {import('@/types/systemConfig').DatabaseFormProps} DatabaseFormProps
 */

import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Badge,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Row,
  Col,
  message,
  Popconfirm
} from 'antd'
import {
  DatabaseOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons'
import { useModal, useAsyncData } from '@/hooks'
import {
  fetchDatabaseConnections,
  createDatabaseConnection,
  updateDatabaseConnection,
  deleteDatabaseConnection,
  testDatabaseConnection
} from '@/api/systemConfig'

const { Option } = Select





/**
 * 数据库连接表单组件
 */
const DatabaseForm = ({ initialValues, onSubmit }) => {
  const [form] = Form.useForm()
  const [dbType, setDbType] = React.useState(initialValues?.type || 'postgresql')
  const [testing, setTesting] = React.useState(false)

  const handleTest = async () => {
    try {
      setTesting(true)
      const values = form.getFieldsValue()
      const response = await testDatabaseConnection(values)
      if (response?.data?.success) {
        message.success('连接成功！')
      } else {
        message.error('连接失败，请检查配置')
      }
    } catch (error) {
      message.error('连接测试失败: ' + (error.message || '未知错误'))
    } finally {
      setTesting(false)
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={initialValues}
      onFinish={onSubmit}
    >
      <Form.Item
        name="name"
        label="连接名称"
        rules={[{ required: true, message: '请输入连接名称' }]}
      >
        <Input placeholder="例如：主数据库" />
      </Form.Item>

      <Form.Item
        name="type"
        label="数据库类型"
        rules={[{ required: true, message: '请选择数据库类型' }]}
      >
        <Select onChange={setDbType}>
          <Option value="postgresql">PostgreSQL</Option>
          <Option value="mysql">MySQL</Option>
          <Option value="duckdb">DuckDB</Option>
          <Option value="redis">Redis</Option>
          <Option value="mongodb">MongoDB</Option>
        </Select>
      </Form.Item>

      {dbType !== 'duckdb' && (
        <>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="host"
                label="主机地址"
                rules={[{ required: true, message: '请输入主机地址' }]}
              >
                <Input placeholder="例如：localhost 或 192.168.1.100" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="port"
                label="端口"
                rules={[{ required: true, message: '请输入端口' }]}
              >
                <InputNumber 
                  min={1} 
                  max={65535} 
                  style={{ width: '100%' }}
                  placeholder={
                    dbType === 'postgresql' ? '5432' :
                    dbType === 'mysql' ? '3306' :
                    dbType === 'redis' ? '6379' :
                    dbType === 'mongodb' ? '27017' : ''
                  }
                />
              </Form.Item>
            </Col>
          </Row>

          {dbType !== 'redis' && (
            <>
              <Form.Item
                name="database"
                label="数据库名"
                rules={[{ required: true, message: '请输入数据库名' }]}
              >
                <Input placeholder="例如：deepsearch" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input placeholder="数据库用户名" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[{ required: true, message: '请输入密码' }]}
                  >
                    <Input.Password placeholder="数据库密码" />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
        </>
      )}

      {dbType === 'duckdb' && (
        <Form.Item
          name="database"
          label="数据库文件路径"
          rules={[{ required: true, message: '请输入数据库文件路径' }]}
        >
          <Input placeholder="例如：./data/market.duckdb" />
        </Form.Item>
      )}

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="poolSize" label="连接池大小">
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="maxConnections" label="最大连接数">
            <InputNumber min={1} max={1000} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="connectionTimeout" label="超时时间(秒)">
            <InputNumber min={1} max={300} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item>
        <Space>
          <Button onClick={handleTest} loading={testing}>
            测试连接
          </Button>
          <Button type="primary" htmlType="submit">
            {initialValues ? '更新' : '创建'}
          </Button>
        </Space>
      </Form.Item>
    </Form>
  )
}

/**
 * 数据库配置管理组件
 */
const DatabaseConfig = () => {
  const editModal = useModal()
  
  // 添加调试日志
  React.useEffect(() => {
    console.log('[DatabaseConfig] 组件已挂载')
    return () => {
      console.log('[DatabaseConfig] 组件已卸载')
    }
  }, [])
  
  // 使用 useCallback 包装异步函数，避免每次渲染都创建新函数
  const fetchConnections = React.useCallback(async () => {
    console.log('[DatabaseConfig] 开始获取数据库连接列表...')
    try {
      const result = await fetchDatabaseConnections()
      console.log('[DatabaseConfig] 获取数据库连接成功:', result)
      return result
    } catch (err) {
      console.error('[DatabaseConfig] 获取数据库连接失败:', err)
      throw err
    }
  }, [])
  
  const {
    data: connections,
    loading,
    refresh,
    error
  } = useAsyncData(
    fetchConnections,
    { 
      immediate: true,
      showError: false, // API 未实现时不显示错误
      onError: (err) => {
        console.error('[DatabaseConfig] useAsyncData onError:', err)
      }
    }
  )
  
  // 监控加载状态
  React.useEffect(() => {
    console.log('[DatabaseConfig] 加载状态:', { loading, error, hasData: !!connections })
  }, [loading, error, connections])

  const handleCreate = async (values) => {
    try {
      await createDatabaseConnection(values)
      message.success('创建成功')
      editModal.close()
      refresh()
    } catch (error) {
      message.error('创建失败: ' + error.message)
    }
  }

  const handleUpdate = async (values) => {
    if (!editModal.data?.id) return
    try {
      await updateDatabaseConnection(editModal.data.id, values)
      message.success('更新成功')
      editModal.close()
      refresh()
    } catch (error) {
      message.error('更新失败: ' + error.message)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteDatabaseConnection(id)
      message.success('删除成功')
      refresh()
    } catch (error) {
      message.error('删除失败: ' + error.message)
    }
  }

  // 调试日志：渲染信息
  console.log('[DatabaseConfig] 渲染组件:', {
    loading,
    connectionsCount: connections?.length || 0,
    error: error?.message
  })
  
  const columns = [
    {
      title: '连接名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
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
      render: (type) => (
        <Tag color="blue">{type.toUpperCase()}</Tag>
      )
    },
    {
      title: '连接地址',
      key: 'address',
      render: (_, record) => (
        <span>
          {record.host ? `${record.host}:${record.port}` : record.database}
        </span>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Badge
          status={
            status === 'connected' ? 'success' :
            status === 'error' ? 'error' : 'default'
          }
          text={
            status === 'connected' ? '已连接' :
            status === 'error' ? '连接错误' : '未连接'
          }
        />
      )
    },
    {
      title: '连接池',
      key: 'pool',
      render: (_, record) => (
        <span>{record.poolSize || '-'} / {record.maxConnections || '-'}</span>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => editModal.open(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此连接？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button
              type="link"
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

  return (
    <>
      <Card
        title="数据库连接管理"
        extra={
          <Space>
            <Button
              icon={<SyncOutlined />}
              onClick={refresh}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => editModal.open()}
            >
              新建连接
            </Button>
          </Space>
        }
      >
        {error ? (
          <div style={{ textAlign: 'center', padding: '50px' }}>
            <p style={{ color: '#ff4d4f' }}>
              {error.message?.includes('503') || error.message?.includes('系统未初始化') 
                ? '后端服务未就绪' 
                : '加载失败: ' + error.message}
            </p>
            {(error.message?.includes('503') || error.message?.includes('系统未初始化')) && (
              <div style={{ marginTop: '16px', padding: '16px', background: '#f0f0f0', borderRadius: '4px' }}>
                <p style={{ marginBottom: '8px' }}>请确保后端服务已启动：</p>
                <code style={{ display: 'block', padding: '8px', background: '#000', color: '#0f0', borderRadius: '4px' }}>
                  python -m deepsearch run --no-frontend
                </code>
              </div>
            )}
            <p style={{ color: '#999', fontSize: '12px', marginTop: '8px' }}>
              详细错误: {error.stack || error.toString()}
            </p>
            <Button onClick={refresh} style={{ marginTop: 16 }}>重试</Button>
          </div>
        ) : (
          <Table
            columns={columns}
            dataSource={connections || []}
            loading={loading && !(connections && connections.length > 0)}
            rowKey="id"
            pagination={false}
            locale={{
              emptyText: loading ? '正在加载数据库连接...' : '暂无数据库连接配置'
            }}
          />
        )}
      </Card>

      <Modal
        title={editModal.data ? '编辑数据库连接' : '新建数据库连接'}
        open={editModal.visible}
        onCancel={editModal.close}
        footer={null}
        width={600}
      >
        <DatabaseForm
          initialValues={editModal.data || undefined}
          onSubmit={editModal.data ? handleUpdate : handleCreate}
        />
      </Modal>
    </>
  )
}

export default DatabaseConfig