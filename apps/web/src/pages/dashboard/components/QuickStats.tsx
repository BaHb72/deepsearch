import React from 'react'
import { Card, Col, Row, Statistic, Typography } from 'antd'
import type { ReactNode } from 'react'

const { Text } = Typography

export interface QuickStatItem {
    key: string
    title: string
    icon: ReactNode
    color: string
    value: string | number
    suffix?: string
    description: string
}

interface QuickStatsProps {
    stats: QuickStatItem[]
}

const QuickStats: React.FC<QuickStatsProps> = ({ stats }) => {
    return (
        <Row gutter={[16, 16]}>
            {stats.map((stat) => (
                <Col xs={24} sm={12} md={6} key={stat.key}>
                    <Card bordered={false} hoverable>
                        <Statistic
                            title={
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ color: stat.color, fontSize: 18 }}>{stat.icon}</span>
                                    <span>{stat.title}</span>
                                </div>
                            }
                            value={stat.value}
                            suffix={stat.suffix}
                            valueStyle={{ color: stat.color }}
                        />
                        <div style={{ marginTop: 8 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                {stat.description}
                            </Text>
                        </div>
                    </Card>
                </Col>
            ))}
        </Row>
    )
}

export default QuickStats
