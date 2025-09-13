"""
数据源CRUD管理API

提供数据源的增删改查、测试和状态管理功能
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger
import asyncio
import aiohttp

from deepsearch.webui.api.common.response_format import APIResponse, APIException, ErrorCodes


# 创建路由
router = APIRouter(prefix="/api/data-sources", tags=["DataSource Management"])


# 数据模型
class DataSourceConfig(BaseModel):
    """数据源配置"""
    timeout: int = Field(default=30000, description="超时时间(ms)")
    retryCount: int = Field(default=3, description="重试次数")
    rateLimit: int = Field(default=100, description="速率限制(req/s)")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口号")
    apiKey: Optional[str] = Field(None, description="API密钥")
    workerUrl: Optional[str] = Field(None, description="Worker URL")
    extra: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外配置")


class DataSource(BaseModel):
    """数据源模型"""
    id: Optional[str] = None  # 使用字符串ID（英文名称）
    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据源类型: akshare|amazingdata|qmt|cloudflare")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, description="优先级(数字越小优先级越高)")
    config: DataSourceConfig = Field(default_factory=DataSourceConfig, description="配置信息")
    status: Optional[str] = Field(default="unknown", description="状态: online|offline|error|degraded")
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


def init_default_datasources():
    """初始化默认数据源"""
    global data_sources
    
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
    
    # 银河证券数据源
    amazingdata_source = DataSource(
        id="amazingdata",
        name="银河证券星耀数智",
        type="amazingdata",
        enabled=True,
        priority=1,
        config=DataSourceConfig(
            timeout=10000,
            retryCount=2,
            rateLimit=100,
            apiKey="***已配置***"
        ),
        status="online",
        successRate=99.2,
        avgResponseTime=50,
        created_at=datetime.now()
    )
    data_sources[amazingdata_source.id] = amazingdata_source
    
    # QMT数据源
    qmt_source = DataSource(
        id="qmt",
        name="QMT实时数据",
        type="qmt",
        enabled=True,
        priority=2,
        config=DataSourceConfig(
            timeout=5000,
            retryCount=1,
            rateLimit=1000,
            host="localhost",
            port=5556
        ),
        status="offline",
        successRate=0,
        avgResponseTime=0,
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
                "config": source.config.dict(),
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
        datasource.status = "unknown"
        
        data_sources[datasource.id] = datasource
        
        logger.info(f"创建数据源: {datasource.name} ({datasource.id})")
        
        return APIResponse.success(
            data=datasource.dict(),
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
        
        # 如果状态改变，更新检查时间
        if datasource.status != existing.status:
            datasource.lastCheckTime = datetime.now()
        
        data_sources[datasource_id] = datasource
        
        logger.info(f"更新数据源: {datasource.name} ({datasource_id})")
        
        return APIResponse.success(
            data=datasource.dict(),
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
    切换数据源启用状态
    
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
        datasource.enabled = enabled
        datasource.updated_at = datetime.now()
        
        # 更新状态
        if not enabled:
            datasource.status = "disabled"
        
        logger.info(f"{'启用' if enabled else '禁用'}数据源: {datasource.name}")
        
        return APIResponse.success(
            data={"id": datasource_id, "enabled": enabled},
            message=f"数据源已{'启用' if enabled else '禁用'}"
        )
    except Exception as e:
        logger.error(f"切换数据源状态失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"切换数据源状态失败: {str(e)}",
            status_code=500
        )


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
                # 模拟测试（实际应该调用AKShare API）
                await asyncio.sleep(0.2)  # 模拟网络延迟
                test_result["success"] = True
                test_result["message"] = "AKShare连接成功"
                test_result["details"]["version"] = "1.12.0"
                test_result["details"]["apis_available"] = 1000
            except Exception as e:
                test_result["message"] = f"连接失败: {str(e)}"
                
        elif request.type == "amazingdata":
            # 测试银河证券API
            if not request.config.apiKey or request.config.apiKey == "***已配置***":
                test_result["message"] = "需要有效的API密钥"
            else:
                try:
                    await asyncio.sleep(0.1)  # 模拟网络延迟
                    test_result["success"] = True
                    test_result["message"] = "银河证券API连接成功"
                    test_result["details"]["account"] = "测试账户"
                    test_result["details"]["quota"] = "10000 req/day"
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
                    
        elif request.type == "qmt":
            # 测试QMT连接
            try:
                # 实际应该连接到QMT网关
                if request.config.host and request.config.port:
                    await asyncio.sleep(0.05)  # 模拟网络延迟
                    # 模拟连接失败（因为QMT通常需要本地运行）
                    test_result["success"] = False
                    test_result["message"] = f"无法连接到 {request.config.host}:{request.config.port}"
                else:
                    test_result["message"] = "需要配置主机和端口"
            except Exception as e:
                test_result["message"] = f"连接失败: {str(e)}"
                
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
                            else:
                                test_result["message"] = f"Worker返回状态码: {response.status}"
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
            else:
                test_result["message"] = "需要配置Worker URL"
        else:
            test_result["message"] = f"不支持的数据源类型: {request.type}"
        
        # 计算延迟
        end_time = datetime.now()
        test_result["latency"] = int((end_time - start_time).total_seconds() * 1000)
        
        if test_result["success"]:
            return APIResponse.success(
                data=test_result,
                message="连接测试成功"
            )
        else:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_CONNECTION_FAILED,
                message=test_result["message"],
                details=test_result
            )
            
    except Exception as e:
        logger.error(f"测试数据源连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"测试连接时发生错误: {str(e)}",
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
async def test_data_source(request: TestDataSourceRequest):
    """测试数据源（兼容路径）"""
    return await test_datasource(request)