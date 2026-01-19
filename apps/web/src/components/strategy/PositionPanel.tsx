/**
 * 持仓管理面板
 *
 * 功能：
 * - 标签页切换：全部持仓 / 底仓 / 做T仓
 * - 实时盈亏显示（逐日盯市）
 * - 做T仓自动识别（今日买入 = 做T仓）
 * - 信号推荐买入/卖出数量
 */
import React, { useState, useEffect, useCallback } from 'react';
import { ProCard } from '@ant-design/pro-components';
import {
    Table,
    Tabs,
    Tag,
    Space,
    Typography,
    Statistic,
    Button,
    Tooltip,
    Spin,
    Empty,
} from 'antd';
import {
    ArrowUpOutlined,
    ArrowDownOutlined,
    ReloadOutlined,
    ShoppingCartOutlined,
    DollarOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
    getPositionsWithPnl,
    getPositionsSummary,
    Position,
    PositionWithPnl,
    PositionsSummary,
} from '../../api/strategy-center';

const { Text } = Typography;

// 持仓类型
type PositionType = 'all' | 'base' | 'trading';

interface PositionPanelProps {
    symbol?: string;  // 当前选中的股票（用于高亮）
    onBuy?: (symbol: string, recommendQty: number) => void;  // 买入回调
    onSell?: (symbol: string, recommendQty: number) => void;  // 卖出回调
}

/**
 * 判断是否为做T仓（今日买入）
 */
const isTradingPosition = (position: Position | PositionWithPnl): boolean => {
    if (!position.last_buy_date) return false;
    const today = new Date().toISOString().split('T')[0];
    const lastBuyDate = position.last_buy_date.split('T')[0];
    return lastBuyDate === today;
};

/**
 * 持仓管理面板
 */
const PositionPanel: React.FC<PositionPanelProps> = ({
    symbol,
    onBuy,
    onSell,
}) => {
    const [activeTab, setActiveTab] = useState<PositionType>('all');
    const [positions, setPositions] = useState<PositionWithPnl[]>([]);
    const [summary, setSummary] = useState<PositionsSummary | null>(null);
    const [loading, setLoading] = useState(false);

    // 加载持仓数据
    const loadPositions = useCallback(async () => {
        setLoading(true);
        try {
            const [posData, summaryData] = await Promise.all([
                getPositionsWithPnl(),
                getPositionsSummary(),
            ]);
            setPositions(posData);
            setSummary(summaryData);
        } catch (error) {
            console.error('Failed to load positions:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    // 初始化加载
    useEffect(() => {
        loadPositions();
    }, [loadPositions]);

    // 根据标签过滤持仓
    const filteredPositions = positions.filter(pos => {
        if (activeTab === 'all') return true;
        if (activeTab === 'trading') return isTradingPosition(pos);
        if (activeTab === 'base') return !isTradingPosition(pos);
        return true;
    });

    // 计算推荐交易数量（做T仓位的10%）
    const getRecommendQty = (pos: PositionWithPnl): number => {
        return Math.max(100, Math.floor(pos.quantity * 0.1 / 100) * 100);
    };

    // 表格列定义
    const columns: ColumnsType<PositionWithPnl> = [
        {
            title: '股票',
            dataIndex: 'symbol',
            key: 'symbol',
            width: 120,
            render: (text, record) => (
                <Space direction="vertical" size={0}>
                    <Text strong style={{
                        color: text === symbol ? '#1890ff' : undefined
                    }}>
                        {text}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        {isTradingPosition(record) ? (
                            <Tag color="orange" style={{ margin: 0 }}>做T</Tag>
                        ) : (
                            <Tag color="blue" style={{ margin: 0 }}>底仓</Tag>
                        )}
                    </Text>
                </Space>
            ),
        },
        {
            title: '持仓',
            key: 'quantity',
            width: 100,
            render: (_, record) => (
                <Space direction="vertical" size={0}>
                    <Text>{record.quantity}股</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        可卖: {record.available_qty}
                    </Text>
                </Space>
            ),
        },
        {
            title: '成本/现价',
            key: 'price',
            width: 110,
            render: (_, record) => (
                <Space direction="vertical" size={0}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        成本: ¥{record.cost_price.toFixed(2)}
                    </Text>
                    <Text style={{
                        color: record.current_price >= record.cost_price ? '#52c41a' : '#ff4d4f'
                    }}>
                        ¥{record.current_price?.toFixed(2) || '--'}
                    </Text>
                </Space>
            ),
        },
        {
            title: '盈亏',
            key: 'pnl',
            width: 120,
            render: (_, record) => {
                const pnl = record.unrealized_pnl || 0;
                const ratio = record.pnl_ratio || 0;
                const isProfit = pnl >= 0;
                return (
                    <Space direction="vertical" size={0}>
                        <Text style={{ color: isProfit ? '#52c41a' : '#ff4d4f' }}>
                            {isProfit ? '+' : ''}{pnl.toFixed(2)}
                        </Text>
                        <Text style={{
                            fontSize: 12,
                            color: isProfit ? '#52c41a' : '#ff4d4f'
                        }}>
                            {isProfit ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                            {Math.abs(ratio).toFixed(2)}%
                        </Text>
                    </Space>
                );
            },
        },
        {
            title: '操作',
            key: 'action',
            width: 140,
            render: (_, record) => {
                const recommendQty = getRecommendQty(record);
                return (
                    <Space>
                        <Tooltip title={`推荐买入 ${recommendQty} 股`}>
                            <Button
                                type="link"
                                size="small"
                                icon={<ShoppingCartOutlined />}
                                onClick={() => onBuy?.(record.symbol, recommendQty)}
                                style={{ color: '#52c41a', padding: 0 }}
                            >
                                买{recommendQty}
                            </Button>
                        </Tooltip>
                        <Tooltip title={`推荐卖出 ${Math.min(recommendQty, record.available_qty)} 股`}>
                            <Button
                                type="link"
                                size="small"
                                icon={<DollarOutlined />}
                                onClick={() => onSell?.(record.symbol, Math.min(recommendQty, record.available_qty))}
                                disabled={record.available_qty === 0}
                                style={{ color: '#ff4d4f', padding: 0 }}
                            >
                                卖{Math.min(recommendQty, record.available_qty)}
                            </Button>
                        </Tooltip>
                    </Space>
                );
            },
        },
    ];

    // 计算各类型持仓统计
    const basePositions = positions.filter(p => !isTradingPosition(p));
    const tradingPositions = positions.filter(p => isTradingPosition(p));

    return (
        <ProCard
            title="持仓管理"
            bordered
            extra={
                <Space>
                    {summary && (
                        <>
                            <Statistic
                                title="总市值"
                                value={summary.total_market_value}
                                precision={0}
                                prefix="¥"
                                valueStyle={{ fontSize: 14 }}
                            />
                            <Statistic
                                title="总盈亏"
                                value={summary.total_unrealized_pnl}
                                precision={2}
                                prefix={summary.total_unrealized_pnl >= 0 ? '+¥' : '¥'}
                                valueStyle={{
                                    fontSize: 14,
                                    color: summary.total_unrealized_pnl >= 0 ? '#52c41a' : '#ff4d4f'
                                }}
                            />
                        </>
                    )}
                    <Button
                        icon={<ReloadOutlined />}
                        size="small"
                        onClick={loadPositions}
                        loading={loading}
                    >
                        刷新
                    </Button>
                </Space>
            }
            style={{ marginBottom: 16 }}
        >
            <Tabs
                activeKey={activeTab}
                onChange={(key) => setActiveTab(key as PositionType)}
                items={[
                    {
                        key: 'all',
                        label: `全部 (${positions.length})`,
                    },
                    {
                        key: 'base',
                        label: `底仓 (${basePositions.length})`,
                    },
                    {
                        key: 'trading',
                        label: `做T仓 (${tradingPositions.length})`,
                    },
                ]}
            />

            {loading ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                    <Spin tip="加载中..." />
                </div>
            ) : filteredPositions.length === 0 ? (
                <Empty description="暂无持仓" />
            ) : (
                <Table
                    columns={columns}
                    dataSource={filteredPositions}
                    rowKey="id"
                    size="small"
                    pagination={false}
                    scroll={{ y: 300 }}
                    rowClassName={(record) =>
                        record.symbol === symbol ? 'ant-table-row-selected' : ''
                    }
                />
            )}
        </ProCard>
    );
};

export default PositionPanel;
