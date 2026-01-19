/**
 * 连接状态组件
 * 展示 MiniQMT/xtdata 连接状态
 */
import React, { useState, useEffect } from 'react'
import { Card, Spin, Tag, Button, Space, Typography } from 'antd'
import { ReloadOutlined, StockOutlined } from '@ant-design/icons'
import { statusApi } from '@/api/miniqmt'

const { Text } = Typography

export interface StatusSectionProps {
    /** 是否自动加载 */
    autoLoad?: boolean
    /** 是否显示为卡片模式 */
    cardMode?: boolean
}

export const StatusSection: React.FC<StatusSectionProps> = ({
    autoLoad = true,
    cardMode = true,
}) => {
    const [loading, setLoading] = useState(false)
    const [status, setStatus] = useState<Record<string, unknown> | null>(null)

    const fetchStatus = async () => {
        setLoading(true)
        try {
            const res = await statusApi.getXtdataStatus()
            if ((res as any).success) {
                setStatus(res as unknown as Record<string, unknown>)
            }
        } catch (err) {
            console.warn('获取状态失败', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (autoLoad) {
            fetchStatus()
        }
    }, [autoLoad])

    const content = (
        <Spin spinning={loading}>
            {status ? (
                <Space direction="vertical" size="small">
                    <div>
                        <Text strong>xtdata 状态: </Text>
                        <Tag color={status.connected ? 'green' : 'red'}>
                            {status.connected ? '已连接' : '未连接'}
                        </Tag>
                    </div>
                    <div>
                        <Text strong>SDK 可用: </Text>
                        <Tag color={status.xtdata_available ? 'green' : 'orange'}>
                            {status.xtdata_available ? '可用' : '不可用'}
                        </Tag>
                    </div>
                    {status.message ? (
                        <div>
                            <Text type="secondary">{String(status.message)}</Text>
                        </div>
                    ) : null}
                </Space>
            ) : (
                <Text type="secondary">加载中...</Text>
            )}
        </Spin>
    )

    if (!cardMode) {
        return content
    }

    return (
        <Card
            title={
                <Space>
                    <StockOutlined />
                    <span>连接状态</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchStatus} loading={loading} size="small">
                    刷新
                </Button>
            }
            size="small"
        >
            {content}
        </Card>
    )
}
