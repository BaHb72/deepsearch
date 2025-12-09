import React from 'react'
import { Card, Col, Row, Statistic, Typography, Progress } from 'antd'
import type { ReactNode } from 'react'

const { Text } = Typography

export interface ResourceItem {
    key: string
    title: string
    value?: number
    inbound?: number
    outbound?: number
    suffix?: string
    icon: ReactNode
    color: string
}

interface ResourceUsageProps {
    resources: ResourceItem[]
}

const ResourceUsage: React.FC<ResourceUsageProps> = ({ resources }) => {
    return (
        <Row gutter={[16, 16]}>
            {resources.map((item) => (
                <Col xs={24} sm={12} md={6} key={item.key}>
                    <Card bordered={false} hoverable bodyStyle={{ padding: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                            <span style={{ fontSize: 24, marginRight: 12 }}>{item.icon}</span>
                            <Text strong>{item.title}</Text>
                        </div>
                        {item.key === 'network' ? (
                            <Row gutter={16}>
                                <Col span={12}>
                                    <Statistic
                                        title="入站"
                                        value={item.inbound}
                                        suffix="KB/s"
                                        valueStyle={{ fontSize: 16, color: '#3f8600' }}
                                    />
                                </Col>
                                <Col span={12}>
                                    <Statistic
                                        title="出站"
                                        value={item.outbound}
                                        suffix="KB/s"
                                        valueStyle={{ fontSize: 16, color: '#cf1322' }}
                                    />
                                </Col>
                            </Row>
                        ) : (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 100 }}>
                                <Progress
                                    type="dashboard"
                                    percent={item.value}
                                    width={80}
                                    strokeColor={item.color}
                                    format={(percent) => (
                                        <span style={{ color: item.color, fontSize: 14 }}>{percent}%</span>
                                    )}
                                />
                            </div>
                        )}
                    </Card>
                </Col>
            ))}
        </Row>
    )
}

export default ResourceUsage
