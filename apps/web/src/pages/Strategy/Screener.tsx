import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Alert,
    Button,
    Descriptions,
    Empty,
    InputNumber,
    List,
    Select,
    Space,
    Spin,
    Table,
    Tag,
    Typography,
    message,
} from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import {
    batchScreenStocks,
    getComposites,
    getStockPools,
    getStrategies,
    quickScreenStocks,
    screenStocks,
    type BatchScreenRequestPayload,
    type CompositeStrategy,
    type QuickScreenRequestPayload,
    type ScreeningResponse,
    type StockPoolItem,
    type StrategyMeta,
} from '../../api/strategy-center';
import {
    PayloadPreview,
    StrategyParamForm,
    buildDefaultParamValues,
    fromStrategyCenterParams,
    toPayloadParamMap,
    type UnifiedParamMap,
} from '../../components/strategy';

const { Text } = Typography;

type ScreenerTemplateKey = 'batch_balanced' | 'quick_intraday' | 'composite_growth';

interface ScreenerTemplateViewModel {
    key: ScreenerTemplateKey;
    name: string;
    endpoint: string;
    description: string;
    capabilityNote: string;
    backendNote: string;
    payload: Record<string, unknown>;
}

const TEMPLATE_ORDER: ScreenerTemplateKey[] = [
    'batch_balanced',
    'quick_intraday',
    'composite_growth',
];

const pickFirstAvailable = (
    pools: StockPoolItem[],
    candidates: string[],
    fallback: string,
): string => {
    const poolIds = new Set(
        pools
            .filter((item) => item.enabled !== false)
            .map((item) => item.id),
    );
    for (const candidate of candidates) {
        if (poolIds.has(candidate)) {
            return candidate;
        }
    }
    if (poolIds.has(fallback)) {
        return fallback;
    }
    const first = pools.find((item) => item.enabled !== false);
    return first?.id ?? fallback;
};

const buildEqualWeights = (strategyIds: string[]): Record<string, number> => {
    if (!strategyIds.length) {
        return {};
    }
    const base = Number((1 / strategyIds.length).toFixed(4));
    const weights: Record<string, number> = {};
    let sum = 0;
    strategyIds.forEach((strategyId, index) => {
        if (index === strategyIds.length - 1) {
            weights[strategyId] = Number((1 - sum).toFixed(4));
        } else {
            weights[strategyId] = base;
            sum += base;
        }
    });
    return weights;
};

const directionTagColor = (direction: string): string => {
    if (direction === 'buy') {
        return 'red';
    }
    if (direction === 'sell') {
        return 'green';
    }
    return 'default';
};

const Screener: React.FC = () => {
    const [loadingMeta, setLoadingMeta] = useState<boolean>(false);
    const [running, setRunning] = useState<boolean>(false);
    const [lastError, setLastError] = useState<string>('');

    const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
    const [composites, setComposites] = useState<CompositeStrategy[]>([]);
    const [stockPools, setStockPools] = useState<StockPoolItem[]>([]);

    const [selectedTemplate, setSelectedTemplate] = useState<ScreenerTemplateKey>('batch_balanced');
    const [selectedQuickStrategyId, setSelectedQuickStrategyId] = useState<string>('');
    const [quickParamInputs, setQuickParamInputs] = useState<UnifiedParamMap>({});
    const [limit, setLimit] = useState<number>(50);
    const [signalThreshold, setSignalThreshold] = useState<number>(0.42);
    const [result, setResult] = useState<ScreeningResponse | null>(null);

    const loadMeta = useCallback(async () => {
        setLoadingMeta(true);
        setLastError('');
        try {
            const [strategyResp, compositeResp, poolsResp] = await Promise.all([
                getStrategies({ enabled_only: true }),
                getComposites(),
                getStockPools(),
            ]);

            const strategyList = Array.isArray(strategyResp?.strategies) ? strategyResp.strategies : [];
            const compositeList = Array.isArray(compositeResp?.composites) ? compositeResp.composites : [];
            const poolList = Array.isArray(poolsResp?.pools) ? poolsResp.pools : [];

            setStrategies(strategyList);
            setComposites(compositeList);
            setStockPools(poolList.filter((item) => item.enabled !== false));
        } catch (error) {
            const text = error instanceof Error ? error.message : String(error);
            setLastError(text);
            message.error(`加载选股配置失败：${text}`);
        } finally {
            setLoadingMeta(false);
        }
    }, []);

    useEffect(() => {
        loadMeta();
    }, [loadMeta]);

    const enabledStrategyIds = useMemo(() => {
        const enabled = strategies.filter((item) => item.enabled).map((item) => item.id);
        const fallback = strategies.map((item) => item.id);
        const picked = (enabled.length ? enabled : fallback).slice(0, 3);
        if (picked.length) {
            return picked;
        }
        return ['ma_crossover', 'mean_reversion_rsi', 'volume_price'];
    }, [strategies]);

    useEffect(() => {
        if (!enabledStrategyIds.length) {
            return;
        }
        setSelectedQuickStrategyId((prev) => {
            if (prev && enabledStrategyIds.includes(prev)) {
                return prev;
            }
            return enabledStrategyIds[0];
        });
    }, [enabledStrategyIds]);

    const quickStrategyId = selectedQuickStrategyId || enabledStrategyIds[0] || 'ma_crossover';
    const quickStrategyMeta = useMemo(
        () => strategies.find((item) => item.id === quickStrategyId),
        [strategies, quickStrategyId],
    );
    const quickParamDefinitions = useMemo(
        () => fromStrategyCenterParams(quickStrategyMeta?.params || {}),
        [quickStrategyMeta],
    );

    useEffect(() => {
        setQuickParamInputs(buildDefaultParamValues(quickParamDefinitions));
    }, [quickStrategyId, quickParamDefinitions]);

    const compositeId = composites[0]?.id ?? '';

    const batchStockPool = pickFirstAvailable(stockPools, ['hs300', 'zz500'], 'all');
    const quickStockPool = pickFirstAvailable(stockPools, ['custom', 'all'], 'custom');
    const compositeStockPool = pickFirstAvailable(stockPools, ['all', 'hs300'], 'all');

    const batchPayload: BatchScreenRequestPayload = useMemo(() => ({
        strategy_ids: enabledStrategyIds,
        weights: buildEqualWeights(enabledStrategyIds),
        stock_pool: [batchStockPool],
        signal_threshold: signalThreshold,
        limit,
    }), [enabledStrategyIds, batchStockPool, signalThreshold, limit]);

    const quickParamPayload = useMemo(
        () => toPayloadParamMap(quickParamDefinitions, quickParamInputs),
        [quickParamDefinitions, quickParamInputs],
    );

    const quickPayload: QuickScreenRequestPayload = useMemo(() => ({
        strategy_id: quickStrategyId,
        stock_pool: [quickStockPool],
        limit: Math.min(limit, 100),
        params: quickParamPayload,
    }), [quickStrategyId, quickStockPool, limit, quickParamPayload]);

    const compositePayload = useMemo(() => ({
        composite_id: compositeId,
        strategy_ids: [],
        stock_pool: [compositeStockPool],
        limit,
    }), [compositeId, compositeStockPool, limit]);

    const quickStrategyOptions = useMemo(
        () =>
            strategies.map((item) => ({
                label: `${item.name} (${item.id})`,
                value: item.id,
            })),
        [strategies],
    );

    const templateMap: Record<ScreenerTemplateKey, ScreenerTemplateViewModel> = useMemo(() => ({
        batch_balanced: {
            key: 'batch_balanced',
            name: '批量均衡',
            endpoint: 'POST /api/strategy-center/screener/batch',
            description: '多策略加权，适合日内批量初筛。',
            capabilityNote: '字段映射：strategy_ids / weights / stock_pool / signal_threshold / limit',
            backendNote: '后端已生效 strategy_ids、weights、stock_pool、signal_threshold、limit。',
            payload: batchPayload,
        },
        quick_intraday: {
            key: 'quick_intraday',
            name: '快速盘中',
            endpoint: 'POST /api/strategy-center/screener/quick',
            description: '单策略快速筛选，适合盘中快速复核。',
            capabilityNote: '字段映射：strategy_id / stock_pool / limit / params',
            backendNote: '后端已生效 strategy_id、stock_pool、limit、params（基于策略参数定义动态下发）。',
            payload: quickPayload as Record<string, unknown>,
        },
        composite_growth: {
            key: 'composite_growth',
            name: '组合增强',
            endpoint: 'POST /api/strategy-center/screener',
            description: '基于 composite_id 自动展开子策略与权重。',
            capabilityNote: '字段映射：composite_id / strategy_ids / stock_pool / limit',
            backendNote: 'composite_id 会读取 composites 配置，自动取 enabled 组件与权重。',
            payload: compositePayload,
        },
    }), [batchPayload, quickPayload, compositePayload]);

    const selectedConfig = templateMap[selectedTemplate];

    const handleRun = useCallback(async () => {
        setRunning(true);
        setLastError('');
        try {
            let resp: ScreeningResponse;
            if (selectedTemplate === 'batch_balanced') {
                resp = await batchScreenStocks(batchPayload);
            } else if (selectedTemplate === 'quick_intraday') {
                resp = await quickScreenStocks(quickPayload);
            } else {
                if (!compositeId) {
                    message.warning('当前没有可用组合策略，请先在策略组合页创建一个 composite。');
                    setRunning(false);
                    return;
                }
                resp = await screenStocks(compositePayload);
            }
            setResult(resp);
            message.success(`筛选完成：扫描 ${resp.total_scanned}，命中 ${resp.total_matched}`);
        } catch (error) {
            const text = error instanceof Error ? error.message : String(error);
            setLastError(text);
            message.error(`筛选失败：${text}`);
        } finally {
            setRunning(false);
        }
    }, [selectedTemplate, batchPayload, quickPayload, compositePayload, compositeId]);

    return (
        <PageContainer
            header={{
                title: '智能选股配置台',
                ghost: true,
            }}
        >
            <ProCard ghost direction="column" gutter={[16, 16]}>
                {lastError && <Alert type="error" showIcon message={lastError} />}

                <ProCard gutter={16}>
                    <ProCard
                        colSpan="28%"
                        title="M2 运行约束与股票池"
                        bordered
                        headerBordered
                    >
                        <Space direction="vertical" size={12} style={{ width: '100%' }}>
                            <Alert
                                type="info"
                                showIcon
                                message="数据源能力建议"
                                description="盘中实时优先 AmazingData；AkShare 主要用于日线与快照兜底。"
                            />
                            <Descriptions size="small" column={1} bordered>
                                <Descriptions.Item label="启用策略数">
                                    {strategies.length}
                                </Descriptions.Item>
                                <Descriptions.Item label="组合策略数">
                                    {composites.length}
                                </Descriptions.Item>
                                <Descriptions.Item label="可用股票池">
                                    {stockPools.length}
                                </Descriptions.Item>
                            </Descriptions>

                            <Table<StockPoolItem>
                                rowKey="id"
                                size="small"
                                pagination={false}
                                dataSource={stockPools}
                                columns={[
                                    {
                                        title: '股票池',
                                        dataIndex: 'name',
                                        key: 'name',
                                        render: (_: string, record) => (
                                            <Space direction="vertical" size={0}>
                                                <Text strong>{record.name}</Text>
                                                <Text type="secondary">{record.id}</Text>
                                            </Space>
                                        ),
                                    },
                                    {
                                        title: '数量',
                                        dataIndex: 'count',
                                        key: 'count',
                                        width: 90,
                                        render: (value?: number) => value ?? '-',
                                    },
                                ]}
                            />
                            <Button
                                icon={<ReloadOutlined />}
                                onClick={loadMeta}
                                loading={loadingMeta}
                            >
                                刷新配置元数据
                            </Button>
                        </Space>
                    </ProCard>

                    <ProCard
                        colSpan="72%"
                        title="M3 选股逻辑配置（已接后端）"
                        bordered
                        headerBordered
                    >
                        <ProCard split="vertical">
                            <ProCard colSpan="36%">
                                <List
                                    dataSource={TEMPLATE_ORDER.map((key) => templateMap[key])}
                                    renderItem={(item) => (
                                        <List.Item
                                            style={{
                                                cursor: 'pointer',
                                                border: item.key === selectedTemplate ? '1px solid #91caff' : '1px solid #f0f0f0',
                                                background: item.key === selectedTemplate ? '#f0f7ff' : '#fff',
                                                borderRadius: 8,
                                                paddingInline: 12,
                                                marginBottom: 10,
                                            }}
                                            onClick={() => setSelectedTemplate(item.key)}
                                        >
                                            <Space direction="vertical" size={2}>
                                                <Text strong>{item.name}</Text>
                                                <Text type="secondary">{item.endpoint}</Text>
                                                <Text type="secondary">{item.description}</Text>
                                            </Space>
                                        </List.Item>
                                    )}
                                />
                            </ProCard>

                            <ProCard colSpan="64%">
                                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                                    <Descriptions size="small" column={1} bordered>
                                        <Descriptions.Item label="当前入口">
                                            {selectedConfig.endpoint}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="字段映射">
                                            {selectedConfig.capabilityNote}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="后端状态">
                                            {selectedConfig.backendNote}
                                        </Descriptions.Item>
                                    </Descriptions>

                                    <Space size={16} wrap>
                                        <Space size={8}>
                                            <Text>limit</Text>
                                            <InputNumber
                                                min={1}
                                                max={500}
                                                value={limit}
                                                onChange={(value) => setLimit(value ?? 50)}
                                            />
                                        </Space>
                                        <Space size={8}>
                                            <Text>signal_threshold</Text>
                                            <InputNumber
                                                min={0}
                                                max={1}
                                                step={0.01}
                                                value={signalThreshold}
                                                onChange={(value) => setSignalThreshold(value ?? 0.42)}
                                                disabled={selectedTemplate !== 'batch_balanced'}
                                            />
                                        </Space>
                                        {selectedTemplate === 'quick_intraday' && (
                                            <Space size={8}>
                                                <Text>strategy</Text>
                                                <Select
                                                    style={{ minWidth: 260 }}
                                                    value={quickStrategyId}
                                                    options={quickStrategyOptions}
                                                    onChange={(value) => setSelectedQuickStrategyId(value)}
                                                    placeholder="选择 quick 策略"
                                                />
                                            </Space>
                                        )}
                                    </Space>

                                    <Alert
                                        type="success"
                                        showIcon
                                        message="参数已连通"
                                        description="batch.signal_threshold 与 quick.params 已进入后端筛选链路；quick.params 会参与简化技术信号计算。"
                                    />

                                    {selectedTemplate === 'quick_intraday' && (
                                        <ProCard
                                            size="small"
                                            title={`quick.params 动态表单 (${quickStrategyMeta?.name || quickStrategyId})`}
                                            bordered
                                        >
                                            <StrategyParamForm
                                                definitions={quickParamDefinitions}
                                                value={quickParamInputs}
                                                onChange={setQuickParamInputs}
                                                emptyText={
                                                    quickStrategyMeta
                                                        ? '当前策略未声明可配置参数。'
                                                        : '当前策略元信息不可用，无法渲染参数表单。'
                                                }
                                            />
                                        </ProCard>
                                    )}

                                    <PayloadPreview payload={selectedConfig.payload} maxHeight={300} />

                                    <Button
                                        type="primary"
                                        icon={<PlayCircleOutlined />}
                                        loading={running}
                                        onClick={handleRun}
                                    >
                                        执行当前模板
                                    </Button>
                                </Space>
                            </ProCard>
                        </ProCard>
                    </ProCard>
                </ProCard>

                <ProCard
                    title="筛选结果"
                    bordered
                    headerBordered
                >
                    {!result && !running && (
                        <Empty description="尚未执行筛选" />
                    )}

                    {running && (
                        <div style={{ textAlign: 'center', padding: 32 }}>
                            <Spin />
                        </div>
                    )}

                    {result && (
                        <Space direction="vertical" size={12} style={{ width: '100%' }}>
                            <Space wrap>
                                <Tag color="blue">request_id: {result.request_id}</Tag>
                                <Tag color="purple">scanned: {result.total_scanned}</Tag>
                                <Tag color="green">matched: {result.total_matched}</Tag>
                                <Tag color="gold">duration: {result.duration_ms}ms</Tag>
                            </Space>

                            <Table
                                rowKey={(record) => `${record.symbol}-${record.rank}`}
                                dataSource={result.results}
                                pagination={{ pageSize: 12 }}
                                columns={[
                                    {
                                        title: '#',
                                        dataIndex: 'rank',
                                        key: 'rank',
                                        width: 70,
                                    },
                                    {
                                        title: '代码',
                                        dataIndex: 'symbol',
                                        key: 'symbol',
                                        width: 140,
                                        render: (value: string) => <Text code>{value}</Text>,
                                    },
                                    {
                                        title: '名称',
                                        dataIndex: 'name',
                                        key: 'name',
                                        render: (value?: string) => value || '-',
                                    },
                                    {
                                        title: '综合评分',
                                        dataIndex: 'score',
                                        key: 'score',
                                        width: 120,
                                        render: (value: number) => {
                                            const color = value > 0 ? '#cf1322' : value < 0 ? '#389e0d' : '#595959';
                                            return <span style={{ color, fontWeight: 600 }}>{value.toFixed(4)}</span>;
                                        },
                                    },
                                    {
                                        title: '方向',
                                        dataIndex: 'direction',
                                        key: 'direction',
                                        width: 110,
                                        render: (value: string) => (
                                            <Tag color={directionTagColor(value)}>
                                                {value}
                                            </Tag>
                                        ),
                                    },
                                    {
                                        title: '组件信号',
                                        dataIndex: 'component_signals',
                                        key: 'component_signals',
                                        render: (value: Record<string, number>) => {
                                            const entries = Object.entries(value || {});
                                            if (!entries.length) {
                                                return '-';
                                            }
                                            return (
                                                <Space wrap size={[4, 4]}>
                                                    {entries.map(([id, score]) => (
                                                        <Tag key={id}>
                                                            {id}:{score.toFixed(3)}
                                                        </Tag>
                                                    ))}
                                                </Space>
                                            );
                                        },
                                    },
                                ]}
                            />
                        </Space>
                    )}
                </ProCard>
            </ProCard>
        </PageContainer>
    );
};

export default Screener;
