/**
 * 内存管理页面
 *
 * 功能:
 * - 实时内存统计显示
 * - 手动/自动 GC 控制
 * - GC 历史记录查看 (列表 + 图表标记)
 * - 内存趋势图 (ECharts)
 * - 进程分布图 (Pie Chart)
 * - tracemalloc 泄漏检测
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
    Button,
    Statistic,
    Space,
    message,
    Typography,
    Table,
    Switch,
    InputNumber,
    Tag,
    Divider,
    Alert,
    Timeline,
    Row,
    Col,
    Empty,
    Badge,
} from 'antd';
import {
    ReloadOutlined,
    PlayCircleOutlined,
    PauseCircleOutlined,
    ClearOutlined,
    CameraOutlined,
    SettingOutlined,
    HistoryOutlined,
    BugOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

// API 基础路径
const API_BASE = '/api/system/memory';

// 类型定义
interface MemoryStats {
    process_id: number;
    rss_mb: number;
    vms_mb: number;
    threads: number;
    open_files: number;
    gc_counts: number[];
    gc_thresholds: number[];
    python_objects: number;
}

interface GCConfig {
    gc_enabled: boolean;
    gc_interval_seconds: number;
    gc_log_enabled: boolean;
    gc_task_running: boolean;
    last_gc_time: string | null;
}

interface GCHistoryItem {
    collected: number[];
    uncollectable: number;
    duration_ms: number;
    memory_before_mb: number;
    memory_after_mb: number;
    memory_freed_mb: number;
    timestamp: string;
}

interface ProcessInfo {
    pid: number;
    name: string;
    rss_mb: number;
    threads: number;
}

interface TraceStatus {
    is_tracing: boolean;
    current_mb: number;
    peak_mb: number;
    snapshots: string[];
}

interface TrendPoint {
    time: string;
    value: number;
    type?: 'stats' | 'gc_before' | 'gc_after';
}

// 缓存命名空间统计
interface CacheNamespace {
    namespace: string;
    cache_dir: string;
    cache_files: number;
    total_size_mb: number;
    ttl: number;
    hits: number;
    misses: number;
    writes: number;
    hit_rate: string;
}

interface CacheStats {
    base_dir: string;
    platform: string;
    namespaces: CacheNamespace[];
    total_size_mb: number;
    namespace_count: number;
}

// 缓存配置
interface CacheConfig {
    enabled: boolean;
    base_dir: string | null;
    default_ttl: number;
    namespaces: Record<string, { ttl: number; enabled: boolean }>;
}

// 文件缓存管理卡片组件
const CacheManagementCard: React.FC = () => {
    const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
    const [cacheConfig, setCacheConfig] = useState<CacheConfig | null>(null);
    const [loading, setLoading] = useState(false);
    const [clearingAll, setClearingAll] = useState(false);
    const [clearingNamespace, setClearingNamespace] = useState<string | null>(null);
    const [savingConfig, setSavingConfig] = useState(false);
    const [editTtl, setEditTtl] = useState<number | null>(null);

    const fetchCacheStats = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/cache/stats`);
            const data = await res.json();
            setCacheStats(data);
        } catch (e) {
            console.error('加载缓存统计失败:', e);
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchCacheConfig = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/cache/config`);
            const data = await res.json();
            if (data.success) {
                setCacheConfig(data.config);
                setEditTtl(data.config.default_ttl);
            }
        } catch (e) {
            console.error('加载缓存配置失败:', e);
        }
    }, []);

    useEffect(() => {
        fetchCacheStats();
        fetchCacheConfig();
    }, [fetchCacheStats, fetchCacheConfig]);

    const handleToggleEnabled = async (checked: boolean) => {
        setSavingConfig(true);
        try {
            const res = await fetch(`${API_BASE}/cache/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: checked }),
            });
            const data = await res.json();
            if (data.success) {
                message.success(checked ? '缓存已启用' : '缓存已禁用');
                fetchCacheConfig();
            }
        } catch {
            message.error('更新配置失败');
        } finally {
            setSavingConfig(false);
        }
    };

    const handleSaveTtl = async () => {
        if (editTtl === null || editTtl === cacheConfig?.default_ttl) return;
        setSavingConfig(true);
        try {
            const res = await fetch(`${API_BASE}/cache/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ default_ttl: editTtl }),
            });
            const data = await res.json();
            if (data.success) {
                message.success(`TTL 已更新为 ${editTtl} 秒`);
                fetchCacheConfig();
            }
        } catch {
            message.error('更新 TTL 失败');
        } finally {
            setSavingConfig(false);
        }
    };

    const handleClearAll = async () => {
        setClearingAll(true);
        try {
            const res = await fetch(`${API_BASE}/cache`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                message.success(`已清除所有缓存: ${data.total_cleared} 条目`);
                fetchCacheStats();
            }
        } catch {
            message.error('清除缓存失败');
        } finally {
            setClearingAll(false);
        }
    };

    const handleClearNamespace = async (namespace: string) => {
        setClearingNamespace(namespace);
        try {
            const res = await fetch(`${API_BASE}/cache/${namespace}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                message.success(`已清除 ${namespace} 缓存: ${data.cleared} 条目`);
                fetchCacheStats();
            }
        } catch {
            message.error(`清除 ${namespace} 缓存失败`);
        } finally {
            setClearingNamespace(null);
        }
    };

    const columns = [
        { title: '命名空间', dataIndex: 'namespace', key: 'namespace' },
        { title: '文件数', dataIndex: 'cache_files', key: 'cache_files' },
        {
            title: '大小 (MB)',
            dataIndex: 'total_size_mb',
            key: 'total_size_mb',
            render: (v: number) => v?.toFixed(2)
        },
        { title: 'TTL (秒)', dataIndex: 'ttl', key: 'ttl' },
        { title: '命中率', dataIndex: 'hit_rate', key: 'hit_rate' },
        {
            title: '操作',
            key: 'action',
            render: (_: unknown, record: CacheNamespace) => (
                <Button
                    size="small"
                    danger
                    loading={clearingNamespace === record.namespace}
                    onClick={() => handleClearNamespace(record.namespace)}
                >
                    清除
                </Button>
            )
        }
    ];

    return (
        <ProCard
            title={<><ClearOutlined /> 文件缓存管理</>}
            extra={
                <Space>
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={fetchCacheStats}
                        loading={loading}
                    >
                        刷新
                    </Button>
                    <Button
                        danger
                        icon={<ClearOutlined />}
                        onClick={handleClearAll}
                        loading={clearingAll}
                        disabled={!cacheStats?.namespaces?.length}
                    >
                        清除所有缓存
                    </Button>
                </Space>
            }
        >
            <Space direction="vertical" style={{ width: '100%' }}>
                {/* 缓存配置 */}
                <Row gutter={16} align="middle">
                    <Col span={6}>
                        <Space>
                            <Text strong>启用缓存:</Text>
                            <Switch
                                checked={cacheConfig?.enabled ?? true}
                                onChange={handleToggleEnabled}
                                loading={savingConfig}
                            />
                            {cacheConfig?.enabled ? (
                                <Tag color="green">已启用</Tag>
                            ) : (
                                <Tag color="red">已禁用</Tag>
                            )}
                        </Space>
                    </Col>
                    <Col span={8}>
                        <Space>
                            <Text strong>默认 TTL:</Text>
                            <InputNumber
                                min={1}
                                max={86400}
                                value={editTtl ?? cacheConfig?.default_ttl}
                                onChange={(v) => setEditTtl(v as number)}
                                addonAfter="秒"
                                style={{ width: 120 }}
                            />
                            <Button
                                size="small"
                                type="primary"
                                onClick={handleSaveTtl}
                                disabled={editTtl === cacheConfig?.default_ttl}
                                loading={savingConfig}
                            >
                                保存
                            </Button>
                        </Space>
                    </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 缓存概览 */}
                <Row gutter={16}>
                    <Col span={8}>
                        <Statistic
                            title="缓存目录"
                            value={cacheStats?.base_dir || '-'}
                            valueStyle={{ fontSize: 14 }}
                        />
                    </Col>
                    <Col span={4}>
                        <Statistic
                            title="平台"
                            value={cacheStats?.platform || '-'}
                        />
                    </Col>
                    <Col span={4}>
                        <Statistic
                            title="命名空间数"
                            value={cacheStats?.namespace_count || 0}
                        />
                    </Col>
                    <Col span={4}>
                        <Statistic
                            title="总大小 (MB)"
                            value={cacheStats?.total_size_mb?.toFixed(2) || '0.00'}
                        />
                    </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 命名空间列表 */}
                {cacheStats?.namespaces?.length ? (
                    <Table
                        dataSource={cacheStats.namespaces}
                        columns={columns}
                        rowKey="namespace"
                        size="small"
                        pagination={false}
                    />
                ) : (
                    <Empty description="暂无缓存数据" />
                )}
            </Space>
        </ProCard>
    );
};

// L2 RAM 缓冲区配置接口
interface L2Config {
    enabled: boolean;
    max_pinned_stocks: number;
    default_capacity: number;
    max_capacity: number;
    auto_unpin_idle_seconds: number;
    total_memory_limit_mb: number;
}

interface PinnedStock {
    code: string;
    since: string;
    buffer_kb: number;
    size: number;
    capacity: number;
    last_access: string;
}

interface L2Stats {
    enabled: boolean;
    pinned_count: number;
    max_pinned: number;
    total_memory_kb: number;
    memory_limit_mb: number;
    memory_usage_pct: number;
    writes: number;
    reads: number;
    pinned: PinnedStock[];
    config: L2Config;
}

// L2 RAM 缓冲区管理卡片
const L2RamBufferCard: React.FC = () => {
    const [stats, setStats] = useState<L2Stats | null>(null);
    const [config, setConfig] = useState<L2Config | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [pinInput, setPinInput] = useState('');
    const [pinning, setPinning] = useState(false);

    // 编辑状态
    const [editMaxPinned, setEditMaxPinned] = useState<number | null>(null);
    const [editCapacity, setEditCapacity] = useState<number | null>(null);
    const [editMemoryLimit, setEditMemoryLimit] = useState<number | null>(null);

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/l2/pinned`);
            const data = await res.json();
            if (data.success) {
                setStats(data.data);
                setConfig(data.data.config);
                setEditMaxPinned(data.data.config.max_pinned_stocks);
                setEditCapacity(data.data.config.default_capacity);
                setEditMemoryLimit(data.data.config.total_memory_limit_mb);
            }
        } catch (e) {
            console.error('加载 L2 统计失败:', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStats();
    }, [fetchStats]);

    const handleToggleEnabled = async (checked: boolean) => {
        setSaving(true);
        try {
            const res = await fetch(`${API_BASE}/l2/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: checked }),
            });
            const data = await res.json();
            if (data.success) {
                message.success(checked ? 'RAM 缓冲区已启用' : 'RAM 缓冲区已禁用');
                fetchStats();
            }
        } catch {
            message.error('更新配置失败');
        } finally {
            setSaving(false);
        }
    };

    const handleSaveConfig = async () => {
        setSaving(true);
        try {
            const updates: Record<string, number> = {};
            if (editMaxPinned !== config?.max_pinned_stocks) updates.max_pinned_stocks = editMaxPinned!;
            if (editCapacity !== config?.default_capacity) updates.default_capacity = editCapacity!;
            if (editMemoryLimit !== config?.total_memory_limit_mb) updates.total_memory_limit_mb = editMemoryLimit!;

            if (Object.keys(updates).length === 0) {
                message.info('没有需要保存的更改');
                setSaving(false);
                return;
            }

            const res = await fetch(`${API_BASE}/l2/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates),
            });
            const data = await res.json();
            if (data.success) {
                message.success('配置已保存');
                fetchStats();
            }
        } catch {
            message.error('保存配置失败');
        } finally {
            setSaving(false);
        }
    };

    const handlePin = async () => {
        if (!pinInput.trim()) return;
        setPinning(true);
        try {
            const codes = pinInput.split(',').map(s => s.trim()).filter(Boolean);
            const res = await fetch(`${API_BASE}/l2/pin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ codes }),
            });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                setPinInput('');
                fetchStats();
            }
        } catch {
            message.error('钉住失败');
        } finally {
            setPinning(false);
        }
    };

    const handleUnpin = async (code: string) => {
        try {
            const res = await fetch(`${API_BASE}/l2/pin/${code}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                message.success(`已取消钉住 ${code}`);
                fetchStats();
            }
        } catch {
            message.error('取消钉住失败');
        }
    };

    const handleClearAll = async () => {
        try {
            const res = await fetch(`${API_BASE}/l2/pinned`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                fetchStats();
            }
        } catch {
            message.error('清空失败');
        }
    };

    const columns = [
        { title: '股票代码', dataIndex: 'code', key: 'code' },
        { title: '缓冲(KB)', dataIndex: 'buffer_kb', key: 'buffer_kb' },
        { title: '数据量', dataIndex: 'size', key: 'size' },
        { title: '容量', dataIndex: 'capacity', key: 'capacity' },
        {
            title: '操作',
            key: 'action',
            render: (_: unknown, record: PinnedStock) => (
                <Button size="small" danger onClick={() => handleUnpin(record.code)}>
                    取消钉住
                </Button>
            ),
        },
    ];

    return (
        <ProCard
            title={<><ThunderboltOutlined /> L2 RAM 缓冲区 (纯内存)</>}
            extra={
                <Space>
                    <Button icon={<ReloadOutlined />} onClick={fetchStats} loading={loading}>
                        刷新
                    </Button>
                    <Button danger icon={<ClearOutlined />} onClick={handleClearAll} disabled={!stats?.pinned?.length}>
                        清空全部
                    </Button>
                </Space>
            }
        >
            <Space direction="vertical" style={{ width: '100%' }}>
                {/* 配置区域 */}
                <Row gutter={16} align="middle">
                    <Col span={4}>
                        <Space>
                            <Text strong>启用:</Text>
                            <Switch
                                checked={config?.enabled ?? true}
                                onChange={handleToggleEnabled}
                                loading={saving}
                            />
                            {config?.enabled ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>}
                        </Space>
                    </Col>
                    <Col span={5}>
                        <Space>
                            <Text strong>最大钉住数:</Text>
                            <InputNumber
                                min={1} max={1000}
                                value={editMaxPinned}
                                onChange={(v) => setEditMaxPinned(v as number)}
                                style={{ width: 80 }}
                            />
                        </Space>
                    </Col>
                    <Col span={5}>
                        <Space>
                            <Text strong>默认容量:</Text>
                            <InputNumber
                                min={100} max={10000}
                                value={editCapacity}
                                onChange={(v) => setEditCapacity(v as number)}
                                style={{ width: 80 }}
                            />
                        </Space>
                    </Col>
                    <Col span={5}>
                        <Space>
                            <Text strong>内存上限(MB):</Text>
                            <InputNumber
                                min={10} max={1000}
                                value={editMemoryLimit}
                                onChange={(v) => setEditMemoryLimit(v as number)}
                                style={{ width: 80 }}
                            />
                        </Space>
                    </Col>
                    <Col span={5}>
                        <Button type="primary" onClick={handleSaveConfig} loading={saving}>
                            保存配置
                        </Button>
                    </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 统计信息 */}
                <Row gutter={16}>
                    <Col span={4}>
                        <Statistic title="钉住数" value={stats?.pinned_count || 0} suffix={`/ ${stats?.max_pinned || 100}`} />
                    </Col>
                    <Col span={4}>
                        <Statistic title="内存使用" value={stats?.total_memory_kb?.toFixed(1) || '0'} suffix="KB" />
                    </Col>
                    <Col span={4}>
                        <Statistic title="内存占用" value={stats?.memory_usage_pct || 0} suffix="%" />
                    </Col>
                    <Col span={4}>
                        <Statistic title="写入次数" value={stats?.writes || 0} />
                    </Col>
                    <Col span={4}>
                        <Statistic title="读取次数" value={stats?.reads || 0} />
                    </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 钉住股票 */}
                <Row gutter={16} align="middle">
                    <Col span={12}>
                        <Space>
                            <Text strong>钉住股票:</Text>
                            <input
                                placeholder="输入代码，逗号分隔"
                                value={pinInput}
                                onChange={(e) => setPinInput(e.target.value)}
                                style={{ width: 200, padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
                            />
                            <Button type="primary" onClick={handlePin} loading={pinning}>
                                钉住
                            </Button>
                        </Space>
                    </Col>
                </Row>

                <Divider style={{ margin: '12px 0' }} />

                {/* 钉住列表 */}
                {stats?.pinned?.length ? (
                    <Table
                        dataSource={stats.pinned}
                        columns={columns}
                        rowKey="code"
                        size="small"
                        pagination={false}
                    />
                ) : (
                    <Empty description="暂无钉住的股票" />
                )}
            </Space>
        </ProCard>
    );
};


const MemoryManagement: React.FC = () => {
    // 内存统计
    const [stats, setStats] = useState<MemoryStats | null>(null);
    const [config, setConfig] = useState<GCConfig | null>(null);
    const [processes, setProcesses] = useState<ProcessInfo[]>([]);
    const [gcHistory, setGcHistory] = useState<GCHistoryItem[]>([]);
    const [traceStatus, setTraceStatus] = useState<TraceStatus | null>(null);

    // 图表数据
    const [trendData, setTrendData] = useState<TrendPoint[]>([]);

    // 加载状态
    const [loading, setLoading] = useState(false);
    const [gcLoading, setGcLoading] = useState(false);
    const [traceLoading, setTraceLoading] = useState(false);

    // 自动刷新
    const [autoRefresh, setAutoRefresh] = useState(true);
    const refreshTimerRef = useRef<number | null>(null);

    // 配置编辑
    const [editingInterval, setEditingInterval] = useState<number>(300);

    // 监听实时数据更新趋势图
    useEffect(() => {
        if (stats) {
            setTrendData(prev => {
                const now = new Date().toISOString();
                const newPoint: TrendPoint = {
                    time: now,
                    value: stats.rss_mb,
                    type: 'stats'
                };
                // 保留最近 100 点
                const next = [...prev, newPoint].slice(-100);
                return next;
            });
        }
    }, [stats]);

    // 加载数据
    const loadStats = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/stats`);
            const data = await res.json();
            if (data.success) {
                setStats(data.data.current_process);
                setConfig(data.data.gc_config);
                setEditingInterval(data.data.gc_config?.gc_interval_seconds || 300);
            }
        } catch (e) {
            console.error('加载内存统计失败:', e);
        }
    }, []);

    const loadProcesses = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/all-processes`);
            const data = await res.json();
            if (data.success) {
                setProcesses(data.data.processes || []);
            }
        } catch (e) {
            console.error('加载进程列表失败:', e);
        }
    }, []);

    const loadGcHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/gc/history`);
            const data = await res.json();
            if (data.success) {
                const history = data.data.history || [];
                setGcHistory(history);
            }
        } catch (e) {
            console.error('加载 GC 历史失败:', e);
        }
    }, []);

    const loadTraceStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/trace/status`);
            const data = await res.json();
            if (data.success) {
                setTraceStatus(data.data);
            }
        } catch (e) {
            console.error('加载追踪状态失败:', e);
        }
    }, []);

    const loadAll = useCallback(async () => {
        setLoading(true);
        await Promise.all([loadStats(), loadProcesses(), loadGcHistory(), loadTraceStatus()]);
        setLoading(false);
    }, [loadStats, loadProcesses, loadGcHistory, loadTraceStatus]);

    // 自动刷新
    useEffect(() => {
        loadAll();

        if (autoRefresh) {
            refreshTimerRef.current = window.setInterval(() => {
                loadStats();
                loadProcesses();
            }, 5000);
        }

        return () => {
            if (refreshTimerRef.current) {
                clearInterval(refreshTimerRef.current);
            }
        };
    }, [autoRefresh, loadAll, loadStats, loadProcesses]);

    // 手动触发 GC
    const handleManualGC = async (full: boolean = true) => {
        setGcLoading(true);
        try {
            const res = await fetch(`${API_BASE}/gc?full=${full}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                await loadStats();
                await loadGcHistory();
            } else {
                message.error('GC 执行失败');
            }
        } catch {
            message.error('GC 请求失败');
        } finally {
            setGcLoading(false);
        }
    };

    // 启动/停止定时 GC
    const handleTogglePeriodicGC = async (start: boolean) => {
        try {
            const endpoint = start ? '/gc/start' : '/gc/stop';
            const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                await loadStats();
            }
        } catch {
            message.error('操作失败');
        }
    };

    // 更新配置
    const handleUpdateConfig = async () => {
        try {
            const res = await fetch(`${API_BASE}/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    gc_enabled: config?.gc_enabled ?? true,
                    gc_interval_seconds: editingInterval,
                    gc_log_enabled: config?.gc_log_enabled ?? true,
                }),
            });
            const data = await res.json();
            if (data.success) {
                message.success('配置已更新');
                await loadStats();
            }
        } catch {
            message.error('更新配置失败');
        }
    };

    // tracemalloc 操作
    const handleStartTrace = async () => {
        setTraceLoading(true);
        try {
            const res = await fetch(`${API_BASE}/trace/start`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                await loadTraceStatus();
            } else {
                message.warning(data.message);
            }
        } catch {
            message.error('启动追踪失败');
        } finally {
            setTraceLoading(false);
        }
    };

    const handleStopTrace = async () => {
        setTraceLoading(true);
        try {
            const res = await fetch(`${API_BASE}/trace/stop`, { method: 'POST' });
            const data = await res.json();
            message.info(data.message);
            await loadTraceStatus();
        } catch {
            message.error('停止追踪失败');
        } finally {
            setTraceLoading(false);
        }
    };

    const handleTakeSnapshot = async (name: string) => {
        try {
            const res = await fetch(`${API_BASE}/trace/snapshot?name=${name}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                message.success(data.message);
                await loadTraceStatus();
            } else {
                message.warning(data.message);
            }
        } catch {
            message.error('拍摄快照失败');
        }
    };

    const getMemoryUsageColor = (mb: number): string => {
        if (mb > 4096) return '#ff4d4f';
        if (mb > 2048) return '#faad14';
        return '#52c41a';
    };

    const processColumns = [
        { title: 'PID', dataIndex: 'pid', key: 'pid', width: 80 },
        { title: '进程名', dataIndex: 'name', key: 'name' },
        {
            title: '内存 (MB)',
            dataIndex: 'rss_mb',
            key: 'rss_mb',
            render: (v: number) => (
                <Text style={{ color: getMemoryUsageColor(v), fontWeight: 'bold' }}>
                    {v.toLocaleString()}
                </Text>
            ),
            sorter: (a: ProcessInfo, b: ProcessInfo) => b.rss_mb - a.rss_mb,
            defaultSortOrder: 'descend' as const,
        },
        { title: '线程数', dataIndex: 'threads', key: 'threads', width: 80 },
    ];

    const renderGcTimeline = () => {
        if (gcHistory.length === 0) {
            return <Empty description="暂无 GC 记录" />;
        }

        return (
            <Timeline
                mode="left"
                items={gcHistory.slice(-10).reverse().map((item) => ({
                    color: item.memory_freed_mb > 0 ? 'green' : 'gray',
                    label: new Date(item.timestamp).toLocaleTimeString(),
                    children: (
                        <div>
                            <Text>
                                回收 <Text strong>{(item.collected || []).reduce((a, b) => a + b, 0)}</Text> 对象
                            </Text>
                            <br />
                            <Text type="secondary">
                                释放 {item.memory_freed_mb.toFixed(1)} MB | 耗时 {item.duration_ms.toFixed(1)} ms
                            </Text>
                        </div>
                    ),
                }))}
            />
        );
    };

    // --- 图表配置 ---

    // 1. 内存趋势图配置
    const getTrendOption = useCallback(() => {
        // 合并实时点
        const points: TrendPoint[] = [...trendData];

        // 构造 GC 标记点
        // 过滤出最近 24 小时的 GC 记录
        const now = new Date().getTime();
        const oneDayAgo = now - 24 * 60 * 60 * 1000;

        const validGcHistory = gcHistory.filter(item => {
            const t = new Date(item.timestamp).getTime();
            return t > oneDayAgo;
        });

        const gcMarkPoints = validGcHistory.map(item => ({
            name: 'GC',
            coord: [item.timestamp, item.memory_after_mb],
            value: `-${item.memory_freed_mb.toFixed(1)}M`,
            itemStyle: {
                color: item.memory_freed_mb > 0 ? '#52c41a' : '#faad14'
            },
            label: {
                formatter: '{c}',
                position: 'top',
                distance: 5,
                fontSize: 10
            }
        }));

        return {
            title: { text: '' },
            tooltip: {
                trigger: 'axis',
                formatter: (params: any) => {
                    const p = params[0];
                    if (!p) return '';
                    const date = new Date(p.data[0]);
                    const timeStr = date.toLocaleTimeString();
                    return `${timeStr}<br/>RSS: <b>${p.data[1]} MB</b>`;
                }
            },
            grid: { top: 30, right: 30, bottom: 20, left: 50 },
            xAxis: {
                type: 'time',
                splitLine: { show: false },
                axisLabel: {
                    formatter: '{HH}:{mm}:{ss}'
                }
            },
            yAxis: {
                type: 'value',
                name: 'MB',
                splitLine: { lineStyle: { type: 'dashed', opacity: 0.5 } },
                scale: true // 让Y轴自适应范围
            },
            series: [
                {
                    name: 'RSS 内存',
                    type: 'line',
                    showSymbol: false,
                    smooth: true,
                    data: points.map(p => [p.time, p.value]),
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                                { offset: 1, color: 'rgba(24, 144, 255, 0.05)' }
                            ]
                        }
                    },
                    lineStyle: { color: '#1890ff', width: 2 },
                    markPoint: gcMarkPoints.length > 0 ? {
                        data: gcMarkPoints,
                        symbol: 'pin',
                        symbolSize: 40
                    } : undefined
                }
            ]
        };
    }, [trendData, gcHistory]);

    // 2. 进程分布图配置
    const getDistributionOption = useCallback(() => {
        // 只显示前 8 个大内存进程，其他的归为“其他”
        const sortedProcesses = [...processes].sort((a, b) => b.rss_mb - a.rss_mb);
        let displayData = [];

        if (sortedProcesses.length > 8) {
            const top8 = sortedProcesses.slice(0, 8);
            const others = sortedProcesses.slice(8);
            const otherRss = others.reduce((sum, p) => sum + p.rss_mb, 0);

            displayData = top8.map(p => ({ name: p.name, value: p.rss_mb }));
            displayData.push({ name: '其他进程', value: parseFloat(otherRss.toFixed(2)) });
        } else {
            displayData = sortedProcesses.map(p => ({
                name: p.name,
                value: p.rss_mb
            }));
        }

        return {
            title: { text: '', left: 'center' },
            tooltip: {
                trigger: 'item',
                formatter: '{b}: {c} MB ({d}%)'
            },
            legend: {
                bottom: 0,
                left: 'center',
                type: 'scroll'
            },
            series: [
                {
                    name: '内存占用',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    center: ['50%', '45%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 5,
                        borderColor: '#fff',
                        borderWidth: 2
                    },
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: 14,
                            fontWeight: 'bold'
                        }
                    },
                    labelLine: { show: false },
                    data: displayData
                }
            ]
        };
    }, [processes]);

    return (
        <PageContainer
            title="内存管理"
            subTitle="监控和优化系统内存使用"
            extra={
                <Space>
                    <Badge status={autoRefresh ? 'processing' : 'default'} text="自动刷新" />
                    <Switch
                        checked={autoRefresh}
                        onChange={setAutoRefresh}
                        size="small"
                    />
                    <Button
                        icon={<ReloadOutlined spin={loading} />}
                        onClick={loadAll}
                        loading={loading}
                    >
                        刷新
                    </Button>
                </Space>
            }
        >
            {/* 内存概览 */}
            <ProCard title="内存概览" bordered style={{ marginBottom: 16 }}>
                <Row gutter={[24, 16]}>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="RSS 内存"
                            value={stats?.rss_mb || 0}
                            suffix="MB"
                            valueStyle={{ color: getMemoryUsageColor(stats?.rss_mb || 0) }}
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="虚拟内存"
                            value={stats?.vms_mb || 0}
                            suffix="MB"
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="线程数"
                            value={stats?.threads || 0}
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="Python 对象"
                            value={stats?.python_objects || 0}
                            formatter={(v) => (v as number).toLocaleString()}
                        />
                    </Col>
                </Row>

                <Divider />

                <Row gutter={16} align="middle">
                    <Col>
                        <Text type="secondary">GC 计数 (0/1/2代): </Text>
                        <Text strong>{stats?.gc_counts?.join(' / ') || '-'}</Text>
                    </Col>
                    <Col>
                        <Text type="secondary">GC 阈值: </Text>
                        <Text>{stats?.gc_thresholds?.join(' / ') || '-'}</Text>
                    </Col>
                    <Col>
                        <Text type="secondary">上次 GC: </Text>
                        <Text>
                            {config?.last_gc_time
                                ? new Date(config.last_gc_time).toLocaleString()
                                : '未执行'}
                        </Text>
                    </Col>
                </Row>
            </ProCard>

            {/* 图表视图 (新!) */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col xs={24} lg={16}>
                    <ProCard title="内存趋势监控" bordered style={{ height: '100%' }}>
                        <ReactECharts
                            option={getTrendOption()}
                            style={{ height: 320, width: '100%' }}
                            notMerge={true}
                            theme="light"
                        />
                    </ProCard>
                </Col>
                <Col xs={24} lg={8}>
                    <ProCard title="系统进程分布" bordered style={{ height: '100%' }}>
                        <ReactECharts
                            option={getDistributionOption()}
                            style={{ height: 320, width: '100%' }}
                            notMerge={true}
                            theme="light"
                        />
                    </ProCard>
                </Col>
            </Row>

            <Row gutter={16}>
                {/* 左侧: GC 控制 */}
                <Col xs={24} lg={12}>
                    <ProCard
                        title={
                            <Space>
                                <ThunderboltOutlined />
                                垃圾回收控制
                            </Space>
                        }
                        bordered
                        style={{ marginBottom: 16 }}
                    >
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                            {/* 手动 GC */}
                            <div>
                                <Text strong>手动触发</Text>
                                <div style={{ marginTop: 8 }}>
                                    <Space>
                                        <Button
                                            type="primary"
                                            icon={<ClearOutlined />}
                                            onClick={() => handleManualGC(true)}
                                            loading={gcLoading}
                                        >
                                            完整 GC
                                        </Button>
                                        <Button
                                            icon={<ClearOutlined />}
                                            onClick={() => handleManualGC(false)}
                                            loading={gcLoading}
                                        >
                                            快速 GC (仅0代)
                                        </Button>
                                    </Space>
                                </div>
                            </div>

                            <Divider style={{ margin: '12px 0' }} />

                            {/* 定时 GC */}
                            <div>
                                <Text strong>定时 GC</Text>
                                <div style={{ marginTop: 8 }}>
                                    <Space>
                                        <Tag color={config?.gc_task_running ? 'green' : 'default'}>
                                            {config?.gc_task_running ? '运行中' : '已停止'}
                                        </Tag>
                                        {config?.gc_task_running ? (
                                            <Button
                                                danger
                                                icon={<PauseCircleOutlined />}
                                                onClick={() => handleTogglePeriodicGC(false)}
                                            >
                                                停止
                                            </Button>
                                        ) : (
                                            <Button
                                                type="primary"
                                                icon={<PlayCircleOutlined />}
                                                onClick={() => handleTogglePeriodicGC(true)}
                                            >
                                                启动
                                            </Button>
                                        )}
                                    </Space>
                                </div>
                            </div>

                            <Divider style={{ margin: '12px 0' }} />

                            {/* 配置 */}
                            <div>
                                <Text strong>GC 间隔配置</Text>
                                <div style={{ marginTop: 8 }}>
                                    <Space>
                                        <InputNumber
                                            value={editingInterval}
                                            onChange={(v) => setEditingInterval(v || 300)}
                                            min={60}
                                            max={3600}
                                            addonAfter="秒"
                                            style={{ width: 150 }}
                                        />
                                        <Button
                                            icon={<SettingOutlined />}
                                            onClick={handleUpdateConfig}
                                        >
                                            应用
                                        </Button>
                                    </Space>
                                </div>
                            </div>
                        </Space>
                    </ProCard>

                    {/* GC 历史 */}
                    <ProCard
                        title={
                            <Space>
                                <HistoryOutlined />
                                GC 历史记录
                            </Space>
                        }
                        bordered
                        style={{ marginBottom: 16 }}
                        extra={
                            <Button size="small" onClick={loadGcHistory}>
                                刷新
                            </Button>
                        }
                    >
                        <div style={{ maxHeight: 300, overflow: 'auto' }}>
                            {renderGcTimeline()}
                        </div>
                    </ProCard>
                </Col>

                {/* 右侧: 进程列表 & 泄漏检测 */}
                <Col xs={24} lg={12}>
                    {/* 进程列表 */}
                    <ProCard
                        title="Python 进程列表"
                        bordered
                        style={{ marginBottom: 16 }}
                    >
                        <Table
                            dataSource={processes}
                            columns={processColumns}
                            rowKey="pid"
                            size="small"
                            pagination={false}
                            scroll={{ y: 200 }}
                            summary={(data) => {
                                const totalMb = (data || []).reduce((sum, p) => sum + p.rss_mb, 0);
                                const totalThreads = (data || []).reduce((sum, p) => sum + p.threads, 0);
                                return (
                                    <Table.Summary.Row>
                                        <Table.Summary.Cell index={0} colSpan={2}>
                                            <Text strong>合计</Text>
                                        </Table.Summary.Cell>
                                        <Table.Summary.Cell index={2}>
                                            <Text strong style={{ color: getMemoryUsageColor(totalMb) }}>
                                                {totalMb.toLocaleString()} MB
                                            </Text>
                                        </Table.Summary.Cell>
                                        <Table.Summary.Cell index={3}>
                                            <Text strong>{totalThreads}</Text>
                                        </Table.Summary.Cell>
                                    </Table.Summary.Row>
                                );
                            }}
                        />
                    </ProCard>

                    {/* 泄漏检测 */}
                    <ProCard
                        title={
                            <Space>
                                <BugOutlined />
                                内存泄漏检测 (tracemalloc)
                            </Space>
                        }
                        bordered
                    >
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                            {/* 追踪状态 */}
                            <div>
                                <Text strong>追踪状态: </Text>
                                <Tag color={traceStatus?.is_tracing ? 'processing' : 'default'}>
                                    {traceStatus?.is_tracing ? '追踪中' : '未启动'}
                                </Tag>
                                {traceStatus?.is_tracing && (
                                    <Text type="secondary">
                                        {' '}当前: {traceStatus.current_mb} MB | 峰值: {traceStatus.peak_mb} MB
                                    </Text>
                                )}
                            </div>

                            {/* 控制按钮 */}
                            <Space wrap>
                                {!traceStatus?.is_tracing ? (
                                    <Button
                                        type="primary"
                                        icon={<PlayCircleOutlined />}
                                        onClick={handleStartTrace}
                                        loading={traceLoading}
                                    >
                                        启动追踪
                                    </Button>
                                ) : (
                                    <>
                                        <Button
                                            danger
                                            icon={<PauseCircleOutlined />}
                                            onClick={handleStopTrace}
                                            loading={traceLoading}
                                        >
                                            停止追踪
                                        </Button>
                                        <Button
                                            icon={<CameraOutlined />}
                                            onClick={() => handleTakeSnapshot('baseline')}
                                        >
                                            基线快照
                                        </Button>
                                        <Button
                                            icon={<CameraOutlined />}
                                            onClick={() => handleTakeSnapshot('current')}
                                        >
                                            当前快照
                                        </Button>
                                    </>
                                )}
                            </Space>

                            {/* 已有快照 */}
                            {traceStatus?.snapshots && traceStatus.snapshots.length > 0 && (
                                <div>
                                    <Text type="secondary">已保存快照: </Text>
                                    {traceStatus.snapshots.map((name) => (
                                        <Tag key={name} color="blue">{name}</Tag>
                                    ))}
                                </div>
                            )}

                            {/* 使用说明 */}
                            <Alert
                                type="info"
                                showIcon
                                message="泄漏检测流程"
                                description={
                                    <ol style={{ margin: 0, paddingLeft: 20 }}>
                                        <li>启动追踪</li>
                                        <li>点击「基线快照」记录初始状态</li>
                                        <li>执行可能泄漏的操作</li>
                                        <li>点击「当前快照」记录当前状态</li>
                                        <li>通过 API 比较: <code>/api/system/memory/trace/compare</code></li>
                                    </ol>
                                }
                            />
                        </Space>
                    </ProCard>
                </Col>
            </Row>

            {/* 文件缓存管理 */}
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                <Col span={24}>
                    <CacheManagementCard />
                </Col>
            </Row>

            {/* L2 RAM 缓冲区管理 */}
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                <Col span={24}>
                    <L2RamBufferCard />
                </Col>
            </Row>
        </PageContainer>
    );
};

export default MemoryManagement;
