import React from 'react'
import { Alert, Card, Space, Tag, Typography } from 'antd'
import { formatDuration } from '../utils'

const { Text } = Typography

interface StatusCardProps {
    systemStatusDetails: {
        label: string
        tagColor: string
        valueColor: string
        alertType: 'success' | 'info' | 'warning' | 'error'
        alertDescription: string
    }
    uptime: number
    lastUpdated: number | null
}

const StatusCard: React.FC<StatusCardProps> = ({ systemStatusDetails, uptime, lastUpdated }) => {
    return (
        <Card title="系统状态" bordered={false}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Alert
                    message={
                        <Space>
                            <Text strong>系统运行状态：</Text>
                            <Tag color={systemStatusDetails.tagColor}>{systemStatusDetails.label}</Tag>
                        </Space>
                    }
                    description={systemStatusDetails.alertDescription}
                    type={systemStatusDetails.alertType}
                    showIcon
                />
                <Space split={<Text type="secondary">|</Text>}>
                    <Text type="secondary">
                        运行时长：
                        <Text strong>{formatDuration(uptime)}</Text>
                    </Text>
                    <Text type="secondary">
                        最后更新：
                        <Text type="secondary">
                            {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '--'}
                        </Text>
                    </Text>
                </Space>
            </Space>
        </Card>
    )
}

export default StatusCard
