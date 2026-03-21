/**
 * 回测结果组件
 *
 * 显示策略回测的收益、胜率、交易记录
 */
import React from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Empty, Typography, Space } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, TrophyOutlined, SwapOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Text } = Typography;

export interface TradeRecord {
    id: string;
    time: string;
    direction: 'buy' | 'sell';
    price: number;
    quantity?: number;
    profit?: number;
    profitPct?: number;
    strategy: string;
    reason: string;
}

export interface BlockedRecord {
    id: string;
    time: string;
    direction: 'buy' | 'sell';
    strategy: string;
    reasonCode: string;
    reason: string;
}

export interface BlockedSummaryItem {
    code: string;
    label: string;
    count: number;
}

export interface BacktestResult {
    /** 总收益率 (%) */
    totalProfitPct: number;
    /** 胜率 (%) */
    winRate: number;
    /** 交易次数 */
    tradeCount: number;
    /** 盈利次数 */
    winCount: number;
    /** 亏损次数 */
    loseCount: number;
    /** 平均盈亏比 */
    avgProfitLossRatio: number;
    /** 最大回撤 (%) */
    maxDrawdown: number;
    /** 交易记录 */
    trades: TradeRecord[];
    /** 未成交约束记录 */
    blockedEvents?: BlockedRecord[];
    /** 未成交约束统计 */
    blockedSummary?: Record<string, number>;
    /** 未成交约束统计（中文聚合） */
    blockedSummaryZh?: Record<string, number>;
    /** 未成交约束统计（结构化条目） */
    blockedSummaryItems?: BlockedSummaryItem[];
}

interface BacktestResultPanelProps {
    /** 回测结果 */
    result?: BacktestResult;
    /** 是否正在加载 */
    loading?: boolean;
    /** 股票名称 */
    stockName?: string;
    /** 日期 */
    date?: string;
}

const BacktestResultPanel: React.FC<BacktestResultPanelProps> = ({
    result,
    loading = false,
    stockName,
    date,
}) => {
    const summaryItems: BlockedSummaryItem[] = React.useMemo(() => {
        if (result?.blockedSummaryItems && result.blockedSummaryItems.length > 0) {
            return [...result.blockedSummaryItems].sort((a, b) => b.count - a.count);
        }
        if (result?.blockedSummaryZh && Object.keys(result.blockedSummaryZh).length > 0) {
            return Object.entries(result.blockedSummaryZh)
                .map(([label, count]) => ({
                    code: label,
                    label,
                    count,
                }))
                .sort((a, b) => b.count - a.count);
        }
        if (result?.blockedSummary && Object.keys(result.blockedSummary).length > 0) {
            return Object.entries(result.blockedSummary)
                .map(([code, count]) => ({
                    code,
                    label: code,
                    count,
                }))
                .sort((a, b) => b.count - a.count);
        }
        return [];
    }, [result]);

    // 表格列配置 - 合理的列宽分配
    const columns: ColumnsType<TradeRecord> = [
        {
            title: '时间',
            dataIndex: 'time',
            key: 'time',
            width: 70,
            align: 'center',
        },
        {
            title: '方向',
            dataIndex: 'direction',
            key: 'direction',
            width: 65,
            align: 'center',
            render: (dir: string) => (
                <Tag color={dir === 'buy' ? 'green' : 'red'}>
                    {dir === 'buy' ? '买入' : '卖出'}
                </Tag>
            ),
        },
        {
            title: '价格',
            dataIndex: 'price',
            key: 'price',
            width: 85,
            align: 'right',
            render: (price: number) => `¥${price.toFixed(2)}`,
        },
        {
            title: '收益',
            dataIndex: 'profitPct',
            key: 'profitPct',
            width: 75,
            align: 'right',
            render: (pct: number | undefined) => {
                if (pct === undefined) return '-';
                const color = pct >= 0 ? '#cf1322' : '#3f8600';
                return (
                    <Text style={{ color }}>
                        {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                    </Text>
                );
            },
        },
        {
            title: '策略',
            dataIndex: 'strategy',
            key: 'strategy',
            width: 120,
            render: (strategy: string) => <Tag>{strategy}</Tag>,
        },
        {
            title: '信号原因',
            dataIndex: 'reason',
            key: 'reason',
            // 不设置width，自动填充剩余空间
        },
    ];

    const blockedColumns: ColumnsType<BlockedRecord> = [
        {
            title: '时间',
            dataIndex: 'time',
            key: 'time',
            width: 70,
            align: 'center',
        },
        {
            title: '方向',
            dataIndex: 'direction',
            key: 'direction',
            width: 65,
            align: 'center',
            render: (dir: string) => (
                <Tag color={dir === 'buy' ? 'green' : 'red'}>
                    {dir === 'buy' ? '买入' : '卖出'}
                </Tag>
            ),
        },
        {
            title: '策略',
            dataIndex: 'strategy',
            key: 'strategy',
            width: 120,
            render: (strategy: string) => <Tag>{strategy}</Tag>,
        },
        {
            title: '约束编码',
            dataIndex: 'reasonCode',
            key: 'reasonCode',
            width: 140,
            render: (reasonCode: string) => <Tag color="orange">{reasonCode}</Tag>,
        },
        {
            title: '未成交原因',
            dataIndex: 'reason',
            key: 'reason',
        },
    ];

    if (!result && !loading) {
        return (
            <Card
                size="small"
                style={{ marginTop: 12 }}
                styles={{ body: { padding: '24px 16px' } }}
            >
                <Empty
                    description="选择策略并点击「开始回测」查看结果"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
            </Card>
        );
    }

    return (
        <Card
            size="small"
            title={
                <Space>
                    <TrophyOutlined />
                    <Text strong>回测结果</Text>
                    {stockName && date && (
                        <Text type="secondary">({stockName} · {date})</Text>
                    )}
                </Space>
            }
            loading={loading}
            style={{ marginTop: 12 }}
        >
            {result && (
                <>
                    {/* 统计卡片 - 增加列间距 */}
                    <Row gutter={[32, 16]} style={{ marginBottom: 16 }}>
                        <Col span={4}>
                            <Statistic
                                title="总收益"
                                value={result.totalProfitPct}
                                precision={2}
                                valueStyle={{
                                    color: result.totalProfitPct >= 0 ? '#cf1322' : '#3f8600',
                                    fontSize: 20,
                                }}
                                prefix={result.totalProfitPct >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                                suffix="%"
                            />
                        </Col>
                        <Col span={4}>
                            <Statistic
                                title="胜率"
                                value={result.winRate}
                                precision={1}
                                valueStyle={{
                                    color: result.winRate >= 50 ? '#cf1322' : '#8c8c8c',
                                    fontSize: 20,
                                }}
                                suffix="%"
                            />
                        </Col>
                        <Col span={4}>
                            <Statistic
                                title="交易次数"
                                value={result.tradeCount}
                                valueStyle={{ fontSize: 20 }}
                                prefix={<SwapOutlined />}
                            />
                        </Col>
                        <Col span={4}>
                            <Statistic
                                title="盈/亏"
                                value={result.winCount}
                                valueStyle={{ fontSize: 20 }}
                                suffix={<Text type="secondary"> / {result.loseCount}</Text>}
                            />
                        </Col>
                        <Col span={4}>
                            <Statistic
                                title="盈亏比"
                                value={result.avgProfitLossRatio}
                                precision={2}
                                valueStyle={{ fontSize: 20 }}
                            />
                        </Col>
                        <Col span={4}>
                            <Statistic
                                title="最大回撤"
                                value={result.maxDrawdown}
                                precision={2}
                                valueStyle={{
                                    color: '#3f8600',
                                    fontSize: 20,
                                }}
                                prefix={<ArrowDownOutlined />}
                                suffix="%"
                            />
                        </Col>
                    </Row>

                    {/* 交易记录表 - 固定表格布局 */}
                    <Table
                        columns={columns}
                        dataSource={result.trades}
                        rowKey="id"
                        size="small"
                        pagination={false}
                        scroll={{ y: 200 }}
                        tableLayout="fixed"
                    />

                    {(summaryItems.length > 0 || result.blockedEvents?.length) ? (
                        <div style={{ marginTop: 16 }}>
                            <Text strong style={{ display: 'block', marginBottom: 8 }}>
                                未成交约束
                            </Text>
                            {summaryItems.length > 0 ? (
                                <Space size={[8, 8]} wrap style={{ marginBottom: 8 }}>
                                    {summaryItems.map((item) => (
                                        <Tag key={item.code} color="orange">
                                            {item.label}: {item.count}
                                        </Tag>
                                    ))}
                                </Space>
                            ) : null}
                            <Table
                                columns={blockedColumns}
                                dataSource={result.blockedEvents || []}
                                rowKey="id"
                                size="small"
                                pagination={false}
                                scroll={{ y: 160 }}
                                tableLayout="fixed"
                            />
                        </div>
                    ) : null}
                </>
            )}
        </Card>
    );
};

export default BacktestResultPanel;
