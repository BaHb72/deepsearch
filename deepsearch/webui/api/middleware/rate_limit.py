"""
请求限流中间件

保护 CloudFlare Worker 限额，实现智能限流策略
"""
import time
import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class Priority(Enum):
    """请求优先级"""
    P0_CRITICAL = 0  # 关键请求（实时数据）
    P1_HIGH = 1      # 高优先级（市场概览）
    P2_NORMAL = 2    # 普通优先级（一般查询）
    P3_LOW = 3       # 低优先级（历史数据）


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    智能限流中间件
    
    功能：
    1. 保护 CloudFlare Worker 每日 100k 限额
    2. 实现分级限流策略
    3. 动态调整限流阈值
    4. 优先保证关键 API
    """
    
    def __init__(
        self,
        app,
        daily_limit: int = 100000,  # CloudFlare 日限额
        requests_per_second: int = 10,  # 每秒请求限制
        burst_size: int = 50,  # 突发容量
        exclude_paths: set = None  # 排除的路径
    ):
        """
        初始化限流中间件
        
        Args:
            app: FastAPI 应用
            daily_limit: 每日请求限额
            requests_per_second: 每秒请求数限制
            burst_size: 突发请求容量
            exclude_paths: 不限流的路径集合
        """
        super().__init__(app)
        
        # 限流配置
        self.daily_limit = daily_limit
        self.hourly_limit = daily_limit // 24  # 每小时限额
        self.minute_limit = daily_limit // (24 * 60)  # 每分钟限额
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        
        # 排除路径
        self.exclude_paths = exclude_paths or {
            "/docs", "/openapi.json", "/api/health", 
            "/api/monitor", "/api/system"
        }
        
        # 请求统计
        self.daily_requests = 0
        self.hourly_requests = 0
        self.minute_requests = 0
        self.last_reset_day = datetime.now().date()
        self.last_reset_hour = datetime.now().hour
        self.last_reset_minute = datetime.now().minute
        
        # 滑动窗口（用于秒级限流）
        self.request_times = deque(maxlen=burst_size)
        
        # 路径优先级映射
        self.path_priorities = {
            # P0: 关键实时数据
            "/api/chart/realtime": Priority.P0_CRITICAL,
            "/api/qmt/": Priority.P0_CRITICAL,
            "/api/market/realtime": Priority.P0_CRITICAL,
            
            # P1: 重要数据
            "/api/market/overview": Priority.P1_HIGH,
            "/api/chart/kline": Priority.P1_HIGH,
            
            # P2: 一般请求
            "/api/data/": Priority.P2_NORMAL,
            "/api/workers/": Priority.P2_NORMAL,
            
            # P3: 低优先级
            "/api/data/history": Priority.P3_LOW,
            "/api/chart/indicators": Priority.P3_LOW,
        }
        
        # CloudFlare 相关路径（需要特别保护）
        self.cloudflare_paths = {
            "/api/workers/",
            "/api/chart/",  # 使用 CloudFlare 数据
            "/api/market/",  # 使用 CloudFlare 数据
        }
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "rejected_requests": 0,
            "cloudflare_requests": 0,
            "priority_rejections": defaultdict(int)
        }
        
        logger.info(f"限流中间件已初始化: 日限额={daily_limit}, 每秒={requests_per_second}")
    
    def _reset_counters(self):
        """重置计数器"""
        now = datetime.now()
        
        # 每日重置
        if now.date() != self.last_reset_day:
            self.daily_requests = 0
            self.last_reset_day = now.date()
            logger.info(f"每日请求计数已重置，昨日总请求: {self.stats['total_requests']}")
        
        # 每小时重置
        if now.hour != self.last_reset_hour:
            self.hourly_requests = 0
            self.last_reset_hour = now.hour
        
        # 每分钟重置
        if now.minute != self.last_reset_minute:
            self.minute_requests = 0
            self.last_reset_minute = now.minute
    
    def _get_path_priority(self, path: str) -> Priority:
        """获取路径的优先级"""
        # 精确匹配
        if path in self.path_priorities:
            return self.path_priorities[path]
        
        # 前缀匹配
        for prefix, priority in self.path_priorities.items():
            if path.startswith(prefix):
                return priority
        
        # 默认普通优先级
        return Priority.P2_NORMAL
    
    def _is_cloudflare_request(self, path: str) -> bool:
        """判断是否是 CloudFlare 相关请求"""
        return any(path.startswith(prefix) for prefix in self.cloudflare_paths)
    
    def _should_reject(self, priority: Priority) -> bool:
        """
        根据当前使用量和优先级决定是否拒绝
        
        降级策略：
        - 80% 额度：拒绝 P3 请求
        - 90% 额度：拒绝 P2 请求
        - 95% 额度：拒绝 P1 请求
        - 98% 额度：只允许 P0 请求
        """
        usage_percent = (self.daily_requests / self.daily_limit) * 100
        
        if usage_percent >= 98 and priority != Priority.P0_CRITICAL:
            return True
        elif usage_percent >= 95 and priority.value >= Priority.P1_HIGH.value:
            return True
        elif usage_percent >= 90 and priority.value >= Priority.P2_NORMAL.value:
            return True
        elif usage_percent >= 80 and priority.value >= Priority.P3_LOW.value:
            return True
        
        return False
    
    def _check_rate_limit(self) -> bool:
        """
        检查速率限制
        
        Returns:
            True 如果允许请求，False 如果超限
        """
        now = time.time()
        
        # 清理过期的请求时间
        while self.request_times and self.request_times[0] < now - 1:
            self.request_times.popleft()
        
        # 检查每秒请求数
        if len(self.request_times) >= self.requests_per_second:
            return False
        
        # 检查突发容量
        if len(self.request_times) >= self.burst_size:
            return False
        
        # 记录请求时间
        self.request_times.append(now)
        return True
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求
        
        Args:
            request: 请求对象
            call_next: 下一个中间件
            
        Returns:
            响应对象
        """
        # 获取请求路径
        path = request.url.path
        
        # 排除不需要限流的路径
        if path in self.exclude_paths:
            return await call_next(request)
        
        # 重置计数器
        self._reset_counters()
        
        # 更新统计
        self.stats["total_requests"] += 1
        self.daily_requests += 1
        self.hourly_requests += 1
        self.minute_requests += 1
        
        # 检查是否是 CloudFlare 请求
        is_cloudflare = self._is_cloudflare_request(path)
        if is_cloudflare:
            self.stats["cloudflare_requests"] += 1
        
        # 获取请求优先级
        priority = self._get_path_priority(path)
        
        # 检查是否需要拒绝（基于优先级和使用量）
        if self._should_reject(priority):
            self.stats["rejected_requests"] += 1
            self.stats["priority_rejections"][priority.name] += 1
            
            usage_percent = (self.daily_requests / self.daily_limit) * 100
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Daily limit approaching ({usage_percent:.1f}%), {priority.name} requests temporarily disabled",
                    "daily_usage": f"{self.daily_requests}/{self.daily_limit}",
                    "retry_after": 60
                },
                headers={"retry_after": "60"}
            )
        
        # 检查每分钟限制
        if self.minute_requests > self.minute_limit:
            self.stats["rejected_requests"] += 1
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Minute limit exceeded ({self.minute_requests}/{self.minute_limit})",
                    "retry_after": 60
                },
                headers={"retry_after": "60"}
            )
        
        # 检查每秒限制
        if not self._check_rate_limit():
            self.stats["rejected_requests"] += 1
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Request rate too high (max {self.requests_per_second}/s)",
                    "retry_after": 1
                },
                headers={"retry_after": "1"}
            )
        
        # 记录 CloudFlare 使用量（用于监控）
        if is_cloudflare:
            usage_percent = (self.daily_requests / self.daily_limit) * 100
            logger.info(
                f"CloudFlare 使用量: {self.daily_requests}/{self.daily_limit} "
                f"({usage_percent:.1f}%), 拒绝: {self.stats['rejected_requests']}"
            )
        
        # 警告接近限额
        if self.daily_requests == int(self.daily_limit * 0.8):
            logger.warning(f"CloudFlare 日限额已使用 80%: {self.daily_requests}/{self.daily_limit}")
        elif self.daily_requests == int(self.daily_limit * 0.9):
            logger.warning(f"CloudFlare 日限额已使用 90%: {self.daily_requests}/{self.daily_limit}")
        elif self.daily_requests == int(self.daily_limit * 0.95):
            logger.error(f"CloudFlare 日限额已使用 95%: {self.daily_requests}/{self.daily_limit}")
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(self.daily_limit)
        response.headers["X-RateLimit-Remaining"] = str(self.daily_limit - self.daily_requests)
        response.headers["X-RateLimit-Reset"] = str(int((datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)).timestamp()))
        
        return response
    
    def get_stats(self) -> Dict:
        """
        获取限流统计信息
        
        Returns:
            统计信息字典
        """
        usage_percent = (self.daily_requests / self.daily_limit) * 100
        
        return {
            "daily_limit": self.daily_limit,
            "daily_used": self.daily_requests,
            "daily_remaining": self.daily_limit - self.daily_requests,
            "usage_percent": f"{usage_percent:.1f}%",
            "hourly_requests": self.hourly_requests,
            "minute_requests": self.minute_requests,
            "total_requests": self.stats["total_requests"],
            "rejected_requests": self.stats["rejected_requests"],
            "rejection_rate": f"{(self.stats['rejected_requests'] / max(self.stats['total_requests'], 1)) * 100:.1f}%",
            "cloudflare_requests": self.stats["cloudflare_requests"],
            "priority_rejections": dict(self.stats["priority_rejections"])
        }


# 全局实例（用于获取统计信息）
_middleware_instance: Optional[RateLimitMiddleware] = None


def get_rate_limit_stats() -> Dict:
    """获取限流统计信息"""
    if _middleware_instance:
        return _middleware_instance.get_stats()
    return {"error": "RateLimitMiddleware not initialized"}