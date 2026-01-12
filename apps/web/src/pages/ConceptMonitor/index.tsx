
import React, { useState, useEffect, useCallback } from 'react';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import SectorRadar from "@/components/SectorRadar";
import ConceptGraph from "@/components/ConceptGraph";
import { conceptApi, SectorVelocity } from "@/api/amazingdata";

const ConceptMonitor: React.FC = () => {
    const selectedStock = '600519'; // 默认股票，未来可改为用户选择
    const [status, setStatus] = useState<string>('Disconnected');
    const [sectorData, setSectorData] = useState<SectorVelocity[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // 获取板块资金流速数据
    const fetchSectorVelocity = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // axios 响应拦截器已返回 response.data，所以这里直接得到 ApiResponse 对象
            const result = await conceptApi.getVelocity(50) as unknown as { success: boolean; data?: SectorVelocity[]; error?: string };

            if (result.success && result.data) {
                setSectorData(result.data);
                setStatus('Connected (API)');
            } else {
                setError(result.error || '获取数据失败');
                setStatus('Error');
            }
        } catch (err) {
            console.error('Failed to fetch sector velocity:', err);
            setError(err instanceof Error ? err.message : '网络错误');
            setStatus('Error');
        } finally {
            setLoading(false);
        }
    }, []);



    // 初始化加载数据并设置定时刷新
    useEffect(() => {
        fetchSectorVelocity();

        // 每30秒刷新一次数据
        const interval = setInterval(() => {
            fetchSectorVelocity();
        }, 30000);

        return () => clearInterval(interval);
    }, [fetchSectorVelocity]);



    const connectWebSocket = () => {
        // 手动刷新数据
        fetchSectorVelocity();
    };

    return (
        <div className="p-6 h-screen w-full bg-background text-foreground flex flex-col gap-4 overflow-hidden">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold tracking-tight">Concept & Fund Flow Monitor</h1>
                <div className="flex gap-2 items-center">
                    <span className="text-sm text-muted-foreground">
                        {loading ? 'Loading...' : status}
                    </span>
                    <Button onClick={connectWebSocket} variant="outline" size="sm" disabled={loading}>
                        {loading ? 'Refreshing...' : 'Refresh'}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded-md text-sm">
                    {error}
                </div>
            )}

            <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
                {/* Left Panel: Sector Radar - 7 cols */}
                <div className="col-span-12 lg:col-span-7 h-full flex flex-col gap-4">
                    <SectorRadar data={sectorData} />

                    {/* Bottom: Ticker / Alerts */}
                    <Card className="flex-1 border-zinc-800 bg-zinc-950/50 p-4">
                        <h3 className="text-sm font-semibold mb-2">Real-time Alerts</h3>
                        <div className="space-y-1 text-xs font-mono text-zinc-400">
                            {sectorData.length > 0 ? (
                                sectorData.slice(0, 5).map((sector, index) => (
                                    <div key={sector.concept_code || index}>
                                        {new Date().toLocaleTimeString()} [{sector.name}]
                                        Lead: {sector.lead_stock} ({(sector.lead_change * 100).toFixed(2)}%)
                                        Velocity: {sector.velocity?.toFixed(2) || 'N/A'}
                                    </div>
                                ))
                            ) : (
                                <div>暂无实时数据</div>
                            )}
                        </div>
                    </Card>
                </div>

                {/* Right Panel: Concept Graph - 5 cols */}
                <div className="col-span-12 lg:col-span-5 h-full">
                    <ConceptGraph stockCode={selectedStock} />
                </div>
            </div>
        </div>
    );
};

export default ConceptMonitor;
