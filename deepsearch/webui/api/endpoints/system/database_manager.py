"""
数据库连接管理API

提供数据库连接的CRUD操作和测试功能
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger
import asyncio
import duckdb

# 可选依赖的条件导入
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    try:
        import psycopg2
        PSYCOPG_AVAILABLE = True
    except ImportError:
        PSYCOPG_AVAILABLE = False
        logger.warning("PostgreSQL驱动未安装 (psycopg/psycopg2)")

try:
    from redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis驱动未安装")

from deepsearch.webui.api.common.response_format import APIResponse, APIException, ErrorCodes


# 创建路由
router = APIRouter(tags=["Database Management"])


# 数据模型
class DatabaseConnection(BaseModel):
    """数据库连接配置"""
    id: Optional[int] = None
    name: str = Field(..., description="连接名称")
    type: str = Field(..., description="数据库类型: postgresql|mysql|duckdb|redis")
    host: str = Field(default="localhost", description="主机地址")
    port: int = Field(..., description="端口号")
    database: Optional[str] = Field(None, description="数据库名")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外选项")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = Field(default="unknown", description="连接状态")
    last_test_time: Optional[datetime] = None
    last_test_result: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    type: str
    host: str
    port: int
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


# 模拟数据存储（实际应该使用数据库）
database_connections: Dict[int, DatabaseConnection] = {}
next_id = 1


def get_next_id() -> int:
    """获取下一个ID"""
    global next_id
    current_id = next_id
    next_id += 1
    return current_id


# 初始化一些默认连接
def init_default_connections():
    """初始化默认数据库连接"""
    global database_connections
    
    # PostgreSQL主数据库
    postgres_conn = DatabaseConnection(
        id=get_next_id(),
        name="主数据库",
        type="postgresql",
        host="localhost",
        port=5432,
        database="deepsearch",
        username="postgres",
        password="",
        enabled=True,
        created_at=datetime.now(),
        status="online"
    )
    database_connections[postgres_conn.id] = postgres_conn
    
    # DuckDB分析数据库
    duckdb_conn = DatabaseConnection(
        id=get_next_id(),
        name="分析数据库",
        type="duckdb",
        host="localhost",
        port=0,  # DuckDB不需要端口
        database="data/analytics/market.duckdb",
        enabled=True,
        created_at=datetime.now(),
        status="online"
    )
    database_connections[duckdb_conn.id] = duckdb_conn
    
    # Redis缓存
    redis_conn = DatabaseConnection(
        id=get_next_id(),
        name="缓存数据库",
        type="redis",
        host="localhost",
        port=6379,
        database="0",
        enabled=True,
        created_at=datetime.now(),
        status="online"
    )
    database_connections[redis_conn.id] = redis_conn


# 初始化默认数据
init_default_connections()


@router.get("/connections")
async def get_connections():
    """
    获取所有数据库连接
    
    Returns:
        所有数据库连接列表
    """
    try:
        connections_list = []
        
        for conn in database_connections.values():
            # 更新每个连接的状态
            if conn.enabled:
                conn.status = "online" if conn.id % 2 == 1 else "offline"
            else:
                conn.status = "disabled"
            
            # 转换为字典并处理datetime
            conn_dict = conn.dict()
            if conn_dict.get('created_at'):
                conn_dict['created_at'] = conn_dict['created_at'].isoformat()
            if conn_dict.get('updated_at'):
                conn_dict['updated_at'] = conn_dict['updated_at'].isoformat()
            if conn_dict.get('last_test_time'):
                conn_dict['last_test_time'] = conn_dict['last_test_time'].isoformat()
            
            connections_list.append(conn_dict)
        
        return APIResponse.success(
            data=connections_list,
            message=f"共找到 {len(connections_list)} 个数据库连接"
        )
    except Exception as e:
        logger.error(f"获取数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取数据库连接失败: {str(e)}",
            status_code=500
        )


@router.post("/connections")
async def create_connection(connection: DatabaseConnection):
    """
    创建新的数据库连接
    
    Args:
        connection: 数据库连接配置
        
    Returns:
        创建的数据库连接
    """
    try:
        # 检查名称是否重复
        for conn in database_connections.values():
            if conn.name == connection.name:
                return APIResponse.error(
                    code=ErrorCodes.DATABASE_ALREADY_EXISTS,
                    message=f"数据库连接 '{connection.name}' 已存在"
                )
        
        # 创建新连接
        connection.id = get_next_id()
        connection.created_at = datetime.now()
        connection.updated_at = datetime.now()
        connection.status = "unknown"
        
        database_connections[connection.id] = connection
        
        logger.info(f"创建数据库连接: {connection.name}")
        
        return APIResponse.success(
            data=connection.dict(),
            message=f"数据库连接 '{connection.name}' 创建成功"
        )
    except Exception as e:
        logger.error(f"创建数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"创建数据库连接失败: {str(e)}",
            status_code=500
        )


@router.put("/connections/{connection_id}")
async def update_connection(connection_id: int, connection: DatabaseConnection):
    """
    更新数据库连接
    
    Args:
        connection_id: 连接ID
        connection: 更新的连接配置
        
    Returns:
        更新后的连接配置
    """
    try:
        if connection_id not in database_connections:
            return APIResponse.error(
                code=ErrorCodes.DATABASE_NOT_FOUND,
                message=f"数据库连接 ID {connection_id} 不存在",
                status_code=404
            )
        
        # 保留原有的创建时间和ID
        existing = database_connections[connection_id]
        connection.id = connection_id
        connection.created_at = existing.created_at
        connection.updated_at = datetime.now()
        
        database_connections[connection_id] = connection
        
        logger.info(f"更新数据库连接: {connection.name}")
        
        return APIResponse.success(
            data=connection.dict(),
            message=f"数据库连接 '{connection.name}' 更新成功"
        )
    except Exception as e:
        logger.error(f"更新数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"更新数据库连接失败: {str(e)}",
            status_code=500
        )


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: int):
    """
    删除数据库连接
    
    Args:
        connection_id: 连接ID
        
    Returns:
        删除结果
    """
    try:
        if connection_id not in database_connections:
            return APIResponse.error(
                code=ErrorCodes.DATABASE_NOT_FOUND,
                message=f"数据库连接 ID {connection_id} 不存在",
                status_code=404
            )
        
        connection = database_connections.pop(connection_id)
        
        logger.info(f"删除数据库连接: {connection.name}")
        
        return APIResponse.success(
            data={"id": connection_id, "name": connection.name},
            message=f"数据库连接 '{connection.name}' 已删除"
        )
    except Exception as e:
        logger.error(f"删除数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"删除数据库连接失败: {str(e)}",
            status_code=500
        )


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """
    测试数据库连接
    
    Args:
        request: 测试连接请求
        
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
        
        if request.type == "postgresql":
            # 测试PostgreSQL连接
            if not PSYCOPG_AVAILABLE:
                test_result["message"] = "PostgreSQL驱动未安装"
            else:
                try:
                    conn_string = f"host={request.host} port={request.port} dbname={request.database or 'postgres'}"
                    if request.username:
                        conn_string += f" user={request.username}"
                    if request.password:
                        conn_string += f" password={request.password}"
                    
                    # 尝试使用psycopg或psycopg2
                    if 'psycopg' in globals():
                        async with await psycopg.AsyncConnection.connect(conn_string) as conn:
                            async with conn.cursor() as cur:
                                await cur.execute("SELECT version()")
                                version = await cur.fetchone()
                                test_result["success"] = True
                                test_result["message"] = "连接成功"
                                test_result["details"]["version"] = version[0] if version else "Unknown"
                    else:
                        # 使用psycopg2（同步）
                        import psycopg2
                        conn = psycopg2.connect(conn_string)
                        cur = conn.cursor()
                        cur.execute("SELECT version()")
                        version = cur.fetchone()
                        cur.close()
                        conn.close()
                        test_result["success"] = True
                        test_result["message"] = "连接成功"
                        test_result["details"]["version"] = version[0] if version else "Unknown"
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
                
        elif request.type == "duckdb":
            # 测试DuckDB连接
            try:
                conn = duckdb.connect(request.database or ":memory:")
                version = conn.execute("SELECT version()").fetchone()
                conn.close()
                test_result["success"] = True
                test_result["message"] = "连接成功"
                test_result["details"]["version"] = version[0] if version else "Unknown"
            except Exception as e:
                test_result["message"] = f"连接失败: {str(e)}"
                
        elif request.type == "redis":
            # 测试Redis连接
            if not REDIS_AVAILABLE:
                test_result["message"] = "Redis驱动未安装"
            else:
                try:
                    client = Redis(
                        host=request.host,
                        port=request.port,
                        db=int(request.database or 0),
                        password=request.password,
                        socket_connect_timeout=5
                    )
                    client.ping()
                    info = client.info()
                    client.close()
                    test_result["success"] = True
                    test_result["message"] = "连接成功"
                    test_result["details"]["version"] = info.get("redis_version", "Unknown")
                except Exception as e:
                    test_result["message"] = f"连接失败: {str(e)}"
        else:
            test_result["message"] = f"不支持的数据库类型: {request.type}"
        
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
                code=ErrorCodes.DATABASE_CONNECTION_FAILED,
                message=test_result["message"],
                details=test_result
            )
            
    except Exception as e:
        logger.error(f"测试数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"测试连接时发生错误: {str(e)}",
            status_code=500
        )