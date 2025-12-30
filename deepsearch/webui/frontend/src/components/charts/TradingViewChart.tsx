/**
 * TradingView Lightweight Charts 组件 (v5 API)
 * 
 * 使用 TradingView 官方开源的 Lightweight Charts 库
 * 支持分时图和K线图
 */
import React, { useEffect, useRef, useCallback, useMemo } from 'react';
import {
    createChart,
    ColorType,
    IChartApi,
    ISeriesApi,
    UTCTimestamp,
    LineSeries,
    CandlestickSeries,
    HistogramSeries,
} from 'lightweight-charts';

export interface TradingViewChartProps {
    /** 分时数据 (用于分时图) */
    lineData?: Array<{
        time: string;
        value: number;
        date?: string;  // YYYY-MM-DD 格式，用于日期分隔
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
    /** VWAP 线 */
    vwapValue?: number;
    /** 基准价格（用于计算右侧 Y 轴的涨跌幅百分比） */
    basePrice?: number;
    /** 买卖信号 (支持策略区分) */
    signals?: Array<{
        time: string;
        type: 'buy' | 'sell';
        price: number;
        strategy?: string;  // 策略名称
        reason?: string;    // 信号原因
    }>;
    /** 
     * 加载更多历史数据的回调
     * @param earliestTimeStr 当前最早的时间字符串 (如 "09:30")
     * @param earliestDate 当前最早的日期 (如 "2024-12-29")
     * @returns 返回更早的数据
     */
    onLoadMore?: (earliestTimeStr: string, earliestDate?: string) => Promise<{
        lineData?: Array<{ time: string; value: number; date?: string }>;
        volumeData?: Array<{ time: string; value: number; date?: string }>;
    } | null>;
    /** 是否正在加载更多数据 */
    loadingMore?: boolean;
}

// A股交易时间基准（用于计算时间索引）
const TRADING_START_HOUR = 9;
const TRADING_START_MINUTE = 30;

/**
 * 将时间字符串转换为分钟索引（从 09:30 开始计算）
 * 这样可以避免时区问题，让时间轴正确显示
 */
function timeToMinuteIndex(timeStr: string, dayOffset: number = 0): number {
    // 解析 HH:MM 或 HH:MM:SS 格式
    if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(timeStr)) {
        const parts = timeStr.split(':');
        const hours = parseInt(parts[0], 10);
        const minutes = parseInt(parts[1], 10);

        // 计算从 09:30 开始的分钟数
        let minutesSinceStart = (hours - TRADING_START_HOUR) * 60 + (minutes - TRADING_START_MINUTE);

        // 如果时间在开盘前，可能是上一天的数据或数据错误
        if (minutesSinceStart < 0) {
            minutesSinceStart = 0;
        }

        // A股上午交易 09:30-11:30 = 120分钟
        // A股下午交易 13:00-15:00 = 120分钟
        // 午休 11:30-13:00 = 90分钟（需要跳过）
        if (hours >= 13) {
            // 下午交易，需要减去午休时间（90分钟）
            minutesSinceStart -= 90;
        }

        // 每天约 240 分钟交易时间
        return dayOffset * 240 + minutesSinceStart;
    }
    return 0;
}

/**
 * 将分钟索引转换回时间字符串（用于显示）
 */
function minuteIndexToTime(index: number): string {
    // 计算是哪一天的第几分钟
    const dayOffset = Math.floor(index / 240);
    let minuteInDay = index % 240;

    // 上午交易时间 09:30-11:30 (120分钟)
    // 下午交易时间 13:00-15:00 (120分钟)
    let hours: number;
    let minutes: number;

    if (minuteInDay < 120) {
        // 上午
        hours = TRADING_START_HOUR + Math.floor(minuteInDay / 60);
        minutes = TRADING_START_MINUTE + (minuteInDay % 60);
        if (minutes >= 60) {
            hours += 1;
            minutes -= 60;
        }
    } else {
        // 下午
        minuteInDay -= 120;
        hours = 13 + Math.floor(minuteInDay / 60);
        minutes = minuteInDay % 60;
    }

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

const TradingViewChart: React.FC<TradingViewChartProps> = ({
    lineData = [],
    candleData = [],
    volumeData = [],
    chartType = 'line',
    height = 400,
    vwapValue,
    basePrice,
    signals = [],
    onLoadMore,
    loadingMore = false,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<'Line'> | ISeriesApi<'Candlestick'> | null>(null);
    // 保存原始时间字符串用于显示
    const timeLabelsRef = useRef<string[]>([]);
    // 保存日期信息用于动态加载
    const datesRef = useRef<(string | undefined)[]>([]);
    // 保存日期分隔点的索引
    const dateSeparatorsRef = useRef<number[]>([]);

    // 转换数据格式 - 使用分钟索引作为时间戳，同时检测日期变化
    const formattedLineData = useMemo(() => {
        const labels: string[] = [];
        const dates: (string | undefined)[] = [];
        const separators: number[] = [];
        let lastDate: string | undefined = undefined;

        const data = lineData.map((d, index) => {
            labels.push(d.time);
            dates.push(d.date);

            // 检测日期变化，记录分隔点
            if (d.date && lastDate && d.date !== lastDate) {
                separators.push(index);
            }
            lastDate = d.date;

            // 使用索引作为时间戳（乘以 60 使其看起来像分钟级时间戳）
            return {
                time: (index * 60) as UTCTimestamp,
                value: d.value,
            };
        });

        timeLabelsRef.current = labels;
        datesRef.current = dates;
        dateSeparatorsRef.current = separators;
        return data;
    }, [lineData]);

    const formattedVolumeData = useMemo(() => {
        return volumeData.map((d, index) => {
            let color = '#26a69a';
            if (lineData.length > 1 && index > 0) {
                color = lineData[index].value >= lineData[index - 1].value ? '#ef5350' : '#26a69a';
            }
            return {
                time: (index * 60) as UTCTimestamp,
                value: d.value,
                color: d.color || color,
            };
        });
    }, [volumeData, lineData]);

    const formattedCandleData = useMemo(() => {
        return candleData.map((d, index) => ({
            time: (index * 60) as UTCTimestamp,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));
    }, [candleData]);

    // 初始化图表
    const initChart = useCallback(() => {
        if (!containerRef.current) return;

        // 销毁旧图表
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }

        // 创建图表
        const chart = createChart(containerRef.current, {
            width: containerRef.current.clientWidth,
            height: height,
            layout: {
                background: { type: ColorType.Solid, color: '#ffffff' },
                textColor: '#333',
                attributionLogo: false,  // 去掉左下角 TV logo
            },
            grid: {
                vertLines: { color: '#f0f0f0' },
                horzLines: { color: '#f0f0f0' },
            },
            crosshair: {
                mode: 0, // Magnet - 吸附到K线价格
                horzLine: {
                    visible: true,
                    labelVisible: true,
                    color: '#1890ff',
                    width: 1,
                    style: 2, // Dashed
                },
                vertLine: {
                    visible: true,
                    labelVisible: true,
                    color: '#999999',
                    width: 1,
                    style: 2, // Dashed
                },
            },
            // 左侧 Y 轴：显示价格
            leftPriceScale: {
                visible: true,
                borderColor: '#dfdfdf',
            },
            // 右侧 Y 轴：显示百分比 (由百分比系列使用)
            rightPriceScale: {
                visible: true,
                borderColor: '#dfdfdf',
            },
            timeScale: {
                borderColor: '#dfdfdf',
                timeVisible: true,
                secondsVisible: false,
                minBarSpacing: 0.5,  // 最小缩放限制
                fixLeftEdge: true,   // 固定左边缘不留白
                fixRightEdge: true,  // 固定右边缘不留白
                tickMarkFormatter: (time: number) => {
                    // 使用索引获取日期和时间
                    const index = Math.round(time / 60);

                    // 检查是否是新的一天开始（每天 09:30）
                    if (index >= 0 && index < datesRef.current.length) {
                        const currentDate = datesRef.current[index];
                        const currentTime = timeLabelsRef.current[index];

                        // 如果是 09:30 或者是第一个数据点，显示日期
                        if (currentTime === '09:30' || index === 0 ||
                            (index > 0 && currentDate !== datesRef.current[index - 1])) {
                            if (currentDate) {
                                // 格式化为 MM-DD
                                const parts = currentDate.split('-');
                                if (parts.length === 3) {
                                    return `${parts[1]}-${parts[2]}`;
                                }
                            }
                        }
                        return timeLabelsRef.current[index];
                    }
                    // 如果超出范围，使用计算的时间
                    return minuteIndexToTime(index);
                },
            },
            localization: {
                locale: 'zh-CN',
                timeFormatter: (time: number) => {
                    // 鼠标悬停时显示日期和时间
                    const index = Math.round(time / 60);
                    if (index >= 0 && index < timeLabelsRef.current.length) {
                        const dateStr = datesRef.current[index];
                        const timeStr = timeLabelsRef.current[index];
                        if (dateStr) {
                            return `${dateStr} ${timeStr}`;
                        }
                        return timeStr;
                    }
                    return minuteIndexToTime(index);
                },
            },
        });

        chartRef.current = chart;

        // 计算基准价格（用于百分比计算）
        const effectiveBasePrice = basePrice || (lineData.length > 0 ? lineData[0].value : 0);

        // 创建主系列 (v5 API: 使用 addSeries)
        if (chartType === 'candlestick' && formattedCandleData.length > 0) {
            const candleSeries = chart.addSeries(CandlestickSeries, {
                upColor: '#ef5350',
                downColor: '#26a69a',
                borderUpColor: '#ef5350',
                borderDownColor: '#26a69a',
                wickUpColor: '#ef5350',
                wickDownColor: '#26a69a',
                priceScaleId: 'left',  // 使用左侧 Y 轴
            });
            candleSeries.setData(formattedCandleData);
            seriesRef.current = candleSeries;
        } else if (formattedLineData.length > 0) {
            // 价格线 - 使用左侧 Y 轴
            const lineSeries = chart.addSeries(LineSeries, {
                color: '#1890ff',
                lineWidth: 2,
                priceScaleId: 'left',  // 使用左侧 Y 轴
                crosshairMarkerRadius: 4,  // 缩小圆圈半径
                crosshairMarkerBorderColor: '#1890ff',  // 蓝色边框
                crosshairMarkerBackgroundColor: '#1890ff',  // 蓝色填充
                crosshairMarkerBorderWidth: 1,
            });
            lineSeries.setData(formattedLineData);
            seriesRef.current = lineSeries;

            // 百分比系列 - 使用右侧 Y 轴 (如果有基准价格)
            if (effectiveBasePrice > 0) {
                const percentSeries = chart.addSeries(LineSeries, {
                    color: 'transparent',  // 隐藏线条，只显示 Y 轴
                    lineWidth: 0,
                    priceScaleId: 'right',  // 使用右侧 Y 轴
                    crosshairMarkerVisible: false,  // 隐藏crosshair marker
                    priceFormat: {
                        type: 'custom',
                        formatter: (price: number) => {
                            const percent = ((price - effectiveBasePrice) / effectiveBasePrice) * 100;
                            return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
                        },
                    },
                });
                // 设置相同的数据让右侧 Y 轴显示百分比刻度
                percentSeries.setData(formattedLineData);
            }

            // 添加VWAP参考线
            if (vwapValue && formattedLineData.length > 0) {
                const vwapSeries = chart.addSeries(LineSeries, {
                    color: '#faad14',
                    lineWidth: 1,
                    lineStyle: 2, // Dashed
                    priceScaleId: 'left',  // 使用左侧 Y 轴
                    crosshairMarkerVisible: false,  // 隐藏crosshair marker，只显示主线的
                });
                const vwapData = formattedLineData.map(d => ({
                    time: d.time,
                    value: vwapValue,
                }));
                vwapSeries.setData(vwapData);
            }
        }

        // 添加成交量
        if (formattedVolumeData.length > 0) {
            const volumeSeries = chart.addSeries(HistogramSeries, {
                color: '#26a69a',
                priceFormat: {
                    type: 'volume',
                },
                priceScaleId: '', // 在下方独立显示
            });
            volumeSeries.priceScale().applyOptions({
                scaleMargins: {
                    top: 0.8,
                    bottom: 0,
                },
            });
            volumeSeries.setData(formattedVolumeData);
        }

        // 添加日期分隔线（使用 Histogram Series 实现垂直线）
        if (dateSeparatorsRef.current.length > 0 && formattedLineData.length > 0) {
            const separatorSeries = chart.addSeries(HistogramSeries, {
                color: 'rgba(128, 128, 128, 0.3)',  // 半透明灰色
                priceScaleId: 'separator',  // 使用独立的价格轴
            });

            // 配置分隔线价格轴，使其跨越整个高度
            separatorSeries.priceScale().applyOptions({
                scaleMargins: {
                    top: 0,
                    bottom: 0,
                },
            });

            // 为每个分隔点创建数据
            const separatorData = dateSeparatorsRef.current.map(index => ({
                time: (index * 60) as UTCTimestamp,
                value: 1,  // 任意正值，因为会占满整个高度
                color: 'rgba(100, 100, 100, 0.4)',
            }));

            separatorSeries.setData(separatorData);
        }

        // 添加买卖信号标记 (支持不同策略的颜色区分)
        if (signals.length > 0 && seriesRef.current) {
            // 策略颜色映射
            const strategyColors: Record<string, { buy: string; sell: string }> = {
                'vwap_deviation': { buy: '#1890ff', sell: '#722ed1' },      // 蓝/紫
                'opening_breakout': { buy: '#52c41a', sell: '#fa8c16' },    // 绿/橙
                'time_window': { buy: '#13c2c2', sell: '#eb2f96' },         // 青/粉
                'momentum_reversal': { buy: '#2f54eb', sell: '#f5222d' },   // 靛蓝/红
                'ma_deviation': { buy: '#36cfc9', sell: '#ff7a45' },        // 青绿/橙红
                'support_resistance': { buy: '#73d13d', sell: '#ff4d4f' },  // 浅绿/浅红
                'grid': { buy: '#40a9ff', sell: '#ff85c0' },                // 天蓝/粉红
                'volume_price': { buy: '#95de64', sell: '#ffa940' },        // 草绿/金橙
                'default': { buy: '#26a69a', sell: '#ef5350' },             // 默认绿/红
            };

            // 策略形状映射
            const strategyShapes: Record<string, { buy: 'arrowUp' | 'circle'; sell: 'arrowDown' | 'circle' }> = {
                'vwap_deviation': { buy: 'arrowUp', sell: 'arrowDown' },
                'opening_breakout': { buy: 'circle', sell: 'circle' },
                'momentum_reversal': { buy: 'arrowUp', sell: 'arrowDown' },
                'default': { buy: 'arrowUp', sell: 'arrowDown' },
            };

            const markers = signals.map(s => {
                // 查找信号时间对应的索引
                const signalIndex = lineData.findIndex(d => d.time === s.time);
                const time = signalIndex >= 0 ? signalIndex * 60 : 0;

                // 获取策略对应的颜色和形状
                const strategyKey = s.strategy || 'default';
                const colors = strategyColors[strategyKey] || strategyColors['default'];
                const shapes = strategyShapes[strategyKey] || strategyShapes['default'];

                // 生成简短的策略标签
                const strategyLabel = s.strategy ? s.strategy.split('_')[0].substring(0, 4).toUpperCase() : '';
                const text = s.type === 'buy'
                    ? `买${strategyLabel ? '·' + strategyLabel : ''}`
                    : `卖${strategyLabel ? '·' + strategyLabel : ''}`;

                return {
                    time: time as UTCTimestamp,
                    position: s.type === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
                    color: s.type === 'buy' ? colors.buy : colors.sell,
                    shape: s.type === 'buy' ? shapes.buy : shapes.sell,
                    text: text,
                    size: 1,
                };
            });
            // 安全调用 setMarkers - 检查方法是否存在
            if (seriesRef.current && typeof (seriesRef.current as any).setMarkers === 'function') {
                (seriesRef.current as any).setMarkers(markers);
            }
        }

        // 自适应内容
        chart.timeScale().fitContent();

        // 监听滚动到边界，动态加载更多数据
        let isLoadingMore = false;
        const handleVisibleRangeChange = () => {
            if (!onLoadMore || isLoadingMore || loadingMore) return;

            const visibleRange = chart.timeScale().getVisibleRange();
            if (!visibleRange || formattedLineData.length === 0) return;

            const earliestDataTime = formattedLineData[0]?.time || 0;
            // 获取最早的原始时间字符串和日期
            const earliestTimeStr = timeLabelsRef.current[0] || '09:30';
            const earliestDate = datesRef.current[0];

            // 当可见范围的左边界接近数据最早时间时，触发加载
            // 使用 5 分钟 (300秒) 的容差
            if (visibleRange.from <= earliestDataTime + 300) {
                console.log('[TradingViewChart] Triggering load more, earliestTimeStr:', earliestTimeStr, 'earliestDate:', earliestDate);
                isLoadingMore = true;
                // 传递原始时间字符串和日期
                onLoadMore(earliestTimeStr, earliestDate).finally(() => {
                    isLoadingMore = false;
                });
            }
        };

        chart.timeScale().subscribeVisibleTimeRangeChange(handleVisibleRangeChange);

        // 响应式调整
        const handleResize = () => {
            if (containerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: containerRef.current.clientWidth,
                });
            }
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.timeScale().unsubscribeVisibleTimeRangeChange(handleVisibleRangeChange);
        };
    }, [formattedLineData, formattedCandleData, formattedVolumeData, chartType, height, vwapValue, basePrice, signals, onLoadMore, loadingMore, lineData]);

    useEffect(() => {
        const cleanup = initChart();
        return () => {
            cleanup?.();
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [initChart]);

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
        <div
            ref={containerRef}
            style={{
                width: '100%',
                height,
            }}
        />
    );
};

export default TradingViewChart;
