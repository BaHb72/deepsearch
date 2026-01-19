/**
 * 分时图组件 (ECharts 实现)
 *
 * 替代原 TradingView Lightweight Charts 版本
 * 原版已备份至 strategy/TradingViewIntradayChart.tsx
 */
import React, { useMemo, useRef, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

export interface TradingViewChartProps {
    /** 分时数据 (用于分时图) */
    lineData?: Array<{
        time: string;
        value: number;
        date?: string;
    }>;
    /** K线数据 (用于K线图) */
    candleData?: Array<{
        time: string;
        open: number;
        high: number;
        low: number;
        close: number;
        date?: string;
    }>;
    /** 成交量数据 */
    volumeData?: Array<{
        time: string;
        value: number;
        color?: string;
        date?: string;
    }>;
    /** 图表类型 */
    chartType?: 'line' | 'candlestick';
    /** 图表高度 */
    height?: number;
    /** 基准价格（用于计算右侧 Y 轴的涨跌幅百分比） */
    basePrice?: number;
    /** 买卖信号 (支持策略区分) */
    signals?: Array<{
        time: string;
        type: 'buy' | 'sell';
        price: number;
        strategy?: string;
        reason?: string;
    }>;
    /**
     * 加载更多历史数据的回调
     */
    onLoadMore?: (earliestTimeStr: string, earliestDate?: string) => Promise<{
        lineData?: Array<{ time: string; value: number; date?: string }>;
        volumeData?: Array<{ time: string; value: number; date?: string }>;
    } | null>;
    /** 是否正在加载更多数据 */
    loadingMore?: boolean;
}

// 策略颜色映射
const STRATEGY_COLORS: Record<string, { buy: string; sell: string }> = {
    'vwap_deviation': { buy: '#1890ff', sell: '#722ed1' },
    'opening_breakout': { buy: '#52c41a', sell: '#fa8c16' },
    'time_window': { buy: '#13c2c2', sell: '#eb2f96' },
    'momentum_reversal': { buy: '#2f54eb', sell: '#f5222d' },
    'ma_deviation': { buy: '#36cfc9', sell: '#ff7a45' },
    'support_resistance': { buy: '#73d13d', sell: '#ff4d4f' },
    'grid': { buy: '#40a9ff', sell: '#ff85c0' },
    'volume_price': { buy: '#95de64', sell: '#ffa940' },
    'default': { buy: '#26a69a', sell: '#ef5350' },
};

const TradingViewChart: React.FC<TradingViewChartProps> = ({
    lineData = [],
    candleData = [],
    volumeData = [],
    chartType = 'line',
    height = 400,
    basePrice,
    signals = [],
    onLoadMore,
    loadingMore = false,
}) => {
    const chartRef = useRef<ReactECharts>(null);
    const isLoadingMoreRef = useRef(false);

    // 计算有效基准价格
    const effectiveBasePrice = useMemo(() => {
        if (basePrice && basePrice > 0) return basePrice;
        if (lineData.length > 0) return lineData[0].value;
        if (candleData.length > 0) return candleData[0].open;
        return 0;
    }, [basePrice, lineData, candleData]);

    // 处理时间标签 (支持多日期)
    const { times, dateLabels, dateSeparatorIndices } = useMemo(() => {
        const source = lineData.length > 0 ? lineData : candleData;
        const times: string[] = [];
        const dateLabels: (string | undefined)[] = [];
        const dateSeparatorIndices: number[] = [];
        let lastDate: string | undefined;

        source.forEach((d, index) => {
            const label = d.date ? `${d.date.slice(5)} ${d.time}` : d.time;
            times.push(label);
            dateLabels.push(d.date);

            if (d.date && lastDate && d.date !== lastDate) {
                dateSeparatorIndices.push(index);
            }
            lastDate = d.date;
        });

        return { times, dateLabels, dateSeparatorIndices };
    }, [lineData, candleData]);

    // 价格数据
    const prices = useMemo(() => {
        if (chartType === 'line') {
            return lineData.map(d => d.value);
        }
        return candleData.map(d => d.close);
    }, [lineData, candleData, chartType]);

    // 计算累计均价线 (VWAP-like)
    const avgPrices = useMemo(() => {
        if (lineData.length === 0 || volumeData.length === 0) return [];

        let totalVol = 0;
        let totalAmt = 0;
        return lineData.map((d, i) => {
            const vol = volumeData[i]?.value || 1;
            totalVol += vol;
            totalAmt += d.value * vol;
            return totalVol === 0 ? d.value : totalAmt / totalVol;
        });
    }, [lineData, volumeData]);

    // 成交量数据 (带颜色)
    const volumeBars = useMemo(() => {
        return volumeData.map((d, i) => {
            let color = '#26a69a';
            if (prices.length > 1 && i > 0) {
                color = prices[i] >= prices[i - 1] ? '#ef5350' : '#26a69a';
            }
            return {
                value: d.value,
                itemStyle: { color: d.color || color }
            };
        });
    }, [volumeData, prices]);

    // K线数据 (OHLC)
    const candleOHLC = useMemo(() => {
        if (chartType !== 'candlestick') return [];
        return candleData.map(d => [d.open, d.close, d.low, d.high]);
    }, [candleData, chartType]);

    // 买卖信号标记
    const signalMarkers = useMemo(() => {
        return signals.map(s => {
            const strategyKey = s.strategy || 'default';
            const colors = STRATEGY_COLORS[strategyKey] || STRATEGY_COLORS['default'];
            const color = s.type === 'buy' ? colors.buy : colors.sell;
            const strategyLabel = s.strategy ? s.strategy.split('_')[0].substring(0, 4).toUpperCase() : '';

            // 查找时间索引
            const timeIndex = times.findIndex(t => t.includes(s.time));

            return {
                coord: [timeIndex >= 0 ? timeIndex : s.time, s.price],
                symbol: s.type === 'buy' ? 'triangle' : 'triangle',
                symbolRotate: s.type === 'sell' ? 180 : 0,
                symbolSize: 14,
                symbolOffset: s.type === 'buy' ? [0, 10] : [0, -10],
                itemStyle: { color },
                label: {
                    show: true,
                    position: s.type === 'buy' ? 'bottom' : 'top',
                    formatter: s.type === 'buy'
                        ? `买${strategyLabel ? '·' + strategyLabel : ''}`
                        : `卖${strategyLabel ? '·' + strategyLabel : ''}`,
                    color,
                    fontSize: 10,
                    fontWeight: 'bold',
                },
            };
        });
    }, [signals, times]);

    // 日期分隔线
    const dateMarkLines = useMemo(() => {
        return dateSeparatorIndices.map(idx => ({
            xAxis: idx,
            lineStyle: { color: '#d9d9d9', type: 'dashed' as const, width: 1 },
            label: { show: false },
        }));
    }, [dateSeparatorIndices]);

    // 计算Y轴范围 (对称，保证基准价在中间)
    const { yMin, yMax, pctMin, pctMax } = useMemo(() => {
        if (prices.length === 0) return { yMin: 0, yMax: 100, pctMin: -10, pctMax: 10 };

        const maxP = Math.max(...prices);
        const minP = Math.min(...prices);
        const bp = effectiveBasePrice || prices[0];
        const maxDiff = Math.max(Math.abs(maxP - bp), Math.abs(minP - bp));
        const padding = maxDiff * 0.15;

        return {
            yMin: bp - maxDiff - padding,
            yMax: bp + maxDiff + padding,
            pctMin: ((-maxDiff - padding) / bp) * 100,
            pctMax: ((maxDiff + padding) / bp) * 100,
        };
    }, [prices, effectiveBasePrice]);

    // ECharts 配置
    const option: EChartsOption = useMemo(() => {
        if (prices.length === 0) return {};

        const bp = effectiveBasePrice || prices[0];

        return {
            animation: false,
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross',
                    label: { backgroundColor: '#6a7985' },
                },
                formatter: (params: any) => {
                    if (!Array.isArray(params) || params.length === 0) return '';
                    const idx = params[0].dataIndex;
                    const price = prices[idx];
                    const volume = volumeData[idx]?.value || 0;
                    const date = dateLabels[idx] || '';
                    const time = times[idx] || '';

                    const change = price - bp;
                    const changePct = bp ? (change / bp) * 100 : 0;
                    const color = change >= 0 ? '#ef5350' : '#26a69a';
                    const avgPrice = avgPrices[idx] || price;

                    return `
                        <div style="font-size:12px;">
                            <div style="margin-bottom:4px;color:#666;">${date ? date.slice(5) + ' ' : ''}${time.includes(' ') ? time.split(' ')[1] : time}</div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                                <span style="color:#666;">价格</span>
                                <span style="color:${color};font-weight:bold;">${price.toFixed(2)}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                                <span style="color:#666;">涨跌额</span>
                                <span style="color:${color};">${change > 0 ? '+' : ''}${change.toFixed(2)}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                                <span style="color:#666;">涨跌幅</span>
                                <span style="color:${color};">${changePct > 0 ? '+' : ''}${changePct.toFixed(2)}%</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                                <span style="color:#666;">均价</span>
                                <span>${avgPrice.toFixed(2)}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;">
                                <span style="color:#666;">成交量</span>
                                <span>${volume}手</span>
                            </div>
                        </div>
                    `;
                },
            },
            axisPointer: {
                link: [{ xAxisIndex: 'all' }],
            },
            grid: [
                { left: 60, right: 60, top: 20, height: '60%' },
                { left: 60, right: 60, top: '78%', height: '16%' },
            ],
            xAxis: [
                {
                    type: 'category',
                    data: times,
                    boundaryGap: false,
                    axisLine: { lineStyle: { color: '#dfdfdf' } },
                    axisLabel: {
                        color: '#666',
                        fontSize: 11,
                        formatter: (_: string, index: number) => {
                            // 只显示关键时间点
                            if (index === 0) return '09:30';
                            if (index === times.length - 1) return '15:00';
                            // 约 1/4 和 3/4 位置显示
                            const quarter = Math.floor(times.length / 4);
                            if (index === quarter) return '10:30';
                            if (index === quarter * 2) return '11:30/13:00';
                            if (index === quarter * 3) return '14:00';
                            return '';
                        },
                    },
                    splitLine: { show: false },
                },
                {
                    type: 'category',
                    data: times,
                    gridIndex: 1,
                    axisLabel: { show: false },
                    axisTick: { show: false },
                    axisLine: { show: false },
                    splitLine: { show: false },
                },
            ],
            yAxis: [
                // 左侧价格轴
                {
                    type: 'value',
                    scale: true,
                    min: yMin,
                    max: yMax,
                    axisLine: { lineStyle: { color: '#dfdfdf' } },
                    axisLabel: {
                        color: (val: any) => {
                            const v = Number(val);
                            if (v > bp) return '#ef5350';
                            if (v < bp) return '#26a69a';
                            return '#333';
                        },
                        formatter: (val: number) => val.toFixed(2),
                    },
                    splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
                },
                // 右侧涨跌幅轴
                {
                    type: 'value',
                    position: 'right',
                    min: pctMin,
                    max: pctMax,
                    axisLine: { lineStyle: { color: '#dfdfdf' } },
                    axisLabel: {
                        color: (val: any) => {
                            const v = Number(val);
                            if (v > 0) return '#ef5350';
                            if (v < 0) return '#26a69a';
                            return '#333';
                        },
                        formatter: (val: number) => `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`,
                    },
                    splitLine: { show: false },
                },
                // 成交量轴
                {
                    type: 'value',
                    gridIndex: 1,
                    splitNumber: 2,
                    axisLabel: { show: false },
                    axisTick: { show: false },
                    axisLine: { show: false },
                    splitLine: { show: false },
                },
            ],
            series: [
                // 价格线 (或K线)
                chartType === 'candlestick' ? {
                    name: '价格',
                    type: 'candlestick',
                    data: candleOHLC,
                    itemStyle: {
                        color: '#ef5350',
                        color0: '#26a69a',
                        borderColor: '#ef5350',
                        borderColor0: '#26a69a',
                    },
                    markPoint: {
                        data: signalMarkers,
                    },
                    markLine: dateMarkLines.length > 0 ? {
                        silent: true,
                        symbol: 'none',
                        data: dateMarkLines,
                    } : undefined,
                } : {
                    name: '价格',
                    type: 'line',
                    data: prices,
                    symbol: 'none',
                    lineStyle: { width: 2, color: '#1890ff' },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(24, 144, 255, 0.2)' },
                                { offset: 1, color: 'rgba(24, 144, 255, 0.02)' },
                            ],
                        } as any,
                    },
                    markPoint: {
                        data: signalMarkers,
                    },
                    markLine: dateMarkLines.length > 0 ? {
                        silent: true,
                        symbol: 'none',
                        data: dateMarkLines,
                    } : undefined,
                },
                // 累计均价线 (黄色)
                ...(avgPrices.length > 0 ? [{
                    name: '均价',
                    type: 'line',
                    data: avgPrices,
                    symbol: 'none',
                    lineStyle: { width: 1, color: '#faad14' },
                }] : []),
                // 成交量
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 2,
                    data: volumeBars,
                    barWidth: '60%',
                },
            ] as any[], // Explicit cast to avoid complex union type errors
        };
    }, [
        prices, volumeBars, avgPrices, candleOHLC, times, dateLabels,
        effectiveBasePrice, yMin, yMax, pctMin, pctMax,
        chartType, signalMarkers, dateMarkLines, volumeData,
    ]);

    // 监听 dataZoom 实现动态加载
    useEffect(() => {
        if (!onLoadMore || !chartRef.current) return;

        const instance = chartRef.current.getEchartsInstance();
        if (!instance) return;

        const handleDataZoom = (params: any) => {
            if (isLoadingMoreRef.current || loadingMore) return;

            // 检查是否滚动到最左侧
            const start = params.start ?? params.batch?.[0]?.start ?? 0;
            if (start <= 2 && lineData.length > 0) {
                isLoadingMoreRef.current = true;
                const earliestTime = lineData[0].time;
                const earliestDate = lineData[0].date;

                onLoadMore(earliestTime, earliestDate).finally(() => {
                    isLoadingMoreRef.current = false;
                });
            }
        };

        instance.on('datazoom', handleDataZoom);
        return () => {
            instance.off('datazoom', handleDataZoom);
        };
    }, [onLoadMore, loadingMore, lineData]);

    // 无数据时显示占位
    if (lineData.length === 0 && candleData.length === 0) {
        return (
            <div
                style={{
                    height,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#999',
                    background: '#fafafa',
                    borderRadius: 8,
                }}
            >
                暂无数据
            </div>
        );
    }

    return (
        <ReactECharts
            ref={chartRef}
            option={option}
            style={{ height, width: '100%' }}
            opts={{ renderer: 'svg' }}
            notMerge={true}
        />
    );
};

export default TradingViewChart;
