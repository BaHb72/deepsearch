import React from 'react'
import { Alert, Button, Card, List, Tag, Typography } from 'antd'


const { Text } = Typography

export interface IncidentItem {
    key: string
    name: string
    title: string
    reason: string
    recommendation: string
    level: 'critical' | 'warning'
}

interface IncidentListProps {
    incidents: IncidentItem[]
}

const IncidentList: React.FC<IncidentListProps> = ({ incidents }) => {
    return (
        <Card
            title="待处理事件"
            extra={<Button type="link">查看全部</Button>}
            bordered={false}
            style={{ height: '100%' }}
        >
            <List
                dataSource={incidents}
                renderItem={(item) => (
                    <List.Item>
                        <Alert
                            message={
                                <div
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                    }}
                                >
                                    <Text strong>{item.name}</Text>
                                    <Tag color={item.level === 'critical' ? 'red' : 'orange'}>{item.title}</Tag>
                                </div>
                            }
                            description={
                                <div style={{ marginTop: 8 }}>
                                    <div>
                                        <Text type="secondary">原因：</Text>
                                        {item.reason}
                                    </div>
                                    <div style={{ marginTop: 4 }}>
                                        <Text type="secondary">建议：</Text>
                                        {item.recommendation}
                                    </div>
                                </div>
                            }
                            type={item.level === 'critical' ? 'error' : 'warning'}
                            showIcon
                            style={{ width: '100%' }}
                        />
                    </List.Item>
                )}
                locale={{ emptyText: '暂无待处理事件' }}
            />
        </Card>
    )
}

export default IncidentList
