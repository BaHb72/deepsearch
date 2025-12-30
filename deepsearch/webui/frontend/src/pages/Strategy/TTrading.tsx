/**
 * 日内做T页面
 * 
 * 新布局:
 * - 分时图全宽显示
 * - 右侧抽屉: 监控列表
 * - 底部: 策略选择器 + 回测结果
 */
import React, { useState, useEffect, useCallback } from 'react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Button,
    Statistic,
    Space,
    message,
    Typography,
    Empty,
    Badge,
    Row,
    Col,
    Spin,
} from 'antd';
import {
    ReloadOutlined,
    ArrowUpOutlined,
    ArrowDownOutlined,
    MenuOutlined,
} from '@ant-design/icons';
import {
    strategyCenterAPI,
    TTradingSignal,
    IntradayAnalysis,
    DatasourceStatus,
    WatchlistItem,
    IntradayDataResponse,
} from '../../api/strategy-center';
import { timestampToBeijingTime } from '../../utils/timeFormat';
import TradingViewChart from '../../components/charts/TradingViewChart';
import DateRangeSelector from '../../components/charts/DateRangeSelector';
import {
    WatchlistDrawer,
    StrategySelector,
    BacktestResultPanel,
    BacktestResult,
    TradeRecord,
} from '../../components/strategy';

const { Text, Title } = Typography;

const TTrading: React.FC = () => {
    // 数据源状态
    const [datasourceStatus, setDatasourceStatus] = useState<DatasourceStatus | null>(null);

    // 监控列表
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
    const [selectedSymbol, setSelectedSymbol] = useState<string>('');
    const [selectedSymbolName, setSelectedSymbolName] = useState<string>('');

    // 分时数据
    const [intradayData, setIntradayData] = useState<IntradayDataResponse | null>(null);
    const [intradayLoading, setIntradayLoading] = useState(false);

    // 日期选择
    const [selectedDate, setSelectedDate] = useState<string>(() => {
        const today = new Date();
        return today.toISOString().split('T')[0];
    });

    // 分析结果
    const [analysis, setAnalysis] = useState<IntradayAnalysis | null>(null);
    const [analyzing, setAnalyzing] = useState(false);

    // 回测结果
    const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
    const [backtestLoading, setBacktestLoading] = useState(false);

    // 抽屉开关
    const [drawerOpen, setDrawerOpen] = useState(false);

    // 加载数据源状态
    const loadDatasourceStatus = useCallback(async () => {
        try {
            const status = await strategyCenterAPI.getDatasourceStatus();
            setDatasourceStatus(status);
        } catch (error) {
            console.error('Failed to load datasource status:', error);
        }
    }, []);

    // 加载监控列表
    const loadWatchlist = useCallback(async () => {
        try {
            const response = await strategyCenterAPI.getWatchlist();
            setWatchlist(response.items || []);
        } catch (error) {
            console.error('Failed to load watchlist:', error);
            setWatchlist([]);
        }
    }, []);

    // 初始化
    useEffect(() => {
        loadDatasourceStatus();
        loadWatchlist();
    }, [loadDatasourceStatus, loadWatchlist]);

    // 添加股票到监控列表
    const handleAddStock = useCallback(async (symbol: string, name: string) => {
        try {
            await strategyCenterAPI.addToWatchlist(symbol, name);
            await loadWatchlist();
            message.success(`已添加 ${name}`);
        } catch (error) {
            console.error('Failed to add stock:', error);
            message.error('添加失败');
        }
    }, [loadWatchlist]);

    // 从监控列表移除
    const handleRemoveStock = useCallback(async (symbol: string) => {
        try {
            await strategyCenterAPI.removeFromWatchlist(symbol);
            await loadWatchlist();
            message.success('已删除');
        } catch (error) {
            console.error('Failed to remove stock:', error);
            message.error('删除失败');
        }
    }, [loadWatchlist]);

    // 加载指定日期的分时数据
    const loadIntradayDataByDate = useCallback(async (symbol: string, date: string) => {
        if (!symbol) return;

        setIntradayLoading(true);
        try {
            const targetDate = new Date(date);
            const startOfDay = new Date(targetDate);
            startOfDay.setHours(9, 30, 0, 0);
            const endOfDay = new Date(targetDate);
            endOfDay.setHours(15, 0, 0, 0);

            const result = await strategyCenterAPI.getKLineData(
                symbol,
                '1m',
                startOfDay.getTime(),
                endOfDay.getTime()
            );

            if (result.bars && result.bars.length > 0) {
                const bars = result.bars.map(bar => ({
                    time: bar.time_str || timestampToBeijingTime(bar.timestamp),
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close,
                    volume: bar.volume,
                    date: bar.date || date,
                }));

                setIntradayData({
                    symbol,
                    bars,
                    current_price: bars[bars.length - 1]?.close || 0,
                    vwap: bars[0]?.open || 0,
                    signals: [],
                });
            } else {
                setIntradayData(null);
            }
        } catch (error) {
            console.error('Failed to load intraday data by date:', error);
            setIntradayData(null);
        } finally {
            setIntradayLoading(false);
        }
    }, []);

    // 快速分析 (点击股票时触发)
    const handleAnalyzeStock = useCallback(async (symbol: string) => {
        if (!symbol) {
            message.warning('请选择股票');
            return;
        }

        setAnalyzing(true);
        setSelectedSymbol(symbol);
        const stockName = watchlist.find(w => w.symbol === symbol)?.name || '';
        setSelectedSymbolName(stockName);
        setBacktestResult(null); // 清空之前的回测结果

        try {
            const [result, intradayResult] = await Promise.all([
                strategyCenterAPI.quickAnalyze(symbol),
                strategyCenterAPI.getIntradayData(symbol, 60),
            ]);

            setAnalysis(result.analysis);

            if (intradayResult.bars && intradayResult.bars.length > 0) {
                setIntradayData(intradayResult);
                // 更新选中日期为最新数据的日期
                const latestDate = intradayResult.bars[intradayResult.bars.length - 1]?.date;
                if (latestDate) {
                    setSelectedDate(latestDate);
                }
            }

            message.success(`${stockName} 分析完成`);
        } catch (error) {
            console.error('Failed to analyze:', error);
            message.error('分析失败');
        } finally {
            setAnalyzing(false);
        }
    }, [watchlist]);

    // 运行回测
    const handleRunBacktest = useCallback(async (strategies: string[]) => {
        if (!selectedSymbol) {
            message.warning('请先选择股票');
            return;
        }

        setBacktestLoading(true);
        try {
            // 模拟回测结果 (后续接入真实API)
            // TODO: 调用真实的回测API
            await new Promise(resolve => setTimeout(resolve, 1500));

            // 模拟生成回测结果
            const mockTrades: TradeRecord[] = [
                {
                    id: '1',
                    time: '09:45',
                    direction: 'buy',
                    price: 43.50,
                    profitPct: 0,
                    strategy: 'vwap_deviation',
                    reason: 'VWAP低吸: 偏离-1.8%',
                },
                {
                    id: '2',
                    time: '10:15',
                    direction: 'sell',
                    price: 44.20,
                    profitPct: 1.61,
                    strategy: 'opening_breakout',
                    reason: '冲高回落至开盘高点',
                },
                {
                    id: '3',
                    time: '13:30',
                    direction: 'buy',
                    price: 43.80,
                    profitPct: 0,
                    strategy: 'time_window',
                    reason: '下午主升段买入',
                },
                {
                    id: '4',
                    time: '14:30',
                    direction: 'sell',
                    price: 44.50,
                    profitPct: 1.60,
                    strategy: 'momentum_reversal',
                    reason: '超涨缩量反转',
                },
            ];

            const result: BacktestResult = {
                totalProfitPct: 2.35,
                winRate: 66.7,
                tradeCount: 4,
                winCount: 2,
                loseCount: 1,
                avgProfitLossRatio: 1.8,
                maxDrawdown: 0.5,
                trades: mockTrades,
            };

            setBacktestResult(result);
            message.success('回测完成');
        } catch (error) {
            console.error('Failed to run backtest:', error);
            message.error('回测失败');
        } finally {
            setBacktestLoading(false);
        }
    }, [selectedSymbol]);

    return (
        <PageContainer
            title="日内做T"
            subTitle={selectedSymbolName ? `${selectedSymbolName} (${selectedSymbol})` : '选择股票开始分析'}
            extra={
                <Space>
                    <Badge
                        status={datasourceStatus?.miniqmt_connected ? 'success' : 'error'}
                        text={datasourceStatus?.miniqmt_connected ? 'MiniQMT 已连接' : 'MiniQMT 未连接'}
                    />
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={() => {
                            loadDatasourceStatus();
                            loadWatchlist();
                            if (selectedSymbol) {
                                handleAnalyzeStock(selectedSymbol);
                            }
                        }}
                    >
                        刷新
                    </Button>
                    <Button
                        type="primary"
                        icon={<MenuOutlined />}
                        onClick={() => setDrawerOpen(true)}
                    >
                        监控列表 ({watchlist.length})
                    </Button>
                </Space>
            }
        >
            {/* 右侧抽屉 - 监控列表 */}
            <WatchlistDrawer
                watchlist={watchlist.map(w => ({
                    symbol: w.symbol,
                    name: w.name,
                    price: w.current_price,
                    change: w.change_pct,
                }))}
                selectedSymbol={selectedSymbol}
                onAdd={handleAddStock}
                onRemove={handleRemoveStock}
                onAnalyze={handleAnalyzeStock}
                open={drawerOpen}
                onOpenChange={setDrawerOpen}
            />

            {/* 主内容区 - 全宽 */}
            {selectedSymbol ? (
                <>
                    {/* 分时图 - 全宽 */}
                    <ProCard
                        title={
                            <Space>
                                <Text strong style={{ fontSize: 16 }}>{selectedSymbolName}</Text>
                                <Text type="secondary">{selectedSymbol}</Text>
                                {analysis && (
                                    <Text
                                        style={{
                                            color: analysis.price_deviation > 0 ? '#cf1322' : '#3f8600',
                                            marginLeft: 8,
                                        }}
                                    >
                                        ¥{analysis.current_price?.toFixed(2)}
                                        <span style={{ marginLeft: 4 }}>
                                            {analysis.price_deviation > 0 ? '+' : ''}
                                            {analysis.price_deviation?.toFixed(2)}%
                                        </span>
                                    </Text>
                                )}
                            </Space>
                        }
                        bordered
                        style={{ marginBottom: 16 }}
                        extra={
                            analysis && (
                                <Space size="large">
                                    <Statistic
                                        title="VWAP"
                                        value={analysis.vwap}
                                        precision={2}
                                        prefix="¥"
                                        valueStyle={{ fontSize: 14 }}
                                    />
                                    <Statistic
                                        title="量比"
                                        value={analysis.volume_ratio}
                                        precision={2}
                                        valueStyle={{ fontSize: 14 }}
                                    />
                                    <Statistic
                                        title="趋势"
                                        value={analysis.trend === 'up' ? '上涨' : analysis.trend === 'down' ? '下跌' : '震荡'}
                                        valueStyle={{
                                            fontSize: 14,
                                            color: analysis.trend === 'up' ? '#52c41a' : analysis.trend === 'down' ? '#ff4d4f' : '#faad14',
                                        }}
                                    />
                                </Space>
                            )
                        }
                    >
                        {(intradayLoading || analyzing) ? (
                            <div style={{
                                height: 350,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'rgba(0, 0, 0, 0.02)',
                                borderRadius: 8,
                            }}>
                                <Spin size="large" tip="加载中..." />
                            </div>
                        ) : !intradayData ? (
                            <div style={{
                                height: 350,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'rgba(0, 0, 0, 0.02)',
                                borderRadius: 8,
                            }}>
                                <Empty
                                    description={
                                        <span style={{ color: '#999' }}>
                                            暂无实时数据<br />
                                            <small>请检查数据源连接或等待交易时段</small>
                                        </span>
                                    }
                                />
                            </div>
                        ) : (
                            <>
                                <TradingViewChart
                                    lineData={(intradayData?.bars || []).map(b => ({
                                        time: b.time,
                                        value: b.close,
                                        date: b.date,
                                    }))}
                                    volumeData={(intradayData?.bars || []).map(b => ({
                                        time: b.time,
                                        value: b.volume,
                                        date: b.date,
                                    }))}
                                    vwapValue={intradayData?.vwap}
                                    basePrice={intradayData?.bars?.[0]?.open}
                                    height={350}
                                    chartType="line"
                                    signals={backtestResult?.trades?.map(t => ({
                                        time: t.time,
                                        type: t.direction,
                                        price: t.price,
                                        strategy: t.strategy,
                                        reason: t.reason,
                                    })) || []}
                                />
                                {/* 日期选择器 */}
                                <div style={{ marginTop: 12 }}>
                                    <DateRangeSelector
                                        symbol={selectedSymbol}
                                        selectedDate={selectedDate}
                                        onDateChange={(date) => {
                                            setSelectedDate(date);
                                            loadIntradayDataByDate(selectedSymbol, date);
                                        }}
                                        days={15}
                                        height={70}
                                    />
                                </div>
                            </>
                        )}
                    </ProCard>

                    {/* 策略选择器 */}
                    <StrategySelector
                        loading={backtestLoading}
                        onRunBacktest={handleRunBacktest}
                        disabled={!selectedSymbol || !intradayData}
                    />

                    {/* 回测结果 */}
                    <BacktestResultPanel
                        result={backtestResult || undefined}
                        loading={backtestLoading}
                        stockName={selectedSymbolName}
                        date={selectedDate}
                    />
                </>
            ) : (
                <ProCard bordered style={{ height: 500, marginTop: 60 }}>
                    <Empty
                        description={
                            <span>
                                点击右上角「监控列表」按钮<br />
                                添加股票并点击「分析」开始
                            </span>
                        }
                        style={{ marginTop: 150 }}
                    />
                </ProCard>
            )}
        </PageContainer>
    );
};

export default TTrading;
