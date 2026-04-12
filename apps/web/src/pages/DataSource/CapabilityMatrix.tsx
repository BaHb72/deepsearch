import React, { useEffect, useState, useMemo } from 'react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Table, Tag, Space, Tooltip, Select, Card, Row, Col,
    Typography, Progress, Checkbox, Badge, Spin
} from 'antd';
import {
    CheckCircleOutlined, CloseCircleOutlined,
    CloudOutlined, DesktopOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
    type CapabilityMatrix as CapabilityMatrixData,
    type CategoryInfo,
    type SourceMatrixInfo,
    dataSourceAPI,
} from '../../api/dataSource';

const { Text } = Typography;

// Badge 颜色映射
const BADGE_COLORS: Record<string, string> = {
    gold: '#faad14',
    blue: '#1890ff',
    green: '#52c41a',
    gray: '#8c8c8c',
    orange: '#fa8c16',
};

// 数据源卡片头部
const SourceHeader: React.FC<{ source: SourceMatrixInfo }> = ({ source }) => {
    const badgeColor = BADGE_COLORS[source.color] || '#8c8c8c';
    return (
        <Space direction="vertical" size={0} style={{ width: '100%', padding: '8px 0' }}>
            <Space>
                <Text strong>{source.name}</Text>
                <Tag color={badgeColor} style={{ fontSize: 10 }}>{source.badge}</Tag>
            </Space>
            <Space size={4}>
                <Tag
                    icon={source.connection_type === 'local' ? <DesktopOutlined /> : <CloudOutlined />}
                    style={{ fontSize: 10 }}
                >
                    {source.connection_type === 'local' ? '本地' : '远程'}
                </Tag>
                <Tag
                    color={source.cost === 'free' ? 'success' : 'warning'}
                    style={{ fontSize: 10 }}
                >
                    {source.cost === 'free' ? '免费' : '付费'}
                </Tag>
            </Space>
            <Progress
                percent={parseInt(source.coverage_rate)}
                size="small"
                style={{ marginTop: 4 }}
                strokeColor={parseInt(source.coverage_rate) >= 50 ? '#52c41a' : '#faad14'}
            />
        </Space>
    );
};

// 能力单元格
const CapabilityCell: React.FC<{ supported: boolean; name: string }> = ({ supported, name }) => (
    <Tooltip title={`${name}: ${supported ? '已支持' : '不支持'}`}>
        <div style={{ textAlign: 'center' }}>
            {supported ? (
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
            ) : (
                <CloseCircleOutlined style={{ color: '#d9d9d9', fontSize: 16 }} />
            )}
        </div>
    </Tooltip>
);

interface CapabilityRow {
    key: string;
    capabilityId: string;
    capabilityName: string;
    category: string;
    categoryName: string;
    sources: Record<string, boolean>;
    supportCount: number;
}

const CapabilityMatrix: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [matrix, setMatrix] = useState<CapabilityMatrixData | null>(null);
    const [selectedCategory, setSelectedCategory] = useState<string>('all');
    const [selectedSources, setSelectedSources] = useState<string[]>([]);
    const [showOnlyDifferences, setShowOnlyDifferences] = useState(false);

    useEffect(() => {
        const fetchMatrix = async () => {
            setLoading(true);
            try {
                const data = await dataSourceAPI.getCapabilityMatrix();
                setMatrix(data);
                if (data?.sources) {
                    setSelectedSources(Object.keys(data.sources));
                }
            } catch (error) {
                console.error('Failed to fetch capability matrix:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchMatrix();
    }, []);

    // 构建表格数据
    const tableData: CapabilityRow[] = useMemo(() => {
        if (!matrix) return [];

        const rows: CapabilityRow[] = [];

        // 遍历所有分类和能力
        Object.entries(matrix.categories).forEach(([catId, category]: [string, CategoryInfo]) => {
            category.capabilities.forEach(cap => {
                const sources: Record<string, boolean> = {};
                let supportCount = 0;

                selectedSources.forEach(sourceId => {
                    const sourceInfo = matrix.sources[sourceId];
                    if (sourceInfo?.capabilities?.[cap.id]) {
                        const supported = sourceInfo.capabilities[cap.id].supported;
                        sources[sourceId] = supported;
                        if (supported) supportCount++;
                    } else {
                        sources[sourceId] = false;
                    }
                });

                rows.push({
                    key: cap.id,
                    capabilityId: cap.id,
                    capabilityName: cap.name,
                    category: catId,
                    categoryName: category.name,
                    sources,
                    supportCount,
                });
            });
        });

        return rows;
    }, [matrix, selectedSources]);

    // 过滤数据
    const filteredData = useMemo(() => {
        let data = tableData;

        // 按分类过滤
        if (selectedCategory !== 'all') {
            data = data.filter(row => row.category === selectedCategory);
        }

        // 只显示差异项
        if (showOnlyDifferences && selectedSources.length > 1) {
            data = data.filter(row => {
                const values = selectedSources.map(s => row.sources[s]);
                const allSame = values.every(v => v === values[0]);
                return !allSame;
            });
        }

        return data;
    }, [tableData, selectedCategory, showOnlyDifferences, selectedSources]);

    // 构建表格列
    const columns: ColumnsType<CapabilityRow> = useMemo(() => {
        const cols: ColumnsType<CapabilityRow> = [
            {
                title: '分类',
                dataIndex: 'categoryName',
                key: 'category',
                width: 100,
                fixed: 'left',
                render: (text: string) => <Tag>{text}</Tag>,
                onCell: (record, index) => {
                    // 合并相同分类的单元格
                    const currentCategory = record.category;
                    const prevRecord = index && index > 0 ? filteredData[index - 1] : null;
                    if (prevRecord && prevRecord.category === currentCategory) {
                        return { rowSpan: 0 };
                    }
                    const rowSpan = filteredData.filter(r => r.category === currentCategory).length;
                    return { rowSpan };
                },
            },
            {
                title: '能力',
                dataIndex: 'capabilityName',
                key: 'capability',
                width: 120,
                fixed: 'left',
            },
        ];

        // 添加数据源列
        if (matrix?.sources) {
            selectedSources.forEach(sourceId => {
                const sourceInfo = matrix.sources[sourceId];
                if (sourceInfo) {
                    cols.push({
                        title: <SourceHeader source={sourceInfo} />,
                        dataIndex: ['sources', sourceId],
                        key: sourceId,
                        width: 140,
                        align: 'center',
                        render: (supported: boolean, record) => (
                            <CapabilityCell
                                supported={supported}
                                name={record.capabilityName}
                            />
                        ),
                    });
                }
            });
        }

        // 添加统计列
        cols.push({
            title: '支持数',
            dataIndex: 'supportCount',
            key: 'supportCount',
            width: 80,
            fixed: 'right',
            align: 'center',
            render: (count: number) => (
                <Badge
                    count={count}
                    style={{
                        backgroundColor: count === selectedSources.length ? '#52c41a'
                            : count > 0 ? '#1890ff' : '#d9d9d9'
                    }}
                />
            ),
        });

        return cols;
    }, [matrix, selectedSources, filteredData]);

    // 分类选项
    const categoryOptions = useMemo(() => {
        if (!matrix?.categories) return [];
        return [
            { label: '全部分类', value: 'all' },
            ...Object.entries(matrix.categories).map(([id, cat]: [string, CategoryInfo]) => ({
                label: cat.name,
                value: id,
            })),
        ];
    }, [matrix]);

    // 数据源选项
    const sourceOptions = useMemo(() => {
        if (!matrix?.sources) return [];
        return Object.entries(matrix.sources).map(([id, source]: [string, SourceMatrixInfo]) => ({
            label: source.name,
            value: id,
        }));
    }, [matrix]);

    if (loading) {
        return (
            <PageContainer>
                <div style={{ textAlign: 'center', padding: '100px 0' }}>
                    <Spin size="large" tip="加载能力矩阵..." />
                </div>
            </PageContainer>
        );
    }

    return (
        <PageContainer
            header={{
                title: '数据源能力矩阵',
                subTitle: '对比各数据源的功能支持情况',
                ghost: true,
            }}
        >
            <ProCard ghost gutter={[16, 16]} direction="column">
                {/* 筛选区域 */}
                <ProCard>
                    <Row gutter={[16, 16]} align="middle">
                        <Col>
                            <Text strong>分类筛选：</Text>
                            <Select
                                style={{ width: 150, marginLeft: 8 }}
                                value={selectedCategory}
                                onChange={setSelectedCategory}
                                options={categoryOptions}
                            />
                        </Col>
                        <Col>
                            <Text strong>数据源：</Text>
                            <Select
                                mode="multiple"
                                style={{ width: 300, marginLeft: 8 }}
                                value={selectedSources}
                                onChange={setSelectedSources}
                                options={sourceOptions}
                                maxTagCount={3}
                            />
                        </Col>
                        <Col>
                            <Checkbox
                                checked={showOnlyDifferences}
                                onChange={e => setShowOnlyDifferences(e.target.checked)}
                            >
                                只显示差异项
                            </Checkbox>
                        </Col>
                    </Row>
                </ProCard>

                {/* 统计卡片 */}
                <Row gutter={16}>
                    {selectedSources.map(sourceId => {
                        const source = matrix?.sources[sourceId];
                        if (!source) return null;
                        return (
                            <Col key={sourceId} xs={24} sm={12} md={8} lg={6}>
                                <Card size="small">
                                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                        <Space>
                                            <Text strong>{source.name}</Text>
                                            <Tag color={BADGE_COLORS[source.color]}>{source.badge}</Tag>
                                        </Space>
                                        <Progress
                                            percent={parseInt(source.coverage_rate)}
                                            size="small"
                                            format={() => `${source.supported_count}/${source.total_count}`}
                                        />
                                        <Text type="secondary" style={{ fontSize: 11 }}>
                                            覆盖率: {source.coverage_rate}
                                        </Text>
                                    </Space>
                                </Card>
                            </Col>
                        );
                    })}
                </Row>

                {/* 能力矩阵表格 */}
                <ProCard>
                    <Table
                        columns={columns}
                        dataSource={filteredData}
                        pagination={false}
                        scroll={{ x: 'max-content', y: 600 }}
                        size="small"
                        bordered
                        rowClassName={(record) => {
                            if (record.supportCount === selectedSources.length) {
                                return 'capability-row-all-support';
                            }
                            if (record.supportCount === 0) {
                                return 'capability-row-none-support';
                            }
                            return 'capability-row-partial-support';
                        }}
                    />
                </ProCard>
            </ProCard>

            <style>{`
                .capability-row-all-support {
                    background-color: #f6ffed;
                }
                .capability-row-none-support {
                    background-color: #fafafa;
                }
                .capability-row-partial-support {
                    background-color: #e6f7ff;
                }
            `}</style>
        </PageContainer>
    );
};

export default CapabilityMatrix;
