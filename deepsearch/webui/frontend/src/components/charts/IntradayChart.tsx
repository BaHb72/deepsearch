/**
 * 分时图组件
 * 使用ECharts展示分时走势和买卖点标记
 */
import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { IntradayBar } from '@/api/strategy-center';

interface IntradayChartProps {
    bars: IntradayBar[];
    signals?: Array<{
        time: string;
        type: 'buy' | 'sell';
        price: number;
        reason?: string;
    }>;
    vwap?: number;
    height?: number;
    loading?: boolean;
}

const IntradayChart: React.FC<IntradayChartProps> = ({
    bars,
    signals = [],
    vwap,
    height = 300,
    loading = false,
}) => {
    const option = useMemo(() => {
        if (!bars || bars.length === 0) {
            return {};
        }

        const times = bars.map(b => b.time);
        const prices = bars.map(b => b.close);
        const volumes = bars.map(b => b.volume);
        const vwapLine = vwap ? bars.map(() => vwap) : [];

        // 买卖点标记
        const markPoints = signals.map(s => ({
            coord: [s.time, s.price],
            name: s.type === 'buy' ? '买' : '卖',
            value: s.type === 'buy' ? '▲' : '▼',
            symbol: s.type === 'buy' ? 'triangle' : 'triangle',
            symbolRotate: s.type === 'buy' ? 0 : 180,
            symbolSize: 16,
            itemStyle: {
                color: s.type === 'buy' ? '#52c41a' : '#ff4d4f',
            },
            label: {
                show: true,
                formatter: s.type === 'buy' ? '买' : '卖',
                color: '#fff',
                fontSize: 10,
            },
        }));

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross',
                },
                formatter: (params: any) => {
                    const priceData = params.find((p: any) => p.seriesName === '价格');
                    const volumeData = params.find((p: any) => p.seriesName === '成交量');
                    if (!priceData) return '';
                    return `
                        <div style="padding: 8px;">
                            <div style="font-weight: bold; margin-bottom: 4px;">${priceData.axisValue}</div>
                            <div>价格: ¥${priceData.value.toFixed(2)}</div>
                            ${volumeData ? `<div>成交量: ${(volumeData.value / 10000).toFixed(1)}万</div>` : ''}
                            ${vwap ? `<div>VWAP: ¥${vwap.toFixed(2)}</div>` : ''}
                        </div>
                    `;
                },
            },
            grid: [
                { left: 60, right: 20, top: 30, height: '55%' },
                { left: 60, right: 20, top: '72%', height: '18%' },
            ],
            xAxis: [
                {
                    type: 'category',
                    data: times,
                    axisLine: { lineStyle: { color: '#999' } },
                    axisLabel: { color: '#666', fontSize: 11 },
                    splitLine: { show: false },
                },
                {
                    type: 'category',
                    data: times,
                    gridIndex: 1,
                    axisLine: { lineStyle: { color: '#999' } },
                    axisLabel: { show: false },
                    splitLine: { show: false },
                },
            ],
            yAxis: [
                {
                    type: 'value',
                    scale: true,
                    axisLine: { lineStyle: { color: '#999' } },
                    axisLabel: {
                        color: '#666',
                        fontSize: 11,
                        formatter: (val: number) => `¥${val.toFixed(2)}`,
                    },
                    splitLine: { lineStyle: { color: '#f0f0f0' } },
                },
                {
                    type: 'value',
                    gridIndex: 1,
                    axisLine: { lineStyle: { color: '#999' } },
                    axisLabel: { show: false },
                    splitLine: { show: false },
                },
            ],
            series: [
                {
                    name: '价格',
                    type: 'line',
                    data: prices,
                    smooth: true,
                    symbol: 'none',
                    lineStyle: {
                        width: 2,
                        color: '#1890ff',
                    },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                                { offset: 1, color: 'rgba(24, 144, 255, 0.05)' },
                            ],
                        },
                    },
                    markPoint: {
                        data: markPoints,
                    },
                },
                ...(vwapLine.length > 0 ? [{
                    name: 'VWAP',
                    type: 'line',
                    data: vwapLine,
                    symbol: 'none',
                    lineStyle: {
                        width: 1,
                        color: '#faad14',
                        type: 'dashed',
                    },
                }] : []),
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: (params: any) => {
                            const idx = params.dataIndex;
                            if (idx === 0) return '#52c41a';
                            return prices[idx] >= prices[idx - 1] ? '#ff4d4f' : '#52c41a';
                        },
                    },
                },
            ],
        };
    }, [bars, signals, vwap]);

    if (!bars || bars.length === 0) {
        return (
            <div style={{
                height,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#999',
                background: '#fafafa',
                borderRadius: 8,
            }}>
                暂无分时数据
            </div>
        );
    }

    return (
        <ReactECharts
            option={option}
            style={{ height }}
            showLoading={loading}
            opts={{ renderer: 'svg' }}
        />
    );
};

export default IntradayChart;
