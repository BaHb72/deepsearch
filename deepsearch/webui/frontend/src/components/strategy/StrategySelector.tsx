/**
 * 策略选择器组件
 * 
 * 允许用户选择要应用的日内做T策略
 */
import React, { useState } from 'react';
import { Card, Checkbox, Button, Space, Row, Col, Tooltip, Spin, Typography } from 'antd';
import { PlayCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

// 可用策略列表
const AVAILABLE_STRATEGIES = [
    {
        key: 'vwap_deviation',
        name: 'VWAP偏离',
        description: '价格偏离成交量加权均价时买入/卖出',
        category: '均值回归',
    },
    {
        key: 'opening_breakout',
        name: '开盘突破',
        description: '突破开盘30分钟高低点顺势操作',
        category: '趋势跟随',
    },
    {
        key: 'time_window',
        name: '时间窗口',
        description: '根据A股时间规律在特定时段操作',
        category: '时间策略',
    },
    {
        key: 'momentum_reversal',
        name: '动量反转',
        description: '短期超涨超跌后的反转机会',
        category: '反转策略',
    },
    {
        key: 'ma_deviation',
        name: '均线偏离',
        description: '价格偏离分时均线时买入/卖出',
        category: '均值回归',
    },
    {
        key: 'support_resistance',
        name: '支撑阻力',
        description: '在支撑位买入、阻力位卖出',
        category: '技术分析',
    },
    {
        key: 'grid',
        name: '网格交易',
        description: '预设价格网格自动高抛低吸',
        category: '量化策略',
    },
    {
        key: 'volume_price',
        name: '量价背离',
        description: '量价关系异常时判断反转',
        category: '技术分析',
    },
];

interface StrategySelectorProps {
    /** 是否正在回测 */
    loading?: boolean;
    /** 回测回调 */
    onRunBacktest: (strategies: string[]) => void;
    /** 是否禁用（未选择股票或日期） */
    disabled?: boolean;
}

const StrategySelector: React.FC<StrategySelectorProps> = ({
    loading = false,
    onRunBacktest,
    disabled = false,
}) => {
    const [selectedStrategies, setSelectedStrategies] = useState<string[]>([
        'vwap_deviation',
        'opening_breakout',
        'momentum_reversal',
    ]);

    const handleChange = (key: string, checked: boolean) => {
        if (checked) {
            setSelectedStrategies([...selectedStrategies, key]);
        } else {
            setSelectedStrategies(selectedStrategies.filter(k => k !== key));
        }
    };

    const handleSelectAll = () => {
        setSelectedStrategies(AVAILABLE_STRATEGIES.map(s => s.key));
    };

    const handleClearAll = () => {
        setSelectedStrategies([]);
    };

    const handleRunBacktest = () => {
        if (selectedStrategies.length === 0) {
            return;
        }
        onRunBacktest(selectedStrategies);
    };

    // 按类别分组
    const categories = [...new Set(AVAILABLE_STRATEGIES.map(s => s.category))];

    return (
        <Card
            size="small"
            title={
                <Space>
                    <Text strong>策略选择</Text>
                    <Text type="secondary">({selectedStrategies.length}/{AVAILABLE_STRATEGIES.length})</Text>
                </Space>
            }
            extra={
                <Space>
                    <Button size="small" onClick={handleSelectAll}>全选</Button>
                    <Button size="small" onClick={handleClearAll}>清空</Button>
                    <Button
                        type="primary"
                        size="small"
                        icon={loading ? <Spin size="small" /> : <PlayCircleOutlined />}
                        onClick={handleRunBacktest}
                        disabled={disabled || selectedStrategies.length === 0 || loading}
                    >
                        开始回测
                    </Button>
                </Space>
            }
            style={{ marginTop: 12 }}
            bodyStyle={{ padding: '12px 16px' }}
        >
            <Row gutter={[16, 8]}>
                {AVAILABLE_STRATEGIES.map(strategy => (
                    <Col key={strategy.key} xs={12} sm={8} md={6} lg={4} xl={3}>
                        <Checkbox
                            checked={selectedStrategies.includes(strategy.key)}
                            onChange={(e) => handleChange(strategy.key, e.target.checked)}
                            disabled={loading}
                        >
                            <Tooltip title={strategy.description}>
                                <Space size={4}>
                                    {strategy.name}
                                    <InfoCircleOutlined style={{ color: '#999', fontSize: 12 }} />
                                </Space>
                            </Tooltip>
                        </Checkbox>
                    </Col>
                ))}
            </Row>
        </Card>
    );
};

export default StrategySelector;
