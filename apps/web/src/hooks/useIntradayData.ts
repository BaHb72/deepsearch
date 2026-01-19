/**
 * 分时数据管理 Hook
 *
 * 负责分时数据的获取、缓存和动态加载
 * 与 TradingViewChart 组件配合使用
 */
import { useState, useCallback, useRef } from 'react';
import { strategyCenterAPI, IntradayBar } from '../api/strategy-center';
import { timestampToBeijingTime } from '../utils/timeFormat';

export interface UseIntradayDataOptions {
    /** 初始加载的分钟数 */
    initialMinutes?: number;
    /** 每次加载更多的天数 */
    loadMoreDays?: number;
}

export interface UseIntradayDataResult {
    /** 分时数据 */
    bars: IntradayBar[];
    /** 当前价格 */
    currentPrice: number;
    /** VWAP */
    vwap: number;
    /** 是否正在加载 */
    loading: boolean;
    /** 是否正在加载更多 */
    loadingMore: boolean;
    /** 错误信息 */
    error: string | null;
    /** 加载指定股票的分时数据 */
    loadData: (symbol: string) => Promise<void>;
    /** 加载更多历史数据 */
    loadMore: (earliestTime: number) => Promise<{
        lineData?: Array<{ time: string; value: number }>;
        volumeData?: Array<{ time: string; value: number }>;
    } | null>;
    /** 清空数据 */
    clear: () => void;
}

/**
 * 分时数据管理 Hook
 */
export function useIntradayData(
    options: UseIntradayDataOptions = {}
): UseIntradayDataResult {
    const { initialMinutes = 60, loadMoreDays = 1 } = options;

    const [bars, setBars] = useState<IntradayBar[]>([]);
    const [currentPrice, setCurrentPrice] = useState(0);
    const [vwap, setVwap] = useState(0);
    const [loading, setLoading] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 记录当前股票代码
    const symbolRef = useRef<string>('');
    // 记录已加载的最早日期
    const earliestDateRef = useRef<Date>(new Date());

    /**
     * 加载指定股票的分时数据
     */
    const loadData = useCallback(async (symbol: string) => {
        if (!symbol) return;

        setLoading(true);
        setError(null);
        symbolRef.current = symbol;
        earliestDateRef.current = new Date();

        try {
            const data = await strategyCenterAPI.getIntradayData(symbol, initialMinutes);
            setBars(data.bars || []);
            setCurrentPrice(data.current_price || 0);
            setVwap(data.vwap || 0);
        } catch (err) {
            console.error('Failed to load intraday data:', err);
            setError('加载分时数据失败');
            setBars([]);
        } finally {
            setLoading(false);
        }
    }, [initialMinutes]);

    /**
     * 加载更多历史数据
     */
    const loadMore = useCallback(async (_earliestTime: number) => {
        if (!symbolRef.current || loadingMore) return null;

        setLoadingMore(true);

        try {
            // 计算需要加载的时间范围
            const toDate = new Date(earliestDateRef.current);
            toDate.setDate(toDate.getDate() - 1); // 前一天结束

            const fromDate = new Date(toDate);
            fromDate.setDate(fromDate.getDate() - loadMoreDays + 1); // loadMoreDays 天前开始

            // 使用 K 线 API 获取历史数据
            const result = await strategyCenterAPI.getKLineData(
                symbolRef.current,
                '1m',
                fromDate.getTime(),
                toDate.getTime()
            );

            if (result.bars && result.bars.length > 0) {
                // 转换数据格式
                const newBars: IntradayBar[] = result.bars.map(bar => ({
                    // 使用北京时区工具函数进行时间转换
                    time: timestampToBeijingTime(bar.timestamp),
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close,
                    volume: bar.volume,
                }));

                // 合并数据 (新数据在前)
                setBars(prev => [...newBars, ...prev]);

                // 更新最早日期
                earliestDateRef.current = fromDate;

                // 返回格式化后的数据供图表使用
                return {
                    lineData: newBars.map(b => ({ time: b.time, value: b.close })),
                    volumeData: newBars.map(b => ({ time: b.time, value: b.volume })),
                };
            }

            return null;
        } catch (err) {
            console.error('Failed to load more data:', err);
            return null;
        } finally {
            setLoadingMore(false);
        }
    }, [loadMoreDays, loadingMore]);

    /**
     * 清空数据
     */
    const clear = useCallback(() => {
        setBars([]);
        setCurrentPrice(0);
        setVwap(0);
        setError(null);
        symbolRef.current = '';
    }, []);

    return {
        bars,
        currentPrice,
        vwap,
        loading,
        loadingMore,
        error,
        loadData,
        loadMore,
        clear,
    };
}

export default useIntradayData;
