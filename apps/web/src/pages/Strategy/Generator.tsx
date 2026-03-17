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
import { strategyAPI, StrategyType, BacktestResult, BacktestTrade } from '../../api/strategy';
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
    const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);

    // Fetch strategy types on mount
    useEffect(() => {
        const fetchTypes = async () => {
            try {
                const res = await strategyAPI.getStrategyTypes();
                setStrategyTypes(res.strategies || []);
            } catch (error) {
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

    const handleRunBacktest = async (values: GeneratorFormValues) => {
        setLoading(true);
        setBacktestResult(null);
        try {
            const { strategy_type, symbols, dateRange, initial_capital, commission, params } = values;
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
                commission,
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
            dataIndex: 'action',
            key: 'action',
            render: (text: string) => (
                <Text type={text === 'BUY' ? 'danger' : 'success'} strong>
                    {text === 'BUY' ? '买入' : '卖出'}
                </Text>
            )
        },
        { title: '价格', dataIndex: 'price', key: 'price', render: (val: number) => val.toFixed(2) },
        { title: '数量', dataIndex: 'size', key: 'size' },
        { title: '佣金', dataIndex: 'commission', key: 'commission', render: (val: number) => val.toFixed(2) },
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
                            <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={loading} block size="large">
                                运行回测
                            </Button>
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
                                    value={(backtestResult.metrics?.totalReturn ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: (backtestResult.metrics?.totalReturn ?? 0) >= 0 ? '#cf1322' : '#3f8600' }}
                                    prefix={(backtestResult.metrics?.totalReturn ?? 0) >= 0 ? <RiseOutlined /> : <FallOutlined />}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="年化收益"
                                    value={(backtestResult.metrics?.annualizedReturn ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: (backtestResult.metrics?.annualizedReturn ?? 0) >= 0 ? '#cf1322' : '#3f8600' }}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="最大回撤"
                                    value={(backtestResult.metrics?.maxDrawdown ?? 0) * 100}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: '#3f8600' }}
                                />
                            </ProCard>
                            <ProCard bordered>
                                <Statistic
                                    title="夏普比率"
                                    value={backtestResult.metrics?.sharpeRatio ?? 0}
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

                    {/* Trade List */}
                    <ProCard title="交易明细" bordered headerBordered>
                        <Table
                            dataSource={backtestResult?.trades || []}
                            columns={tradeColumns}
                            rowKey={(record: BacktestTrade, index) => `${record.date}-${index}`}
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
