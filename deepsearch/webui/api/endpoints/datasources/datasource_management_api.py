# encoding:utf-8
"""
数据源管理API
提供数据源的增删改查、测试、监控等功能
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.config import get_config
# 导入数据源相关类
try:
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import AmazingDataProvider
    from deepsearch.config.models.amazingdata import AmazingDataConfig
    from deepsearch.infrastructure.providers.interfaces.base import DataSourceType, DataProviderError
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_exceptions import AmazingDataAuthenticationError as AuthenticationError
    # NetworkError使用DataProviderError代替
    NetworkError = DataProviderError
except ImportError as e:
    logger.warning(f"部分模块导入失败，某些功能可能不可用: {e}")
    # 定义占位类以避免完全失败
    class AmazingDataProvider:
        async def initialize(self): pass
        async def is_connected(self): return False
        async def get_stock_list(self, limit=None): return []
        async def disconnect(self): pass
    class AmazingDataConfig:
        pass
    from enum import Enum
    class DataSourceType(Enum):
        AMAZINGDATA = "amazingdata"
    # 定义异常类
    class AuthenticationError(Exception):
        pass
    class DataProviderError(Exception):
        pass
    class NetworkError(Exception):
        pass

# 定义接口类
class ICompleteDataProvider:
    pass

router = APIRouter(prefix="/api/datasource", tags=["datasource"])

# 数据源管理器（单例）
class DataSourceManager:
    """数据源管理器"""

    def __init__(self):
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.providers: Dict[str, ICompleteDataProvider] = {}
        self.config = get_config()
        self._load_from_config()

    def _load_from_config(self):
        """从配置文件加载数据源"""
        # 加载数据源配置
        if hasattr(self.config, 'data_sources') and self.config.data_sources and hasattr(self.config.data_sources, 'providers'):
            providers = self.config.data_sources.providers

            # 加载AmazingData配置
            if (hasattr(providers, 'amazingdata') and
                providers.amazingdata and
                hasattr(providers.amazingdata, 'enabled') and
                providers.amazingdata.enabled):
                amazingdata = providers.amazingdata
                source_id = str(uuid.uuid4())
                self.sources[source_id] = {
                    'id': source_id,
                    'name': 'AmazingData-默认',
                    'type': 'amazingdata',
                    'status': 'disconnected',
                    'enabled': amazingdata.enabled,
                    'priority': amazingdata.priority,
                    'config': {
                        'host': amazingdata.config.get('host', amazingdata.config.get('connection', {}).get('host', '120.86.124.106')),
                        'port': amazingdata.config.get('port', amazingdata.config.get('connection', {}).get('port', 8600)),
                        'username': amazingdata.config.get('username', amazingdata.config.get('connection', {}).get('username', '')),
                        'password': amazingdata.config.get('password', amazingdata.config.get('connection', {}).get('password', '')),
                        'cacheEnabled': amazingdata.config.get('cache', {}).get('enabled', True),
                        'cacheTTL': amazingdata.config.get('cache', {}).get('ttl', 300),
                        'timeout': amazingdata.config.get('connection', {}).get('timeout', amazingdata.config.get('timeout', 30)),
                        'maxRetries': amazingdata.config.get('connection', {}).get('max_retries', amazingdata.config.get('max_retries', 3)),
                        'heartbeatInterval': amazingdata.config.get('connection', {}).get('heartbeat_interval', amazingdata.config.get('heartbeat_interval', 60)),
                        'autoReconnect': amazingdata.config.get('connection', {}).get('auto_reconnect', amazingdata.config.get('auto_reconnect', True))
                    },
                    'statistics': {
                        'queries': 0,
                        'queryErrors': 0,
                        'cacheHits': 0,
                        'cacheMisses': 0,
                        'avgResponseTime': 0,
                        'uptime': 0,
                        'subscriptions': 0
                    },
                    'lastCheck': None
                }

    async def get_all(self) -> List[Dict[str, Any]]:
        """获取所有数据源"""
        # 更新状态
        for source_id, source in self.sources.items():
            if source_id in self.providers:
                provider = self.providers[source_id]
                is_connected = await provider.is_connected()
                source['status'] = 'connected' if is_connected else 'disconnected'

                # 获取统计信息
                stats = await provider.get_statistics()
                if stats:
                    source['statistics'] = stats.get('statistics', {})

        return list(self.sources.values())

    async def add(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """添加数据源"""
        source_id = str(uuid.uuid4())
        source = {
            'id': source_id,
            'name': data['name'],
            'type': data['type'],
            'status': 'disconnected',
            'enabled': data.get('enabled', True),
            'priority': data.get('priority', 1),
            'config': data.get('config', {}),
            'statistics': {
                'queries': 0,
                'queryErrors': 0,
                'cacheHits': 0,
                'cacheMisses': 0,
                'avgResponseTime': 0,
                'uptime': 0,
                'subscriptions': 0
            },
            'lastCheck': None
        }

        self.sources[source_id] = source

        # 如果启用，立即初始化
        if source['enabled']:
            await self._init_provider(source_id)

        return source

    async def update(self, source_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新数据源"""
        if source_id not in self.sources:
            raise HTTPException(status_code=404, detail="数据源不存在")

        source = self.sources[source_id]

        # 更新字段
        source['name'] = data.get('name', source['name'])
        source['enabled'] = data.get('enabled', source['enabled'])
        source['priority'] = data.get('priority', source['priority'])
        source['config'].update(data.get('config', {}))

        # 如果配置改变，重新初始化
        if source_id in self.providers:
            await self._close_provider(source_id)

        if source['enabled']:
            await self._init_provider(source_id)

        return source

    async def delete(self, source_id: str) -> bool:
        """删除数据源"""
        if source_id not in self.sources:
            raise HTTPException(status_code=404, detail="数据源不存在")

        # 关闭连接
        if source_id in self.providers:
            await self._close_provider(source_id)

        del self.sources[source_id]
        return True

    async def toggle(self, source_id: str, enabled: bool) -> Dict[str, Any]:
        """切换启用状态"""
        if source_id not in self.sources:
            raise HTTPException(status_code=404, detail="数据源不存在")

        source = self.sources[source_id]
        source['enabled'] = enabled

        if enabled:
            await self._init_provider(source_id)
        else:
            await self._close_provider(source_id)

        return source

    async def test(self, source_id: str) -> Dict[str, Any]:
        """测试数据源连接"""
        if source_id not in self.sources:
            raise HTTPException(status_code=404, detail="数据源不存在")

        source = self.sources[source_id]
        start_time = time.time()

        try:
            # 创建临时provider测试
            if source['type'] == 'amazingdata':
                config = AmazingDataConfig(
                    username=source['config']['username'],
                    password=source['config']['password'],
                    host=source['config']['host'],
                    port=source['config']['port'],
                    timeout=source['config'].get('timeout', 30)
                )
                provider = AmazingDataProvider(config)

                # 测试连接
                await provider.initialize()
                is_connected = await provider.is_connected()

                # 测试查询
                code_list = []
                if is_connected:
                    # 测试获取股票列表
                    try:
                        code_list = await provider.get_stock_list(limit=10)  # 只获取10条测试
                        test_success = code_list is not None and len(code_list) > 0
                    except Exception as e:
                        logger.warning(f"获取股票列表失败: {e}")
                        test_success = is_connected  # 连接成功即可
                else:
                    test_success = False

                await provider.disconnect()

                latency = int((time.time() - start_time) * 1000)
                source['lastCheck'] = datetime.now().isoformat()

                return {
                    'success': test_success,
                    'message': '连接成功' if test_success else '连接失败',
                    'latency': latency,
                    'details': {
                        'connected': is_connected,
                        'stockCount': len(code_list) if code_list else 0
                    }
                }

        except AuthenticationError as e:
            return {
                'success': False,
                'message': f'认证失败: {e.message}',
                'latency': int((time.time() - start_time) * 1000)
            }
        except NetworkError as e:
            return {
                'success': False,
                'message': f'网络错误: {e.message}',
                'latency': int((time.time() - start_time) * 1000)
            }
        except Exception as e:
            logger.error(f"测试数据源失败: {e}")
            return {
                'success': False,
                'message': f'测试失败: {str(e)}',
                'latency': int((time.time() - start_time) * 1000)
            }

    async def _init_provider(self, source_id: str):
        """初始化数据提供者"""
        if source_id not in self.sources:
            return

        source = self.sources[source_id]

        try:
            if source['type'] == 'amazingdata':
                config = AmazingDataConfig(
                    username=source['config']['username'],
                    password=source['config']['password'],
                    host=source['config']['host'],
                    port=source['config']['port'],
                    cache_enabled=source['config'].get('cacheEnabled', True),
                    cache_ttl=source['config'].get('cacheTTL', 300),
                    timeout=source['config'].get('timeout', 30),
                    max_retries=source['config'].get('maxRetries', 3),
                    heartbeat_interval=source['config'].get('heartbeatInterval', 60),
                    auto_reconnect=source['config'].get('autoReconnect', True)
                )
                provider = AmazingDataProvider(config)
                await provider.initialize()

                self.providers[source_id] = provider
                source['status'] = 'connected'
                logger.info(f"数据源 {source['name']} 初始化成功")

        except Exception as e:
            source['status'] = 'error'
            source['errorMessage'] = str(e)
            logger.error(f"数据源 {source['name']} 初始化失败: {e}")

    async def _close_provider(self, source_id: str):
        """关闭数据提供者"""
        if source_id in self.providers:
            try:
                provider = self.providers[source_id]
                await provider.disconnect()
                del self.providers[source_id]
                logger.info(f"数据源 {source_id} 已关闭")
            except Exception as e:
                logger.error(f"关闭数据源失败: {e}")

    def get_provider(self, source_id: str) -> Optional[ICompleteDataProvider]:
        """获取数据提供者"""
        return self.providers.get(source_id)


# 创建全局管理器实例
data_source_manager = DataSourceManager()


# Pydantic 模型
class DataSourceCreate(BaseModel):
    """创建数据源模型"""
    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据源类型")
    enabled: bool = Field(True, description="是否启用")
    priority: int = Field(1, description="优先级")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置信息")


class DataSourceUpdate(BaseModel):
    """更新数据源模型"""
    name: Optional[str] = Field(None, description="数据源名称")
    enabled: Optional[bool] = Field(None, description="是否启用")
    priority: Optional[int] = Field(None, description="优先级")
    config: Optional[Dict[str, Any]] = Field(None, description="配置信息")


class DataSourceToggle(BaseModel):
    """切换状态模型"""
    enabled: bool = Field(..., description="是否启用")


# API 端点
@router.get("/list", summary="获取数据源列表")
async def get_data_sources():
    """获取所有数据源"""
    try:
        sources = await data_source_manager.get_all()
        return {
            'success': True,
            'data': sources
        }
    except Exception as e:
        logger.error(f"获取数据源列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/add", summary="添加数据源")
async def add_data_source(data: DataSourceCreate):
    """添加新的数据源"""
    try:
        source = await data_source_manager.add(data.dict())
        return {
            'success': True,
            'data': source
        }
    except Exception as e:
        logger.error(f"添加数据源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/update/{source_id}", summary="更新数据源")
async def update_data_source(source_id: str, data: DataSourceUpdate):
    """更新数据源配置"""
    try:
        source = await data_source_manager.update(
            source_id,
            data.dict(exclude_unset=True)
        )
        return {
            'success': True,
            'data': source
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新数据源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/delete/{source_id}", summary="删除数据源")
async def delete_data_source(source_id: str):
    """删除数据源"""
    try:
        success = await data_source_manager.delete(source_id)
        return {
            'success': success,
            'message': '删除成功' if success else '删除失败'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除数据源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/toggle/{source_id}", summary="切换启用状态")
async def toggle_data_source(source_id: str, data: DataSourceToggle):
    """切换数据源启用状态"""
    try:
        source = await data_source_manager.toggle(source_id, data.enabled)
        return {
            'success': True,
            'data': source
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换数据源状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/test/{source_id}", summary="测试连接")
async def test_data_source(source_id: str):
    """测试数据源连接"""
    try:
        result = await data_source_manager.test(source_id)
        return {
            'success': True,
            'data': result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试数据源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/statistics/{source_id}", summary="获取统计信息")
async def get_data_source_statistics(source_id: str):
    """获取数据源统计信息"""
    try:
        provider = data_source_manager.get_provider(source_id)
        if not provider:
            raise HTTPException(
                status_code=404,
                detail="数据源未初始化或不存在"
            )

        stats = await provider.get_statistics()
        return {
            'success': True,
            'data': stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health/{source_id}", summary="健康检查")
async def check_data_source_health(source_id: str):
    """数据源健康检查"""
    try:
        provider = data_source_manager.get_provider(source_id)
        if not provider:
            return {
                'success': False,
                'data': {
                    'status': 'offline',
                    'message': '数据源未初始化'
                }
            }

        health = await provider.health_check()
        return {
            'success': True,
            'data': health
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'success': False,
            'data': {
                'status': 'error',
                'message': str(e)
            }
        }


@router.post("/batch-test", summary="批量测试")
async def batch_test_data_sources():
    """批量测试所有启用的数据源"""
    try:
        sources = await data_source_manager.get_all()
        enabled_sources = [s for s in sources if s['enabled']]

        results = {}
        for source in enabled_sources:
            result = await data_source_manager.test(source['id'])
            results[source['id']] = {
                'name': source['name'],
                'result': result
            }

        return {
            'success': True,
            'data': results
        }
    except Exception as e:
        logger.error(f"批量测试失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )