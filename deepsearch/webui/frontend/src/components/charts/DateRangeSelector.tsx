/**
 * TradingView Lightweight Charts 日期选择器
 * 
 * 使用 TradingView Lightweight Charts 作为迷你图表实现日期选择器
 * 特点：显示所有日期数据，日期分段标记，点击切换日期
 */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
    createChart,
    ColorType,
    IChartApi,
    ISeriesApi,
    UTCTimestamp,
    LineSeries,
    HistogramSeries,
    CrosshairMode,
} from 'lightweight-charts';
import { Spin } from 'antd';
import { strategyCenterAPI } from '../../api/strategy-center';

export interface DateRangeSelectorProps {
    /** 股票代码 */
    symbol: string;
    /** 当前选中日期 */
    selectedDate: string;
    /** 日期变化回调 */
    onDateChange: (date: string) => void;
    /** 查询天数 */
    days?: number;
    /** 组件高度 */
    height?: number;
}

interface BarData {
    date: string;
    time: string;
    close: number;
    index: number;
}

const DateRangeSelector: React.FC<DateRangeSelectorProps> = ({
    symbol,
    selectedDate,
    onDateChange,
    days = 10,
    height = 70,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const overlayRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
    const highlightSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
    const [allBars, setAllBars] = useState<BarData[]>([]);
    const [loading, setLoading] = useState(false);

    // 日期到索引范围的映射
    const dateRanges = useMemo(() => {
        const ranges: { [date: string]: { start: number; end: number } } = {};
        let currentDate = '';
        let startIdx = 0;

        allBars.forEach((bar, index) => {
            if (bar.date !== currentDate) {
                if (currentDate) {
                    ranges[currentDate] = { start: startIdx, end: index - 1 };
                }
                currentDate = bar.date;
                startIdx = index;
            }
        });

        if (currentDate) {
            ranges[currentDate] = { start: startIdx, end: allBars.length - 1 };
        }

        return ranges;
    }, [allBars]);

    // 获取日期列表
    const dates = useMemo(() => Object.keys(dateRanges).sort(), [dateRanges]);

    // 索引到日期的映射
    const indexToDate = useMemo(() => {
        const map: { [index: number]: string } = {};
        allBars.forEach((bar, index) => {
            map[index] = bar.date;
        });
        return map;
    }, [allBars]);

    // 加载多天分时数据
    const loadData = useCallback(async () => {
        if (!symbol) return;

        setLoading(true);
        try {
            const endDate = new Date();
            const startDate = new Date();
            startDate.setDate(startDate.getDate() - days * 2);

            const result = await strategyCenterAPI.getKLineData(
                symbol,
                '1m',
                startDate.getTime(),
                endDate.getTime()
            );

            if (result.bars && result.bars.length > 0) {
                const bars = result.bars
                    .filter(bar => bar.date && bar.time_str)
                    .map((bar, index) => ({
                        date: bar.date!,
                        time: bar.time_str!,
                        close: bar.close,
                        index,
                    }));

                setAllBars(bars);
            }
        } catch (err) {
            console.error('Failed to load data:', err);
        } finally {
            setLoading(false);
        }
    }, [symbol, days]);

    // 更新选中日期的高亮
    const updateHighlight = useCallback(() => {
        if (!highlightSeriesRef.current || allBars.length === 0) return;

        const selectedRange = dateRanges[selectedDate];

        // 创建高亮数据 - 选中日期区域显示蓝色柱状
        const highlightData = allBars.map((bar, index) => {
            const isSelected = selectedRange &&
                index >= selectedRange.start &&
                index <= selectedRange.end;
            return {
                time: (index * 60) as UTCTimestamp,
                value: isSelected ? 0.5 : 0,
                color: isSelected ? 'rgba(24, 144, 255, 0.25)' : 'transparent',
            };
        });

        highlightSeriesRef.current.setData(highlightData);
    }, [allBars, selectedDate, dateRanges]);

    // 绘制日期分隔线和标签
    const updateDateMarkers = useCallback(() => {
        if (!overlayRef.current || !containerRef.current || allBars.length === 0) return;

        const containerWidth = containerRef.current.clientWidth;
        const barWidth = containerWidth / allBars.length;

        // 清空旧的标记
        overlayRef.current.innerHTML = '';

        dates.forEach((date, idx) => {
            const range = dateRanges[date];
            if (!range) return;

            const startX = range.start * barWidth;
            const endX = (range.end + 1) * barWidth;
            const centerX = (startX + endX) / 2;
            const isSelected = date === selectedDate;

            // 日期分隔线（每天开始位置）
            if (idx > 0) {
                const divider = document.createElement('div');
                divider.style.cssText = `
                    position: absolute;
                    left: ${startX}px;
                    top: 0;
                    width: 1px;
                    height: ${height - 18}px;
                    background: #e0e0e0;
                    pointer-events: none;
                `;
                overlayRef.current!.appendChild(divider);
            }

            // 日期标签
            const label = document.createElement('div');
            label.style.cssText = `
                position: absolute;
                left: ${centerX}px;
                bottom: 2px;
                transform: translateX(-50%);
                font-size: 10px;
                color: ${isSelected ? '#1890ff' : '#999'};
                font-weight: ${isSelected ? 'bold' : 'normal'};
                white-space: nowrap;
                pointer-events: none;
                background: ${isSelected ? 'rgba(24, 144, 255, 0.1)' : 'transparent'};
                padding: 1px 4px;
                border-radius: 2px;
            `;
            label.textContent = date.slice(5); // MM-DD
            overlayRef.current!.appendChild(label);
        });
    }, [allBars, dates, dateRanges, selectedDate, height]);

    // 初始化图表
    const initChart = useCallback(() => {
        if (!containerRef.current || allBars.length === 0) return;

        // 销毁旧图表
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }

        const chart = createChart(containerRef.current, {
            width: containerRef.current.clientWidth,
            height: height - 18,  // 留出底部日期标签空间
            layout: {
                background: { type: ColorType.Solid, color: '#fafafa' },
                textColor: '#666',
                attributionLogo: false,
            },
            grid: {
                vertLines: { visible: false },
                horzLines: { visible: false },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    color: '#1890ff',
                    width: 1,
                    style: 2,
                    labelVisible: false,
                },
                horzLine: {
                    visible: false,
                    labelVisible: false,
                },
            },
            leftPriceScale: { visible: false },
            rightPriceScale: { visible: false },
            timeScale: {
                visible: false,  // 隐藏原生时间轴，使用自定义日期标签
            },
            handleScale: false,
            handleScroll: false,
        });

        chartRef.current = chart;

        // 添加底部高亮层
        const highlightSeries = chart.addSeries(HistogramSeries, {
            priceScaleId: '',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        highlightSeriesRef.current = highlightSeries;

        // 添加走势线
        const lineSeries = chart.addSeries(LineSeries, {
            color: '#1890ff',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 3,
        });

        // 转换数据格式
        const lineData = allBars.map((bar, index) => ({
            time: (index * 60) as UTCTimestamp,
            value: bar.close,
        }));

        lineSeries.setData(lineData);
        lineSeriesRef.current = lineSeries;

        // 显示所有数据
        chart.timeScale().fitContent();

        // 初始化高亮和日期标记
        updateHighlight();
        updateDateMarkers();

        // 处理点击事件
        chart.subscribeClick((param) => {
            if (param.time !== undefined) {
                const index = Math.round((param.time as number) / 60);
                const clickedDate = indexToDate[index];
                if (clickedDate && clickedDate !== selectedDate) {
                    onDateChange(clickedDate);
                }
            }
        });

        // 响应式调整
        const handleResize = () => {
            if (containerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: containerRef.current.clientWidth,
                });
                updateDateMarkers();
            }
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, [allBars, selectedDate, onDateChange, indexToDate, height, updateHighlight, updateDateMarkers]);

    // 加载数据
    useEffect(() => {
        loadData();
    }, [loadData]);

    // 初始化图表
    useEffect(() => {
        if (allBars.length > 0) {
            const cleanup = initChart();
            return () => {
                cleanup?.();
                if (chartRef.current) {
                    chartRef.current.remove();
                    chartRef.current = null;
                }
            };
        }
    }, [initChart, allBars.length > 0]);

    // 更新高亮和日期标记
    useEffect(() => {
        updateHighlight();
        updateDateMarkers();
    }, [updateHighlight, updateDateMarkers]);

    if (loading) {
        return (
            <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', borderRadius: 4 }}>
                <Spin size="small" />
            </div>
        );
    }

    if (allBars.length === 0) {
        return (
            <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12, background: '#fafafa', borderRadius: 4 }}>
                暂无历史数据
            </div>
        );
    }

    return (
        <div style={{
            border: '1px solid #e0e0e0',
            borderRadius: 4,
            overflow: 'hidden',
            position: 'relative',
        }}>
            <div
                ref={containerRef}
                style={{
                    width: '100%',
                    height: height - 18,
                    cursor: 'pointer',
                }}
            />
            {/* 日期标签和分隔线覆盖层 */}
            <div
                ref={overlayRef}
                style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                    pointerEvents: 'none',
                }}
            />
            {/* 底部日期区域背景 */}
            <div style={{
                height: 18,
                background: '#f5f5f5',
                borderTop: '1px solid #e8e8e8',
            }} />
        </div>
    );
};

export default DateRangeSelector;
