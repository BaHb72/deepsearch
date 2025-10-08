"""
配置管理 API 路由。
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Final, cast

import yaml
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from deepsearch.config import get_config, reload_config
from deepsearch.constants import YAML_ENCODING

# Windows 兼容性：设置事件循环策略
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()

MASKED_SECRET: Final[str] = "***"  # nosec B105 - UI 脱敏显示占位符


def parse_database_error(error_str: str, db_type: str = "postgresql") -> str:
    """
    解析数据库连接错误，返回友好的错误信息。

    Args:
        error_str: 原始错误信息
        db_type: 数据库类型

    Returns:
        友好的错误提示
    """
    error_lower = error_str.lower()

    # PostgreSQL 错误处理
    if db_type == "postgresql":
        if "no password supplied" in error_lower:
            return "请输入数据库密码"
        elif "password authentication failed" in error_lower:
            return "密码错误，请检查密码是否正确"
        elif "authentication failed" in error_lower:
            return "认证失败，请检查用户名和密码是否正确"
        elif "could not connect to server" in error_lower or "connection refused" in error_lower:
            return "无法连接到数据库服务器，请确认：\n1. 数据库服务是否已启动\n2. 主机地址和端口是否正确\n3. 防火墙是否允许连接"
        elif "database" in error_lower and "does not exist" in error_lower:
            return "指定的数据库不存在，请先创建数据库"
        elif "role" in error_lower and "does not exist" in error_lower:
            return "数据库用户不存在，请检查用户名"
        elif "timeout" in error_lower:
            return "连接超时，请检查：\n1. 网络连接是否正常\n2. 数据库服务器是否可访问"
        elif "connection failed" in error_lower:
            # 对于多个连接尝试失败的情况，简化错误信息
            return "连接失败，请检查数据库服务是否正常运行"
        elif "could not translate host name" in error_lower:
            return "无法解析主机名，请检查主机地址是否正确"
        elif "ssl" in error_lower:
            return "SSL连接错误，请检查SSL配置"

    # MySQL 错误处理
    elif db_type == "mysql":
        if "access denied" in error_lower:
            return "访问被拒绝，请检查：\n1. 用户名和密码是否正确\n2. 用户是否有连接权限"
        elif "can't connect" in error_lower:
            return "无法连接到MySQL服务器，请确认服务是否已启动"
        elif "unknown database" in error_lower:
            return "指定的数据库不存在"
        elif "host" in error_lower and "is not allowed" in error_lower:
            return "当前主机不允许连接，请检查MySQL用户权限配置"
        elif "too many connections" in error_lower:
            return "连接数过多，请稍后重试"

    # SQLite 错误处理
    elif db_type == "sqlite":
        if "unable to open database file" in error_lower:
            return "无法打开数据库文件，请检查：\n1. 文件路径是否正确\n2. 目录是否存在\n3. 是否有读写权限"
        elif "no such table" in error_lower:
            return "数据库表不存在"
        elif "database is locked" in error_lower:
            return "数据库被锁定，请稍后重试"

    # 通用错误处理
    if "permission denied" in error_lower:
        return "权限不足，请检查文件或目录权限"
    elif "disk full" in error_lower:
        return "磁盘空间不足"
    elif "network" in error_lower:
        return "网络错误，请检查网络连接"

    # 如果没有匹配的错误类型，返回简化的错误信息
    # 去除多余的连接尝试信息
    if "Multiple connection attempts failed" in error_str:
        # 提取第一个有意义的错误信息
        lines = error_str.split("\n")
        for line in lines:
            if "failed:" in line:
                # 提取错误核心信息
                parts = line.split("failed:", 1)
                if len(parts) > 1:
                    core_error = parts[1].strip()
                    # 递归解析核心错误
                    return parse_database_error(core_error, db_type)
        return "连接失败，请检查数据库配置"

    # 限制错误信息长度，避免显示过多技术细节
    if len(error_str) > 150:
        return "数据库连接失败，请检查配置信息是否正确"

    return "数据库连接失败：" + error_str


class ConfigUpdate(BaseModel):
    """配置更新请求模型。"""

    section: str
    key: str
    value: Any


@router.get("")
async def get_configuration() -> Dict[str, Any]:
    """
    获取当前系统配置。

    Returns:
        系统配置字典
    """
    try:
        # 检查settings是否为None
        config = get_config()
        if config is None:
            return {
                "error": "配置未加载",
                "message": "配置系统未能正确初始化",
                "config_missing": True,
                "env": "unknown",
            }

        # 检查配置文件是否存在
        # 从 deepsearch/webui/api/endpoints/system/config.py 向上5级到达 deepsearch/config
        config_dir = Path(__file__).parent.parent.parent.parent.parent / "config"
        env = config.app.env
        config_path = config_dir / f"settings.{env}.yaml"

        if not config_path.exists():
            return {
                "error": "配置文件不存在",
                "message": f"请创建配置文件: {config_path}",
                "config_missing": True,
                "config_path": str(config_path),
                "env": env,
            }

        # 将配置转换为字典格式
        config_dict: Dict[str, Any] = config.model_dump()

        # 移除敏感信息
        if "security" in config_dict and config_dict["security"] is not None:
            config_dict["security"] = {
                "api_key": MASKED_SECRET if config_dict["security"].get("api_key") else None,
                "secret_key": MASKED_SECRET if config_dict["security"].get("secret_key") else None,
            }

        # 对数据库密码进行脱敏处理
        if "database" in config_dict:
            if "main" in config_dict["database"] and "password" in config_dict["database"]["main"]:
                if config_dict["database"]["main"]["password"]:
                    # 添加标志表示是否有保存的密码
                    config_dict["database"]["main"]["has_saved_password"] = True
                    config_dict["database"]["main"]["password"] = MASKED_SECRET
                else:
                    config_dict["database"]["main"]["has_saved_password"] = False
            if (
                "cache" in config_dict["database"]
                and "password" in config_dict["database"]["cache"]
            ):
                if config_dict["database"]["cache"]["password"]:
                    # 添加标志表示是否有保存的密码
                    config_dict["database"]["cache"]["has_saved_password"] = True
                    config_dict["database"]["cache"]["password"] = MASKED_SECRET
                else:
                    config_dict["database"]["cache"]["has_saved_password"] = False

        return config_dict

    except Exception as e:
        logger.error(f"获取配置失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
async def get_config_schema() -> Dict[str, Any]:
    """
    获取配置模式定义。

    Returns:
        配置的 JSON Schema
    """
    try:
        config = get_config()
        if config is None:
            raise HTTPException(status_code=500, detail="配置系统未初始化")
        return cast(Dict[str, Any], config.model_json_schema())
    except Exception as e:
        logger.error(f"获取配置模式失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    保存配置到文件。

    Args:
        config_data: 完整的配置数据

    Returns:
        保存结果
    """
    try:
        # 检查settings是否存在
        config = get_config()
        if config is None:
            return {"success": False, "message": "配置系统未初始化，无法保存配置"}

        # 获取当前环境
        env = config.app.env

        # 构建配置文件路径
        # 从 deepsearch/webui/api/endpoints/system/config.py 向上5级到达 deepsearch/config
        config_dir = Path(__file__).parent.parent.parent.parent.parent / "config"
        config_path = config_dir / f"settings.{env}.yaml"

        # 读取现有配置文件（保留注释等）
        existing_content = ""
        existing_config: Dict[str, Any] = {}  # 新增：保存解析后的配置
        if config_path.exists():
            with config_path.open("r", encoding=YAML_ENCODING) as f:
                existing_content = f.read()
            # 新增：解析现有配置
            try:
                existing_config = yaml.safe_load(existing_content) or {}
            except Exception as e:
                logger.warning(f"Failed to parse existing config: {e}")
                existing_config = {}

        # 准备要保存的配置
        save_data = {}

        # 处理各个配置部分
        if "app" in config_data:
            save_data["app"] = config_data["app"]

        if "log" in config_data:
            save_data["log"] = config_data["log"]

        # 处理数据库配置
        if "database" in config_data:
            db_config = config_data["database"]
            # 如果是新格式（包含main和cache）
            if "main" in db_config or "cache" in db_config:
                save_data["database"] = {
                    "main": db_config.get("main", {}),
                    "cache": db_config.get("cache", {}),
                }
                # 处理主数据库密码保存逻辑
                if "main" in save_data["database"]:
                    # 获取现有密码
                    existing_password = (
                        existing_config.get("database", {}).get("main", {}).get("password", "")
                    )

                    if "password" in save_data["database"]["main"]:
                        remember_password = db_config.get("main", {}).get("rememberPassword", False)
                        password = save_data["database"]["main"]["password"]

                        if password == MASKED_SECRET:
                            # 脱敏密码，使用现有密码
                            save_data["database"]["main"]["password"] = existing_password
                        elif remember_password and password:
                            # 新密码且记住密码
                            save_data["database"]["main"]["password"] = password
                        else:
                            # 不记住密码或密码为空
                            save_data["database"]["main"]["password"] = ""  # nosec B105 B106 - 清空已保存密码
                    else:
                        # 如果没有密码字段，保持现有密码
                        save_data["database"]["main"]["password"] = existing_password

                # 删除临时的rememberPassword字段
                if (
                    "main" in save_data["database"]
                    and "rememberPassword" in save_data["database"]["main"]
                ):
                    del save_data["database"]["main"]["rememberPassword"]
                # 处理缓存数据库密码保存逻辑
                if "cache" in save_data["database"]:
                    # 获取现有密码
                    existing_cache_password = (
                        existing_config.get("database", {}).get("cache", {}).get("password", "")
                    )

                    if "password" in save_data["database"]["cache"]:
                        cache_password = save_data["database"]["cache"]["password"]
                        if cache_password == MASKED_SECRET:
                            # 脱敏密码，使用现有密码
                            save_data["database"]["cache"]["password"] = existing_cache_password
                        elif cache_password:
                            # 新密码，明文保存
                            save_data["database"]["cache"]["password"] = cache_password
                        else:
                            # 密码为空
                            save_data["database"]["cache"]["password"] = ""  # nosec B105 B106 - 清空已保存密码
                    else:
                        # 如果没有密码字段，保持现有密码
                        save_data["database"]["cache"]["password"] = existing_cache_password

            # 兼容旧格式
            elif "url" in db_config:
                save_data["database"] = {"url": db_config["url"]}

        if "message_bus" in config_data:
            save_data["message_bus"] = config_data["message_bus"]

        if "webui" in config_data:
            save_data["webui"] = config_data["webui"]

        if "monitoring" in config_data:
            save_data["monitoring"] = config_data["monitoring"]

        if "security" in config_data:
            # 不保存脱敏的安全信息
            security = config_data["security"]
            save_security = {}
            if security.get("api_key") and security["api_key"] != MASKED_SECRET:
                save_security["api_key"] = security["api_key"]
            if security.get("secret_key") and security["secret_key"] != MASKED_SECRET:
                save_security["secret_key"] = security["secret_key"]
            if save_security:
                save_data["security"] = save_security

        # 创建备份
        if config_path.exists():
            backup_path = config_path.with_suffix(".yaml.bak")
            with backup_path.open("w", encoding=YAML_ENCODING) as f:
                f.write(existing_content)

        # 保存配置
        with config_path.open("w", encoding=YAML_ENCODING) as f:
            yaml.dump(save_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"配置已保存到: {config_path}")

        try:
            reload_config()
        except Exception as reload_error:
            logger.error(f"保存后重新加载配置失败: {reload_error}")
            return {
                "success": False,
                "message": f"配置已写入文件，但重新加载失败: {reload_error}",
                "path": str(config_path),
            }

        # 返回最新配置，便于前端立即刷新展示
        updated_config = await get_configuration()

        return {
            "success": True,
            "message": "配置保存成功",
            "path": str(config_path),
            "config": updated_config,
        }

    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return {"success": False, "message": f"保存配置失败: {str(e)}"}


@router.put("")
async def update_config(update: ConfigUpdate) -> Dict[str, Any]:
    """
    更新配置项。

    注意：此功能在生产环境中应该谨慎使用。

    Args:
        update: 配置更新信息

    Returns:
        更新后的配置
    """
    # 保留此接口以保持向后兼容
    return {"status": "deprecated", "message": "请使用 POST /api/config/save 接口保存完整配置"}


@router.get("/validate")
async def validate_config() -> Dict[str, Any]:
    """
    验证当前配置的有效性。

    Returns:
        验证结果
    """
    issues = []

    try:
        # 检查settings是否存在
        config = get_config()
        if config is None:
            return {"valid": False, "error": "配置系统未初始化", "issues": []}

        # 检查必要的目录是否存在
        if not config.log.active:
            issues.append({"level": "warning", "section": "log", "message": "日志功能已禁用"})

        # 检查消息总线配置
        if not config.message_bus.enabled_buses:
            issues.append(
                {"level": "error", "section": "message_bus", "message": "没有启用的消息总线"}
            )

        # 检查监控配置
        if config.monitoring and not config.monitoring.enable_metrics:
            issues.append({"level": "info", "section": "monitoring", "message": "监控指标未启用"})

        return {"valid": len([i for i in issues if i["level"] == "error"]) == 0, "issues": issues}

    except Exception as e:
        logger.error(f"验证配置失败：{e}")
        return {"valid": False, "error": str(e), "issues": []}


class DatabaseConnectionTest(BaseModel):
    """数据库连接测试请求模型。"""

    db_type: str  # postgresql, mysql, sqlite
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    path: str = ""  # for sqlite


class CacheConnectionTest(BaseModel):
    """缓存连接测试请求模型。"""

    host: str = "localhost"
    port: int = 6379
    username: str = ""
    password: str = ""
    db: int = 0


@router.post("/test-database")
async def test_database_connection(config: DatabaseConnectionTest) -> Dict[str, Any]:
    """
    测试数据库连接。

    Args:
        config: 数据库连接配置

    Returns:
        连接测试结果
    """
    try:
        # 如果密码是 ***，从配置中读取实际密码
        actual_password = config.password
        config_obj = get_config()
        if config.password == MASKED_SECRET and config_obj:
            # 从配置中获取保存的密码
            if config.db_type == "postgresql":
                saved_password = config_obj.database.main.password
                if saved_password:
                    actual_password = saved_password

        if config.db_type == "postgresql":
            # 测试 PostgreSQL 连接
            try:
                import psycopg

                # 使用 psycopg3 异步连接
                async with await psycopg.AsyncConnection.connect(
                    host=config.host,
                    port=config.port,
                    dbname=config.database,
                    user=config.username,
                    password=actual_password,
                    connect_timeout=5,
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT version()")
                        result = await cur.fetchone()
                        version = result[0] if result else "Unknown"

                return {"success": True, "message": "PostgreSQL 连接成功", "version": version}
            except ImportError:
                return {
                    "success": False,
                    "message": "PostgreSQL 驱动未安装，请运行: pip install psycopg[binary]",
                }
            except Exception as e:
                error_msg = parse_database_error(str(e), "postgresql")
                return {"success": False, "message": f"PostgreSQL 连接失败: {error_msg}"}

        elif config.db_type == "mysql":
            # 测试 MySQL 连接
            try:
                import aiomysql

                conn = await aiomysql.connect(
                    host=config.host,
                    port=config.port,
                    db=config.database,
                    user=config.username,
                    password=actual_password,
                    connect_timeout=5,
                )
                cursor = await conn.cursor()
                await cursor.execute("SELECT VERSION()")
                version = await cursor.fetchone()
                await cursor.close()
                conn.close()

                return {
                    "success": True,
                    "message": "MySQL 连接成功",
                    "version": version[0] if version else None,
                }
            except ImportError:
                return {
                    "success": False,
                    "message": "MySQL 驱动未安装，请运行: pip install aiomysql",
                }
            except Exception as e:
                error_msg = parse_database_error(str(e), "mysql")
                return {"success": False, "message": f"MySQL 连接失败: {error_msg}"}

        elif config.db_type == "sqlite":
            # 测试 SQLite 连接
            try:
                import aiosqlite

                conn = await aiosqlite.connect(config.path)
                cursor = await conn.execute("SELECT sqlite_version()")
                version = await cursor.fetchone()
                await conn.close()

                return {
                    "success": True,
                    "message": "SQLite 连接成功",
                    "version": version[0] if version else None,
                }
            except ImportError:
                return {
                    "success": False,
                    "message": "SQLite 驱动未安装，请运行: pip install aiosqlite",
                }
            except Exception as e:
                error_msg = parse_database_error(str(e), "sqlite")
                return {"success": False, "message": f"SQLite 连接失败: {error_msg}"}
        else:
            return {"success": False, "message": f"不支持的数据库类型: {config.db_type}"}

    except Exception as e:
        logger.error(f"数据库连接测试失败：{e}")
        return {"success": False, "message": f"连接测试失败: {str(e)}"}


@router.post("/test-cache")
async def test_cache_connection(config: CacheConnectionTest) -> Dict[str, Any]:
    """
    测试 Redis 缓存连接。

    Args:
        config: Redis 连接配置

    Returns:
        连接测试结果
    """
    try:
        # 如果密码是 ***，从配置中读取实际密码
        actual_password = config.password
        actual_username = config.username
        config_obj = get_config()
        if config.username == MASKED_SECRET and config_obj:
            saved_username = getattr(config_obj.database.cache, "username", "")
            if saved_username:
                actual_username = saved_username
        if config.password == MASKED_SECRET and config_obj:
            saved_password = config_obj.database.cache.password
            if saved_password:
                actual_password = saved_password
        # 尝试使用 redis-py 的异步客户端
        try:
            import redis.asyncio as redis_async

            # 创建 Redis 连接
            client = redis_async.Redis(
                host=config.host,
                port=config.port,
                username=actual_username or None,
                password=actual_password if actual_password else None,
                db=config.db,
                socket_connect_timeout=5,
            )

            # 测试连接
            await client.ping()

            # 获取 Redis 信息
            info = await client.info()
            redis_version = info.get("redis_version", "Unknown")

            # 关闭连接
            await client.aclose()

            return {"success": True, "message": "Redis 连接成功", "version": redis_version}
        except ImportError:
            # 如果 redis.asyncio 不可用，尝试同步方式测试
            import redis

            try:
                client = redis.Redis(
                    host=config.host,
                    port=config.port,
                    username=actual_username or None,
                    password=actual_password if actual_password else None,
                    db=config.db,
                    socket_connect_timeout=5,
                )

                # 同步测试连接
                client.ping()

                # 获取 Redis 信息
                info = client.info()
                redis_version = info.get("redis_version", "Unknown")

                # 关闭连接
                client.close()

                return {
                    "success": True,
                    "message": "Redis 连接成功（同步模式）",
                    "version": redis_version,
                }
            except Exception as e:
                error_msg = str(e)
                # Redis 错误处理
                if "Authentication required" in error_msg:
                    error_msg = "需要密码认证"
                elif "invalid password" in error_msg.lower():
                    error_msg = "密码错误"
                elif "connection refused" in error_msg.lower():
                    error_msg = "连接被拒绝，请检查Redis服务是否启动"
                elif "timeout" in error_msg.lower():
                    error_msg = "连接超时"

                return {"success": False, "message": f"Redis 连接失败: {error_msg}"}

    except asyncio.TimeoutError:
        return {"success": False, "message": "Redis 连接超时"}
    except Exception as e:
        logger.error(f"Redis 连接测试失败：{e}")
        return {"success": False, "message": f"Redis 连接失败: {str(e)}"}

