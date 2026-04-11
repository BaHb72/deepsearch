import React from 'react'
import { Empty, Progress, Space, Tag, Typography } from 'antd'

import type { ConceptPulseBoard, ConceptPulseLeader, IndexConceptPulseEvent } from '@/api/marketDataLive'

const { Text, Title } = Typography

interface ConceptPulseEventPanelProps {
    event?: IndexConceptPulseEvent | null
    loading?: boolean
}

const formatAmount = (value?: number | null) => {
    if (value == null) return '--'
    if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`
    if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)} 万`
    return value.toFixed(0)
}

const formatPct = (value?: number | null) => {
    if (value == null) return '--'
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

const scoreColor = (score: number) => {
    if (score >= 80) return '#16a34a'
    if (score >= 60) return '#2563eb'
    if (score >= 40) return '#d97706'
    return '#64748b'
}

const coverageColor = (score?: number | null) => {
    if (score == null) return 'default'
    if (score >= 80) return 'success'
    if (score >= 60) return 'processing'
    if (score >= 40) return 'warning'
    return 'default'
}

const qualityLevel = (score?: number | null) => {
    if (score == null) return '待评估'
    if (score >= 85) return 'A+'
    if (score >= 70) return 'A'
    if (score >= 55) return 'B'
    return 'C'
}

const renderLeader = (leader?: ConceptPulseLeader | null) => {
    if (!leader) {
        return <Text type="secondary">当前没有足够的数据对板块内个股进行质量评分。</Text>
    }

    return (
        <div
            style={{
                background: 'linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)',
                border: '1px solid #dbeafe',
                borderRadius: 14,
                padding: 16,
            }}
        >
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Space align="center" wrap>
                    <Title level={5} style={{ margin: 0 }}>{leader.name}</Title>
                    <Text type="secondary">{leader.symbol}</Text>
                    <Tag color={leader.change_pct >= 0 ? 'red' : 'blue'}>
                        {formatPct(leader.change_pct)}
                    </Tag>
                    <Tag color="processing">质量 {qualityLevel(leader.quality_score)}</Tag>
                    <Tag color={coverageColor(leader.confidence_score)}>
                        置信度 {leader.confidence_score.toFixed(0)}
                    </Tag>
                </Space>

                <Space size={24} wrap>
                    <div>
                        <Text type="secondary">最新价</Text>
                        <div style={{ fontWeight: 700, fontSize: 18 }}>{leader.last_price.toFixed(2)}</div>
                    </div>
                    <div>
                        <Text type="secondary">成交额</Text>
                        <div style={{ fontWeight: 700, fontSize: 18 }}>{formatAmount(leader.amount)}</div>
                    </div>
                    <div>
                        <Text type="secondary">主力净流入占比</Text>
                        <div style={{ fontWeight: 700, fontSize: 18 }}>{formatPct(leader.main_net_inflow_pct)}</div>
                    </div>
                </Space>

                <div>
                    <Text strong>综合质量 {leader.quality_score.toFixed(1)}</Text>
                    <Progress percent={Math.round(leader.quality_score)} strokeColor={scoreColor(leader.quality_score)} showInfo={false} />
                </div>
                <div>
                    <Text type="secondary">技术面 {leader.technical_score.toFixed(1)}</Text>
                    <Progress percent={Math.round(leader.technical_score)} strokeColor="#2563eb" showInfo={false} size="small" />
                    <Text type="secondary">资金面 {leader.capital_score.toFixed(1)}</Text>
                    <Progress percent={Math.round(leader.capital_score)} strokeColor="#16a34a" showInfo={false} size="small" />
                    <Text type="secondary">基本面 {leader.fundamental_score.toFixed(1)}</Text>
                    <Progress percent={Math.round(leader.fundamental_score)} strokeColor="#d97706" showInfo={false} size="small" />
                </div>

                <Space wrap size={[8, 8]}>
                    <Tag color={coverageColor(leader.technical_coverage)}>
                        技术覆盖 {leader.technical_coverage.toFixed(0)}
                    </Tag>
                    <Tag color={coverageColor(leader.capital_coverage)}>
                        资金覆盖 {leader.capital_coverage.toFixed(0)}
                    </Tag>
                    <Tag color={coverageColor(leader.fundamental_coverage)}>
                        基本面覆盖 {leader.fundamental_coverage.toFixed(0)}
                    </Tag>
                </Space>

                <Space wrap size={[16, 8]}>
                    <Text type="secondary">5日收益 {formatPct(leader.return_5d)}</Text>
                    <Text type="secondary">20日收益 {formatPct(leader.return_20d)}</Text>
                    <Text type="secondary">近5日净流入天数 {leader.recent_positive_days ?? '--'}</Text>
                    <Text type="secondary">ROE 类指标 {formatPct(leader.roe_like)}</Text>
                    <Text type="secondary">利润率 {formatPct(leader.profit_margin)}</Text>
                    <Text type="secondary">资产负债率 {leader.debt_ratio == null ? '--' : `${(leader.debt_ratio * 100).toFixed(1)}%`}</Text>
                    <Text type="secondary">站上 MA20 {leader.above_ma20 ? '是' : '否'}</Text>
                </Space>

                <div>
                    <Text strong>入选理由</Text>
                    <Space wrap size={[8, 8]} style={{ display: 'flex', marginTop: 8 }}>
                        {leader.selection_reasons.map((reason) => (
                            <Tag key={reason} color="blue">{reason}</Tag>
                        ))}
                    </Space>
                </div>

                <div>
                    <Text strong>风险提示</Text>
                    <Space wrap size={[8, 8]} style={{ display: 'flex', marginTop: 8 }}>
                        {leader.risk_flags.length
                            ? leader.risk_flags.map((risk) => (
                                <Tag key={risk} color="orange">{risk}</Tag>
                            ))
                            : <Tag color="success">当前未识别出明显短板</Tag>}
                    </Space>
                </div>
            </Space>
        </div>
    )
}

const renderCandidateStrip = (board: ConceptPulseBoard) => {
    const extraCandidates = board.candidates.slice(1)
    if (!extraCandidates.length) return null
    return (
        <Space wrap size={[8, 8]} style={{ marginTop: 10 }}>
            <Text type="secondary">次优候选</Text>
            {extraCandidates.map((candidate) => (
                <Tag key={candidate.symbol}>
                    {candidate.name} {candidate.quality_score.toFixed(1)} / {candidate.confidence_score.toFixed(0)}
                </Tag>
            ))}
        </Space>
    )
}

const ConceptPulseEventPanel: React.FC<ConceptPulseEventPanelProps> = ({
    event,
    loading = false,
}) => {
    if (!event) {
        return (
            <Empty
                description={loading ? '正在加载启动事件' : '当前运行期内还没有识别到新的概念启动事件'}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
        )
    }

    return (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div
                style={{
                    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                    borderRadius: 16,
                    padding: 18,
                    color: '#f8fafc',
                }}
            >
                <Space direction="vertical" size={6}>
                    <Text style={{ color: 'rgba(248,250,252,0.72)' }}>启动时间 {event.time}</Text>
                    <Title level={4} style={{ margin: 0, color: '#f8fafc' }}>
                        {event.label}
                    </Title>
                    <Text style={{ color: 'rgba(248,250,252,0.80)' }}>
                        最强概念 {event.strongest_board}，当前共触发 {event.boards.length} 个概念。
                    </Text>
                </Space>
            </div>

            {event.boards.map((board) => (
                <div
                    key={board.board}
                    style={{
                        border: '1px solid #e2e8f0',
                        borderRadius: 16,
                        padding: 16,
                        background: '#fff',
                    }}
                >
                    <Space direction="vertical" size={12} style={{ width: '100%' }}>
                        <Space align="center" wrap>
                            <Title level={5} style={{ margin: 0 }}>{board.board}</Title>
                            <Tag color="processing">活跃度 {board.activity_score.toFixed(1)}</Tag>
                            <Tag color={board.lead_change != null && board.lead_change >= 0 ? 'red' : 'blue'}>
                                领涨 {formatPct(board.lead_change)}
                            </Tag>
                            <Text type="secondary">流速 {board.speed_per_min.toFixed(2)}/分</Text>
                            <Text type="secondary">流量 {formatAmount(board.amount_total)}</Text>
                        </Space>
                        {renderLeader(board.leader)}
                        {renderCandidateStrip(board)}
                    </Space>
                </div>
            ))}
        </Space>
    )
}

export default ConceptPulseEventPanel
