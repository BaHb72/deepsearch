import React, { useEffect, useState } from 'react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Card, Table, Tag, Button, Space, message, Drawer, Descriptions,
    Badge, Typography, Collapse, Progress, Row, Col, Tooltip, Divider
} from 'antd';
import {
    ReloadOutlined, ThunderboltOutlined, CheckCircleOutlined,
    CloseCircleOutlined, ApiOutlined, DatabaseOutlined,
    CloudOutlined, DesktopOutlined, CrownOutlined, StarOutlined
} from '@ant-design/icons';
import {
    dataSourceAPI, DataSource, SourceCapabilitiesResponse,
    CapabilityCategorySummary, CapabilityItem
} from '../../api/dataSource';

const { Text, Title } = Typography;
const { Panel } = Collapse;

// 分类图标映射
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
    market: <DatabaseOutlined />,
    quote: <ApiOutlined />,
    depth: <ThunderboltOutlined />,
    special: <StarOutlined />,
    fundamental: <DatabaseOutlined />,
    utility: <CloudOutlined />,
};

// Badge 颜色映射
const BADGE_COLORS: Record<string, string> = {
    gold: '#faad14',
    blue: '#1890ff',
    green: '#52c41a',
    gray: '#8c8c8c',
    orange: '#fa8c16',
};

// 能力分类展示组件
const CapabilityCategories: React.FC<{
    categorizedCapabilities: Record<string, CapabilityCategorySummary>;
}> = ({ categorizedCapabilities }) => {
    if (!categorizedCapabilities || Object.keys(categorizedCapabilities).length === 0) {
        return <Text type="secondary">暂无能力信息</Text>;
    }

    return (
        <Collapse
            defaultActiveKey={Object.keys(categorizedCapabilities)}
            ghost
            style={{ background: 'transparent' }}
        >
            {Object.entries(categorizedCapabilities).map(([catId, category]) => {
                const supportedCount = category.capabilities.filter(c => c.supported).length;
                const totalCount = category.capabilities.length;
                const percent = totalCount > 0 ? Math.round((supportedCount / totalCount) * 100) : 0;

                return (
                    <Panel
                        key={catId}
                        header={
                            <Space>
                                {CATEGORY_ICONS[catId] || <ApiOutlined />}
                                <Text strong>{category.name}</Text>
                                <Tag color={percent === 100 ? 'success' : percent > 50 ? 'processing' : 'warning'}>
                                    {supportedCount}/{totalCount}
                                </Tag>
                            </Space>
                        }
                        extra={
                            <Progress
                                percent={percent}
                                size="small"
                                style={{ width: 80 }}
                                strokeColor={percent === 100 ? '#52c41a' : percent > 50 ? '#1890ff' : '#faad14'}
                            />
                        }
                    >
                        <Space wrap size={[8, 8]}>
                            {category.capabilities.map((cap: CapabilityItem) => (
                                <Tooltip
                                    key={cap.id}
                                    title={cap.supported ? '已支持' : '不支持'}
                                >
                                    <Tag
                                        color={cap.supported ? 'geekblue' : 'default'}
                                        style={{
                                            opacity: cap.supported ? 1 : 0.5,
                                            textDecoration: cap.supported ? 'none' : 'line-through'
                                        }}
                                        icon={cap.supported ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                    >
                                        {cap.name}
                                    </Tag>
                                </Tooltip>
                            ))}
                        </Space>
                    </Panel>
                );
            })}
        </Collapse>
    );
};

// 数据源元数据展示组件
const SourceMetadataCard: React.FC<{
    metadata: SourceCapabilitiesResponse | null;
}> = ({ metadata }) => {
    if (!metadata) return null;

    const badgeColor = BADGE_COLORS[metadata.color] || '#8c8c8c';

    return (
        <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 8]}>
                <Col span={24}>
                    <Space align="center">
                        <Title level={5} style={{ margin: 0 }}>{metadata.name}</Title>
                        <Tag color={badgeColor} style={{ marginLeft: 8 }}>
                            {metadata.badge}
                        </Tag>
                        <Tag color={metadata.cost === 'free' ? 'success' : 'warning'}>
                            {metadata.cost === 'free' ? '免费' : '付费'}
                        </Tag>
                    </Space>
                </Col>
                <Col span={24}>
                    <Text type="secondary">{metadata.description}</Text>
                </Col>
                <Col span={24}>
                    <Space>
                        <Tag icon={metadata.connection_type === 'local' ? <DesktopOutlined /> : <CloudOutlined />}>
                            {metadata.connection_type === 'local' ? '本地部署' : '远程服务'}
                        </Tag>
                        {metadata.requires_auth && (
                            <Tag icon={<CrownOutlined />} color="orange">需要认证</Tag>
                        )}
                    </Space>
                </Col>
                {metadata.unique_features && metadata.unique_features.length > 0 && (
                    <Col span={24}>
                        <Divider style={{ margin: '8px 0' }} />
                        <Text type="secondary" style={{ fontSize: 12 }}>独特功能：</Text>
                        <div style={{ marginTop: 4 }}>
                            <Space wrap size={[4, 4]}>
                                {metadata.unique_features.map((feature, idx) => (
                                    <Tag key={idx} color="purple" style={{ fontSize: 11 }}>
                                        {feature}
                                    </Tag>
                                ))}
                            </Space>
                        </div>
                    </Col>
                )}
            </Row>
        </Card>
    );
};

// 能力统计摘要组件
const CapabilitySummaryCard: React.FC<{
    summary: { total: number; supported: number; unsupported: number } | undefined;
}> = ({ summary }) => {
    if (!summary) return null;

    const percent = summary.total > 0 ? Math.round((summary.supported / summary.total) * 100) : 0;

    return (
        <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16} align="middle">
                <Col span={8}>
                    <Progress
                        type="circle"
                        percent={percent}
                        width={60}
                        strokeColor={percent >= 70 ? '#52c41a' : percent >= 40 ? '#1890ff' : '#faad14'}
                        format={() => (
                            <span style={{ fontSize: 14, fontWeight: 600 }}>{percent}%</span>
                        )}
                    />
                </Col>
                <Col span={16}>
                    <Space direction="vertical" size={0}>
                        <Text type="secondary" style={{ fontSize: 12 }}>能力覆盖率</Text>
                        <Text strong style={{ fontSize: 16 }}>
                            {summary.supported} / {summary.total}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                            已支持 / 全部能力
                        </Text>
                    </Space>
                </Col>
            </Row>
        </Card>
    );
};

const DataExplorer: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [dataSources, setDataSources] = useState<DataSource[]>([]);
    const [selectedSource, setSelectedSource] = useState<DataSource | null>(null);
    const [drawerVisible, setDrawerVisible] = useState(false);
    const [capabilitiesDetail, setCapabilitiesDetail] = useState<SourceCapabilitiesResponse | null>(null);
    const [testingConnection, setTestingConnection] = useState(false);
    const [testResult, setTestResult] = useState<any>(null);
    const [capabilitiesLoading, setCapabilitiesLoading] = useState(false);

    const fetchDataSources = async () => {
        setLoading(true);
        try {
            const data = await dataSourceAPI.getDataSources();
            setDataSources(data);
        } catch (error) {
            message.error('获取数据源列表失败');
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDataSources();
    }, []);

    const handleViewDetails = async (record: DataSource) => {
        setSelectedSource(record);
        setDrawerVisible(true);
        setCapabilitiesDetail(null);
        setTestResult(null);
        setCapabilitiesLoading(true);

        // 获取完整的能力详情
        try {
            const detail = await dataSourceAPI.getSourceCapabilitiesDetail(record.name);
            setCapabilitiesDetail(detail);
        } catch (error) {
            console.error('Failed to fetch capabilities detail:', error);
        } finally {
            setCapabilitiesLoading(false);
        }
    };

    const handleTestConnection = async () => {
        if (!selectedSource) return;
        setTestingConnection(true);
        setTestResult(null);
        try {
            const result = await dataSourceAPI.testDataSource(selectedSource.name);
            setTestResult(result);
            if (result.success) {
                message.success(`连接 ${selectedSource.name} 成功`);
            } else {
                message.error(`连接 ${selectedSource.name} 失败`);
            }
        } catch (error) {
            message.error(`测试连接出现错误`);
            console.error(error);
        } finally {
            setTestingConnection(false);
        }
    };

    const columns = [
        {
            title: '名称',
            dataIndex: 'name',
            key: 'name',
            render: (text: string) => <Text strong>{text}</Text>,
        },
        {
            title: '类型',
            dataIndex: 'type',
            key: 'type',
            render: (text: string) => <Tag color="blue">{text}</Tag>,
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => {
                let color = 'default';
                switch (status) {
                    case 'active': color = 'success'; break;
                    case 'ready': color = 'cyan'; break;
                    case 'error': color = 'error'; break;
                    case 'offline': color = 'default'; break;
                    case 'degraded': color = 'warning'; break;
                }
                return <Badge status={color as any} text={status} />;
            },
        },
        {
            title: '可用性',
            dataIndex: 'available',
            key: 'available',
            render: (available: boolean) => (
                available ? <Tag color="success">可用</Tag> : <Tag color="error">不可用</Tag>
            ),
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: DataSource) => (
                <Space size="middle">
                    <a onClick={() => handleViewDetails(record)}>详情</a>
                </Space>
            ),
        },
    ];

    return (
        <PageContainer
            header={{
                title: '数据源浏览器',
                ghost: true,
                extra: [
                    <Button key="refresh" icon={<ReloadOutlined />} onClick={fetchDataSources} loading={loading}>
                        刷新
                    </Button>,
                ],
            }}
        >
            <ProCard ghost gutter={[16, 16]}>
                <ProCard colSpan={24}>
                    <Table
                        columns={columns}
                        dataSource={dataSources}
                        rowKey="name"
                        loading={loading}
                        pagination={false}
                    />
                </ProCard>
            </ProCard>

            <Drawer
                title={`数据源详情: ${selectedSource?.name}`}
                placement="right"
                width={640}
                onClose={() => setDrawerVisible(false)}
                open={drawerVisible}
                extra={
                    <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleTestConnection} loading={testingConnection}>
                        测试连接
                    </Button>
                }
            >
                {selectedSource && (
                    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        {/* 数据源元数据 */}
                        <SourceMetadataCard metadata={capabilitiesDetail} />

                        {/* 能力统计摘要 */}
                        <CapabilitySummaryCard summary={capabilitiesDetail?.summary} />

                        {/* 基本信息 */}
                        <Descriptions title="连接信息" bordered column={1} size="small">
                            <Descriptions.Item label="名称">{selectedSource.name}</Descriptions.Item>
                            <Descriptions.Item label="类型">{selectedSource.type}</Descriptions.Item>
                            <Descriptions.Item label="优先级">{selectedSource.priority}</Descriptions.Item>
                            <Descriptions.Item label="最近检查">{selectedSource.lastCheck || '-'}</Descriptions.Item>
                        </Descriptions>

                        {/* 分类能力展示 */}
                        <Card
                            title="功能能力"
                            size="small"
                            loading={capabilitiesLoading}
                        >
                            {capabilitiesDetail?.categorized_capabilities ? (
                                <CapabilityCategories
                                    categorizedCapabilities={capabilitiesDetail.categorized_capabilities}
                                />
                            ) : (
                                <Text type="secondary">暂无能力信息或加载中...</Text>
                            )}
                        </Card>

                        {/* 测试结果 */}
                        {testResult && (
                            <Card
                                title="测试结果"
                                size="small"
                                style={{
                                    borderColor: testResult.success ? '#b7eb8f' : '#ffa39e',
                                    background: testResult.success ? '#f6ffed' : '#fff1f0'
                                }}
                            >
                                <Space direction="vertical">
                                    <Space>
                                        {testResult.success ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <CloseCircleOutlined style={{ color: '#f5222d' }} />}
                                        <Text strong>{testResult.success ? '连接成功' : '连接失败'}</Text>
                                    </Space>
                                    <Text>延迟: {testResult.latency_ms} ms</Text>
                                    <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                                        <pre style={{ fontSize: '12px' }}>{JSON.stringify(testResult.data, null, 2)}</pre>
                                    </div>
                                </Space>
                            </Card>
                        )}
                    </Space>
                )}
            </Drawer>
        </PageContainer>
    );
};

export default DataExplorer;
