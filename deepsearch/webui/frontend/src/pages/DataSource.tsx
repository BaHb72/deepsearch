import React, { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Tooltip,
  Row,
  Col,
  Statistic,
  Badge,
  Drawer,
  Descriptions,
  Alert,
  Popconfirm,
  InputNumber,
  Tabs,
  Divider,
  Typography
} from 'antd'
import { ProCard, ProTable, ProForm, ProFormText, ProFormSelect, ProFormSwitch, ProFormDigit } from '@ant-design/pro-components'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ApiOutlined,
  DatabaseOutlined,
  CloudOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  MonitorOutlined,
  LinkOutlined,
  DisconnectOutlined,
  SyncOutlined,
  WarningOutlined,
  SafetyOutlined
} from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

// 数据源类型配置
const dataSourceTypes = {
  amazingdata: {
    name: 'AmazingData',
    icon: <ThunderboltOutlined />,
    color: 'gold',
    description: '银河证券星耀数智数据库',
    configFields: ['api_key', 'api_secret', 'server_url', 'timeout']
  },
  cloudflare: {
    name: 'CloudFlare Workers',
    icon: <CloudOutlined />,
    color: 'blue',
    description: 'CloudFlare边缘网络代理',
    configFields: ['worker_url', 'auth_token', 'region', 'timeout']
  },
  qmt: {
    name: 'QMT Gateway',
    icon: <ApiOutlined />,
    color: 'green',
    description: 'QMT量化交易终端',
    configFields: ['host', 'port', 'username', 'password', 'timeout']
  },
  akshare: {
    name: 'AKShare',
    icon: <DatabaseOutlined />,
    color: 'purple',
    description: 'AKShare开源财经数据',
    configFields: ['proxy_url', 'timeout', 'retry_count']
  },
  postgresql: {
    name: 'PostgreSQL',
    icon: <DatabaseOutlined />,
    color: 'cyan',
    description: 'PostgreSQL数据库',
    configFields: ['host', 'port', 'database', 'username', 'password', 'pool_size']
  },
  redis: {
    name: 'Redis',
    icon: <DatabaseOutlined />,
    color: 'red',
    description: 'Redis缓存数据库',
    configFields: ['host', 'port', 'password', 'db', 'pool_size']
  }
}

const DataSource = () => {
  const [dataSources, setDataSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingSource, setEditingSource] = useState(null)
  const [testingId, setTestingId] = useState(null)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)
  const [selectedSource, setSelectedSource] = useState(null)
  const [form] = Form.useForm()

  // 模拟数据
  useEffect(() => {
    fetchDataSources()
  }, [])

  const fetchDataSources = async () => {
    setLoading(true)
    // 模拟API调用
    setTimeout(() => {
      setDataSources([
        {
          id: 1,
          name: 'AmazingData主数据源',
          type: 'amazingdata',
          status: 'connected',
          enabled: true,
          priority: 1,
          config: {
            server_url: 'https://api.amazingdata.com',
            timeout: 30000
          },
          statistics: {
            requests: 15234,
            success_rate: 99.8,
            avg_latency: 45,
            last_check: '2024-01-20 10:30:00'
          }
        },
        {
          id: 2,
          name: 'CloudFlare代理',
          type: 'cloudflare',
          status: 'connected',
          enabled: true,
          priority: 2,
          config: {
            worker_url: 'https://worker.example.com',
            region: 'asia',
            timeout: 20000
          },
          statistics: {
            requests: 8921,
            success_rate: 98.5,
            avg_latency: 120,
            last_check: '2024-01-20 10:29:30'
          }
        },
        {
          id: 3,
          name: 'QMT本地网关',
          type: 'qmt',
          status: 'disconnected',
          enabled: false,
          priority: 3,
          config: {
            host: '127.0.0.1',
            port: 8888,
            timeout: 10000
          },
          statistics: {
            requests: 0,
            success_rate: 0,
            avg_latency: 0,
            last_check: '2024-01-20 10:25:00'
          }
        },
        {
          id: 4,
          name: 'PostgreSQL主库',
          type: 'postgresql',
          status: 'connected',
          enabled: true,
          priority: 0,
          config: {
            host: 'localhost',
            port: 5432,
            database: 'deepsearch',
            pool_size: 10
          },
          statistics: {
            requests: 45678,
            success_rate: 100,
            avg_latency: 5,
            last_check: '2024-01-20 10:30:00'
          }
        }
      ])
      setLoading(false)
    }, 1000)
  }

  const handleAdd = () => {
    setEditingSource(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingSource(record)
    form.setFieldsValue({
      ...record,
      ...record.config
    })
    setModalVisible(true)
  }

  const handleDelete = async (id) => {
    message.success('数据源删除成功')
    fetchDataSources()
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      if (editingSource) {
        message.success('数据源更新成功')
      } else {
        message.success('数据源添加成功')
      }
      setModalVisible(false)
      fetchDataSources()
    } catch (error) {
      console.error('Validation failed:', error)
    }
  }

  const handleTest = async (record) => {
    setTestingId(record.id)
    // 模拟测试连接
    setTimeout(() => {
      if (record.type === 'qmt') {
        message.error(`连接失败: ${record.name}`)
      } else {
        message.success(`连接成功: ${record.name}`)
      }
      setTestingId(null)
    }, 2000)
  }

  const handleToggleStatus = async (record) => {
    const newStatus = !record.enabled
    message.success(`数据源${newStatus ? '启用' : '禁用'}成功`)
    fetchDataSources()
  }

  const showDetail = (record) => {
    setSelectedSource(record)
    setDetailDrawerVisible(true)
  }

  const columns = [
    {
      title: '数据源名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (text, record) => (
        <Space>
          {dataSourceTypes[record.type]?.icon}
          <a onClick={() => showDetail(record)}>{text}</a>
        </Space>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 150,
      render: (type) => (
        <Tag color={dataSourceTypes[type]?.color}>
          {dataSourceTypes[type]?.name}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status) => (
        <Badge
          status={status === 'connected' ? 'success' : 'error'}
          text={status === 'connected' ? '已连接' : '未连接'}
        />
      )
    },
    {
      title: '启用状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggleStatus(record)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      )
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a, b) => a.priority - b.priority,
      render: (priority) => (
        <Tag color={priority === 1 ? 'gold' : priority === 2 ? 'blue' : 'default'}>
          {priority}
        </Tag>
      )
    },
    {
      title: '成功率',
      key: 'success_rate',
      width: 100,
      render: (_, record) => (
        <span style={{ color: record.statistics.success_rate > 95 ? '#52c41a' : '#faad14' }}>
          {record.statistics.success_rate}%
        </span>
      )
    },
    {
      title: '平均延迟',
      key: 'avg_latency',
      width: 100,
      render: (_, record) => (
        <span>{record.statistics.avg_latency}ms</span>
      )
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 200,
      render: (_, record) => (
        <Space>
          <Tooltip title="测试连接">
            <Button
              type="link"
              icon={<LinkOutlined />}
              loading={testingId === record.id}
              onClick={() => handleTest(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Tooltip title="删除">
            <Popconfirm
              title="确定删除此数据源吗？"
              onConfirm={() => handleDelete(record.id)}
            >
              <Button type="link" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Tooltip>
        </Space>
      )
    }
  ]

  const renderConfigForm = (type) => {
    const config = dataSourceTypes[type]
    if (!config) return null

    const fieldComponents = {
      api_key: <ProFormText name="api_key" label="API Key" rules={[{ required: true }]} />,
      api_secret: <ProFormText.Password name="api_secret" label="API Secret" rules={[{ required: true }]} />,
      server_url: <ProFormText name="server_url" label="服务器地址" rules={[{ required: true, type: 'url' }]} />,
      worker_url: <ProFormText name="worker_url" label="Worker URL" rules={[{ required: true, type: 'url' }]} />,
      auth_token: <ProFormText.Password name="auth_token" label="认证Token" />,
      region: <ProFormSelect name="region" label="区域" options={[
        { label: '亚洲', value: 'asia' },
        { label: '欧洲', value: 'europe' },
        { label: '美洲', value: 'america' }
      ]} />,
      host: <ProFormText name="host" label="主机地址" rules={[{ required: true }]} />,
      port: <ProFormDigit name="port" label="端口" rules={[{ required: true }]} min={1} max={65535} />,
      database: <ProFormText name="database" label="数据库名" rules={[{ required: true }]} />,
      username: <ProFormText name="username" label="用户名" rules={[{ required: true }]} />,
      password: <ProFormText.Password name="password" label="密码" rules={[{ required: true }]} />,
      proxy_url: <ProFormText name="proxy_url" label="代理地址" />,
      timeout: <ProFormDigit name="timeout" label="超时时间(ms)" min={1000} max={60000} />,
      retry_count: <ProFormDigit name="retry_count" label="重试次数" min={0} max={10} />,
      pool_size: <ProFormDigit name="pool_size" label="连接池大小" min={1} max={100} />,
      db: <ProFormDigit name="db" label="数据库索引" min={0} max={15} />
    }

    return config.configFields.map(field => (
      <Col span={12} key={field}>
        {fieldComponents[field]}
      </Col>
    ))
  }

  return (
    <div>
      <ProCard>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总数据源"
                value={dataSources.length}
                prefix={<DatabaseOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="已连接"
                value={dataSources.filter(ds => ds.status === 'connected').length}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="已启用"
                value={dataSources.filter(ds => ds.enabled).length}
                valueStyle={{ color: '#1890ff' }}
                prefix={<SafetyOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均成功率"
                value={98.5}
                suffix="%"
                valueStyle={{ color: '#52c41a' }}
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title={
            <Space>
              <DatabaseOutlined />
              <span>数据源配置管理</span>
            </Space>
          }
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchDataSources}>
                刷新
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
                添加数据源
              </Button>
            </Space>
          }
        >
          <Alert
            message="数据源优先级说明"
            description="系统将按照优先级从低到高的顺序尝试连接数据源，当高优先级数据源不可用时自动切换到下一个可用数据源。"
            type="info"
            showIcon
            closable
            style={{ marginBottom: 16 }}
          />

          <Table
            columns={columns}
            dataSource={dataSources}
            rowKey="id"
            loading={loading}
            scroll={{ x: 1200 }}
            pagination={{
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条记录`
            }}
          />
        </Card>
      </ProCard>

      {/* 添加/编辑弹窗 */}
      <Modal
        title={editingSource ? '编辑数据源' : '添加数据源'}
        open={modalVisible}
        onOk={handleSave}
        onCancel={() => setModalVisible(false)}
        width={800}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            enabled: true,
            priority: 10,
            timeout: 30000
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="数据源名称"
                rules={[{ required: true, message: '请输入数据源名称' }]}
              >
                <Input placeholder="请输入数据源名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="type"
                label="数据源类型"
                rules={[{ required: true, message: '请选择数据源类型' }]}
              >
                <Select placeholder="请选择数据源类型">
                  {Object.entries(dataSourceTypes).map(([key, value]) => (
                    <Select.Option key={key} value={key}>
                      <Space>
                        {value.icon}
                        {value.name}
                      </Space>
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label="优先级">
                <InputNumber min={1} max={100} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="enabled" label="启用状态" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
          </Row>

          <Divider>连接配置</Divider>

          <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => prevValues.type !== currentValues.type}>
            {({ getFieldValue }) => (
              <Row gutter={16}>
                {renderConfigForm(getFieldValue('type'))}
              </Row>
            )}
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情抽屉 */}
      <Drawer
        title="数据源详情"
        placement="right"
        width={600}
        onClose={() => setDetailDrawerVisible(false)}
        open={detailDrawerVisible}
      >
        {selectedSource && (
          <div>
            <Descriptions bordered column={1}>
              <Descriptions.Item label="名称">{selectedSource.name}</Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={dataSourceTypes[selectedSource.type]?.color}>
                  {dataSourceTypes[selectedSource.type]?.name}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Badge
                  status={selectedSource.status === 'connected' ? 'success' : 'error'}
                  text={selectedSource.status === 'connected' ? '已连接' : '未连接'}
                />
              </Descriptions.Item>
              <Descriptions.Item label="优先级">{selectedSource.priority}</Descriptions.Item>
              <Descriptions.Item label="描述">
                {dataSourceTypes[selectedSource.type]?.description}
              </Descriptions.Item>
            </Descriptions>

            <Divider>性能统计</Divider>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic title="总请求数" value={selectedSource.statistics.requests} />
              </Col>
              <Col span={12}>
                <Statistic 
                  title="成功率" 
                  value={selectedSource.statistics.success_rate} 
                  suffix="%"
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col span={12}>
                <Statistic 
                  title="平均延迟" 
                  value={selectedSource.statistics.avg_latency} 
                  suffix="ms"
                />
              </Col>
              <Col span={12}>
                <Statistic 
                  title="最后检查" 
                  value={selectedSource.statistics.last_check}
                  valueStyle={{ fontSize: 14 }}
                />
              </Col>
            </Row>

            <Divider>配置信息</Divider>
            <Descriptions bordered column={1} size="small">
              {Object.entries(selectedSource.config).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {typeof value === 'object' ? JSON.stringify(value) : value}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default DataSource