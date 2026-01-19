import React, { useEffect, useState, useRef } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, MouseEventParams, UTCTimestamp, AreaSeries } from 'lightweight-charts';
import { Spin } from 'antd';
import { strategyCenterAPI } from '../../api/strategy-center';

export interface DateRangeSelectorProps {
    symbol: string;
    selectedDate: string;
    onDateChange: (date: string) => void;
    days?: number; // 加载的历史天数
    height?: number;
}

const DateRangeSelectorTV: React.FC<DateRangeSelectorProps> = ({
    symbol,
    selectedDate,
    onDateChange,
    days = 100,
    height = 40,
}) => {
    const [loading, setLoading] = useState(false);
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
    const [chartData, setChartData] = useState<any[]>([]);

    // 加载日 K 线数据
    useEffect(() => {
        const loadHistory = async () => {
            if (!symbol) return;
            setLoading(true);
            try {
                const endDate = new Date();
                const startDate = new Date();
                startDate.setDate(startDate.getDate() - days);

                const result = await strategyCenterAPI.getKLineData(
                    symbol,
                    '1d',
                    startDate.getTime(),
                    endDate.getTime()
                );

                if (result.bars && result.bars.length > 0) {
                    // 转换为 TV 格式
                    const data = result.bars.map(bar => ({
                        time: bar.date, // 字符串日期 '2025-12-31' TV能识别
                        value: bar.close,
                    }));
                    setChartData(data);
                }
            } catch (err) {
                console.error('Failed to load history for TV slider:', err);
            } finally {
                setLoading(false);
            }
        };
        loadHistory();
    }, [symbol, days]);

    // 初始化图表
    useEffect(() => {
        if (!chartContainerRef.current || chartData.length === 0) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#333',
            },
            width: chartContainerRef.current.clientWidth,
            height,
            grid: {
                vertLines: { visible: false },
                horzLines: { visible: false },
            },
            timeScale: {
                visible: false, // 隐藏时间轴，做成纯滑块条效果 (或者开启以显示日期)
                borderVisible: false,
                fixLeftEdge: true,
                fixRightEdge: true,
            },
            rightPriceScale: {
                visible: false, // 隐藏价格轴
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
            },
            handleScale: {
                axisPressedMouseMove: true,
                mouseWheel: true,
                pinch: true,
            },
            crosshair: {
                vertLine: {
                    visible: true,
                    labelVisible: false,
                },
                horzLine: {
                    visible: false,
                    labelVisible: false,
                },
            },
        });

        // 面积图风格，类似各种金融App的缩略图 (v5 API)
        const newSeries = chart.addSeries(AreaSeries, {
            lineColor: '#2962FF',
            topColor: 'rgba(41, 98, 255, 0.3)',
            bottomColor: 'rgba(41, 98, 255, 0.0)',
            lineWidth: 1,
            priceLineVisible: false,
        });

        newSeries.setData(chartData);
        chart.timeScale().fitContent();

        chartRef.current = chart;
        seriesRef.current = newSeries;

        // 点击事件
        chart.subscribeClick((param: MouseEventParams) => {
            if (param.time) {
                // param.time 是 string (如果我们传的是string)
                const dateStr = param.time as string;
                if (dateStr !== selectedDate) {
                    onDateChange(dateStr);
                }
            }
        });

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [chartData, height, selectedDate, onDateChange]);

    if (loading) {
        return (
            <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Spin size="small" />
            </div>
        );
    }

    return (
        <div ref={chartContainerRef} style={{ width: '100%', height }} />
    );
};

export default DateRangeSelectorTV;
