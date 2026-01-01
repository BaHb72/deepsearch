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
    createSeriesMarkers,
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

    // 转换数据格式 - 使用真正的 Unix 时间戳
    // TradingView lightweight-charts 需要 UTC 秒级时间戳
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

            // 将时间字符串转换为真正的 Unix 时间戳
            // 技巧：直接把北京时间当作 UTC 传给 TradingView，这样显示的就是北京时间
            let timestamp: number;
            const dateStr = d.date || new Date().toISOString().split('T')[0];
            const timeStr = d.time || '09:30';

            // 解析时间 (HH:MM 或 HH:MM:SS)
            const timeParts = timeStr.split(':');
            const hours = parseInt(timeParts[0], 10);
            const minutes = parseInt(timeParts[1], 10);
            const seconds = timeParts[2] ? parseInt(timeParts[2], 10) : 0;

            // 构建日期时间
            const dateParts = dateStr.split('-');
            const year = parseInt(dateParts[0], 10);
            const month = parseInt(dateParts[1], 10) - 1; // JS月份从0开始
            const day = parseInt(dateParts[2], 10);

            // 使用 Date.UTC 构建 UTC 时间戳，但传入的是北京时间
            // 这样 TradingView 显示的 UTC 时间就是北京时间
            timestamp = Date.UTC(year, month, day, hours, minutes, seconds) / 1000;

            return {
                time: timestamp as UTCTimestamp,
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

            // 使用与 lineData 相同的时间戳
            const timestamp = formattedLineData[index]?.time || (index * 60) as UTCTimestamp;

            return {
                time: timestamp,
                value: d.value,
                color: d.color || color,
            };
        });
    }, [volumeData, lineData, formattedLineData]);



    const formattedCandleData = useMemo(() => {
        return candleData.map((d, index) => {
            // 使用与 lineData 相同的时间戳
            const timestamp = formattedLineData[index]?.time || (index * 60) as UTCTimestamp;

            return {
                time: timestamp,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
            };
        });
    }, [candleData, formattedLineData]);

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
            // 左侧 Y 轴：显示价格 (占据顶部 65%)
            leftPriceScale: {
                visible: true,
                borderColor: '#dfdfdf',
                scaleMargins: {
                    top: 0.05,
                    bottom: 0.35, // 底部留出 35% (其中 10% 是空白间隔)
                },
            },
            // 右侧 Y 轴：显示百分比 (占据顶部 65%)
            rightPriceScale: {
                visible: true,
                borderColor: '#dfdfdf',
                scaleMargins: {
                    top: 0.05,
                    bottom: 0.35, // 底部留出 35%
                },
            },
            timeScale: {
                borderColor: '#dfdfdf',
                timeVisible: true,
                secondsVisible: false,
                minBarSpacing: 0.5,
                fixLeftEdge: true,
                fixRightEdge: false,
                rightOffset: 10,
                // 完全使用 TradingView 原生时间显示
            },
            localization: {
                locale: 'zh-CN',
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

            // 添加累计均价线 (黄线) - 类似东财分时图的均线
            if (formattedLineData.length > 0 && lineData.length > 0) {
                // 计算每个时刻的累计均价 (VWAP-like)
                let totalVol = 0;
                let totalAmt = 0;
                const avgPriceData = lineData.map((d, index) => {
                    const vol = volumeData[index]?.value || 1;
                    totalVol += vol;
                    totalAmt += d.value * vol;
                    return {
                        time: (index * 60) as UTCTimestamp,
                        value: totalVol === 0 ? d.value : totalAmt / totalVol,
                    };
                });

                const avgSeries = chart.addSeries(LineSeries, {
                    color: '#faad14',  // 黄色
                    lineWidth: 1,
                    priceScaleId: 'left',
                    crosshairMarkerVisible: false,
                });
                avgSeries.setData(avgPriceData);
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
                    top: 0.75, // 位于底部 25% (75% - 100%)
                    bottom: 0,
                },
            });
            volumeSeries.setData(formattedVolumeData);
        }

        // 添加分隔线 (在 Price 和 Volume 之间)
        {
            const dividerSeries = chart.addSeries(HistogramSeries, {
                color: 'rgba(0, 0, 0, 0.05)', // 非常淡的背景色，或者也可以不加
                priceScaleId: 'divider',
                priceFormat: { type: 'volume' },
            });
            // 确保分隔线不显示任何内容，或者我们用它来画一条横线
            // 这里我们主要依赖 gap (Top 65% - 75%)
            dividerSeries.priceScale().applyOptions({
                scaleMargins: {
                    top: 0.75,
                    bottom: 0,
                },
                visible: false, // 隐藏坐标轴
            });
        }


        // 添加日期分隔线（使用 Histogram Series 实现垂直线）
        if (dateSeparatorsRef.current.length > 0 && formattedLineData.length > 0) {
            const separatorSeries = chart.addSeries(HistogramSeries, {
                color: '#f0f0f0',  // 浅灰色垂直线
                priceScaleId: 'overlay',  // 使用独立覆盖层
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
                // 规范化时间格式进行匹配（处理 "09:45" vs "9:45" 等差异）
                const normalizeTime = (t: string) => {
                    const parts = t.split(':');
                    const h = parseInt(parts[0], 10);
                    const m = parseInt(parts[1], 10);
                    return `${h}:${m.toString().padStart(2, '0')}`;
                };

                const normalizedSignalTime = normalizeTime(s.time);
                const signalIndex = lineData.findIndex(d => {
                    const normalizedDataTime = normalizeTime(d.time);
                    return normalizedDataTime === normalizedSignalTime;
                });



                // 使用 formattedLineData 中的真正时间戳
                const time = signalIndex >= 0 && formattedLineData[signalIndex]
                    ? formattedLineData[signalIndex].time
                    : 0;

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
            // 使用 v5 API: createSeriesMarkers

            if (seriesRef.current && markers.length > 0) {
                try {
                    // v5 API: createSeriesMarkers(series, markers)
                    createSeriesMarkers(seriesRef.current, markers);
                } catch (err) {
                    console.error('[Markers] Error creating markers:', err);
                }
            }
        }

        // rightOffset 在 timeScale 选项中已设置，这里不再调用 setVisibleLogicalRange
        // 以避免覆盖 rightOffset 的效果



        // Tooltip 逻辑
        const toolTipWidth = 120;
        const toolTipHeight = 160;
        const toolTipMargin = 15;

        // 创建 Tooltip 元素
        const toolTip = document.createElement('div');
        toolTip.style.width = '140px';
        toolTip.style.height = 'auto';
        toolTip.style.position = 'absolute';
        toolTip.style.display = 'none';
        toolTip.style.padding = '8px';
        toolTip.style.boxSizing = 'border-box';
        toolTip.style.fontSize = '12px';
        toolTip.style.textAlign = 'left';
        toolTip.style.zIndex = '1000';
        toolTip.style.top = '12px';
        toolTip.style.left = '12px';
        toolTip.style.pointerEvents = 'none';
        toolTip.style.border = '1px solid #f0f0f0';
        toolTip.style.borderRadius = '4px';
        toolTip.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.15)';
        toolTip.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
        toolTip.style.color = '#333';
        toolTip.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

        containerRef.current.appendChild(toolTip);

        // 订阅十字光标移动
        chart.subscribeCrosshairMove(param => {
            if (
                param.point === undefined ||
                !param.time ||
                param.point.x < 0 ||
                param.point.x > containerRef.current!.clientWidth ||
                param.point.y < 0 ||
                param.point.y > containerRef.current!.clientHeight
            ) {
                toolTip.style.display = 'none';
                return;
            }

            // 获取数据
            const timeIndex = Math.round(param.time as number / 60);
            const dataIndex = formattedLineData.findIndex(d => (d.time as number) / 60 === timeIndex);

            // 尝试直接获取 Series 数据
            let price = 0;
            let volume = 0;

            // 从 lineData 中查找（更可靠）
            if (dataIndex >= 0 && dataIndex < lineData.length) {
                price = lineData[dataIndex].value;
            } else {
                // 如果找不到原始数据，尝试从 seriesData 获取
                // 注意：seriesRef 可能是 Candle 或 Line，这里简化处理
                // @ts-ignore
                const priceData = param.seriesData.get(seriesRef.current);
                if (priceData) price = priceData.value || priceData.close || 0;
            }

            // 获取成交量
            if (formattedVolumeData.length > 0 && dataIndex >= 0 && dataIndex < volumeData.length) {
                volume = volumeData[dataIndex].value;
            }

            // 计算涨跌幅
            const effectiveBase = basePrice || (lineData.length > 0 ? lineData[0].value : 0);
            const change = price - effectiveBase;
            const changePercent = effectiveBase ? (change / effectiveBase) * 100 : 0;
            const color = change >= 0 ? '#ef5350' : '#26a69a';

            // 均价 (这里简单模拟：成交额/成交量，如果数据里有均价更好。暂时用 VWAP 代替或不显示)
            const avgPrice = vwapValue || price; // 临时替代

            // 格式化时间
            const timeStr = timeLabelsRef.current[dataIndex] || minuteIndexToTime(timeIndex);
            let dateStr = datesRef.current[dataIndex];
            if (dateStr) {
                // MM-DD
                const parts = dateStr.split('-');
                if (parts.length === 3) dateStr = `${parts[1]}-${parts[2]}`;
            }

            toolTip.style.display = 'block';
            toolTip.innerHTML = `
                <div style="margin-bottom: 4px; color: #666;">${dateStr || ''} ${timeStr}</div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #666;">价格</span>
                    <span style="color: ${color}; font-weight: bold;">${price.toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #666;">涨跌额</span>
                    <span style="color: ${color};">${change > 0 ? '+' : ''}${change.toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #666;">涨跌幅</span>
                    <span style="color: ${color};">${changePercent > 0 ? '+' : ''}${changePercent.toFixed(2)}%</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #666;">均价</span>
                    <span style="text-align: right;">${avgPrice.toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #666;">成交量</span>
                    <span style="text-align: right;">${volume}手</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #666;">成交额</span>
                    <span style="text-align: right;">--万</span>
                </div>
            `;

            // 动态定位
            const coordinate = seriesRef.current!.priceToCoordinate(price);
            let left = param.point.x + toolTipMargin;
            let top = param.point.y + toolTipMargin;

            // 防止溢出边界
            if (left + 140 > containerRef.current!.clientWidth) {
                left = param.point.x - 140 - toolTipMargin;
            }
            if (top + 160 > containerRef.current!.clientHeight) {
                top = param.point.y - 160 - toolTipMargin;
            }

            toolTip.style.left = left + 'px';
            toolTip.style.top = top + 'px';
        });

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
            chart.unsubscribeCrosshairMove(() => { }); // 取消订阅
            if (containerRef.current && toolTip.parentNode === containerRef.current) {
                containerRef.current.removeChild(toolTip);
            }
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
