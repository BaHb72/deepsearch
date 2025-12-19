
import React, { useEffect, useRef, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { conceptApi, ConceptLinkage } from "@/api/amazingdata";

interface Node {
    id: string;
    name: string;
    val: number; // radius
    color?: string;
    type: 'stock' | 'concept';
}

interface Link {
    source: string;
    target: string;
}

interface GraphData {
    nodes: Node[];
    links: Link[];
}

interface ConceptGraphProps {
    stockCode?: string;
}


const ConceptGraph: React.FC<ConceptGraphProps> = ({ stockCode }) => {
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const graphRef = useRef<any>(null);

    // 将API响应转换为图谱数据
    const transformToGraphData = useCallback((linkageData: ConceptLinkage, centerCode: string): GraphData => {
        const nodes: Node[] = [];
        const links: Link[] = [];
        const nodeSet = new Set<string>();

        // 添加中心股票节点
        if (!nodeSet.has(centerCode)) {
            nodes.push({
                id: centerCode,
                name: centerCode,
                val: 20,
                color: "#ffffff",
                type: 'stock'
            });
            nodeSet.add(centerCode);
        }

        // 添加概念节点和关联股票
        for (const concept of linkageData.concepts) {
            // 添加概念节点
            if (!nodeSet.has(concept.code)) {
                nodes.push({
                    id: concept.code,
                    name: concept.name || concept.code,
                    val: 15,
                    color: "#3b82f6",
                    type: 'concept'
                });
                nodeSet.add(concept.code);
            }

            // 连接中心股票到概念
            links.push({
                source: centerCode,
                target: concept.code
            });

            // 添加关联股票节点
            for (const peer of concept.peers.slice(0, 5)) { // 限制每个概念最多5个关联股票
                if (peer !== centerCode && !nodeSet.has(peer)) {
                    nodes.push({
                        id: peer,
                        name: peer,
                        val: 10,
                        color: "#94a3b8",
                        type: 'stock'
                    });
                    nodeSet.add(peer);
                }

                // 连接概念到关联股票
                if (peer !== centerCode) {
                    links.push({
                        source: concept.code,
                        target: peer
                    });
                }
            }
        }

        return { nodes, links };
    }, []);

    // 获取概念联动数据
    const fetchLinkageData = useCallback(async (code: string) => {
        setLoading(true);
        setError(null);

        try {
            // 使用 amazingdata API 客户端
            const result = await conceptApi.getLinkage(code) as unknown as { success: boolean; data?: ConceptLinkage; error?: string };

            if (result.success && result.data) {
                const graphData = transformToGraphData(result.data, code);
                setData(graphData);
            } else {
                // 如果API没有数据，显示一个简单的占位图
                setData({
                    nodes: [{ id: code, name: code, val: 20, color: "#ffffff", type: 'stock' }],
                    links: []
                });
                if (result.error) {
                    setError(result.error);
                }
            }
        } catch (err) {
            console.error('Failed to fetch linkage data:', err);
            setError(err instanceof Error ? err.message : '获取联动数据失败');
            // 显示占位节点
            setData({
                nodes: [{ id: code, name: code, val: 20, color: "#ffffff", type: 'stock' }],
                links: []
            });
        } finally {
            setLoading(false);
        }
    }, [transformToGraphData]);

    useEffect(() => {
        if (stockCode) {
            fetchLinkageData(stockCode);
        }
    }, [stockCode, fetchLinkageData]);

    return (
        <Card className="h-full w-full border-zinc-800 bg-zinc-950/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-zinc-200 flex items-center justify-between">
                    <span>Values Chain Analysis</span>
                    {loading && <span className="text-xs text-zinc-500">Loading...</span>}
                </CardTitle>
            </CardHeader>
            <CardContent className="h-[400px] overflow-hidden relative">
                {error && (
                    <div className="absolute top-2 left-2 right-2 bg-red-500/10 border border-red-500/30 text-red-400 px-2 py-1 rounded text-xs z-10">
                        {error}
                    </div>
                )}
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/50 z-20">
                        <span className="text-zinc-400">Loading...</span>
                    </div>
                )}
                {!loading && data.nodes.length === 0 && !error && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-white">暂无联动数据</span>
                    </div>
                )}
                {data.nodes.length > 0 && (
                    <ForceGraph2D
                        ref={graphRef}
                        graphData={data}
                        nodeLabel="name"
                        nodeColor="color"
                        backgroundColor="rgba(0,0,0,0)"
                        width={800}
                        height={400}
                        linkColor={() => "rgba(255,255,255,0.2)"}
                        nodeCanvasObject={(node: any, ctx, globalScale) => {
                            const label = node.name;
                            const fontSize = 12 / globalScale;
                            ctx.font = `${fontSize}px Sans-Serif`;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillStyle = node.color || '#ffffff';

                            // 绘制节点圆形
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, node.val / 2, 0, 2 * Math.PI, false);
                            ctx.fill();

                            // 绘制标签
                            ctx.fillStyle = '#ffffff';
                            ctx.fillText(label, node.x, node.y + node.val / 2 + fontSize);
                        }}
                    />
                )}
            </CardContent>
        </Card>
    );
};

export default ConceptGraph;
