"""
数据库管理 API 路由

提供数据库连接管理、状态查询等功能
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from deepsearch.core.managers.component_manager import ComponentStatus

router = APIRouter()


def get_database_component():
    """获取数据库组件实例"""
    try:
        from deepsearch.webui.server import app_state
        engine = getattr(app_state, 'engine', None)
        if not engine:
            raise HTTPException(status_code=503, detail="系统未初始化")

        # 获取数据库组件
        db_component = engine.get_component_by_name('database')

        if not db_component:
            raise HTTPException(status_code=404, detail="数据库组件未找到")

        return db_component
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库组件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库组件失败: {str(e)}")


@router.get("/status")
async def get_database_status() -> Dict[str, Any]:
    """
    获取数据库详细状态

    Returns:
        包含连接状态、配置信息、健康检查等详细信息
    """
    try:
        # 尝试获取数据库组件
        try:
            db_component = get_database_component()
            has_component = True
        except HTTPException as he:
            # 如果系统未初始化或组件未找到，返回默认状态
            if he.status_code in [503, 404]:
                logger.warning(f"数据库组件不可用: {he.detail}")
                has_component = False
                db_component = None
            else:
                raise

        # 获取配置信息
        from deepsearch.config import get_config
        config = get_config()
        db_config = config.database.main

        # 如果没有组件，返回未初始化状态
        if not has_component or not db_component:
            return {
                "connected": False,
                "status": "not_initialized",
                "connection_status": "disconnected",
                "config": {
                    "type": db_config.type,
                    "host": db_config.host,
                    "port": db_config.port,
                    "database": db_config.database,
                    "username": db_config.username,
                    "auto_connect": db_config.auto_connect,
                    "enabled": db_config.enabled
                },
                "timescaledb_enabled": False,
                "last_health_check": None,
                "connection_pool": {},
                "disconnect_reason": "系统未初始化",
                "health": {
                    "status": "unavailable",
                    "message": "Database component not initialized"
                }
            }

        # 获取状态信息
        status_info = db_component.get_status_info()

        # 确保status_info不为None
        if status_info is None:
            status_info = {}

        result = {
            "connected": db_component.is_connected(),
            "status": status_info.get("status", "unknown"),
            "connection_status": status_info.get("connection_status", "disconnected"),
            "config": {
                "type": db_config.type,
                "host": db_config.host,
                "port": db_config.port,
                "database": db_config.database,
                "username": db_config.username,
                "auto_connect": db_config.auto_connect,
                "enabled": db_config.enabled
            },
            "timescaledb_enabled": status_info.get("timescaledb_enabled", False),
            "last_health_check": status_info.get("last_health_check"),
            "connection_pool": status_info.get("connection_pool", {}),
            "disconnect_reason": status_info.get("disconnect_reason")
        }

        # 健康状态检查（暂时简化，待健康管理器实现后再完善）
        try:
            if db_component.is_connected():
                result["health"] = {"status": "healthy", "message": "Database is connected"}
            else:
                result["health"] = {"status": "unhealthy", "message": "Database is not connected"}
        except Exception as e:
            logger.warning(f"获取健康状态失败: {e}")
            result["health"] = {"status": "error", "error": str(e)}

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


from pydantic import BaseModel
from typing import Optional


class ConnectRequest(BaseModel):
    password: Optional[str] = None


@router.post("/connect")
async def connect_database(request: ConnectRequest) -> Dict[str, Any]:
    """
    手动连接数据库
    
    Args:
        request: 包含可选密码的请求体
    
    Returns:
        连接结果
    """
    logger.info("收到数据库连接请求")
    try:
        password = request.password

        db_component = get_database_component()

        # 检查是否已连接
        if db_component.is_connected():
            return {
                "success": True,
                "message": "数据库已经连接",
                "already_connected": True
            }

        # 检查配置
        from deepsearch.config import get_config
        config = get_config()
        db_config = config.database.main

        if not db_config.enabled:
            raise HTTPException(status_code=400, detail="数据库功能未启用")

        # 如果提供了密码，临时使用该密码
        if password:
            # 临时设置密码用于连接
            original_password = db_config.password
            db_config.password = password
            try:
                # 执行连接
                await db_component.connect_async()

                # 如果组件未启动，启动它
                if db_component.status != ComponentStatus.RUNNING:
                    await db_component.start_async()

                # 连接成功后恢复原密码配置
                db_config.password = original_password

                return {
                    "success": True,
                    "message": "数据库连接成功",
                    "status": "connected"
                }
            except Exception as e:
                # 恢复原密码配置
                db_config.password = original_password
                raise

        # 没有提供密码，检查配置中的密码
        if db_config.type != "sqlite" and not db_config.password:
            raise HTTPException(status_code=400, detail="请先设置数据库密码")

        # 执行连接
        try:
            await db_component.connect_async()

            # 如果组件未启动，启动它
            if db_component.status and db_component.status != ComponentStatus.RUNNING:
                await db_component.start_async()

            return {
                "success": True,
                "message": "数据库连接成功",
                "status": "connected"
            }

        except RuntimeError as e:
            error_msg = str(e)
            if "数据库密码未设置" in error_msg:
                raise HTTPException(status_code=400, detail="请先在配置页面设置数据库密码")
            elif "数据库连接失败" in error_msg:
                # 提取友好的错误信息
                raise HTTPException(status_code=500, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail=f"连接失败: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"连接数据库失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/disconnect")
async def disconnect_database() -> Dict[str, Any]:
    """
    手动断开数据库连接
    
    Returns:
        断开结果
    """
    try:
        db_component = get_database_component()

        # 检查是否已断开
        if not db_component.is_connected():
            return {
                "success": True,
                "message": "数据库未连接",
                "already_disconnected": True
            }

        # 停止组件（会自动断开连接）
        if db_component.status == ComponentStatus.RUNNING:
            await db_component.stop_async()

        # 确保断开连接
        await db_component.disconnect_async()

        return {
            "success": True,
            "message": "数据库连接已断开",
            "status": "disconnected"
        }

    except Exception as e:
        logger.error(f"断开数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"断开失败: {str(e)}")


@router.post("/reconnect")
async def reconnect_database() -> Dict[str, Any]:
    """
    重新连接数据库（先断开再连接）
    
    Returns:
        重连结果
    """
    try:
        # 先断开
        disconnect_result = await disconnect_database()
        if not disconnect_result.get("success"):
            return disconnect_result

        # 等待一下确保完全断开
        import asyncio
        await asyncio.sleep(0.5)

        # 再连接
        connect_result = await connect_database()
        return connect_result

    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"重连数据库失败: {e}")
        raise HTTPException(status_code=500, detail=f"重连失败: {str(e)}")


@router.get("/tables")
async def get_database_tables(
    limit: int = 200,
    include_counts: bool = False,
    fetch_columns: bool = False
) -> Dict[str, Any]:
    """
    获取数据库表列表（快速响应版）

    Query Params:
        - limit: 返回的表数量上限（默认 200）
        - include_counts: 是否统计每张表的行数（默认 false，开启可能较慢，且最多统计 50 张）
        - fetch_columns: 是否统计列数（默认 false）

    Returns:
        包含表清单、是否截断、连接状态等信息的字典
    """
    try:
        db_component = get_database_component()

        # 未连接时返回可消费的成功响应，避免前端一直 loading
        if not db_component.is_connected():
            return {
                "success": True,
                "connected": False,
                "message": "数据库未连接",
                "tables": [],
                "total": 0
            }

        # 获取表列表（尽量轻量）
        from sqlalchemy import inspect, text

        async with db_component.engine.begin() as conn:
            inspector = inspect(conn.sync_connection)
            tables = inspector.get_table_names()

            # 控制返回数量，避免一次性处理过多表
            has_more = False
            if limit and len(tables) > limit:
                has_more = True
                tables = tables[:limit]

            # 初始仅返回表名，默认不统计列与行，保证快速响应
            table_info = [{"name": t, "columns": None, "rows": None, "type": "table"} for t in tables]

            # 可选：统计列数（可能较慢）
            if fetch_columns:
                for t in table_info:
                    try:
                        cols = inspector.get_columns(t["name"])
                        t["columns"] = len(cols)
                    except Exception as e:
                        t["columns"] = None
                        t["error_columns"] = str(e)

            # 可选：统计行数（较慢，且限制最多 50 张表以避免阻塞）
            if include_counts:
                max_count_tables = min(len(table_info), 50)
                for i in range(max_count_tables):
                    t = table_info[i]
                    try:
                        # 使用引号包裹表名以降低 SQL 注入/保留字风险（表名来自系统元数据，仍做基本保护）
                        result = await conn.execute(text(f'SELECT COUNT(*) FROM "{t["name"]}"'))
                        t["rows"] = result.scalar()
                    except Exception as e:
                        t["rows"] = None
                        t["error_rows"] = str(e)

            # 如果启用了 TimescaleDB，尝试标记超表（失败不影响主流程）
            if getattr(db_component, "is_timescale_enabled", False):
                try:
                    result = await conn.execute(text(
                        "SELECT hypertable_name FROM timescaledb_information.hypertables"
                    ))
                    hypertables = [row[0] for row in result]
                    for t in table_info:
                        if t["name"] in hypertables:
                            t["type"] = "hypertable"
                except Exception as e:
                    logger.debug(f"获取超表信息失败: {e}")

        return {
            "success": True,
            "tables": table_info,
            "total": len(table_info),
            "has_more": has_more
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库表列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")
