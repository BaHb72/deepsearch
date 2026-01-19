
import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface SectorData {
    concept_code: string;
    name: string;
    velocity: number;
    total_volume?: number;
    lead_stock: string;
    lead_change: number;
}

interface SectorRadarProps {
    data: SectorData[];
}

const SectorRadar: React.FC<SectorRadarProps> = ({ data }) => {
    const getOption = useMemo(() => {
        // 如果没有数据，返回空图表配置
        if (!data || data.length === 0) {
            return {
                backgroundColor: 'transparent',
                title: {
                    text: '暂无数据',
                    left: 'center',
                    top: 'center',
                    textStyle: { color: '#ffffff' }
                }
            };
        }

        // Transform data for Bubble Chart
        // X: Velocity (Flow Speed)
        // Y: Lead Stock Change % (Strength)
        // Size: Fixed or Volume
        // Color: Red/Green based on velocity

        const seriesData = data.map(item => {
            const velocity = item.velocity || 0;
            const leadChange = (item.lead_change || 0) * 100;
            return {
                name: item.name || 'Unknown',
                value: [
                    velocity, // X
                    leadChange, // Y (%)
                    velocity, // Size dimension (mapped)
                    item.lead_stock || 'N/A', // Extra info
                    item.concept_code || ''
                ]
            };
        });

        return {
            backgroundColor: 'transparent',
            tooltip: {
                formatter (params: any) {
                    const val = params.data.value;
                    return `
                        <div style="font-weight:bold">${params.data.name}</div>
                        Velocity: ${(val[0] || 0).toFixed(2)}<br/>
                        Lead Stock: ${val[3]} (${(val[1] || 0).toFixed(2)}%)
                    `;
                }
            },
            xAxis: {
                name: 'Flow Velocity',
                splitLine: { show: false },
                axisLine: { lineStyle: { color: '#888' } }
            },
            yAxis: {
                name: 'Lead Change %',
                splitLine: { lineStyle: { type: 'dashed', color: '#333' } },
                axisLine: { lineStyle: { color: '#888' } }
            },
            visualMap: {
                show: false,
                dimension: 0,
                min: -1000000,
                max: 1000000,
                inRange: {
                    color: ['#ef4444', '#3b82f6', '#22c55e'] // Red(Out) -> Blue(Neutral) -> Green(In)
                }
            },
            series: [{
                type: 'scatter',
                symbolSize (data: any) {
                    // Log scale for size or clamped
                    const v = Math.abs(data[2] || 0);
                    return Math.min(Math.max(Math.log(v + 1) * 3 + 5, 10), 50);
                },
                data: seriesData,
                itemStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(255, 255, 255, 0.5)'
                },
                label: {
                    show: true,
                    formatter: '{b}',
                    position: 'top',
                    color: '#fff'
                }
            }]
        };
    }, [data]);

    return (
        <Card className="h-full w-full border-zinc-800 bg-zinc-950/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-zinc-200">Sector Flow Radar</CardTitle>
            </CardHeader>
            <CardContent className="h-[400px]">
                <ReactECharts
                    option={getOption}
                    style={{ height: '100%', width: '100%' }}
                    theme="dark"
                    opts={{ renderer: 'canvas' }}
                />
            </CardContent>
        </Card>
    );
};

export default SectorRadar;
