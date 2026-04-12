"""
配置管理 API 路由。
"""

import asyncio
import copy
import sys
from pathlib import Path
from typing import Any, Dict, Final, cast

import yaml
from core.config import Settings, get_config, reload_config
from core.config.models.log import LogConfig as LogConfigModel
from core.constants import YAML_ENCODING
from core.observability.logger import logger_manager
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, ValidationError

# Windows 兼容性：设置事件循环策略
if sys.platform == "win32":
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is not None:
        asyncio.set_event_loop_policy(selector_policy())

router = APIRouter()

MASKED_SECRET: Final[str] = "***"  # nosec B105 - UI 脱敏显示占位符


def _serialize_log_config(config: LogConfigModel) -> Dict[str, Any]:
    """将 LogConfig 转换为可序列化的字典。"""
    return config.model_dump()


@router.get("/log")
async def get_log_configuration() -> Dict[str, Any]:
    """获取当前日志配置。"""
    try:
        config = get_config()
        if config is None or config.log is None:
            raise HTTPException(status_code=500, detail="日志配置未初始化")
        return _serialize_log_config(config.log)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取日志配置失败：{exc}")
        raise HTTPException(status_code=500, detail=f"获取日志配置失败：{exc}") from exc


@router.post("/log")
async def update_log_configuration(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新日志配置并刷新日志系统。"""
    try:
        log_config = LogConfigModel.model_validate(payload)
    except ValidationError as exc:
        logger.warning("日志配置验证失败：{}", exc)
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    save_result = await save_config({"log": log_config.model_dump()})
    try:
        logger_manager.stop()
        logger_manager.start()
    except Exception as exc:  # pragma: no cover - 仅记录刷新失败
        logger.warning(f"刷新日志系统失败：{exc}")
        warnings = save_result.setdefault("warnings", [])
        warnings.append(f"日志配置已写入，但运行时刷新失败：{exc}")

    save_result.setdefault("log", _serialize_log_config(log_config))
    return save_result


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


def _build_config_payload(config: Settings) -> Dict[str, Any]:
    """将配置对象转换为脱敏后的字典。"""

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

    config_dict: Dict[str, Any] = config.model_dump()

    if "security" in config_dict and config_dict["security"] is not None:
        config_dict["security"] = {
            "api_key": MASKED_SECRET if config_dict["security"].get("api_key") else None,
            "secret_key": MASKED_SECRET if config_dict["security"].get("secret_key") else None,
        }

    if "database" in config_dict:
        if "main" in config_dict["database"] and "password" in config_dict["database"]["main"]:
            if config_dict["database"]["main"]["password"]:
                config_dict["database"]["main"]["has_saved_password"] = True
                config_dict["database"]["main"]["password"] = MASKED_SECRET
            else:
                config_dict["database"]["main"]["has_saved_password"] = False
        if "cache" in config_dict["database"] and "password" in config_dict["database"]["cache"]:
            if config_dict["database"]["cache"]["password"]:
                config_dict["database"]["cache"]["has_saved_password"] = True
                config_dict["database"]["cache"]["password"] = MASKED_SECRET
            else:
                config_dict["database"]["cache"]["has_saved_password"] = False

    return config_dict


async def _reload_and_export_config() -> Dict[str, Any]:
    """重新加载配置并返回脱敏后的字典表示。"""

    def _reload() -> Dict[str, Any]:
        reloaded = reload_config()
        return _build_config_payload(reloaded)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return await loop.run_in_executor(None, _reload)

    return _reload()


@router.get("")
async def get_configuration() -> Dict[str, Any]:
    """
    获取当前系统配置。

    Returns:
        系统配置字典
    """
    try:
        config = get_config()
        if config is None:
            return {
                "error": "配置未加载",
                "message": "配置系统未能正确初始化",
                "config_missing": True,
                "env": "unknown",
            }

        return _build_config_payload(config)

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

        # 准备要保存的配置，默认继承现有内容避免丢失未编辑的字段
        save_data: Dict[str, Any]
        if existing_config:
            save_data = copy.deepcopy(existing_config)
        else:
            save_data = {}

        def _update_section(name: str) -> None:
            if name in config_data:
                value = config_data[name]
                if value is None:
                    save_data.pop(name, None)
                else:
                    save_data[name] = copy.deepcopy(value)

        for section in (
            "app",
            "log",
            "message_bus",
            "webui",
            "monitoring",
            "notifications",
            "runtime",
            "performance",
            "debug",
            "health_check",
            "qmt",
            "miniqmt",
            "amazingdata",
            "cloudflare",
            "cloudflare_workers",
            "data_sources",
            "data_providers",
        ):
            _update_section(section)

        # 处理数据库配置
        if "database" in config_data:
            db_config = config_data["database"]
            if db_config is None:
                save_data.pop("database", None)
            elif isinstance(db_config, dict):
                existing_db = copy.deepcopy(existing_config.get("database", {}))
                merged_db: Dict[str, Any] = copy.deepcopy(existing_db)

                if "url" in db_config:
                    merged_db["url"] = db_config["url"]

                # 处理主数据库配置
                if "main" in db_config and isinstance(db_config["main"], dict):
                    main_updates = dict(db_config["main"])
                    main_existing = copy.deepcopy(existing_db.get("main", {}))
                    main_updates.pop("has_saved_password", None)
                    remember_password = bool(main_updates.pop("rememberPassword", False))
                    existing_password = main_existing.get("password", "")

                    if "password" in main_updates:
                        password_value = main_updates["password"]
                        if password_value == MASKED_SECRET:
                            main_updates["password"] = existing_password
                        elif remember_password and password_value:
                            main_updates["password"] = password_value
                        else:
                            main_updates["password"] = ""
                    else:
                        if "password" in main_existing:
                            main_updates["password"] = main_existing["password"]

                    merged_main = {**main_existing, **main_updates}
                    merged_db["main"] = merged_main

                # 处理缓存数据库配置
                if "cache" in db_config and isinstance(db_config["cache"], dict):
                    cache_updates = dict(db_config["cache"])
                    cache_existing = copy.deepcopy(existing_db.get("cache", {}))
                    cache_updates.pop("has_saved_password", None)
                    existing_cache_password = cache_existing.get("password", "")

                    if "password" in cache_updates:
                        cache_password = cache_updates["password"]
                        if cache_password == MASKED_SECRET:
                            cache_updates["password"] = existing_cache_password
                        elif cache_password:
                            cache_updates["password"] = cache_password
                        else:
                            cache_updates["password"] = ""
                    else:
                        if "password" in cache_existing:
                            cache_updates["password"] = cache_existing["password"]

                    if cache_updates.get("username") == MASKED_SECRET:
                        cache_updates["username"] = cache_existing.get("username", "")

                    merged_cache = {**cache_existing, **cache_updates}
                    merged_db["cache"] = merged_cache

                # 合并其他数据库子配置（如 analytics 等）
                for key, value in db_config.items():
                    if key not in {"main", "cache", "url"}:
                        merged_db[key] = value

                save_data["database"] = merged_db

        if "security" in config_data:
            security_payload = config_data["security"] or {}
            existing_security = existing_config.get("security", {})
            save_security: Dict[str, Any] = {}

            if "api_key" in security_payload:
                api_key = security_payload.get("api_key")
                if api_key == MASKED_SECRET:
                    if existing_security:
                        save_security["api_key"] = existing_security.get("api_key", "")
                elif api_key:
                    save_security["api_key"] = api_key
                else:
                    save_security["api_key"] = ""

            if "secret_key" in security_payload:
                secret_key = security_payload.get("secret_key")
                if secret_key == MASKED_SECRET:
                    if existing_security:
                        save_security["secret_key"] = existing_security.get("secret_key", "")
                elif secret_key:
                    save_security["secret_key"] = secret_key
                else:
                    save_security["secret_key"] = ""

            # 清理空值，避免写入冗余字段
            save_security = {
                key: value for key, value in save_security.items() if value not in (None, "")
            }

            if save_security:
                save_data["security"] = save_security
            else:
                save_data.pop("security", None)

        # 合并未显式处理的其他键，确保新增字段不会丢失
        handled_keys = {
            "app",
            "log",
            "database",
            "message_bus",
            "webui",
            "monitoring",
            "security",
            "notifications",
            "runtime",
            "performance",
            "debug",
            "health_check",
            "qmt",
            "miniqmt",
            "amazingdata",
            "cloudflare",
            "cloudflare_workers",
            "data_sources",
            "data_providers",
        }
        for key, value in config_data.items():
            if key not in handled_keys:
                save_data[key] = copy.deepcopy(value)

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
            updated_config = await _reload_and_export_config()
        except Exception as reload_error:
            logger.error(f"保存后重新加载配置失败: {reload_error}")
            return {
                "success": False,
                "message": f"配置已写入文件，但重新加载失败: {reload_error}",
                "path": str(config_path),
            }

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
                    conninfo="",
                    host=config.host,
                    port=config.port,
                    dbname=config.database,
                    user=config.username,
                    password=actual_password,
                    connect_timeout=5,
                ) as pg_conn:
                    async with pg_conn.cursor() as cur:
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

                mysql_conn = await aiomysql.connect(
                    host=config.host,
                    port=config.port,
                    db=config.database,
                    user=config.username,
                    password=actual_password,
                    connect_timeout=5,
                )
                mysql_cursor = await mysql_conn.cursor()
                await mysql_cursor.execute("SELECT VERSION()")
                version = await mysql_cursor.fetchone()
                await mysql_cursor.close()
                mysql_conn.close()

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

                sqlite_conn = await aiosqlite.connect(config.path)
                sqlite_cursor = await sqlite_conn.execute("SELECT sqlite_version()")
                version = await sqlite_cursor.fetchone()
                await sqlite_conn.close()

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
            client: redis_async.Redis = redis_async.Redis(
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
                sync_client = redis.Redis(
                    host=config.host,
                    port=config.port,
                    username=actual_username or None,
                    password=actual_password if actual_password else None,
                    db=config.db,
                    socket_connect_timeout=5,
                )

                # 同步测试连接
                sync_client.ping()

                # 获取 Redis 信息
                info = dict(sync_client.info())
                redis_version = info.get("redis_version", "Unknown")

                # 关闭连接
                sync_client.close()

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


# ---------------------------------------------------------------------------
# 轮询配置 API
# ---------------------------------------------------------------------------


class PhaseBehaviorUpdate(BaseModel):
    """阶段行为更新模型。"""

    interval_seconds: float | None = None
    timeout_seconds: float | None = None
    skip_polling: bool | None = None


class SessionGuardUpdate(BaseModel):
    """交易阶段判断配置更新模型。"""

    enabled: bool | None = None
    calendar_source: str | None = None  # amazingdata, miniqmt, auto
    market: str | None = None  # SH, SZ, BJ, HK 等


class PollingConfigUpdate(BaseModel):
    """轮询配置更新模型。"""

    calendar_ttl_minutes: int | None = None
    session_guard: SessionGuardUpdate | None = None
    defaults: Dict[str, PhaseBehaviorUpdate] | None = None


@router.get("/polling")
async def get_polling_config() -> Dict[str, Any]:
    """
    获取当前轮询配置。

    Returns:
        轮询配置字典
    """
    try:
        from core.config.trading_schedule_config import config_to_dict, get_trading_schedule_config

        config = get_trading_schedule_config()
        return {
            "success": True,
            "config": config_to_dict(config),
        }
    except Exception as e:
        logger.error(f"获取轮询配置失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取轮询配置失败：{e}") from e


@router.put("/polling")
async def update_polling_config(payload: PollingConfigUpdate) -> Dict[str, Any]:
    """
    更新轮询配置并热重载。

    Args:
        payload: 轮询配置更新

    Returns:
        更新结果
    """
    try:
        from core.config.trading_schedule_config import (
            PhaseBehavior,
            SessionGuardConfig,
            config_to_dict,
            get_trading_schedule_config,
            reload_trading_schedule_config,
            save_trading_schedule_config,
        )

        config = get_trading_schedule_config()

        # 更新 calendar_ttl_minutes
        if payload.calendar_ttl_minutes is not None:
            config.calendar_ttl_minutes = payload.calendar_ttl_minutes

        # 更新 session_guard 配置
        if payload.session_guard:
            current_guard = config.session_guard
            new_enabled = (
                payload.session_guard.enabled
                if payload.session_guard.enabled is not None
                else current_guard.enabled
            )
            new_source = (
                payload.session_guard.calendar_source.lower()
                if payload.session_guard.calendar_source is not None
                else current_guard.calendar_source
            )
            new_market = (
                payload.session_guard.market.upper()
                if payload.session_guard.market is not None
                else current_guard.market
            )
            config.session_guard = SessionGuardConfig(
                enabled=new_enabled,
                calendar_source=new_source,
                market=new_market,
            )

        # 更新阶段行为配置
        if payload.defaults:
            for phase_name, phase_update in payload.defaults.items():
                current = config.defaults.get(phase_name, PhaseBehavior())

                new_interval = (
                    phase_update.interval_seconds
                    if phase_update.interval_seconds is not None
                    else current.interval_seconds
                )
                new_timeout = (
                    phase_update.timeout_seconds
                    if phase_update.timeout_seconds is not None
                    else current.timeout_seconds
                )
                new_skip = (
                    phase_update.skip_polling
                    if phase_update.skip_polling is not None
                    else current.skip_polling
                )

                config.defaults[phase_name] = PhaseBehavior(
                    interval_seconds=new_interval,
                    timeout_seconds=new_timeout,
                    skip_polling=new_skip,
                    skip_windows=current.skip_windows,
                )

        # 保存并热重载
        save_trading_schedule_config(config)
        updated_config = reload_trading_schedule_config()

        logger.info("轮询配置已更新并热重载")
        return {
            "success": True,
            "message": "轮询配置已更新",
            "config": config_to_dict(updated_config),
        }
    except Exception as e:
        logger.error(f"更新轮询配置失败：{e}")
        raise HTTPException(status_code=500, detail=f"更新轮询配置失败：{e}") from e


# ---------------------------------------------------------------------------
# 超时配置 API
# ---------------------------------------------------------------------------


class TimeoutConfigResponse(BaseModel):
    """超时配置响应模型。

    用于前后端超时同步，确保前端超时 >= 后端超时。
    """

    # 前端 HTTP 客户端超时（毫秒）
    client_timeout_ms: int = 90000  # 90秒，覆盖首次调用场景

    # 按操作类型细分的超时配置
    timeouts_by_operation: Dict[str, int] = {
        "default": 30000,  # 默认操作 30s
        "data_fetch": 90000,  # 数据获取（可能触发登录）90s
        "health_check": 5000,  # 健康检查 5s
        "config_save": 10000,  # 配置保存 10s
    }

    # 后端超时参考（仅供展示，前端不直接使用）
    backend_timeouts: Dict[str, float] = {
        "dask_adapter_normal": 45.0,
        "dask_adapter_first_call": 90.0,
        "sdk_internal": 30.0,
    }


@router.get("/timeouts")
async def get_timeout_config() -> TimeoutConfigResponse:
    """
    获取超时配置。

    前端应在启动时调用此接口，根据返回值配置 HTTP 客户端超时。
    这确保前后端超时同步，避免前端先超时导致的用户体验问题。

    Returns:
        超时配置
    """
    try:
        config = get_config()

        # 从统一超时配置读取 AmazingData 超时设置
        timeouts_cfg = getattr(config, "timeouts", None)
        if timeouts_cfg:
            dask_normal_timeout = timeouts_cfg.amazingdata.normal_call
            dask_first_call_timeout = timeouts_cfg.amazingdata.first_call
        else:
            dask_normal_timeout = 45.0
            dask_first_call_timeout = 90.0

        # 前端超时应该 >= 后端最大超时 + 网络缓冲
        buffer_ms = 5000  # 5秒网络缓冲
        client_timeout_ms = int(dask_first_call_timeout * 1000) + buffer_ms

        return TimeoutConfigResponse(
            client_timeout_ms=client_timeout_ms,
            timeouts_by_operation={
                "default": 30000,
                "data_fetch": client_timeout_ms,
                "health_check": 5000,
                "config_save": 10000,
            },
            backend_timeouts={
                "dask_adapter_normal": dask_normal_timeout,
                "dask_adapter_first_call": dask_first_call_timeout,
                "sdk_internal": 30.0,
            },
        )
    except Exception as e:
        logger.error(f"获取超时配置失败：{e}")
        # 返回安全的默认值
        return TimeoutConfigResponse()
