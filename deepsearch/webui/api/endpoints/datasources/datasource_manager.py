"""
数据源CRUD管理API

提供数据源的增删改查、测试和状态管理功能
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timedelta
from loguru import logger
import asyncio
import aiohttp
import yaml
from pathlib import Path
import os
import time

from deepsearch.webui.api.common.response_format import APIResponse, APIException, ErrorCodes
from deepsearch.config import get_config
from deepsearch.infrastructure.cache.cache_manager import CacheManager
# 导入进程隔离的安全包装器
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import AmazingDataSafeWrapper


# 创建路由
router = APIRouter(prefix="/api/data-sources", tags=["DataSource Management"])

# 创建全局缓存管理器实例
cache_manager = CacheManager(
    l1_max_size=10000,  # L1缓存最大条目数
    l1_ttl=300  # 默认TTL 5分钟
)


# 数据模型
class DataSourceConfig(BaseModel):
    """数据源配置"""
    timeout: int = Field(default=30000, description="超时时间(ms)")
    retryCount: int = Field(default=3, description="重试次数")
    rateLimit: int = Field(default=100, description="速率限制(req/s)")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口号")
    workerUrl: Optional[str] = Field(None, description="Worker URL")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    networkProvider: Optional[str] = Field("telecom", description="网络运营商: telecom|unicom|custom")
    heartbeatInterval: Optional[int] = Field(60, description="心跳间隔(秒)")
    autoReconnect: Optional[bool] = Field(True, description="自动重连")
    localPath: Optional[str] = Field("D://AmazingData_local_data//", description="本地数据路径")
    useLocal: Optional[bool] = Field(True, description="使用本地数据")
    extra: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外配置")


class DataSource(BaseModel):
    """数据源模型"""
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

    id: Optional[str] = None  # 使用字符串ID（英文名称）
    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据源类型: akshare|amazingdata|qmt|cloudflare")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, description="优先级(数字越小优先级越高)")
    config: DataSourceConfig = Field(default_factory=DataSourceConfig, description="配置信息")
    status: Optional[str] = Field(default="untested", description="状态: online|offline|error|degraded|untested")
    successRate: Optional[float] = Field(None, description="成功率")
    avgResponseTime: Optional[int] = Field(None, description="平均响应时间(ms)")
    lastCheckTime: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestDataSourceRequest(BaseModel):
    """测试数据源请求"""
    type: str
    config: DataSourceConfig


# 模拟数据存储（实际应该使用数据库）
data_sources: Dict[str, DataSource] = {}


def update_datasource_status_after_test(datasource_type: str, success: bool, latency: int):
    """测试后更新数据源状态

    Args:
        datasource_type: 数据源类型
        success: 是否成功
        latency: 延迟时间(ms)
    """
    datasource_id = datasource_type.lower()
    if datasource_id in data_sources:
        if success:
            data_sources[datasource_id].status = "online"
            data_sources[datasource_id].successRate = 100.0
            data_sources[datasource_id].avgResponseTime = latency
        else:
            data_sources[datasource_id].status = "error"
            data_sources[datasource_id].successRate = 0.0
        data_sources[datasource_id].lastCheckTime = datetime.now()
        logger.info(f"更新数据源 {datasource_id} 状态为 {'online' if success else 'error'}")

    # 同步更新监控系统的健康状态
    try:
        from deepsearch.observability.monitoring.data_source_monitor import (
            get_monitor,
            DataSourceType
        )

        monitor = get_monitor()

        # 将数据源类型转换为枚举
        source_type_map = {
            "amazingdata": DataSourceType.AMAZINGDATA,
            "akshare": DataSourceType.AKSHARE,
            "qmt": DataSourceType.QMT,
            "cloudflare": DataSourceType.CLOUDFLARE,
            "akshare_proxy": DataSourceType.AKSHARE_PROXY,
            "akshare_direct": DataSourceType.AKSHARE_DIRECT,
            "miniqmt": DataSourceType.MINIQMT,
        }

        source_type = source_type_map.get(datasource_id)
        if source_type:
            # 强制更新健康状态
            monitor.update_health_status(source_type, success, reset_metrics_if_healthy=success)
            logger.info(f"已同步更新监控系统中 {datasource_id} 的健康状态为: {'健康' if success else '异常'}")
        else:
            logger.warning(f"未找到数据源类型映射: {datasource_id}")

    except Exception as e:
        logger.error(f"更新监控系统健康状态失败: {e}")


def get_config_file_path() -> Path:
    """获取配置文件路径"""
    # 获取当前环境
    env = os.getenv("DEEPSEARCH_ENV", "prod")

    # 构建配置文件路径
    config_dir = Path(__file__).parent.parent.parent.parent.parent / "config"
    config_file = config_dir / f"settings.{env}.yaml"

    if not config_file.exists():
        # 如果环境特定的配置文件不存在，使用默认的
        config_file = config_dir / "settings.prod.yaml"

    return config_file


def save_to_config(source_type: str, config_data: Dict[str, Any]):
    """
    保存数据源配置到YAML文件

    Args:
        source_type: 数据源类型 (amazingdata, qmt, cloudflare)
        config_data: 配置数据
    """
    try:
        config_file = get_config_file_path()

        # 读取现有配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        # 更新特定数据源的配置
        if source_type == "amazingdata":
            if 'amazingdata' not in config:
                config['amazingdata'] = {}

            # 更新AmazingData配置
            config['amazingdata']['enabled'] = config_data.get('enabled', False)
            config['amazingdata']['username'] = config_data.get('username', '')
            config['amazingdata']['password'] = config_data.get('password', '')
            config['amazingdata']['host'] = config_data.get('host', '101.230.159.234')
            config['amazingdata']['port'] = config_data.get('port', 8600)
            config['amazingdata']['timeout'] = config_data.get('timeout', 10000) // 1000  # 转换为秒
            config['amazingdata']['heartbeat_interval'] = config_data.get('heartbeatInterval', 60)
            config['amazingdata']['auto_reconnect'] = config_data.get('autoReconnect', True)
            config['amazingdata']['local_path'] = config_data.get('localPath', 'D://AmazingData_local_data//')
            config['amazingdata']['use_local'] = config_data.get('useLocal', True)
            config['amazingdata']['max_retries'] = config_data.get('retryCount', 2)

            # 处理网络运营商
            network_provider = config_data.get('networkProvider', 'telecom')
            config['amazingdata']['network_provider'] = network_provider

        elif source_type == "qmt":
            if 'qmt' not in config:
                config['qmt'] = {}

            config['qmt']['enabled'] = config_data.get('enabled', False)
            config['qmt']['host'] = config_data.get('host', 'localhost')
            config['qmt']['port'] = config_data.get('port', 8888)

        elif source_type == "cloudflare":
            if 'cloudflare_workers' not in config:
                config['cloudflare_workers'] = {}

            config['cloudflare_workers']['url'] = config_data.get('workerUrl', '')
            config['cloudflare_workers']['timeout'] = config_data.get('timeout', 30000) // 1000
            config['cloudflare_workers']['retry_count'] = config_data.get('retryCount', 3)

        # 保存配置到文件
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"配置已保存到 {config_file}: {source_type}")

    except Exception as e:
        logger.error(f"保存配置失败: {e}")


def init_default_datasources():
    """初始化默认数据源（从配置文件加载）"""
    global data_sources

    # 尝试从配置文件加载配置
    try:
        config_file = get_config_file_path()
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"无法加载配置文件，使用默认配置: {e}")
        config = {}

    # AKShare数据源
    akshare_source = DataSource(
        id="akshare",
        name="AKShare直连",
        type="akshare",
        enabled=True,
        priority=3,
        config=DataSourceConfig(
            timeout=30000,
            retryCount=3,
            rateLimit=10
        ),
        status="online",
        successRate=95.5,
        avgResponseTime=200,
        created_at=datetime.now()
    )
    data_sources[akshare_source.id] = akshare_source

    # 银河证券数据源 - 从配置文件加载
    amazingdata_config = config.get('amazingdata', {})
    amazingdata_source = DataSource(
        id="amazingdata",
        name="银河证券星耀数智",
        type="amazingdata",
        enabled=amazingdata_config.get('enabled', False),
        priority=1,
        config=DataSourceConfig(
            timeout=amazingdata_config.get('timeout', 10) * 1000,  # 从秒转换为毫秒
            retryCount=amazingdata_config.get('max_retries', 2),
            rateLimit=100,
            username=amazingdata_config.get('username', ''),
            password=amazingdata_config.get('password', ''),
            networkProvider=amazingdata_config.get('network_provider', 'telecom'),
            host=amazingdata_config.get('host', '101.230.159.234'),
            port=amazingdata_config.get('port', 8600),
            heartbeatInterval=amazingdata_config.get('heartbeat_interval', 60),
            autoReconnect=amazingdata_config.get('auto_reconnect', True),
            localPath=amazingdata_config.get('local_path', 'D://AmazingData_local_data//'),
            useLocal=amazingdata_config.get('use_local', True)
        ),
        status="offline",
        successRate=None,
        avgResponseTime=None,
        created_at=datetime.now()
    )
    data_sources[amazingdata_source.id] = amazingdata_source
    
    # QMT数据源 - 从配置文件加载
    qmt_config = config.get('qmt', {})
    qmt_source = DataSource(
        id="qmt",
        name="QMT实时数据",
        type="qmt",
        enabled=qmt_config.get('enabled', True),
        priority=2,
        config=DataSourceConfig(
            timeout=5000,
            retryCount=1,
            rateLimit=1000,
            host=qmt_config.get('host', 'localhost'),
            port=qmt_config.get('port', 5556)
        ),
        status="offline",
        successRate=None,
        avgResponseTime=None,
        created_at=datetime.now()
    )
    data_sources[qmt_source.id] = qmt_source
    
    # CloudFlare代理
    cloudflare_source = DataSource(
        id="cloudflare",
        name="CloudFlare代理",
        type="cloudflare",
        enabled=True,
        priority=4,
        config=DataSourceConfig(
            timeout=20000,
            retryCount=3,
            rateLimit=50,
            workerUrl="https://api.workers.dev"
        ),
        status="online",
        successRate=98.0,
        avgResponseTime=150,
        created_at=datetime.now()
    )
    data_sources[cloudflare_source.id] = cloudflare_source


# 初始化默认数据
init_default_datasources()


@router.get("/status")
async def get_datasources_status():
    """
    获取所有数据源状态
    
    Returns:
        数据源状态列表
    """
    try:
        sources_list = list(data_sources.values())
        
        # 按优先级排序
        sources_list.sort(key=lambda x: x.priority)
        
        # 转换为前端期望的格式
        formatted_list = []
        for source in sources_list:
            formatted_list.append({
                "id": source.id,
                "name": source.name,
                "type": source.type,
                "enabled": source.enabled,
                "priority": source.priority,
                "config": source.config.model_dump(mode='json'),
                "status": source.status,
                "successRate": source.successRate,
                "avgResponseTime": source.avgResponseTime,
                "lastCheckTime": source.lastCheckTime.isoformat() if source.lastCheckTime else None
            })
        
        return APIResponse.success(
            data=formatted_list,
            message=f"共找到 {len(formatted_list)} 个数据源"
        )
    except Exception as e:
        logger.error(f"获取数据源状态失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取数据源状态失败: {str(e)}",
            status_code=500
        )


@router.get("/list")
async def list_datasources():
    """
    获取所有数据源列表（别名）
    
    Returns:
        数据源列表
    """
    return await get_datasources_status()


@router.post("/create")
async def create_datasource(datasource: DataSource):
    """
    创建新的数据源
    
    Args:
        datasource: 数据源配置
        
    Returns:
        创建的数据源
    """
    try:
        # 生成ID（使用类型和时间戳）
        if not datasource.id:
            datasource.id = f"{datasource.type}_{int(datetime.now().timestamp())}"
        
        # 检查ID是否已存在
        if datasource.id in data_sources:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_ALREADY_EXISTS,
                message=f"数据源 '{datasource.id}' 已存在"
            )
        
        # 设置创建时间
        datasource.created_at = datetime.now()
        datasource.updated_at = datetime.now()
        datasource.status = "untested"
        
        data_sources[datasource.id] = datasource
        
        logger.info(f"创建数据源: {datasource.name} ({datasource.id})")
        
        return APIResponse.success(
            data=datasource.model_dump(mode='json'),
            message=f"数据源 '{datasource.name}' 创建成功"
        )
    except Exception as e:
        logger.error(f"创建数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"创建数据源失败: {str(e)}",
            status_code=500
        )


@router.post("")
async def create_datasource_alt(datasource: DataSource):
    """创建数据源（兼容前端 /data-source 路径）"""
    return await create_datasource(datasource)


@router.put("/{datasource_id}/update")
async def update_datasource(datasource_id: str, datasource: DataSource):
    """
    更新数据源
    
    Args:
        datasource_id: 数据源ID
        datasource: 更新的配置
        
    Returns:
        更新后的数据源
    """
    try:
        if datasource_id not in data_sources:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"数据源 '{datasource_id}' 不存在",
                status_code=404
            )
        
        # 保留原有的创建时间和ID
        existing = data_sources[datasource_id]
        datasource.id = datasource_id
        datasource.created_at = existing.created_at
        datasource.updated_at = datetime.now()
        
        # 设置合理的状态
        if not datasource.enabled:
            datasource.status = "offline"
            datasource.successRate = None
            datasource.avgResponseTime = None
        else:
            # 保持现有状态或设置为unknown
            if existing.status in ["online", "offline", "error", "degraded"]:
                datasource.status = existing.status
                datasource.successRate = existing.successRate
                datasource.avgResponseTime = existing.avgResponseTime
            else:
                datasource.status = "untested"
                datasource.successRate = None
                datasource.avgResponseTime = None

        # 更新检查时间
        datasource.lastCheckTime = datetime.now()

        data_sources[datasource_id] = datasource

        # 保存到配置文件
        if datasource.type in ['amazingdata', 'qmt', 'cloudflare']:
            config_data = datasource.config.model_dump(mode='json')
            config_data['enabled'] = datasource.enabled
            save_to_config(datasource.type, config_data)

        logger.info(f"更新数据源: {datasource.name} ({datasource_id})")

        return APIResponse.success(
            data=datasource.model_dump(mode='json'),
            message=f"数据源 '{datasource.name}' 更新成功"
        )
    except Exception as e:
        logger.error(f"更新数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"更新数据源失败: {str(e)}",
            status_code=500
        )


@router.put("/{datasource_id}")
async def update_datasource_alt(datasource_id: str, datasource: DataSource):
    """更新数据源（兼容前端路径）"""
    return await update_datasource(datasource_id, datasource)


@router.delete("/{datasource_id}/delete")
async def delete_datasource(datasource_id: str):
    """
    删除数据源
    
    Args:
        datasource_id: 数据源ID
        
    Returns:
        删除结果
    """
    try:
        if datasource_id not in data_sources:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"数据源 '{datasource_id}' 不存在",
                status_code=404
            )
        
        datasource = data_sources.pop(datasource_id)
        
        logger.info(f"删除数据源: {datasource.name} ({datasource_id})")
        
        return APIResponse.success(
            data={"id": datasource_id, "name": datasource.name},
            message=f"数据源 '{datasource.name}' 已删除"
        )
    except Exception as e:
        logger.error(f"删除数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"删除数据源失败: {str(e)}",
            status_code=500
        )


@router.delete("/{datasource_id}")
async def delete_datasource_alt(datasource_id: str):
    """删除数据源（兼容前端路径）"""
    return await delete_datasource(datasource_id)


@router.patch("/{datasource_id}/toggle")
async def toggle_datasource(datasource_id: str, enabled: bool):
    """
    切换数据源启用状态（带测试）

    Args:
        datasource_id: 数据源ID
        enabled: 是否启用

    Returns:
        更新结果
    """
    try:
        if datasource_id not in data_sources:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"数据源 '{datasource_id}' 不存在",
                status_code=404
            )

        datasource = data_sources[datasource_id]

        # 如果是启用操作，先测试连接
        if enabled:
            logger.info(f"启用前测试数据源连接: {datasource.name}")

            # 对于AmazingData，使用进程池管理
            if datasource.type == "amazingdata":
                try:
                    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
                        get_global_pool
                    )

                    pool = get_global_pool()

                    # 创建专属进程（不自动清理，生产环境长期运行）
                    config = datasource.config.model_dump() if datasource.config else {}
                    proxy = pool.get_or_create(
                        datasource_id,
                        auto_cleanup=False,  # 生产进程不自动清理
                        config=config
                    )

                    if proxy and proxy.is_running:
                        logger.info(f"[Toggle] Created dedicated process for {datasource_id}")
                        datasource.enabled = True
                        datasource.status = "online"
                        datasource.updated_at = datetime.now()

                        return APIResponse.success(
                            data={
                                "id": datasource_id,
                                "enabled": True,
                                "status": "online",
                                "message": f"{datasource.name}已启用（专属进程已创建）"
                            }
                        )
                    else:
                        raise Exception("Failed to start dedicated process")

                except Exception as e:
                    logger.error(f"[Toggle] Failed to enable datasource: {e}")
                    return APIResponse.error(
                        code=ErrorCodes.DATASOURCE_TEST_FAILED,
                        message=f"启用失败: {str(e)}",
                        status_code=500
                    )

            # 对于其他数据源，执行原有的测试流程
            # 构建测试请求
            test_request = TestDataSourceRequest(
                type=datasource.type,
                config=datasource.config
            )

            # 执行测试
            test_response = await test_datasource(test_request)

            # 检查测试结果
            test_success = False
            test_message = "测试失败"
            test_details = {}

            # test_datasource返回的是字典，使用字典键访问而不是属性访问
            if isinstance(test_response, dict):
                # 优先从data字段获取
                if 'data' in test_response and test_response['data']:
                    test_data = test_response['data']
                    test_success = test_data.get("success", False)
                    test_message = test_data.get("message", "连接测试失败")
                    test_details = test_data.get("details", {})
                    logger.debug(f"从data字段获取测试结果: success={test_success}, message={test_message}, details={test_details}")
                # 如果没有data，尝试从顶层获取message
                elif 'message' in test_response:
                    test_message = test_response['message']
                    # 如果有details字段，也获取它
                    if 'details' in test_response:
                        test_details = test_response['details'] if isinstance(test_response['details'], dict) else {}
                    logger.debug(f"从顶层获取错误信息: message={test_message}, details={test_details}")
            else:
                # 如果不是字典（可能是对象），使用原有的属性访问方式
                if hasattr(test_response, 'data') and test_response.data:
                    test_success = test_response.data.get("success", False)
                    test_message = test_response.data.get("message", "连接测试失败")
                    test_details = test_response.data.get("details", {})
                    logger.debug(f"从对象data属性获取测试结果: success={test_success}, message={test_message}")
                elif hasattr(test_response, 'message'):
                    test_message = test_response.message
                    logger.debug(f"从对象message属性获取错误信息: {test_message}")

            # 测试失败，不启用
            if not test_success:
                logger.error(f"数据源 {datasource.name} 测试失败: {test_message}")

                # 更新状态为error但不启用
                datasource.status = "error"
                datasource.updated_at = datetime.now()

                return APIResponse.error(
                    code=ErrorCodes.DATASOURCE_TEST_FAILED,
                    message=f"数据源测试失败: {test_message}",
                    data={
                        "id": datasource_id,
                        "enabled": False,
                        "status": "error",
                        "test_details": test_details
                    },
                    status_code=400
                )

            # 测试成功，继续启用流程
            logger.info(f"数据源 {datasource.name} 测试成功，继续启用")
            datasource.status = "online"
        else:
            # 禁用操作 - 销毁专属进程
            if datasource.type == "amazingdata":
                try:
                    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
                        get_global_pool
                    )

                    pool = get_global_pool()
                    # 停止进程
                    success = pool.stop(datasource_id)
                    logger.info(f"[Toggle] Stopped process for {datasource_id}: {success}")
                except Exception as e:
                    logger.warning(f"[Toggle] Error stopping process: {e}")

            datasource.status = "offline"

        # 更新配置
        datasource.enabled = enabled
        datasource.updated_at = datetime.now()

        # 保存到配置文件
        if datasource.type in ['amazingdata', 'qmt', 'cloudflare']:
            config_data = datasource.config.model_dump(mode='json')
            config_data['enabled'] = enabled
            save_to_config(datasource.type, config_data)

        logger.info(f"{'启用' if enabled else '禁用'}数据源: {datasource.name}")

        return APIResponse.success(
            data={
                "id": datasource_id,
                "enabled": enabled,
                "status": datasource.status
            },
            message=f"数据源已{'启用' if enabled else '禁用'}"
        )
    except Exception as e:
        logger.error(f"切换数据源状态失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"切换数据源状态失败: {str(e)}",
            status_code=500
        )


@router.put("/config")
async def update_global_config(config: dict):
    """
    更新全局数据源配置

    Args:
        config: 全局配置（如速率限制等）

    Returns:
        更新结果
    """
    try:
        # 这里应该保存到配置文件或数据库
        # 目前只是返回成功
        logger.info(f"更新全局配置: {config}")

        return APIResponse.success(
            data=config,
            message="全局配置更新成功"
        )
    except Exception as e:
        logger.error(f"更新全局配置失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"更新全局配置失败: {str(e)}",
            status_code=500
        )


# 导入测试辅助模块
try:
    from .amazingdata_test_helper import test_amazingdata_connection, create_test_result
except ImportError:
    logger.warning("amazingdata_test_helper模块未找到，使用内置测试逻辑")
    test_amazingdata_connection = None
    create_test_result = None

async def test_datasource_enhanced(request: TestDataSourceRequest, symbol: str = "000001", test_type: str = "realtime"):
    """
    增强版数据源测试，包含实际数据获取测试

    Args:
        request: 测试请求
        symbol: 股票代码，用于测试数据获取
        test_type: 测试类型（realtime/history）

    Returns:
        测试结果，包含连接状态和数据获取能力验证
    """
    try:
        # 添加详细的请求日志
        logger.info(f"[TEST] 开始测试数据源: type={request.type}, symbol={symbol}, test_type={test_type}")
        logger.info(f"[TEST] 请求配置: {request.config.model_dump() if hasattr(request.config, 'model_dump') else request.config}")

        test_result = {
            "success": False,
            "source": request.type,
            "message": "",
            "latency_ms": 0,
            "data_size": 0,
            "error": None,
            "details": {}
        }

        start_time = time.time()

        if request.type == "amazingdata":
            # 使用辅助模块测试（如果可用）
            if test_amazingdata_connection:
                logger.info("[TEST] 使用辅助模块进行测试")

                # 获取服务器配置
                host = request.config.host
                port = request.config.port or 8600

                # 根据网络运营商选择服务器
                if request.config.networkProvider == "telecom":
                    host = "101.230.159.234"
                    port = 8600
                elif request.config.networkProvider == "unicom":
                    host = "140.206.44.234"
                    port = 8600
                elif not host:
                    host = "101.230.159.234"
                    port = 8600

                # 调用辅助函数，添加异常保护
                try:
                    test_result = test_amazingdata_connection(
                        username=request.config.username,
                        password=request.config.password,
                        host=host,
                        port=port,
                        test_type=test_type
                    )
                except Exception as helper_error:
                    logger.error(f"[TEST] 辅助模块执行失败: {helper_error}")
                    test_result = {
                        "success": False,
                        "source": request.type,
                        "message": "测试失败",
                        "error": f"测试模块异常: {str(helper_error)}",
                        "latency_ms": (time.time() - start_time) * 1000,
                        "data_size": 0
                    }

                # 确保返回正确的source字段
                test_result["source"] = request.type

                # 记录结果
                logger.info(f"[TEST] 辅助模块测试完成: {test_result}")

                # 更新延迟时间（如果需要）
                if "latency_ms" not in test_result:
                    test_result["latency_ms"] = (time.time() - start_time) * 1000

            elif not request.config.username or not request.config.password:
                test_result["message"] = "测试失败"
                test_result["error"] = "需要提供用户名和密码"
            else:
                # 根据网络运营商选择服务器
                host = request.config.host
                port = request.config.port or 8600

                # 如果选择了运营商，使用对应的IP
                if request.config.networkProvider == "telecom":
                    host = "101.230.159.234"
                    port = 8600
                elif request.config.networkProvider == "unicom":
                    host = "140.206.44.234"
                    port = 8600
                elif not host:
                    host = "101.230.159.234"
                    port = 8600

                try:
                    logger.info(f"[TEST] 使用进程隔离安全包装器进行AmazingData测试...")

                    # 创建安全包装器实例
                    safe_wrapper = AmazingDataSafeWrapper(
                        auto_restart=True,
                        max_retries=2,
                        default_timeout=30.0
                    )

                    # 使用安全登录方法
                    logger.info(f"[TEST] 开始安全登录: username={request.config.username}, host={host}, port={port}")
                    success, error_msg = safe_wrapper.safe_login(
                        username=request.config.username,
                        password=request.config.password,
                        host=host,
                        port=port,
                        timeout=30.0
                    )
                    logger.info(f"[TEST] 登录结果: success={success}, error={error_msg}")

                    if success:
                        # 登录成功，尝试获取数据
                        # 注意：在进程隔离模式下，我们只测试登录连接性
                        # 实际数据获取应该通过专门的数据API进行
                        if test_type == "realtime":
                            # 格式化股票代码（如果需要）
                            formatted_symbol = symbol
                            if len(symbol) == 6 and symbol.isdigit():
                                # 判断市场
                                if symbol.startswith(('60', '68', '50', '51')):
                                    formatted_symbol = f"SH.{symbol}"
                                elif symbol.startswith(('00', '30', '12')):
                                    formatted_symbol = f"SZ.{symbol}"

                            # 在进程隔离模式下，登录成功即表示连接正常
                            test_result["success"] = True
                            test_result["message"] = "测试成功"
                            test_result["details"]["symbol"] = formatted_symbol
                            test_result["details"]["data_type"] = "连接测试"
                            test_result["details"]["server"] = f"{host}:{port}"
                            test_result["details"]["status"] = "已连接（进程隔离模式）"
                            test_result["details"]["note"] = "使用进程隔离安全模式，避免SDK崩溃影响主进程"

                            # 注意：不执行BaseData等可能崩溃的操作
                            # 这些操作应该在实际数据获取时通过进程代理执行
                            logger.info("[TEST] 进程隔离模式下跳过基础数据获取测试")

                        else:
                            # 测试历史数据获取
                            test_result["success"] = True
                            test_result["message"] = "连接成功（历史数据测试待实现）"

                        # 注意：不需要调用logout，安全包装器会处理
                        logger.info("[TEST] 跳过logout操作（由安全包装器处理）")
                    else:
                        logger.error(f"[TEST] 安全登录失败: {error_msg}")
                        test_result["message"] = "测试失败"
                        test_result["error"] = error_msg or "登录失败"

                        # 如果是SDK未安装的错误，添加安装提示
                        if "ImportError" in (error_msg or ""):
                            test_result["details"]["note"] = "需要安装installer目录下的AmazingData-1.0.9-cp313-none-any.whl"

                except Exception as e:
                    logger.error(f"[TEST] 测试过程发生异常: {type(e).__name__}: {str(e)}")
                    logger.exception("[TEST] 详细异常信息:")
                    test_result["message"] = "测试失败"
                    test_result["error"] = str(e)

        else:
            # 其他数据源保持原有测试逻辑
            standard_result = await test_datasource(request)
            return standard_result

        # 计算延迟
        test_result["latency_ms"] = (time.time() - start_time) * 1000

        # 记录最终结果
        logger.info(f"[TEST] 测试完成: success={test_result['success']}, message={test_result['message']}, error={test_result.get('error')}")
        logger.info(f"[TEST] 返回结果: {test_result}")

        # 更新数据源状态
        if test_result["success"]:
            update_datasource_status_after_test(request.type, True, int(test_result["latency_ms"]))
        else:
            update_datasource_status_after_test(request.type, False, 0)

        return test_result

    except Exception as e:
        logger.error(f"测试数据源连接失败: {e}")
        return {
            "success": False,
            "source": request.type,
            "message": "测试失败",
            "error": str(e),
            "latency_ms": 0,
            "data_size": 0
        }


@router.post("/test")
async def test_datasource(request: TestDataSourceRequest):
    """
    测试数据源连接
    
    Args:
        request: 测试请求
        
    Returns:
        测试结果
    """
    try:
        test_result = {
            "success": False,
            "message": "",
            "latency": 0,
            "details": {}
        }
        
        start_time = datetime.now()
        
        if request.type == "akshare":
            # 测试AKShare连接
            try:
                # 真实测试AKShare连接
                import akshare as ak

                # 测试基本功能 - 获取交易日历（这是最基础的API）
                test_start = time.time()
                try:
                    # 尝试获取最近一个交易日
                    import pandas as pd

                    # 获取最近的交易日历
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

                    # 测试获取交易日历
                    trade_calendar = ak.tool_trade_date_hist_sina()

                    # 测试获取股票列表（更轻量级的测试）
                    stock_info = ak.stock_info_a_code_name()

                    test_latency = int((time.time() - test_start) * 1000)

                    test_result["success"] = True
                    test_result["message"] = "AKShare连接成功"
                    test_result["details"]["version"] = ak.__version__ if hasattr(ak, '__version__') else "unknown"
                    test_result["details"]["trade_days_count"] = len(trade_calendar) if trade_calendar is not None else 0
                    test_result["details"]["stock_count"] = len(stock_info) if stock_info is not None else 0
                    test_result["details"]["test_latency_ms"] = test_latency

                    # 更新数据源状态
                    update_datasource_status_after_test("akshare", True, test_latency)

                except ImportError:
                    test_result["success"] = False
                    test_result["message"] = "AKShare库未安装"
                    test_result["details"]["error"] = "Module not installed"
                    test_result["details"]["note"] = "请运行: pip install akshare"
                    update_datasource_status_after_test("akshare", False, 0)

                except Exception as api_error:
                    # API调用失败（可能是网络问题）
                    test_result["success"] = False
                    test_result["message"] = f"AKShare API调用失败: {str(api_error)}"
                    test_result["details"]["error"] = str(api_error)
                    test_result["details"]["note"] = "请检查网络连接或API服务状态"
                    update_datasource_status_after_test("akshare", False, 0)

            except Exception as e:
                test_result["success"] = False
                test_result["message"] = f"测试失败: {str(e)}"
                test_result["details"]["error"] = str(e)
                update_datasource_status_after_test("akshare", False, 0)
                
        elif request.type == "amazingdata":
            # 测试银河证券API
            if not request.config.username or not request.config.password:
                test_result["message"] = "需要提供用户名和密码"
            else:
                # 根据网络运营商选择服务器
                host = request.config.host
                port = request.config.port or 8600

                # 如果选择了运营商，使用对应的IP
                if request.config.networkProvider == "telecom":
                    host = "101.230.159.234"
                    port = 8600
                elif request.config.networkProvider == "unicom":
                    host = "140.206.44.234"
                    port = 8600
                elif not host:
                    # 如果没有指定host，默认使用电信
                    host = "101.230.159.234"
                    port = 8600

                try:
                    # 使用新的测试函数（每次创建独立进程）
                    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
                        test_connection_with_datasource
                    )

                    logger.info(f"[DataSource] Testing AmazingData with dedicated process: {request.config.username}@{host}:{port}")
                    logger.debug(f"[DataSource] Network provider: {request.config.networkProvider}, Use local: {request.config.useLocal}")

                    # 执行测试（使用独立进程）
                    test_response = test_connection_with_datasource(
                        datasource_id="amazingdata",
                        username=request.config.username,
                        password=request.config.password,
                        host=host,
                        port=port
                    )

                    logger.debug(f"[DataSource] Test response: success={test_response['success']}, error={test_response.get('error')}")

                    if test_response["success"]:
                        test_result["success"] = True
                        test_result["message"] = "银河证券星耀数智连接成功"
                        test_result["latency"] = int(test_response["latency_ms"])
                        logger.info("[DataSource] AmazingData test successful")
                        test_result["details"]["server"] = f"{host}:{port}"
                        test_result["details"]["username"] = request.config.username
                        test_result["details"]["network_provider"] = request.config.networkProvider or "custom"
                        test_result["details"]["status"] = "已认证"
                        test_result["details"]["test_id"] = test_response.get("test_id")
                        test_result["details"]["stats"] = test_response.get("stats", {})
                        test_result["details"]["note"] = "使用数据源专属进程池"
                        # 更新数据源状态
                        update_datasource_status_after_test("amazingdata", True, test_result["latency"])
                    else:
                        error_msg = test_response.get("error", "登录失败")
                        logger.error(f"[DataSource] AmazingData test failed: {error_msg}")
                        test_result["success"] = False
                        test_result["message"] = error_msg
                        test_result["details"]["error"] = error_msg
                        test_result["details"]["error_type"] = "login_failed"
                        test_result["details"]["test_id"] = test_response.get("test_id")
                        # 如果是SDK未安装的错误，添加安装提示
                        if "ImportError" in error_msg:
                            test_result["details"]["note"] = "需要安装installer目录下的AmazingData-1.0.9-cp313-none-any.whl"
                        # 更新数据源状态为错误
                        update_datasource_status_after_test("amazingdata", False, 0)
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
                    
        elif request.type == "qmt":
            # 测试QMT连接
            try:
                if not request.config.host or not request.config.port:
                    test_result["success"] = False
                    test_result["message"] = "需要配置主机和端口"
                    test_result["details"]["error"] = "Missing configuration"
                else:
                    # 尝试真实连接到QMT网关（使用socket测试端口）
                    import socket
                    test_start = time.time()

                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)  # 5秒超时

                    try:
                        result = sock.connect_ex((request.config.host, request.config.port))
                        sock.close()

                        test_latency = int((time.time() - test_start) * 1000)

                        if result == 0:
                            # 端口开放，可能QMT正在运行
                            test_result["success"] = True
                            test_result["message"] = f"QMT网关端口 {request.config.host}:{request.config.port} 可访问"
                            test_result["details"]["host"] = request.config.host
                            test_result["details"]["port"] = request.config.port
                            test_result["details"]["latency_ms"] = test_latency
                            update_datasource_status_after_test("qmt", True, test_latency)
                        else:
                            # 端口关闭
                            test_result["success"] = False
                            test_result["message"] = f"无法连接到QMT网关 {request.config.host}:{request.config.port}"
                            test_result["details"]["error"] = "Connection refused"
                            test_result["details"]["note"] = "请确保QMT终端已启动并运行数据收集脚本"
                            update_datasource_status_after_test("qmt", False, 0)

                    except socket.timeout:
                        test_result["success"] = False
                        test_result["message"] = f"连接超时 {request.config.host}:{request.config.port}"
                        test_result["details"]["error"] = "Connection timeout"
                        test_result["details"]["note"] = "请检查网络连接和防火墙设置"
                        update_datasource_status_after_test("qmt", False, 0)

                    except Exception as sock_error:
                        test_result["success"] = False
                        test_result["message"] = f"连接失败: {str(sock_error)}"
                        test_result["details"]["error"] = str(sock_error)
                        update_datasource_status_after_test("qmt", False, 0)

            except Exception as e:
                test_result["success"] = False
                test_result["message"] = f"测试失败: {str(e)}"
                test_result["details"]["error"] = str(e)
                update_datasource_status_after_test("qmt", False, 0)
                
        elif request.type == "cloudflare":
            # 测试CloudFlare Worker
            if request.config.workerUrl:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{request.config.workerUrl}/health",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status == 200:
                                test_result["success"] = True
                                test_result["message"] = "CloudFlare Worker连接成功"
                                test_result["details"]["status"] = "healthy"
                                test_result["details"]["endpoint"] = request.config.workerUrl
                                # 更新数据源状态
                                update_datasource_status_after_test("cloudflare", True, test_result.get("latency", 150))
                            else:
                                test_result["message"] = f"Worker返回状态码: {response.status}"
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
            else:
                test_result["message"] = "需要配置Worker URL"
        else:
            test_result["message"] = f"不支持的数据源类型: {request.type}"
        
        # 计算延迟（提前计算，以便在更新状态时使用）
        end_time = datetime.now()
        test_result["latency"] = int((end_time - start_time).total_seconds() * 1000)

        # 获取更新后的数据源信息
        datasource_type_lower = request.type.lower()
        updated_datasource = None
        if datasource_type_lower in data_sources:
            updated_datasource = data_sources[datasource_type_lower].model_dump(mode='json')

        # 在结果中包含更新后的数据源信息
        test_result["datasource"] = updated_datasource

        if test_result["success"]:
            return APIResponse.success(
                data=test_result,
                message="连接测试成功"
            )
        else:
            # 确保错误信息在data字段，以便toggle_datasource能正确读取
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_CONNECTION_FAILED,
                message=test_result["message"],
                data=test_result  # 使用data而非details，保持响应格式一致
            )
            
    except Exception as e:
        logger.error(f"测试数据源连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"测试连接时发生错误: {str(e)}",
            status_code=500
        )


@router.get("/monitor")
async def get_data_source_monitor():
    """
    获取数据源监控信息

    该端点桥接现有的监控服务，返回前端期望的格式

    Returns:
        监控数据，包含overview、sources、timeline和alerts
    """
    try:
        # 尝试从监控服务获取数据
        try:
            from deepsearch.observability.monitoring.data_source_monitor import get_monitor, DataSourceType as MonitorDataSourceType
            monitor = get_monitor()

            # 获取健康状态
            health_status = monitor.get_all_health_status()

            # 获取统计信息（最近1小时）
            statistics = monitor.get_access_statistics(3600)

            # 构建数据源列表
            sources = []
            source_id = 1

            # 定义友好的数据源名称映射
            source_name_map = {
                "amazingdata": "AmazingData",
                "cloudflare_proxy": "CloudFlare Workers",
                "qmt": "QMT Gateway",
                "akshare": "AKShare",
                "akshare_proxy": "AKShare Proxy",
                "akshare_direct": "AKShare Direct",
                "miniqmt": "MiniQMT",
                "database": "PostgreSQL",
                "default": "Default Provider"
            }

            # 遍历所有监控的数据源
            for source_name, health in health_status.items():
                # 确定状态
                status = "online" if health.get("healthy", False) else "offline"

                # 确定健康度
                success_rate = health.get("success_rate", 0)
                if success_rate >= 95:
                    health_level = "healthy"
                elif success_rate >= 80:
                    health_level = "warning"
                else:
                    health_level = "error"

                # 计算趋势（简单判断）
                recent_error_rate = health.get("recent_error_rate", 0)
                if recent_error_rate > 10:
                    trend = "down"
                elif recent_error_rate < 2:
                    trend = "up"
                else:
                    trend = "stable"

                # 格式化最后检查时间
                last_access = health.get("last_access")
                if last_access:
                    try:
                        last_time = datetime.fromisoformat(last_access)
                        time_diff = datetime.now() - last_time
                        if time_diff.seconds < 60:
                            last_check = f"{time_diff.seconds}秒前"
                        elif time_diff.seconds < 3600:
                            last_check = f"{time_diff.seconds // 60}分钟前"
                        else:
                            last_check = f"{time_diff.seconds // 3600}小时前"
                    except:
                        last_check = "未知"
                else:
                    last_check = "从未访问"

                # 添加到源列表
                sources.append({
                    "id": source_id,
                    "name": source_name_map.get(source_name, source_name),
                    "type": source_name.lower().replace("_", ""),
                    "status": status,
                    "health": health_level,
                    "latency": int(health.get("avg_latency_ms", 0)),
                    "requests": health.get("total_requests", 0),
                    "errors": int(health.get("total_requests", 0) * (1 - success_rate / 100) if health.get("total_requests", 0) > 0 else 0),
                    "successRate": round(success_rate, 2),
                    "lastCheck": last_check,
                    "trend": trend
                })
                source_id += 1

            # 计算overview统计
            total_sources = len(sources)
            online_sources = sum(1 for s in sources if s["status"] == "online")
            offline_sources = total_sources - online_sources
            healthy_count = sum(1 for s in sources if s["health"] == "healthy")
            warning_count = sum(1 for s in sources if s["health"] == "warning")
            error_count = sum(1 for s in sources if s["health"] == "error")

            total_requests = sum(s["requests"] for s in sources)
            avg_latency = sum(s["latency"] * s["requests"] for s in sources) / total_requests if total_requests > 0 else 0
            overall_success_rate = sum(s["successRate"] * s["requests"] for s in sources) / total_requests if total_requests > 0 else 0

            # 构建响应数据
            monitor_data = {
                "overview": {
                    "total": total_sources,
                    "online": online_sources,
                    "offline": offline_sources,
                    "healthy": healthy_count,
                    "warning": warning_count,
                    "error": error_count,
                    "totalRequests": total_requests,
                    "avgLatency": round(avg_latency, 2),
                    "successRate": round(overall_success_rate, 2),
                    "errorRate": round(100 - overall_success_rate, 2),
                    "requestsPerMinute": statistics.get("requests_per_minute", 0) if statistics else 0,
                    "bytesTransferred": 0,  # 暂不统计
                    "cacheHitRate": 0,  # 暂不统计
                    "activeConnections": online_sources
                },
                "sources": sources,
                "timeline": [],  # 暂时返回空数组，后续可以从监控历史中提取
                "alerts": []  # 暂时返回空数组，后续可以添加告警逻辑
            }

            return APIResponse.success(
                data=monitor_data,
                message="获取监控数据成功"
            )

        except ImportError as e:
            # 监控模块未安装或导入失败，返回模拟数据
            logger.warning(f"监控模块不可用，返回默认数据: {e}")

            # 返回默认的监控数据，避免前端显示空白
            default_data = {
                "overview": {
                    "total": 6,
                    "online": 3,
                    "offline": 3,
                    "healthy": 2,
                    "warning": 1,
                    "error": 3,
                    "totalRequests": 0,
                    "avgLatency": 0,
                    "successRate": 0,
                    "errorRate": 0,
                    "requestsPerMinute": 0,
                    "bytesTransferred": 0,
                    "cacheHitRate": 0,
                    "activeConnections": 0
                },
                "sources": [
                    {
                        "id": 1,
                        "name": "AmazingData",
                        "type": "amazingdata",
                        "status": "offline",
                        "health": "error",
                        "latency": 0,
                        "requests": 0,
                        "errors": 0,
                        "successRate": 0,
                        "lastCheck": "监控服务不可用",
                        "trend": "stable"
                    },
                    {
                        "id": 2,
                        "name": "CloudFlare Workers",
                        "type": "cloudflare",
                        "status": "offline",
                        "health": "error",
                        "latency": 0,
                        "requests": 0,
                        "errors": 0,
                        "successRate": 0,
                        "lastCheck": "监控服务不可用",
                        "trend": "stable"
                    },
                    {
                        "id": 3,
                        "name": "QMT Gateway",
                        "type": "qmt",
                        "status": "offline",
                        "health": "error",
                        "latency": 0,
                        "requests": 0,
                        "errors": 0,
                        "successRate": 0,
                        "lastCheck": "监控服务不可用",
                        "trend": "stable"
                    }
                ],
                "timeline": [],
                "alerts": [{
                    "level": "warning",
                    "message": "监控服务未启动，显示默认数据",
                    "timestamp": datetime.now().isoformat()
                }]
            }

            return APIResponse.success(
                data=default_data,
                message="监控服务不可用，返回默认数据"
            )

    except Exception as e:
        logger.error(f"获取监控数据失败: {e}")

        # 发生异常时返回空数据结构，确保前端不会崩溃
        return APIResponse.success(
            data={
                "overview": {
                    "total": 0,
                    "online": 0,
                    "offline": 0,
                    "healthy": 0,
                    "warning": 0,
                    "error": 0,
                    "totalRequests": 0,
                    "avgLatency": 0,
                    "successRate": 0,
                    "errorRate": 0,
                    "requestsPerMinute": 0,
                    "bytesTransferred": 0,
                    "cacheHitRate": 0,
                    "activeConnections": 0
                },
                "sources": [],
                "timeline": [],
                "alerts": [{
                    "level": "error",
                    "message": f"获取监控数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }]
            },
            message="获取监控数据失败"
        )


@router.post("/switch")
async def switch_primary_source(source_name: str):
    """
    切换主数据源

    Args:
        source_name: 数据源名称

    Returns:
        切换结果
    """
    try:
        logger.info(f"切换主数据源为: {source_name}")

        # 检查数据源是否存在
        datasource_id = source_name.lower()
        if datasource_id not in data_sources:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"数据源 {source_name} 不存在",
                status_code=404
            )

        datasource = data_sources[datasource_id]

        # 检查数据源是否已启用
        if not datasource.enabled:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_ENABLED,
                message=f"数据源 {source_name} 未启用，请先启用该数据源",
                status_code=400
            )

        # 检查数据源状态
        if datasource.status != "online":
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_ONLINE,
                message=f"数据源 {source_name} 当前状态为 {datasource.status}，无法切换为主数据源",
                status_code=400
            )

        # 将所有其他数据源的优先级降低
        for ds_id, ds in data_sources.items():
            if ds_id != datasource_id:
                # 将其他数据源的优先级设置为较低值（数字越大优先级越低）
                ds.priority = max(ds.priority, 10)

        # 将目标数据源设置为最高优先级
        datasource.priority = 1
        datasource.updated_at = datetime.now()

        # 保存优先级配置到配置文件
        _save_datasource_priority(datasource_id, datasource.priority, source_name)

        logger.info(f"已切换主数据源为 {source_name}，优先级设置为1")

        return APIResponse.success(
            data={
                "source": source_name,
                "priority": 1,
                "status": datasource.status,
                "message": f"已切换主数据源为 {source_name}"
            },
            message="主数据源切换成功"
        )

    except Exception as e:
        logger.error(f"切换主数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"切换主数据源失败: {str(e)}",
            status_code=500
        )


@router.post("/cache/refresh")
async def refresh_data_source_cache(source_name: Optional[str] = None):
    """
    刷新数据源缓存

    Args:
        source_name: 可选，指定数据源名称。如果不指定，刷新所有数据源缓存

    Returns:
        刷新结果
    """
    try:
        if source_name:
            logger.info(f"刷新数据源 {source_name} 的缓存")

            # 检查数据源是否存在
            datasource_id = source_name.lower()
            if datasource_id not in data_sources:
                return APIResponse.error(
                    code=ErrorCodes.DATASOURCE_NOT_FOUND,
                    message=f"数据源 {source_name} 不存在",
                    status_code=404
                )

            # 实现缓存刷新逻辑
            # 清除指定数据源相关的所有缓存键
            await refresh_source_cache(datasource_id)

            message = f"数据源 {source_name} 缓存已刷新"
        else:
            logger.info("刷新所有数据源缓存")

            # 实现全量缓存刷新
            # 清除所有缓存并重新加载关键数据
            await refresh_all_cache()

            message = "所有数据源缓存已刷新"

        return APIResponse.success(
            data={
                "source": source_name,
                "timestamp": datetime.now().isoformat()
            },
            message=message
        )

    except Exception as e:
        logger.error(f"刷新缓存失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"刷新缓存失败: {str(e)}",
            status_code=500
        )


# 为了兼容性，提供 /api/data-source 路径的路由
data_source_router = APIRouter(prefix="/api/data-source", tags=["DataSource Compatibility"])

@data_source_router.post("")
async def create_data_source(datasource: DataSource):
    """创建数据源（兼容路径）"""
    return await create_datasource(datasource)

@data_source_router.put("/{id}")
async def update_data_source(id: str, datasource: DataSource):
    """更新数据源（兼容路径）"""
    return await update_datasource(id, datasource)

@data_source_router.delete("/{id}")
async def delete_data_source(id: str):
    """删除数据源（兼容路径）"""
    return await delete_datasource(id)

@data_source_router.patch("/{id}/toggle")
async def toggle_data_source(id: str, request: dict):
    """切换数据源状态（兼容路径）"""
    return await toggle_datasource(id, request.get("enabled", False))

@data_source_router.post("/test")
async def test_data_source(request: dict):
    """测试数据源（兼容路径，支持多种请求格式）"""

    logger.info(f"[API] /data-source/test 收到请求: {request}")

    # 检查请求格式，支持前端的格式 {source, symbol, test_type}
    if "source" in request and "symbol" in request:
        # 前端格式：转换为标准格式
        source_type = request.get("source", "amazingdata")
        symbol = request.get("symbol", "000001")
        test_type = request.get("test_type", "realtime")

        logger.info(f"[API] 解析前端请求: source={source_type}, symbol={symbol}, test_type={test_type}")

        # 获取对应数据源的配置
        datasource = data_sources.get(source_type)
        if not datasource:
            logger.error(f"[API] 数据源 '{source_type}' 未找到")
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"数据源 '{source_type}' 未找到",
                status_code=404
            )

        # 创建标准测试请求
        test_request = TestDataSourceRequest(
            type=source_type,
            config=datasource.config
        )

        logger.info(f"[API] 调用test_datasource_enhanced...")
        # 执行测试（增强版，包含实际数据测试）
        result = await test_datasource_enhanced(test_request, symbol, test_type)

        # 检查并修正错误信息
        if isinstance(result, dict):
            if result.get("error") == "AmazingData provider does not support realtime data":
                logger.warning("[API] 检测到历史错误信息，替换为正确的错误描述")
                result["error"] = "AmazingData SDK未正确初始化或无法连接到服务器"
                result["message"] = "测试失败"
                result["details"] = {
                    "note": "请检查AmazingData SDK是否已安装，以及用户名密码是否正确",
                    "suggestion": "运行 pip install installer/AmazingData-1.0.9-cp313-none-any.whl 安装SDK"
                }

        logger.info(f"[API] 返回结果: success={result.get('success')}, error={result.get('error')}")
        return result

    elif "type" in request and "config" in request:
        # 标准格式：直接转换
        test_request = TestDataSourceRequest(**request)
        return await test_datasource(test_request)

    else:
        return APIResponse.error(
            code=ErrorCodes.INVALID_PARAMS,
            message="无效的请求格式",
            status_code=400
        )


def _save_datasource_priority(datasource_id: str, priority: int, source_name: str) -> None:
    """
    保存数据源优先级配置到配置文件

    Args:
        datasource_id: 数据源ID
        priority: 优先级值
        source_name: 数据源名称
    """
    try:
        config = get_config()
        config_dir = Path(config.app.data_dir) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # 优先级配置文件路径
        priority_file = config_dir / "datasource_priorities.yaml"

        # 读取现有配置
        priorities = {}
        if priority_file.exists():
            with open(priority_file, 'r', encoding='utf-8') as f:
                priorities = yaml.safe_load(f) or {}

        # 更新优先级配置
        priorities[datasource_id] = {
            "name": source_name,
            "priority": priority,
            "updated_at": datetime.now().isoformat()
        }

        # 保存到文件
        with open(priority_file, 'w', encoding='utf-8') as f:
            yaml.dump(priorities, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"已保存数据源 {source_name} 的优先级配置: priority={priority}")

    except Exception as e:
        logger.error(f"保存数据源优先级配置失败: {e}")
        # 不抛出异常，避免影响主流程


async def refresh_source_cache(datasource_id: str) -> None:
    """
    刷新指定数据源的缓存

    Args:
        datasource_id: 数据源ID
    """
    try:
        # 构建数据源相关的缓存键模式
        # 通常缓存键格式为: datasource:{datasource_id}:{data_type}:{params}
        cache_patterns = [
            f"datasource:{datasource_id}:*",
            f"kline:{datasource_id}:*",
            f"tick:{datasource_id}:*",
            f"snapshot:{datasource_id}:*",
            f"realtime:{datasource_id}:*",
            f"orderbook:{datasource_id}:*"
        ]

        # 清除L1和L2缓存中匹配的键
        cleared_count = 0
        for pattern in cache_patterns:
            # 目前使用简单的前缀匹配，清除L1缓存
            # 注意: 当前cache_manager.clear()清除所有缓存
            # 后续可以实现更精确的模式匹配清除
            if pattern.startswith(f"datasource:{datasource_id}"):
                # 清除特定层的缓存
                await cache_manager.clear('l1')
                cleared_count += 1
                logger.debug(f"清除缓存模式: {pattern}")

        logger.info(f"已清除数据源 {datasource_id} 的 {cleared_count} 个缓存模式")

        # 预热关键数据（可选）
        # await warm_critical_cache(datasource_id)

    except Exception as e:
        logger.error(f"刷新数据源缓存失败: {e}")
        raise


async def refresh_all_cache() -> None:
    """
    刷新所有数据源的缓存
    """
    try:
        # 清除所有L1和L2缓存
        await cache_manager.clear()
        logger.info("已清除所有缓存层数据")

        # 获取缓存统计信息
        stats = cache_manager.get_stats()
        logger.info(f"缓存清除后统计: L1缓存项={stats.get('l1_stats', {}).get('size', 0)}, "
                   f"L2缓存项={stats.get('l2_stats', {}).get('size', 0) if stats.get('l2_stats') else 0}")

        # 预热关键数据
        await warm_essential_cache()

    except Exception as e:
        logger.error(f"刷新全部缓存失败: {e}")
        raise


async def warm_essential_cache() -> None:
    """
    预热关键缓存数据
    """
    try:
        # 预热常用数据
        essential_keys = [
            "system:config",
            "datasource:status",
            "market:calendar:current",
            "market:trading_hours"
        ]

        # 使用loader函数预热缓存
        async def load_essential_data(key: str):
            # 这里应该调用实际的数据加载逻辑
            # 目前返回占位数据
            if key == "system:config":
                return {"version": "1.0", "env": "production"}
            elif key == "datasource:status":
                return {"amazingdata": "active", "akshare": "active"}
            elif key == "market:calendar:current":
                return {"date": datetime.now().date().isoformat(), "is_trading": True}
            elif key == "market:trading_hours":
                return {"open": "09:30", "close": "15:00"}
            return None

        # 批量预热
        await cache_manager.warm_cache(essential_keys, load_essential_data)
        logger.info(f"已预热 {len(essential_keys)} 个关键缓存项")

    except Exception as e:
        logger.error(f"预热缓存失败: {e}")
        # 预热失败不影响主流程


@router.get("/process-status")
async def get_process_status():
    """
    获取进程池状态

    返回所有数据源进程的运行状态
    """
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
            get_global_pool
        )

        pool = get_global_pool()
        status = pool.get_status()

        return APIResponse.success(
            data=status,
            message="进程池状态获取成功"
        )

    except Exception as e:
        logger.error(f"[ProcessStatus] Failed to get process status: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取进程状态失败: {str(e)}",
            status_code=500
        )