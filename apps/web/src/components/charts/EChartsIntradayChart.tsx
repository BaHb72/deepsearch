import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

interface IntradayBar {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    date: string;
}

interface EChartsIntradayChartProps {
    data: IntradayBar[];
    vwapValue?: number;
    basePrice?: number; // 昨日收盘价 (用于计算涨跌幅)
    height?: number;
}

const EChartsIntradayChart: React.FC<EChartsIntradayChartProps> = ({
    data,
    basePrice,
    height = 400,
}) => {

    const option = useMemo(() => {
        if (!data || data.length === 0) return {};

        const times = data.map(d => d.time);
        const prices = data.map(d => d.close);
        const volumes = data.map((d, i) => {
            const prevClose = i > 0 ? data[i - 1].close : (basePrice || d.open);
            return [i, d.volume, d.close >= prevClose ? 1 : -1]; // 1: Red, -1: Green
        });

        // 计算平均价 (VWAP similar logic per bar or cumulative? T-Trading usually has a yellow avg line)
        // Calculating approximate avg price line if not provided
        let totalVol = 0;
        let totalAmt = 0;
        const avgPrices = data.map(d => {
            totalVol += d.volume;
            totalAmt += d.close * d.volume; // Approximate amount
            return totalVol === 0 ? d.close : totalAmt / totalVol;
        });

        // 价格轴范围 (对称，保证 0% 在中间)
        const maxPrice = Math.max(...prices);
        const minPrice = Math.min(...prices);
        const bp = basePrice || prices[0];
        const maxDiff = Math.max(Math.abs(maxPrice - bp), Math.abs(minPrice - bp));
        const limitUp = bp + maxDiff * 1.1; // 留点余地
        const limitDown = bp - maxDiff * 1.1;

        return {
            animation: false,
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross',
                    label: {
                        backgroundColor: '#6a7985'
                    }
                },
                formatter (params: any[]) {
                    // Custom tooltip
                    if (!params || params.length === 0) return '';
                    const idx = params[0].dataIndex;
                    const item = data[idx];
                    const p = item.close;
                    const chg = bp ? (p - bp) : 0;
                    const pct = bp ? (chg / bp * 100) : 0;
                    const color = chg >= 0 ? '#ef5350' : '#26a69a';

                    return `
                        <div style="font-size:12px;">
                            <div>${item.date} ${item.time}</div>
                            <div style="color:${color}">Price: ${p.toFixed(2)}</div>
                            <div style="color:${color}">Chg: ${chg.toFixed(2)} (${pct.toFixed(2)}%)</div>
                            <div>Vol: ${item.volume}</div>
                        </div>
                    `;
                }
            },
            axisPointer: {
                link: { xAxisIndex: 'all' }
            },
            grid: [
                {
                    left: 50,
                    right: 50,
                    top: 20,
                    height: '60%'
                },
                {
                    left: 50,
                    right: 50,
                    top: '75%',
                    height: '20%'
                }
            ],
            xAxis: [
                {
                    type: 'category',
                    data: times,
                    scale: true,
                    boundaryGap: false,
                    axisLine: { onZero: false },
                    splitLine: { show: false },
                    min: 0,
                    max: 240, // 强制 241 个点 ?
                    axisLabel: {
                        // 按索引控制标签显示: 0=09:30, 120=11:30/13:00, 240=15:00
                        formatter: (value: string, index: number) => {
                            if (index === 0) return '09:30';
                            if (index === 120) return '11:30/13:00';
                            if (index === 240 || index === times.length - 1) return '15:00';
                            return '';
                        },
                        interval: 0, // 每个点都会调用 formatter
                        showMinLabel: true,
                        showMaxLabel: true
                    }
                },
                {
                    type: 'category',
                    gridIndex: 1,
                    data: times,
                    axisLabel: { show: false },
                    axisTick: { show: false }
                }
            ],
            yAxis: [
                {
                    scale: true,
                    gridIndex: 0,
                    min: limitDown,
                    max: limitUp,
                    splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } },
                    axisLabel: {
                        color: (val: number) => {
                            if (val > bp) return '#ef5350';
                            if (val < bp) return '#26a69a';
                            return '#333';
                        }
                    }
                },
                {
                    scale: true,
                    gridIndex: 0,
                    min: (limitDown - bp) / bp * 100,
                    max: (limitUp - bp) / bp * 100,
                    position: 'right',
                    axisLabel: {
                        formatter: '{value}%',
                        color: (val: number) => {
                            if (val > 0) return '#ef5350';
                            if (val < 0) return '#26a69a';
                            return '#333';
                        }
                    },
                    splitLine: { show: false }
                },
                {
                    gridIndex: 1,
                    splitNumber: 3,
                    axisLabel: { show: false },
                    axisTick: { show: false },
                    splitLine: { show: false }
                }
            ],
            series: [
                {
                    name: 'Price',
                    type: 'line',
                    data: prices,
                    itemStyle: { color: '#000', opacity: 0 }, // Hide points
                    lineStyle: { width: 1, color: '#1890ff' },
                    showSymbol: false,
                    smooth: true
                },
                {
                    name: 'AvgPrice',
                    type: 'line',
                    data: avgPrices,
                    lineStyle: { width: 1, color: '#faad14' }, // Yellow line
                    showSymbol: false,
                    smooth: true
                },
                {
                    name: 'Volume',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 2,
                    data: volumes.map(v => ({
                        value: v[1],
                        itemStyle: {
                            color: v[2] === 1 ? '#ef5350' : '#26a69a'
                        }
                    }))
                }
            ]
        };
    }, [data, basePrice]);

    if (!data || data.length === 0) return <div>No Data</div>;

    return (
        <ReactECharts option={option} style={{ height, width: '100%' }} />
    );
};

export default EChartsIntradayChart;
