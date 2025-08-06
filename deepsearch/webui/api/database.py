"""
数据库管理 API 路由

提供数据库连接管理、状态查询等功能
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from deepsearch.core.component_manager import ComponentStatus

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
        db_component = get_database_component()

        # 获取状态信息
        status_info = db_component.get_status_info()

        # 确保status_info不为None
        if status_info is None:
            status_info = {}

        # 添加额外的配置信息
        from deepsearch.config import get_config
        config = get_config()
        db_config = config.database.main

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
async def get_database_tables() -> Dict[str, Any]:
    """
    获取数据库表列表
    
    Returns:
        数据库中的表信息
    """
    try:
        db_component = get_database_component()

        # 检查连接状态
        if not db_component.is_connected():
            raise HTTPException(status_code=400, detail="数据库未连接")

        # 获取表列表
        from sqlalchemy import inspect, text

        async with db_component.engine.begin() as conn:
            # 获取所有表名
            inspector = inspect(conn.sync_connection)
            tables = inspector.get_table_names()

            # 获取每个表的基本信息
            table_info = []
            for table_name in tables:
                try:
                    # 获取列信息
                    columns = inspector.get_columns(table_name)

                    # 获取行数（仅适用于小表）
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    row_count = result.scalar()

                    table_info.append({
                        "name": table_name,
                        "columns": len(columns),
                        "rows": row_count,
                        "type": "table"
                    })
                except Exception as e:
                    logger.warning(f"获取表 {table_name} 信息失败: {e}")
                    table_info.append({
                        "name": table_name,
                        "columns": 0,
                        "rows": 0,
                        "type": "table",
                        "error": str(e)
                    })

            # 如果启用了 TimescaleDB，获取超表信息
            if db_component.is_timescale_enabled:
                try:
                    result = await conn.execute(text(
                        "SELECT hypertable_name FROM timescaledb_information.hypertables"
                    ))
                    hypertables = [row[0] for row in result]

                    # 标记超表
                    for table in table_info:
                        if table["name"] in hypertables:
                            table["type"] = "hypertable"

                except Exception as e:
                    logger.debug(f"获取超表信息失败: {e}")

        return {
            "success": True,
            "tables": table_info,
            "total": len(table_info)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库表列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")
