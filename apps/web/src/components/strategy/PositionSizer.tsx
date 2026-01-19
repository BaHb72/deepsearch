/**
 * 仓位计算控制器
 *
 * 功能：
 * - 支持多种仓位计算算法（固定比例、ATR动态）
 * - 人工干预：可手动调整推荐数量
 * - 半自动模式：信号推荐 + 确认下单
 */
import React, { useState, useEffect, useCallback } from 'react';
import { ProCard } from '@ant-design/pro-components';
import {
    InputNumber,
    Select,
    Space,
    Button,
    Typography,
    Tooltip,
    Tag,
    Modal,
    message,
    Row,
    Col,
    Statistic,
    Switch,
} from 'antd';
import {
    CalculatorOutlined,
    SendOutlined,
    SettingOutlined,
    ThunderboltOutlined,
    ExclamationCircleOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

// 仓位计算模式
export type SizingMode = 'fixed' | 'atr' | 'kelly';

// 信号方向
export type SignalDirection = 'buy' | 'sell';

// 交易建议
export interface TradeRecommendation {
    symbol: string;
    direction: SignalDirection;
    quantity: number;
    price: number;
    reason: string;
    confidence: number;
    strategy?: string;
}

interface PositionSizerProps {
    // 当前持仓信息
    symbol: string;
    currentQty: number;       // 当前持仓数量
    availableQty: number;     // 可卖数量
    costPrice: number;        // 成本价
    currentPrice: number;     // 当前价格

    // 信号推荐
    recommendation?: TradeRecommendation;

    // 回调
    onExecute?: (direction: SignalDirection, quantity: number, price: number) => void;
    onSettingsChange?: (settings: PositionSizerSettings) => void;
}

export interface PositionSizerSettings {
    mode: SizingMode;
    fixedRatio: number;      // 固定比例（%）
    atrMultiplier: number;   // ATR 倍数
    riskAmount: number;      // 单笔风险金额
    autoMode: boolean;       // 是否自动执行
}

const DEFAULT_SETTINGS: PositionSizerSettings = {
    mode: 'fixed',
    fixedRatio: 10,
    atrMultiplier: 2,
    riskAmount: 1000,
    autoMode: false,
};

/**
 * 仓位计算控制器组件
 */
const PositionSizer: React.FC<PositionSizerProps> = ({
    symbol,
    currentQty,
    availableQty,
    costPrice: _costPrice,  // 保留用于未来盈亏计算
    currentPrice,
    recommendation,
    onExecute,
    onSettingsChange,
}) => {
    const [settings, setSettings] = useState<PositionSizerSettings>(DEFAULT_SETTINGS);
    const [manualQty, setManualQty] = useState<number>(100);
    const [showSettings, setShowSettings] = useState(false);
    const [confirmModalVisible, setConfirmModalVisible] = useState(false);
    const [pendingTrade, setPendingTrade] = useState<{
        direction: SignalDirection;
        quantity: number;
        price: number;
    } | null>(null);

    // 计算推荐仓位
    const calculateRecommendQty = useCallback((): number => {
        switch (settings.mode) {
            case 'fixed':
                // 固定比例：当前持仓 × 比例
                return Math.max(100, Math.floor(currentQty * settings.fixedRatio / 100 / 100) * 100);

            case 'atr':
                // ATR 动态：风险金额 ÷ (ATR × 倍数)
                // 简化：使用价格波动的2%作为ATR估算
                const estimatedATR = currentPrice * 0.02;
                const riskPerShare = estimatedATR * settings.atrMultiplier;
                const qty = Math.floor(settings.riskAmount / riskPerShare / 100) * 100;
                return Math.max(100, qty);

            case 'kelly':
                // 凯利公式：需要胜率和赔率
                // 简化版：假设胜率55%，赔率1.5
                const winRate = 0.55;
                const odds = 1.5;
                const kellyRatio = (winRate * odds - (1 - winRate)) / odds;
                const safeRatio = kellyRatio * 0.4;  // 使用40%凯利
                return Math.max(100, Math.floor(currentQty * safeRatio / 100) * 100);

            default:
                return 100;
        }
    }, [settings, currentQty, currentPrice]);

    // 当设置或持仓变化时更新推荐数量
    useEffect(() => {
        const qty = calculateRecommendQty();
        setManualQty(qty);
        onSettingsChange?.(settings);
    }, [settings, calculateRecommendQty, onSettingsChange]);

    // 使用信号推荐
    useEffect(() => {
        if (recommendation && recommendation.symbol === symbol) {
            setManualQty(recommendation.quantity);
        }
    }, [recommendation, symbol]);

    // 更新设置
    const updateSettings = (partial: Partial<PositionSizerSettings>) => {
        setSettings(prev => ({ ...prev, ...partial }));
    };

    // 执行交易（带确认）
    const handleExecute = (direction: SignalDirection) => {
        const price = currentPrice;
        const quantity = direction === 'sell'
            ? Math.min(manualQty, availableQty)
            : manualQty;

        if (direction === 'sell' && quantity > availableQty) {
            message.warning(`可卖数量不足，最多可卖 ${availableQty} 股`);
            return;
        }

        setPendingTrade({ direction, quantity, price });
        setConfirmModalVisible(true);
    };

    // 确认执行
    const confirmExecute = () => {
        if (pendingTrade) {
            onExecute?.(pendingTrade.direction, pendingTrade.quantity, pendingTrade.price);
            message.success(`${pendingTrade.direction === 'buy' ? '买入' : '卖出'} ${pendingTrade.quantity} 股`);
        }
        setConfirmModalVisible(false);
        setPendingTrade(null);
    };

    // 模式描述
    const getModeDescription = (mode: SizingMode): string => {
        switch (mode) {
            case 'fixed': return '固定比例';
            case 'atr': return 'ATR动态';
            case 'kelly': return '凯利公式';
            default: return '';
        }
    };

    return (
        <ProCard
            title={
                <Space>
                    <CalculatorOutlined />
                    <span>仓位控制</span>
                    <Tag color="blue">{getModeDescription(settings.mode)}</Tag>
                </Space>
            }
            bordered
            extra={
                <Space>
                    <Tooltip title="自动执行模式">
                        <Switch
                            size="small"
                            checked={settings.autoMode}
                            onChange={(checked) => updateSettings({ autoMode: checked })}
                            checkedChildren="自动"
                            unCheckedChildren="手动"
                        />
                    </Tooltip>
                    <Button
                        icon={<SettingOutlined />}
                        size="small"
                        onClick={() => setShowSettings(!showSettings)}
                    >
                        设置
                    </Button>
                </Space>
            }
            style={{ marginBottom: 16 }}
        >
            {/* 设置面板 */}
            {showSettings && (
                <div style={{ marginBottom: 16, padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <Row gutter={16}>
                        <Col span={8}>
                            <Text type="secondary">计算模式</Text>
                            <Select
                                value={settings.mode}
                                onChange={(mode) => updateSettings({ mode })}
                                style={{ width: '100%', marginTop: 4 }}
                                options={[
                                    { value: 'fixed', label: '固定比例 - 简单稳健' },
                                    { value: 'atr', label: 'ATR动态 - 波动自适应' },
                                    { value: 'kelly', label: '凯利公式 - 专业量化' },
                                ]}
                            />
                        </Col>
                        {settings.mode === 'fixed' && (
                            <Col span={8}>
                                <Text type="secondary">仓位比例 (%)</Text>
                                <InputNumber
                                    value={settings.fixedRatio}
                                    onChange={(v) => updateSettings({ fixedRatio: v || 10 })}
                                    min={1}
                                    max={50}
                                    style={{ width: '100%', marginTop: 4 }}
                                    addonAfter="%"
                                />
                            </Col>
                        )}
                        {settings.mode === 'atr' && (
                            <>
                                <Col span={4}>
                                    <Text type="secondary">ATR倍数</Text>
                                    <InputNumber
                                        value={settings.atrMultiplier}
                                        onChange={(v) => updateSettings({ atrMultiplier: v || 2 })}
                                        min={0.5}
                                        max={5}
                                        step={0.5}
                                        style={{ width: '100%', marginTop: 4 }}
                                    />
                                </Col>
                                <Col span={4}>
                                    <Text type="secondary">风险金额</Text>
                                    <InputNumber
                                        value={settings.riskAmount}
                                        onChange={(v) => updateSettings({ riskAmount: v || 1000 })}
                                        min={100}
                                        max={10000}
                                        step={100}
                                        style={{ width: '100%', marginTop: 4 }}
                                        prefix="¥"
                                    />
                                </Col>
                            </>
                        )}
                    </Row>
                </div>
            )}

            {/* 信号推荐 */}
            {recommendation && recommendation.symbol === symbol && (
                <div style={{
                    marginBottom: 16,
                    padding: 12,
                    background: recommendation.direction === 'buy' ? '#f6ffed' : '#fff1f0',
                    borderRadius: 8,
                    border: `1px solid ${recommendation.direction === 'buy' ? '#b7eb8f' : '#ffa39e'}`
                }}>
                    <Space>
                        <ThunderboltOutlined style={{
                            color: recommendation.direction === 'buy' ? '#52c41a' : '#ff4d4f'
                        }} />
                        <Text strong>
                            信号推荐：{recommendation.direction === 'buy' ? '买入' : '卖出'}
                            {recommendation.quantity} 股 @ ¥{recommendation.price.toFixed(2)}
                        </Text>
                        <Tag color={recommendation.direction === 'buy' ? 'green' : 'red'}>
                            {recommendation.strategy}
                        </Tag>
                        <Text type="secondary">
                            置信度: {(recommendation.confidence * 100).toFixed(0)}%
                        </Text>
                    </Space>
                    <div style={{ marginTop: 8 }}>
                        <Text type="secondary">{recommendation.reason}</Text>
                    </div>
                </div>
            )}

            {/* 交易控制 */}
            <Row gutter={16} align="middle">
                <Col span={6}>
                    <Statistic
                        title="推荐数量"
                        value={calculateRecommendQty()}
                        suffix="股"
                        valueStyle={{ fontSize: 16 }}
                    />
                </Col>
                <Col span={6}>
                    <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
                        实际数量（可修改）
                    </Text>
                    <InputNumber
                        value={manualQty}
                        onChange={(v) => setManualQty(v || 100)}
                        min={100}
                        step={100}
                        style={{ width: '100%' }}
                        addonAfter="股"
                    />
                </Col>
                <Col span={12}>
                    <Space size="middle">
                        <Button
                            type="primary"
                            icon={<SendOutlined />}
                            style={{ background: '#52c41a', borderColor: '#52c41a' }}
                            onClick={() => handleExecute('buy')}
                        >
                            买入 {manualQty} 股
                        </Button>
                        <Button
                            type="primary"
                            danger
                            icon={<SendOutlined />}
                            onClick={() => handleExecute('sell')}
                            disabled={availableQty === 0}
                        >
                            卖出 {Math.min(manualQty, availableQty)} 股
                        </Button>
                    </Space>
                </Col>
            </Row>

            {/* 确认弹窗 */}
            <Modal
                title={
                    <Space>
                        <ExclamationCircleOutlined style={{ color: '#faad14' }} />
                        确认交易
                    </Space>
                }
                open={confirmModalVisible}
                onOk={confirmExecute}
                onCancel={() => {
                    setConfirmModalVisible(false);
                    setPendingTrade(null);
                }}
                okText="确认执行"
                cancelText="取消"
            >
                {pendingTrade && (
                    <div>
                        <p>
                            <Text strong>股票：</Text> {symbol}
                        </p>
                        <p>
                            <Text strong>方向：</Text>
                            <Tag color={pendingTrade.direction === 'buy' ? 'green' : 'red'}>
                                {pendingTrade.direction === 'buy' ? '买入' : '卖出'}
                            </Tag>
                        </p>
                        <p>
                            <Text strong>数量：</Text> {pendingTrade.quantity} 股
                        </p>
                        <p>
                            <Text strong>价格：</Text> ¥{pendingTrade.price.toFixed(2)}
                        </p>
                        <p>
                            <Text strong>金额：</Text> ¥{(pendingTrade.quantity * pendingTrade.price).toFixed(2)}
                        </p>
                    </div>
                )}
            </Modal>
        </ProCard>
    );
};

export default PositionSizer;
