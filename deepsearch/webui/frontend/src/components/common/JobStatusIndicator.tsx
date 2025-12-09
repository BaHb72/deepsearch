import React, { useEffect, useState, useCallback } from 'react'
import { Button, Space, Popover, List, Typography, message } from 'antd'
import { CloudSyncOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons'
import dataSourceAPI, { IngestionJob } from '@/api/dataSource'

const { Text } = Typography

const JobStatusIndicator: React.FC = () => {
    const [jobs, setJobs] = useState<IngestionJob[]>([])
    const [loading, setLoading] = useState(false)
    const [polling, setPolling] = useState(true)

    const fetchJobs = useCallback(async () => {
        try {
            const res = await dataSourceAPI.listIngestionJobs({ limit: 5 })
            setJobs(res.jobs)
        } catch (error) {
            console.error('Failed to fetch jobs', error)
        }
    }, [])

    useEffect(() => {
        fetchJobs()
        const interval = setInterval(() => {
            if (polling) {
                fetchJobs()
            }
        }, 3000)
        return () => clearInterval(interval)
    }, [fetchJobs, polling])

    const activeJob = jobs.find(j => ['queued', 'running'].includes(j.status))

    const handleTrigger = async () => {
        setLoading(true)
        try {
            await dataSourceAPI.triggerPrefetchJob(true)
            message.success('已触发后台同步任务')
            fetchJobs()
        } catch (error) {
            message.error('触发失败')
        } finally {
            setLoading(false)
        }
    }

    const handleCancel = async (jobId: string) => {
        try {
            await dataSourceAPI.cancelJob(jobId)
            message.success('已取消任务')
            fetchJobs()
        } catch (error) {
            message.error('取消失败')
        }
    }

    const renderStatusIcon = (status: string) => {
        switch (status) {
            case 'running': return <LoadingOutlined spin style={{ color: '#1890ff' }} />
            case 'queued': return <CloudSyncOutlined style={{ color: '#faad14' }} />
            case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />
            case 'failed': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
            case 'cancelled': return <CloseCircleOutlined style={{ color: '#d9d9d9' }} />
            default: return <CloudSyncOutlined />
        }
    }

    const content = (
        <div style={{ width: 320 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, padding: '0 4px' }}>
                <Text strong>后台任务</Text>
                <Space>
                    <Button size="small" icon={<SyncOutlined />} onClick={fetchJobs} />
                    <Button size="small" type="primary" onClick={handleTrigger} loading={loading}>
                        立即同步
                    </Button>
                </Space>
            </div>
            <List
                size="small"
                dataSource={jobs}
                renderItem={item => (
                    <List.Item
                        actions={[
                            ['queued', 'running'].includes(item.status) && (
                                <a key="cancel" onClick={() => handleCancel(item.jobId)} style={{ fontSize: 12 }}>取消</a>
                            )
                        ]}
                    >
                        <List.Item.Meta
                            avatar={renderStatusIcon(item.status)}
                            title={<Text ellipsis style={{ maxWidth: 160, fontSize: 13 }}>{item.jobType}</Text>}
                            description={
                                <Space direction="vertical" size={0} style={{ fontSize: 12, lineHeight: 1.2 }}>
                                    <Text type="secondary">{item.status} • {item.recordCount || 0} records</Text>
                                    <Text type="secondary" style={{ fontSize: 10 }}>
                                        {item.startedAt ? new Date(item.startedAt).toLocaleTimeString() : '-'}
                                    </Text>
                                </Space>
                            }
                        />
                    </List.Item>
                )}
            />
        </div>
    )

    return (
        <Popover content={content} title={null} trigger="click" placement="bottomRight">
            <Button type="text" style={{ height: '100%' }}>
                <Space>
                    {activeJob ? (
                        <>
                            <LoadingOutlined />
                            <span style={{ fontSize: 12 }}>同步中...</span>
                        </>
                    ) : (
                        <CloudSyncOutlined />
                    )}
                </Space>
            </Button>
        </Popover>
    )
}

export default JobStatusIndicator
