import React, { useEffect, useState } from 'react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Form,
    Select,
    InputNumber,
    DatePicker,
    Button,
    Row,
    Col,
    Statistic,
    Table,
    message,
    Typography,
    Divider,
} from 'antd';
import { Line } from '@ant-design/charts';
import { PlayCircleOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
    strategyAPI,
    StrategyType,
    BacktestResult,
    BacktestTrade,
    BacktestOptimizationResult,
    BacktestOptimizationRankedItem,
} from '../../api/strategy';
import {
    StrategyParamForm,
    buildDefaultParamValues,
    fromGeneratorStrategyParams,
    toPayloadParamMap,
    type UnifiedParamDef,
    type UnifiedParamMap,
} from '../../components/strategy';

const { Text } = Typography;
const { RangePicker } = DatePicker;

interface GeneratorFormValues {
    strategy_type: string;
    symbols: string[];
    dateRange: [dayjs.Dayjs, dayjs.Dayjs];
    initial_capital: number;
    commission: number;
    params?: UnifiedParamMap;
}

const StrategyGenerator: React.FC = () => {
    const [form] = Form.useForm();
    const [strategyTypes, setStrategyTypes] = useState<StrategyType[]>([]);
    const [selectedStrategy, setSelectedStrategy] = useState<StrategyType | null>(null);
    const [paramDefinitions, setParamDefinitions] = useState<Record<string, UnifiedParamDef>>({});
    const [paramValues, setParamValues] = useState<UnifiedParamMap>({});
    const [loading, setLoading] = useState(false);
    const [optimizeLoading, setOptimizeLoading] = useState(false);
    const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
    const [optimizationResult, setOptimizationResult] = useState<BacktestOptimizationResult | null>(
        null
    );

    // Fetch strategy types on mount
    useEffect(() => {
        const fetchTypes = async () => {
            try {
                const res = await strategyAPI.getStrategyTypes();
                setStrategyTypes(res.strategies || []);
            } catch {
                message.error('获取策略类型失败');
            }
        };
        fetchTypes();
    }, []);

    const handleStrategyChange = (value: string) => {
        const strategy = strategyTypes.find((item) => item.type === value);
        setSelectedStrategy(strategy || null);

        if (strategy) {
            const nextDefinitions = fromGeneratorStrategyParams(strategy.params);
            const defaults = buildDefaultParamValues(nextDefinitions);
            setParamDefinitions(nextDefinitions);
            setParamValues(defaults);
            form.setFieldsValue({ params: defaults });
            return;
        }

        setParamDefinitions({});
        setParamValues({});
        form.setFieldsValue({ params: {} });
    };

    const resolveStrategyParams = (params?: UnifiedParamMap) => {
        const resolvedParams = toPayloadParamMap(paramDefinitions, params || paramValues);
        const missingKeys = Object.entries(paramDefinitions)
            .filter(([key, def]) => {
                const resolved = resolvedParams[key];
                if (resolved === undefined) {
                    return true;
                }
                if (def.type === 'str' || def.type === 'select' || def.type === 'list') {
                    return String(resolved).trim() === '';
                }
                return false;
            })
            .map(([key]) => key);

        return { resolvedParams, missingKeys };
    };

    const buildOptimizationGrid = (resolvedParams: Record<string, unknown>) => {
        const numericKeys = Object.entries(resolvedParams)
            .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
            .map(([key]) => key)
            .slice(0, 3);

        const grid: Record<string, unknown[]> = {};
        for (const [key, value] of Object.entries(resolvedParams)) {
            if (!numericKeys.includes(key)) {
                grid[key] = [value];
                continue;
            }

            const numericValue = Number(value);
            const candidates = Number.isInteger(numericValue)
                ? [
                    Math.max(1, Math.round(numericValue * 0.8)),
                    Math.round(numericValue),
                    Math.max(1, Math.round(numericValue * 1.2)),
                ]
                : [
                    Number((numericValue * 0.8).toFixed(6)),
                    Number(numericValue.toFixed(6)),
                    Number((numericValue * 1.2).toFixed(6)),
                ];

            grid[key] = Array.from(new Set(candidates));
        }
        return grid;
    };

    const handleRunBacktest = async (values: GeneratorFormValues) => {
        setLoading(true);
        setBacktestResult(null);
        try {
            const { strategy_type, symbols, dateRange, initial_capital, commission, params } = values;
            const { resolvedParams, missingKeys } = resolveStrategyParams(params);

            if (missingKeys.length) {
                message.warning(`请完善策略参数：${missingKeys.join('、')}`);
                return;
            }

            // Format request
            const requestData = {
                strategy_type,
                symbols: Array.isArray(symbols) ? symbols : [symbols],
                start_date: dateRange[0].format('YYYY-MM-DD'),
                end_date: dateRange[1].format('YYYY-MM-DD'),
                initial_capital,
                timeframe: '1d' as const,
                adjust: 'qfq' as const,
                slippage: 0,
                enforce_a_share_rules: true,
                plot: false,
                commission,
                min_commission: 5,
                commission_exempt_min: false,
                stamp_tax_rate: 0.001,
                transfer_fee_rate: 0.00001,
                strategy_params: resolvedParams,
            };

            const result = await strategyAPI.runBacktest(requestData);
            setBacktestResult(result);
            message.success('回测完成');
        } catch (error: unknown) {
            console.error(error);
            const text = error instanceof Error ? error.message : '回测失败';
            message.error(text);
        } finally {
            setLoading(false);
        }
    };

    const handleRunOptimization = async () => {
        setOptimizeLoading(true);
        setOptimizationResult(null);
        try {
            const values = await form.validateFields();
            const {
                strategy_type,
                symbols,
                dateRange,
                initial_capital,
                commission,
                params,
            } = values as GeneratorFormValues;
            const { resolvedParams, missingKeys } = resolveStrategyParams(params);

            if (missingKeys.length) {
                message.warning(`请完善策略参数：${missingKeys.join('、')}`);
                return;
            }

            const optimizationPayload = {
                strategy_type,
                symbols: Array.isArray(symbols) ? symbols : [symbols],
                start_date: dateRange[0].format('YYYY-MM-DD'),
                end_date: dateRange[1].format('YYYY-MM-DD'),
                param_grid: buildOptimizationGrid(resolvedParams),
                metric: 'sharpe_ratio',
                initial_cash: initial_capital,
                timeframe: '1d' as const,
                adjust: 'qfq' as const,
                enforce_a_share_rules: true,
                top_n: 20,
                max_combinations: 256,
                commission,
                min_commission: 5,
                commission_exempt_min: false,
                stamp_tax_rate: 0.001,
                transfer_fee_rate: 0.00001,
                slippage: 0,
            };

            const optimizeResult = await strategyAPI.runBacktestOptimization(optimizationPayload, {
                pollIntervalMs: 1200,
                timeoutMs: 180000,
            });

            setOptimizationResult(optimizeResult);
            if (optimizeResult.status === 'failed') {
                message.error(optimizeResult.error || '参数优化失败');
            } else {
                message.success('参数优化完成');
            }
        } catch (error: unknown) {
            console.error(error);
            const text = error instanceof Error ? error.message : '参数优化失败';
            message.error(text);
        } finally {
            setOptimizeLoading(false);
        }
    };

    // Chart config
    const chartConfig = backtestResult ? {
        data: backtestResult.equity_curve,
        xField: 'date',
        yField: 'equity',
        xAxis: {
            title: { text: '日期' },
            type: 'time',
        },
        yAxis: {
            title: { text: '资金权益' },
        },
        tooltip: {
            formatter: (datum: { equity: number }) => {
                return { name: '权益', value: datum.equity.toFixed(2) };
            },
        },
        smooth: true,
        point: {
            size: 0,
            shape: 'circle',
        },
    } : {};

    // Trades table columns
    const tradeColumns = [
        { title: '日期', dataIndex: 'date', key: 'date' },
        { title: '标的', dataIndex: 'symbol', key: 'symbol' },
        {
            title: '操作',
            dataIndex: 'side',
            key: 'side',
            render: (text: string) => (
                <Text type={text === 'BUY' ? 'danger' : 'success'} strong>
                    {text === 'BUY' ? '买入' : '卖出'}
                </Text>
            )
        },
        { title: '价格', dataIndex: 'price', key: 'price', render: (val: number) => val.toFixed(2) },
        { title: '数量', dataIndex: 'size', key: 'size' },
        { title: '佣金', dataIndex: 'fee', key: 'fee', render: (val: number) => val.toFixed(2) },
        {
            title: '盈亏',
            dataIndex: 'pnl',
            key: 'pnl',
            render: (val: number) => {
                if (!val) return '-';
                const color = val > 0 ? '#cf1322' : val < 0 ? '#3f8600' : 'inherit';
                return <span style={{ color }}>{val.toFixed(2)}</span>;
            }
        },
    ];

    const optimizationColumns = [
        { title: '排名', dataIndex: 'rank', key: 'rank', width: 72 },
        {
            title: '评分',
            dataIndex: 'score',
            key: 'score',
            width: 120,
            render: (val: number) => Number(val || 0).toFixed(4),
        },
        {
            title: '总收益率(%)',
            dataIndex: 'total_return',
            key: 'total_return',
            width: 140,
            render: (val?: number) => ((val || 0) * 100).toFixed(2),
        },
        {
            title: '夏普',
            dataIndex: 'sharpe_ratio',
            key: 'sharpe_ratio',
            width: 100,
            render: (val?: number) => Number(val || 0).toFixed(3),
        },
        {
            title: '最大回撤(%)',
            dataIndex: 'max_drawdown',
            key: 'max_drawdown',
            width: 140,
            render: (val?: number) => ((val || 0) * 100).toFixed(2),
        },
        {
            title: '参数',
            dataIndex: 'params',
            key: 'params',
            render: (params: Record<string, unknown>) => (
                <Text code>{JSON.stringify(params, null, 0)}</Text>
            ),
        },
    ];

    return (
        <PageContainer header={{ title: '策略生成器', ghost: true }}>
            <ProCard ghost gutter={[16, 16]}>
                {/* Configuration Panel */}
                <ProCard colSpan={8} title="策略配置" bordered headerBordered>
                    <Form
                        form={form}
                        layout="vertical"
                        onFinish={handleRunBacktest}
                        initialValues={{
                            initial_capital: 100000,
                            commission: 0.0003,
                            dateRange: [dayjs().subtract(1, 'year'), dayjs()],
                            symbols: ['000001']
                        }}
                    >
                        <Form.Item name="strategy_type" label="策略类型" rules={[{ required: true }]}>
                            <Select
                                placeholder="选择策略"
                                onChange={handleStrategyChange}
                                options={strategyTypes.map(s => ({ label: s.name, value: s.type }))}
                            />
                        </Form.Item>

                        <Form.Item name="symbols" label="标的代码" rules={[{ required: true }]} help="目前支持单只股票回测，请输入如 000001">
                            {/* Ideally a Search Select, simplified as Select tags or Input for now */}
                            <Select mode="tags" placeholder="输入股票代码" tokenSeparators={[',', ' ']} />
                        </Form.Item>

                        <Form.Item name="dateRange" label="回测区间" rules={[{ required: true }]}>
                            <RangePicker style={{ width: '100%' }} />
                        </Form.Item>

                        <Row gutter={16}>
                            <Col span={12}>
                                <Form.Item name="initial_capital" label="初始资金">
                                    <InputNumber style={{ width: '100%' }} min={1000} />
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item name="commission" label="佣金费率">
                                    <InputNumber style={{ width: '100%' }} min={0} step={0.0001} />
                                </Form.Item>
                            </Col>
                        </Row>

                        <Divider orientation="left">策略参数</Divider>

                        <StrategyParamForm
                            definitions={paramDefinitions}
                            value={paramValues}
                            onChange={(next) => {
                                setParamValues(next);
                                form.setFieldsValue({ params: next });
                            }}
                            emptyText={selectedStrategy ? '当前策略未声明可配置参数。' : '请先选择策略类型'}
                        />

                        <Form.Item style={{ marginTop: 24 }}>
                            <Row gutter={12}>
                                <Col span={12}>
                                    <Button
                                        type="primary"
                                        htmlType="submit"
                                        icon={<PlayCircleOutlined />}
                                        loading={loading}
                                        disabled={optimizeLoading}
                                        block
                                        size="large"
                                    >
                                        运行回测
                                    </Button>
                                </Col>
                                <Col span={12}>
                                    <Button
                                        onClick={handleRunOptimization}
                                        loading={optimizeLoading}
                                        disabled={loading || !selectedStrategy}
                                        block
                                        size="large"
                                    >
                                        参数优化
                                    </Button>
                                </Col>
                            </Row>
                        </Form.Item>
                    </Form>
                </ProCard>

                {/* Results Panel */}
                <ProCard colSpan={16} ghost direction="column" gutter={[0, 16]}>

                    {/* Metrics Cards */}
                    {backtestResult && (
                        <ProCard gutter={16} ghost>
                            <ProCard bordered>
                                <Statistic
                                    title="总收益率"
                                    value={(backtestResult.metrics?.total_return ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: (backtestResult.metrics?.total_return ?? 0) >= 0 ? '#cf1322' : '#3f8600' }}
                                    prefix={(backtestResult.metrics?.total_return ?? 0) >= 0 ? <RiseOutlined /> : <FallOutlined />}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="年化收益"
                                    value={(backtestResult.metrics?.annual_return ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: (backtestResult.metrics?.annual_return ?? 0) >= 0 ? '#cf1322' : '#3f8600' }}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="最大回撤"
                                    value={(backtestResult.metrics?.max_drawdown ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: '#3f8600' }}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="夏普比率"
                                    value={backtestResult.metrics?.sharpe_ratio ?? 0}
                                    precision={2}
                                />
                            </ProCard>
                        </ProCard>
                    )}

                    {/* Equity Curve */}
                    <ProCard title="资金曲线" bordered headerBordered style={{ minHeight: 400 }}>
                        {backtestResult ? (
                            <Line {...chartConfig} />
                        ) : (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300, color: '#999' }}>
                                暂无回测数据，请运行策略
                            </div>
                        )}
                    </ProCard>

                    {optimizationResult && (
                        <ProCard title="参数优化结果" bordered headerBordered>
                            <Row gutter={16} style={{ marginBottom: 16 }}>
                                <Col span={6}>
                                    <Statistic
                                        title="最优评分"
                                        value={optimizationResult.best_score || 0}
                                        precision={4}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="组合总数"
                                        value={optimizationResult.combination_count || 0}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="已评估"
                                        value={optimizationResult.evaluated_count || 0}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="失败样本"
                                        value={optimizationResult.failed_count || 0}
                                    />
                                </Col>
                            </Row>
                            <div style={{ marginBottom: 12 }}>
                                <Text strong>最优参数：</Text>
                                <Text code>{JSON.stringify(optimizationResult.best_params || {})}</Text>
                            </div>
                            <Table
                                dataSource={optimizationResult.ranked_results || []}
                                columns={optimizationColumns}
                                rowKey={(record: BacktestOptimizationRankedItem, index) =>
                                    `${record.rank || index}-${record.score || 0}`
                                }
                                size="small"
                                pagination={{ pageSize: 10 }}
                                scroll={{ x: 980 }}
                            />
                        </ProCard>
                    )}

                    {/* Trade List */}
                    <ProCard title="交易明细" bordered headerBordered>
                        <Table
                            dataSource={backtestResult?.trades || []}
                            columns={tradeColumns}
                            rowKey={(record: BacktestTrade, index) => `${record.trade_id || record.order_id || index}`}
                            size="small"
                            pagination={{ pageSize: 10 }}
                        />
                    </ProCard>
                </ProCard>
            </ProCard>
        </PageContainer>
    );
};

export default StrategyGenerator;
