"""
智能内存管理模块

提供自动内存监控、清理和优化
"""
import gc
import sys
import time
import weakref
import threading
import psutil
from datetime import datetime
from collections import deque
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set

# resource模块只在Unix/Linux系统上可用
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False  # Windows不支持resource模块

from loguru import logger


class MemoryStats:
    """内存统计信息"""
    
    def __init__(self):
        self.measurements = deque(maxlen=1000)
        self.peak_usage = 0
        self.total_allocated = 0
        self.total_freed = 0
        
    def record(self, usage: int, allocated: int = 0, freed: int = 0):
        """记录内存使用"""
        self.measurements.append({
            'timestamp': datetime.now(),
            'usage': usage,
            'allocated': allocated,
            'freed': freed
        })
        
        if usage > self.peak_usage:
            self.peak_usage = usage
            
        self.total_allocated += allocated
        self.total_freed += freed
        
    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        if not self.measurements:
            return {}
            
        recent = list(self.measurements)[-100:]
        usages = [m['usage'] for m in recent]
        
        return {
            'current': usages[-1] if usages else 0,
            'peak': self.peak_usage,
            'average': sum(usages) / len(usages) if usages else 0,
            'total_allocated': self.total_allocated,
            'total_freed': self.total_freed,
            'net_allocated': self.total_allocated - self.total_freed
        }


class SmartMemoryManager:
    """智能内存管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            # 内存限制设置
            self.memory_limit = psutil.virtual_memory().total * 0.8  # 使用80%内存
            self.warning_threshold = self.memory_limit * 0.9  # 90%时警告
            self.gc_threshold = 100 * 1024 * 1024  # 100MB触发GC
            
            # 对象追踪
            self.large_objects = weakref.WeakValueDictionary()
            self.object_sizes = {}
            self.cache_objects = weakref.WeakSet()
            
            # 统计信息
            self.stats = MemoryStats()
            self.gc_stats = deque(maxlen=100)
            
            # 监控设置
            self.monitoring_enabled = True
            self.monitor_thread = None
            self.monitor_interval = 10  # 秒
            
            # 自动清理设置
            try:
                from deepsearch.config import settings
                self.auto_cleanup = settings.app.env == "production"
            except ImportError:
                self.auto_cleanup = False
            self.last_cleanup = datetime.now()
            self.cleanup_interval = 300  # 5分钟
            
            self._lock = threading.Lock()
            self._initialized = True
            
            # 启动监控
            self.start_monitoring()
            
    def start_monitoring(self):
        """启动内存监控"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
            
        def monitor():
            while self.monitoring_enabled:
                try:
                    self._monitor_memory()
                    time.sleep(self.monitor_interval)
                except Exception as e:
                    logger.error(f"内存监控错误: {e}")
                    
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        logger.debug("内存监控已启动")
        
    def stop_monitoring(self):
        """停止内存监控"""
        self.monitoring_enabled = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.debug("内存监控已停止")
        
    def _monitor_memory(self):
        """监控内存使用"""
        process = psutil.Process()
        memory_usage = process.memory_info().rss
        
        # 记录统计
        self.stats.record(memory_usage)
        
        # 检查内存使用
        if memory_usage > self.memory_limit:
            logger.error(f"内存使用超限: {memory_usage / 1024 / 1024:.2f}MB / {self.memory_limit / 1024 / 1024:.2f}MB")
            if self.auto_cleanup:
                self.cleanup()
                
        elif memory_usage > self.warning_threshold:
            logger.warning(f"内存使用接近限制: {memory_usage / 1024 / 1024:.2f}MB / {self.memory_limit / 1024 / 1024:.2f}MB")
            
        # 定期清理
        if self.auto_cleanup:
            now = datetime.now()
            if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
                self.cleanup()
                self.last_cleanup = now
                
    def register_large_object(self, obj: Any, name: str) -> bool:
        """注册大对象"""
        try:
            size = sys.getsizeof(obj)
            
            # 只注册大于1MB的对象
            if size > 1024 * 1024:
                with self._lock:
                    self.large_objects[name] = obj
                    self.object_sizes[name] = size
                    
                logger.debug(f"注册大对象: {name} ({size / 1024 / 1024:.2f}MB)")
                return True
                
        except Exception as e:
            logger.debug(f"注册对象失败: {e}")
            
        return False
        
    def unregister_object(self, name: str):
        """注销对象"""
        with self._lock:
            if name in self.large_objects:
                del self.large_objects[name]
                
            if name in self.object_sizes:
                size = self.object_sizes.pop(name)
                logger.debug(f"注销对象: {name} ({size / 1024 / 1024:.2f}MB)")
                
    def add_cache_object(self, obj: Any):
        """添加缓存对象（可被清理）"""
        self.cache_objects.add(obj)
        
    def cleanup(self, force: bool = False) -> Dict[str, int]:
        """清理内存"""
        logger.info("开始内存清理...")
        
        cleanup_stats = {
            'gc_collected': 0,
            'objects_cleared': 0,
            'cache_cleared': 0,
            'memory_freed': 0
        }
        
        initial_memory = psutil.Process().memory_info().rss
        
        # 1. 强制垃圾回收
        gc_stats_before = gc.get_stats()
        collected = gc.collect()
        cleanup_stats['gc_collected'] = collected
        
        # 记录GC统计
        gc_stats_after = gc.get_stats()
        self.gc_stats.append({
            'timestamp': datetime.now(),
            'collected': collected,
            'stats': gc_stats_after
        })
        
        # 2. 清理大对象（如果强制清理）
        if force:
            with self._lock:
                cleared = 0
                for name in list(self.large_objects.keys()):
                    if name in self.large_objects:
                        del self.large_objects[name]
                        cleared += 1
                        
                cleanup_stats['objects_cleared'] = cleared
                
        # 3. 清理缓存对象
        cache_cleared = len(self.cache_objects)
        self.cache_objects.clear()
        cleanup_stats['cache_cleared'] = cache_cleared
        
        # 4. 清理模块缓存
        if force:
            self._clear_module_caches()
            
        # 计算释放的内存
        gc.collect()  # 再次回收
        final_memory = psutil.Process().memory_info().rss
        memory_freed = initial_memory - final_memory
        cleanup_stats['memory_freed'] = memory_freed
        
        # 记录统计
        self.stats.record(final_memory, freed=max(0, memory_freed))
        
        logger.info(
            f"内存清理完成: 回收对象={collected}, "
            f"清理大对象={cleanup_stats['objects_cleared']}, "
            f"清理缓存={cache_cleared}, "
            f"释放内存={memory_freed / 1024 / 1024:.2f}MB"
        )
        
        return cleanup_stats
        
    def _clear_module_caches(self):
        """清理模块级缓存"""
        try:
            # 清理functools缓存
            import functools
            functools._lru_cache_clear_all()
        except:
            pass
            
        try:
            # 清理re模块缓存
            import re
            re.purge()
        except:
            pass
            
    @contextmanager
    def memory_limit_context(self, limit_mb: int):
        """内存限制上下文"""
        if sys.platform == "win32":
            # Windows不支持resource限制，使用软限制
            old_limit = self.memory_limit
            self.memory_limit = limit_mb * 1024 * 1024
            
            try:
                yield
            finally:
                self.memory_limit = old_limit
        elif HAS_RESOURCE:
            # Unix系统使用resource限制
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (limit_mb * 1024 * 1024, hard))
            
            try:
                yield
            finally:
                resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
        else:
            # 其他系统，直接执行
            yield
                
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        process = psutil.Process()
        virtual_memory = psutil.virtual_memory()
        
        return {
            'system': {
                'total': virtual_memory.total,
                'available': virtual_memory.available,
                'percent': virtual_memory.percent,
                'used': virtual_memory.used,
                'free': virtual_memory.free
            },
            'process': {
                'rss': process.memory_info().rss,
                'vms': process.memory_info().vms,
                'percent': process.memory_percent(),
                'num_threads': process.num_threads()
            },
            'limits': {
                'configured_limit': self.memory_limit,
                'warning_threshold': self.warning_threshold,
                'gc_threshold': self.gc_threshold
            },
            'objects': {
                'large_objects': len(self.large_objects),
                'cache_objects': len(self.cache_objects),
                'total_size': sum(self.object_sizes.values())
            },
            'stats': self.stats.get_summary()
        }
        
    def get_large_objects(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """获取最大的对象"""
        objects = []
        
        with self._lock:
            for name, size in self.object_sizes.items():
                if name in self.large_objects:
                    objects.append({
                        'name': name,
                        'size': size,
                        'size_mb': size / 1024 / 1024,
                        'type': type(self.large_objects[name]).__name__
                    })
                    
        # 按大小排序
        objects.sort(key=lambda x: x['size'], reverse=True)
        
        return objects[:top_n]
        
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用"""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'current_usage': {},
            'trends': {},
            'recommendations': []
        }
        
        # 当前使用情况
        memory_info = self.get_memory_info()
        analysis['current_usage'] = {
            'process_mb': memory_info['process']['rss'] / 1024 / 1024,
            'system_percent': memory_info['system']['percent'],
            'large_objects_mb': memory_info['objects']['total_size'] / 1024 / 1024
        }
        
        # 趋势分析
        if self.stats.measurements:
            recent = list(self.stats.measurements)[-100:]
            usages = [m['usage'] for m in recent]
            
            # 计算趋势
            if len(usages) > 10:
                # 简单线性回归
                x = list(range(len(usages)))
                y = usages
                n = len(x)
                
                x_mean = sum(x) / n
                y_mean = sum(y) / n
                
                numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
                
                if denominator != 0:
                    slope = numerator / denominator
                    analysis['trends']['slope'] = slope
                    analysis['trends']['growing'] = slope > 0
                    
                    # 预测
                    if slope > 0:
                        current = usages[-1]
                        time_to_limit = (self.memory_limit - current) / slope / 6  # 转换为分钟
                        analysis['trends']['time_to_limit_minutes'] = max(0, time_to_limit)
                        
        # 生成建议
        if memory_info['process']['percent'] > 50:
            analysis['recommendations'].append({
                'level': 'WARNING',
                'message': '进程内存使用超过50%',
                'action': '考虑优化内存使用或增加系统内存'
            })
            
        if len(self.large_objects) > 50:
            analysis['recommendations'].append({
                'level': 'INFO',
                'message': f'追踪了{len(self.large_objects)}个大对象',
                'action': '检查是否有不必要的对象引用'
            })
            
        if analysis.get('trends', {}).get('growing'):
            analysis['recommendations'].append({
                'level': 'WARNING',
                'message': '内存使用呈增长趋势',
                'action': '可能存在内存泄漏，建议检查代码'
            })
            
        return analysis
        
    def find_memory_leaks(self) -> List[Dict[str, Any]]:
        """查找可能的内存泄漏"""
        leaks = []
        
        # 检查循环引用
        gc.collect()
        for obj in gc.garbage:
            leaks.append({
                'type': 'circular_reference',
                'object': str(obj)[:100],
                'size': sys.getsizeof(obj) if hasattr(obj, '__sizeof__') else 0
            })
            
        # 检查持续增长的对象
        growing_objects = []
        for name, size in self.object_sizes.items():
            if name in self.large_objects:
                # 这里可以添加更复杂的增长检测逻辑
                growing_objects.append({
                    'name': name,
                    'size': size
                })
                
        if growing_objects:
            leaks.append({
                'type': 'growing_objects',
                'objects': growing_objects
            })
            
        return leaks
        
    def optimize_memory(self):
        """优化内存使用"""
        logger.info("开始内存优化...")
        
        # 1. 调整GC阈值
        gc.set_threshold(700, 10, 10)
        
        # 2. 清理不必要的模块
        self._clear_module_caches()
        
        # 3. 压缩大对象（如果可能）
        compressed = 0
        for name in list(self.large_objects.keys()):
            if name in self.large_objects:
                obj = self.large_objects[name]
                # 这里可以添加对象压缩逻辑
                compressed += 1
                
        # 4. 执行清理
        self.cleanup()
        
        logger.info(f"内存优化完成，处理了{compressed}个对象")
        
    def reset(self):
        """重置内存管理器"""
        with self._lock:
            self.large_objects.clear()
            self.object_sizes.clear()
            self.cache_objects.clear()
            self.stats = MemoryStats()
            self.gc_stats.clear()
            
        logger.info("内存管理器已重置")


# 创建全局实例
memory_manager = SmartMemoryManager()


# 便捷函数
def track_large_object(obj: Any, name: str):
    """追踪大对象"""
    return memory_manager.register_large_object(obj, name)


def clear_cache():
    """清理缓存"""
    return memory_manager.cleanup()


@contextmanager
def memory_limit(limit_mb: int):
    """内存限制上下文"""
    with memory_manager.memory_limit_context(limit_mb):
        yield