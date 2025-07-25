"""
Web UI 集成示例。

展示如何在未来的 Web UI 中集成监控系统。
"""
import json

# 示例：FastAPI 集成
"""
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from deepsearch.monitoring import EventSystemMonitor, MonitorAPI
from deepsearch.event.engine import EventEngine

app = FastAPI(title="DeepSearch Monitor API")

# 允许跨域访问（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化监控系统
engine = EventEngine()
monitor = EventSystemMonitor(engine)
monitor_api = MonitorAPI(monitor)
monitor_api.start()


@app.get("/api/monitor/dashboard")
async def get_dashboard():
    '''获取仪表板数据'''
    data = monitor_api.get_dashboard_data()
    return JSONResponse(content=data)


@app.get("/api/monitor/metrics/realtime")
async def get_realtime_metrics(event_types: str = None):
    '''获取实时指标'''
    types = event_types.split(",") if event_types else None
    data = monitor_api.get_realtime_metrics(types)
    return JSONResponse(content=data)


@app.get("/api/monitor/health")
async def get_health():
    '''获取健康状态'''
    data = monitor_api.get_health_status()
    return JSONResponse(content=data)


@app.get("/api/monitor/slow-events")
async def get_slow_events(limit: int = 50):
    '''获取慢事件列表'''
    data = monitor_api.get_slow_events(limit)
    return JSONResponse(content=data)


@app.get("/api/monitor/history")
async def get_history(hours: int = 24):
    '''获取历史数据'''
    data = monitor_api.get_historical_data(hours)
    return JSONResponse(content=data)


@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    '''WebSocket 实时推送'''
    await websocket.accept()
    
    try:
        while True:
            # 每5秒推送一次数据
            data = monitor_api.get_dashboard_data()
            await websocket.send_json(data)
            await asyncio.sleep(5)
    except Exception:
        pass
    finally:
        await websocket.close()
"""

# 示例：Flask 集成
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from deepsearch.monitoring import EventSystemMonitor, MonitorAPI

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化监控
monitor_api = None  # 在应用启动时初始化


@app.route("/api/monitor/dashboard")
def get_dashboard():
    data = monitor_api.get_dashboard_data()
    return jsonify(data)


@app.route("/api/monitor/metrics/realtime")
def get_realtime_metrics():
    event_types = request.args.get("event_types")
    types = event_types.split(",") if event_types else None
    data = monitor_api.get_realtime_metrics(types)
    return jsonify(data)


# Socket.IO 实时推送
@socketio.on("connect")
def handle_connect():
    # 开始定期推送
    def push_updates():
        while True:
            data = monitor_api.get_dashboard_data()
            emit("monitor_update", data, broadcast=True)
            socketio.sleep(5)
    
    socketio.start_background_task(push_updates)
"""

# 示例：前端 JavaScript 调用
"""
// 使用 Fetch API
async function getDashboardData() {
    const response = await fetch('http://localhost:8000/api/monitor/dashboard');
    const data = await response.json();
    console.log('Dashboard data:', data);
    
    // 更新 UI
    document.getElementById('health-status').textContent = data.current.health_status;
    document.getElementById('total-events').textContent = data.current.total_events;
    document.getElementById('queue-size').textContent = data.current.queue_size;
    
    // 显示告警
    const alertsContainer = document.getElementById('alerts');
    data.alerts.forEach(alert => {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${alert.level}`;
        alertDiv.textContent = alert.message;
        alertsContainer.appendChild(alertDiv);
    });
}

// 使用 WebSocket 实时更新
const ws = new WebSocket('ws://localhost:8000/ws/monitor');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateDashboard(data);
};

// 使用 Chart.js 绘制实时图表
async function drawRealtimeChart() {
    const response = await fetch('http://localhost:8000/api/monitor/metrics/realtime');
    const data = await response.json();
    
    const ctx = document.getElementById('realtimeChart').getContext('2d');
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.timestamps.map(t => new Date(t).toLocaleTimeString()),
            datasets: Object.entries(data.series).map(([eventType, metrics]) => ({
                label: eventType,
                data: metrics.avg_time_ms,
                borderColor: getRandomColor(),
                tension: 0.1
            }))
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: '事件处理时间（毫秒）'
                }
            }
        }
    });
}
"""

# 示例：React 组件
"""
import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';

function MonitorDashboard() {
    const [dashboard, setDashboard] = useState(null);
    const [metrics, setMetrics] = useState(null);
    
    useEffect(() => {
        // 初始加载
        fetchDashboard();
        fetchMetrics();
        
        // 定期更新
        const interval = setInterval(() => {
            fetchDashboard();
            fetchMetrics();
        }, 5000);
        
        return () => clearInterval(interval);
    }, []);
    
    const fetchDashboard = async () => {
        const response = await fetch('/api/monitor/dashboard');
        const data = await response.json();
        setDashboard(data);
    };
    
    const fetchMetrics = async () => {
        const response = await fetch('/api/monitor/metrics/realtime');
        const data = await response.json();
        setMetrics(data);
    };
    
    if (!dashboard || !metrics) {
        return <div>Loading...</div>;
    }
    
    const chartData = {
        labels: metrics.timestamps.map(t => new Date(t).toLocaleTimeString()),
        datasets: Object.entries(metrics.series).map(([eventType, data]) => ({
            label: eventType,
            data: data.avg_time_ms,
            borderColor: getEventColor(eventType),
            fill: false
        }))
    };
    
    return (
        <div className="monitor-dashboard">
            <div className="status-cards">
                <StatusCard 
                    title="健康状态" 
                    value={dashboard.current.health_status}
                    trend={dashboard.trends.health_change}
                />
                <StatusCard 
                    title="处理事件" 
                    value={dashboard.current.total_events}
                    trend={dashboard.trends.events_change}
                />
                <StatusCard 
                    title="队列大小" 
                    value={dashboard.current.queue_size}
                    trend={dashboard.trends.queue_size_change}
                />
            </div>
            
            <div className="charts">
                <Line data={chartData} options={chartOptions} />
            </div>
            
            <AlertList alerts={dashboard.alerts} />
        </div>
    );
}
"""


# 数据格式示例
def show_data_format_examples():
    """展示 API 返回的数据格式，便于前端开发参考。"""

    # 仪表板数据格式
    dashboard_format = {
        "current": {
            "timestamp": "2024-01-20T10:30:00",
            "health_status": "healthy",  # healthy, degraded, unhealthy
            "total_events": 15234,
            "queue_size": 12,
            "slow_events": 3,
            "active_alerts": 0
        },
        "trends": {
            "events_change": 234,  # 相比上一时间段的变化
            "queue_size_change": -2,
            "slow_events_change": 1
        },
        "alerts": [
            {
                "level": "warning",  # error, warning, info
                "type": "error_rate",  # health, performance, error_rate
                "message": "事件 ORDER_STATUS 失败率过高：5.2%",
                "timestamp": "2024-01-20T10:29:45"
            }
        ]
    }

    # 实时指标数据格式
    metrics_format = {
        "series": {
            "TICK": {
                "count": [100, 105, 98, 110],
                "success_rate": [100.0, 100.0, 99.5, 100.0],
                "avg_time_ms": [12.5, 13.2, 11.8, 12.9]
            },
            "ORDER_STATUS": {
                "count": [50, 48, 52, 51],
                "success_rate": [95.0, 94.8, 96.2, 95.1],
                "avg_time_ms": [25.3, 24.8, 26.1, 25.5]
            }
        },
        "timestamps": [
            "2024-01-20T10:27:00",
            "2024-01-20T10:28:00",
            "2024-01-20T10:29:00",
            "2024-01-20T10:30:00"
        ]
    }

    # 健康状态数据格式
    health_format = {
        "status": "healthy",
        "checks": {
            "engine_running": {
                "success": True,
                "message": None,
                "duration": 0.001,
                "critical": True
            },
            "message_bus": {
                "success": True,
                "message": None,
                "duration": 0.005,
                "critical": True
            },
            "queue_size": {
                "success": True,
                "message": None,
                "duration": 0.001,
                "critical": False
            }
        }
    }

    return {
        "dashboard": dashboard_format,
        "metrics": metrics_format,
        "health": health_format
    }


if __name__ == "__main__":
    # 打印数据格式示例
    examples = show_data_format_examples()
    print("=== 监控 API 数据格式示例 ===\n")

    for name, format_data in examples.items():
        print(f"\n{name.upper()} 数据格式:")
        print(json.dumps(format_data, indent=2, ensure_ascii=False))
        print("-" * 50)
