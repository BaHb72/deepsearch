/**
 * 日期选择器组件 (ECharts 滑块版 v3 - 动态预加载)
 * 
 * 显示日 K 线迷你缩略图，底部支持 DataZoom 拖拽选择日期
 * 支持滚动到边界时自动预加载更多历史数据
 */
import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin } from 'antd';
import { strategyCenterAPI } from '../../api/strategy-center';

export interface DateRangeSelectorProps {
    symbol: string;
    selectedDate: string;
    onDateChange: (date: string) => void;
    days?: number; // 初始加载的历史天数 (默认 60)
    height?: number;
    /** 每次预加载的天数 */
    preloadDays?: number;
    /** 最大加载天数限制 */
    maxDays?: number;
}

const DateRangeSelector: React.FC<DateRangeSelectorProps> = ({
    symbol,
    selectedDate,
    onDateChange,
    days = 60,
    height = 60,
    preloadDays = 60,
    maxDays = 365,
}) => {
    const [loading, setLoading] = useState(false);
    const [preloading, setPreloading] = useState(false);
    const [klineData, setKlineData] = useState<any[]>([]);
    const [loadedDays, setLoadedDays] = useState(days);
    const echartsRef = useRef<ReactECharts>(null);

    // 防止重复加载
    const isPreloadingRef = useRef(false);
    // 记录上一次的 zoom 状态，用于恢复位置
    const lastZoomRef = useRef<{ start: number; end: number } | null>(null);

    // 加载日 K 线数据
    const loadKlineData = useCallback(async (daysToLoad: number, isAppend = false) => {
        if (!symbol) return;

        if (isAppend) {
            setPreloading(true);
        } else {
            setLoading(true);
        }

        try {
            const endDate = new Date();
            const startDate = new Date();
            startDate.setDate(startDate.getDate() - daysToLoad);

            const result = await strategyCenterAPI.getKLineData(
                symbol,
                '1d',
                startDate.getTime(),
                endDate.getTime()
            );

            if (result.bars && result.bars.length > 0) {
                if (isAppend && klineData.length > 0) {
                    // 追加模式：合并新数据（去重）
                    const existingDates = new Set(klineData.map(d => d.date));
                    const newBars = result.bars.filter((bar: any) => !existingDates.has(bar.date));

                    if (newBars.length > 0) {
                        // 新数据在前面（历史数据）
                        const mergedData = [...newBars, ...klineData];
                        setKlineData(mergedData);
                        setLoadedDays(daysToLoad);

                        // 计算新数据占比，调整 zoom 位置以保持视图不变
                        if (lastZoomRef.current && echartsRef.current) {
                            const instance = echartsRef.current.getEchartsInstance();
                            const oldLen = klineData.length;
                            const newLen = mergedData.length;
                            const addedLen = newBars.length;

                            // 调整百分比：新增的数据在左侧
                            const ratio = oldLen / newLen;
                            const newStart = lastZoomRef.current.start * ratio + (addedLen / newLen) * 100;
                            const newEnd = lastZoomRef.current.end * ratio + (addedLen / newLen) * 100;

                            // 延迟设置，避免与当前 dataZoom 事件冲突
                            setTimeout(() => {
                                instance.dispatchAction({
                                    type: 'dataZoom',
                                    start: newStart,
                                    end: newEnd,
                                });
                            }, 50);
                        }
                    }
                } else {
                    setKlineData(result.bars);
                    setLoadedDays(daysToLoad);
                }
            }
        } catch (err) {
            console.error('Failed to load kline data for slider:', err);
        } finally {
            setLoading(false);
            setPreloading(false);
            isPreloadingRef.current = false;
        }
    }, [symbol, klineData]);

    // 初始加载
    useEffect(() => {
        setKlineData([]);
        setLoadedDays(days);
        loadKlineData(days, false);
    }, [symbol, days]);

    // 预加载更多历史数据
    const preloadMore = useCallback(() => {
        if (isPreloadingRef.current || loadedDays >= maxDays) return;

        isPreloadingRef.current = true;
        const newDays = Math.min(loadedDays + preloadDays, maxDays);
        loadKlineData(newDays, true);
    }, [loadedDays, maxDays, preloadDays, loadKlineData]);

    // 计算选中日期的索引
    const selectedIndex = useMemo(() => {
        if (klineData.length === 0) return -1;
        return klineData.findIndex(item => item.date === selectedDate);
    }, [klineData, selectedDate]);

    // 生成 ECharts 配置
    const option = useMemo(() => {
        if (klineData.length === 0) return {};

        const dates = klineData.map(item => item.date);
        const closePrices = klineData.map(item => item.close);

        // 计算初始 dataZoom 范围
        const totalDays = dates.length;
        const visibleDays = 30;
        let zoomEnd = 100;
        let zoomStart = Math.max(0, 100 - (visibleDays / totalDays) * 100);

        // 如果有选中日期，调整范围使其可见
        if (selectedIndex >= 0) {
            const selectedPct = (selectedIndex / (totalDays - 1)) * 100;
            if (selectedPct < zoomStart) {
                zoomStart = Math.max(0, selectedPct - 10);
                zoomEnd = zoomStart + (visibleDays / totalDays) * 100;
            } else if (selectedPct > zoomEnd) {
                zoomEnd = Math.min(100, selectedPct + 10);
                zoomStart = zoomEnd - (visibleDays / totalDays) * 100;
            }
        }

        return {
            animation: false,
            tooltip: {
                trigger: 'axis',
                formatter: function (params: any) {
                    if (!params || params.length === 0) return '';
                    const idx = params[0].dataIndex;
                    const bar = klineData[idx];
                    if (!bar) return '';
                    const change = bar.close - bar.open;
                    const changePct = ((change / bar.open) * 100).toFixed(2);
                    const color = change >= 0 ? '#ef5350' : '#26a69a';
                    return `
                        <div style="font-size:12px;">
                            <div style="font-weight:bold;margin-bottom:4px;">${bar.date}</div>
                            <div>收盘: <span style="color:${color};font-weight:bold;">${bar.close.toFixed(2)}</span></div>
                            <div>涨跌: <span style="color:${color};">${change >= 0 ? '+' : ''}${changePct}%</span></div>
                        </div>
                    `;
                },
                axisPointer: { type: 'line' }
            },
            grid: {
                left: 0,
                right: 0,
                top: 5,
                bottom: 25,
            },
            xAxis: {
                type: 'category',
                data: dates,
                boundaryGap: false,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: { show: false },
            },
            yAxis: {
                type: 'value',
                show: false,
                scale: true,
            },
            dataZoom: [
                {
                    type: 'slider',
                    show: true,
                    xAxisIndex: 0,
                    bottom: 0,
                    height: 20,
                    start: zoomStart,
                    end: zoomEnd,
                    handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
                    handleSize: '80%',
                    handleStyle: {
                        color: '#fff',
                        shadowBlur: 3,
                        shadowColor: 'rgba(0, 0, 0, 0.3)',
                        shadowOffsetX: 1,
                        shadowOffsetY: 1,
                    },
                    textStyle: { color: '#666', fontSize: 10 },
                    borderColor: '#ddd',
                    backgroundColor: 'rgba(47,69,84,0.1)',
                    dataBackground: {
                        lineStyle: { color: '#1890ff', opacity: 0.8 },
                        areaStyle: { color: '#1890ff', opacity: 0.2 }
                    },
                    selectedDataBackground: {
                        lineStyle: { color: '#1890ff' },
                        areaStyle: { color: '#1890ff', opacity: 0.3 }
                    },
                    fillerColor: 'rgba(24, 144, 255, 0.15)',
                    brushSelect: false,
                    realtime: true,
                },
                {
                    type: 'inside',
                    xAxisIndex: 0,
                    start: zoomStart,
                    end: zoomEnd,
                    zoomOnMouseWheel: true,
                    moveOnMouseMove: true,
                }
            ],
            // 预加载提示
            graphic: preloading ? [{
                type: 'text',
                left: 10,
                top: 5,
                style: {
                    text: '加载中...',
                    fontSize: 10,
                    fill: '#1890ff',
                }
            }] : (loadedDays >= maxDays ? [{
                type: 'text',
                left: 10,
                top: 5,
                style: {
                    text: `已加载 ${klineData.length} 天`,
                    fontSize: 10,
                    fill: '#999',
                }
            }] : []),
            series: [
                {
                    name: '收盘价',
                    type: 'line',
                    data: closePrices,
                    symbol: 'none',
                    lineStyle: { width: 1.5, color: '#1890ff' },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                                { offset: 1, color: 'rgba(24, 144, 255, 0.05)' },
                            ],
                        }
                    },
                    markPoint: selectedIndex >= 0 ? {
                        symbol: 'circle',
                        symbolSize: 8,
                        data: [{
                            coord: [selectedIndex, closePrices[selectedIndex]],
                            itemStyle: { color: '#1890ff', borderColor: '#fff', borderWidth: 2 },
                        }]
                    } : undefined,
                    markLine: selectedIndex >= 0 ? {
                        silent: true,
                        symbol: 'none',
                        lineStyle: { color: '#1890ff', type: 'dashed', width: 1 },
                        label: {
                            show: true,
                            position: 'end',
                            formatter: selectedDate.slice(5),
                            color: '#1890ff',
                            fontSize: 10,
                            backgroundColor: '#fff',
                            padding: [2, 4],
                            borderRadius: 2,
                        },
                        data: [{ xAxis: selectedIndex }]
                    } : undefined,
                },
            ],
        };
    }, [klineData, selectedIndex, selectedDate, preloading, loadedDays, maxDays]);

    // 处理点击事件
    const onChartClick = useCallback((params: any) => {
        if (params.componentType === 'series' || params.componentType === 'markLine') {
            const idx = params.dataIndex;
            if (idx !== undefined && klineData[idx]) {
                const date = klineData[idx].date;
                if (date && date !== selectedDate) {
                    onDateChange(date);
                }
            }
        }
    }, [klineData, selectedDate, onDateChange]);

    // 处理 DataZoom 事件
    const onDataZoom = useCallback((params: any) => {
        let startPct = 0;
        let endPct = 100;

        if (params.batch && params.batch.length > 0) {
            startPct = params.batch[0].start;
            endPct = params.batch[0].end;
        } else if (params.start !== undefined) {
            startPct = params.start;
            endPct = params.end;
        }

        // 保存当前 zoom 状态
        lastZoomRef.current = { start: startPct, end: endPct };

        // 检查是否滚动到左边界 (历史方向) - 触发预加载
        if (startPct <= 5 && !isPreloadingRef.current && loadedDays < maxDays) {
            preloadMore();
        }

        // 更新选中日期为滑块结束位置
        if (klineData.length > 0) {
            const index = Math.min(
                klineData.length - 1,
                Math.floor((klineData.length - 1) * (endPct / 100))
            );
            const date = klineData[index]?.date;
            if (date && date !== selectedDate) {
                onDateChange(date);
            }
        }
    }, [klineData, selectedDate, onDateChange, loadedDays, maxDays, preloadMore]);

    if (loading) {
        return (
            <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Spin size="small" />
            </div>
        );
    }

    if (klineData.length === 0) {
        return (
            <div style={{
                height,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#999',
                fontSize: 12,
            }}>
                暂无历史数据
            </div>
        );
    }

    return (
        <ReactECharts
            ref={echartsRef}
            option={option}
            style={{ height, width: '100%' }}
            opts={{ renderer: 'svg' }}
            onEvents={{
                'click': onChartClick,
                'datazoom': onDataZoom
            }}
        />
    );
};

export default DateRangeSelector;
