"""模块数据源配置表迁移脚本。

创建 module_source_configs 表并可选迁移现有 YAML 配置。
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, cast

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Executable

from deepsearch.observability.logger import logger

# 分开的SQL语句
SQL_CREATE_TABLE = """
                   CREATE TABLE IF NOT EXISTS module_source_configs
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       module_name
                       VARCHAR
                   (
                       64
                   ) UNIQUE NOT NULL,
                       label VARCHAR
                   (
                       128
                   ),
                       description VARCHAR
                   (
                       512
                   ),
                       category VARCHAR
                   (
                       32
                   ) DEFAULT 'general',
                       primary_source VARCHAR
                   (
                       32
                   ),
                       fallback_sources JSONB DEFAULT '[]'::jsonb,
                       enabled BOOLEAN NOT NULL DEFAULT true,
                       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW
                   (
                   ),
                       updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW
                   (
                   )
                       ) \
                   """

SQL_CREATE_INDEX_MODULE = """
                          CREATE INDEX IF NOT EXISTS idx_module_source_configs_module_name
                              ON module_source_configs(module_name) \
                          """

SQL_CREATE_INDEX_CATEGORY = """
                            CREATE INDEX IF NOT EXISTS idx_module_source_configs_category
                                ON module_source_configs(category) \
                            """

SQL_CREATE_FUNCTION = """
                      CREATE
                      OR REPLACE FUNCTION update_module_source_configs_updated_at()
RETURNS TRIGGER AS $$
                      BEGIN
    NEW.updated_at
                      = NOW();
                      RETURN NEW;
                      END;
$$
                      LANGUAGE plpgsql \
                      """

SQL_DROP_TRIGGER = """
DROP TRIGGER IF EXISTS trigger_update_module_source_configs_updated_at
    ON module_source_configs
"""

SQL_CREATE_TRIGGER = """
                     CREATE TRIGGER trigger_update_module_source_configs_updated_at
                         BEFORE UPDATE
                         ON module_source_configs
                         FOR EACH ROW
                         EXECUTE FUNCTION update_module_source_configs_updated_at() \
                     """


def load_yaml_config() -> Optional[Dict[str, Any]]:
    """加载现有 YAML 配置。"""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "config" / "module_sources.yaml",
        Path("deepsearch/config/module_sources.yaml"),
        Path("config/module_sources.yaml"),
    ]

    for path in candidates:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    logger.info(f"加载 YAML 配置: {path}")
                    if isinstance(config, dict):
                        return cast(Dict[str, Any], config)
                    return None
            except Exception as e:
                logger.warning(f"加载 {path} 失败: {e}")

    return None


async def run_migration(migrate_data: bool = True) -> bool:
    """执行完整迁移。

    Args:
        migrate_data: 是否迁移现有数据

    Returns:
        迁移是否成功
    """
    from deepsearch.core.component_factory import DatabaseComponentFactory
    from deepsearch.infrastructure.persistence.database import DatabaseService

    db_component = DatabaseComponentFactory.create()

    try:
        # 初始化数据库连接
        await db_component.initialize_async()
        logger.info("数据库连接已建立")

        db_service = DatabaseService(db_component)

        # 1. 创建表和索引
        logger.info("创建 module_source_configs 表...")
        async with db_service.get_session() as session:
            db_session: AsyncSession = cast(AsyncSession, session)

            # 分别执行每条SQL
            await db_session.execute(cast(Executable, text(SQL_CREATE_TABLE)))
            logger.debug("表结构创建完成")

            await db_session.execute(cast(Executable, text(SQL_CREATE_INDEX_MODULE)))
            logger.debug("module_name 索引创建完成")

            await db_session.execute(cast(Executable, text(SQL_CREATE_INDEX_CATEGORY)))
            logger.debug("category 索引创建完成")

            await db_session.execute(cast(Executable, text(SQL_CREATE_FUNCTION)))
            logger.debug("更新函数创建完成")

            await db_session.execute(cast(Executable, text(SQL_DROP_TRIGGER)))
            await db_session.execute(cast(Executable, text(SQL_CREATE_TRIGGER)))
            logger.debug("触发器创建完成")

            await db_session.commit()
        logger.info("✅ module_source_configs 表创建成功")

        # 2. 迁移数据
        if migrate_data:
            config = load_yaml_config()
            if config:
                modules_cfg = config.get("modules", {})
                if modules_cfg:
                    logger.info(f"发现 {len(modules_cfg)} 个模块配置待迁移")

                    import json

                    migrated = 0
                    async with db_service.get_session() as session:
                        db_session = cast(AsyncSession, session)

                        for module_name, cfg in modules_cfg.items():
                            try:
                                # 检查是否已存在
                                result = await db_session.execute(
                                    cast(
                                        Executable,
                                        text(
                                            "SELECT id FROM module_source_configs WHERE module_name = :name"
                                        ),
                                    ),
                                    {"name": module_name},
                                )
                                cursor_result = result.mappings()
                                existing = cursor_result.first()

                                if existing:
                                    logger.debug(f"模块 {module_name} 已存在，跳过")
                                    continue

                                # 插入新记录
                                primary = cfg.get("primary")
                                fallback = cfg.get("fallback", [])
                                if isinstance(fallback, str):
                                    fallback = [fallback]

                                insert_sql = cast(
                                    Executable,
                                    text(
                                        """
                                                  INSERT INTO module_source_configs
                                                      (module_name, primary_source, fallback_sources, category)
                                                  VALUES (:module_name, :primary, :fallback::jsonb, :category)
                                                  """
                                    ),
                                )

                                await db_session.execute(
                                    insert_sql,
                                    {
                                        "module_name": module_name,
                                        "primary": primary,
                                        "fallback": json.dumps(fallback),
                                        "category": cfg.get("category", "general"),
                                    },
                                )

                                migrated += 1
                                logger.info(f"  迁移: {module_name}")

                            except Exception as e:
                                logger.warning(f"迁移 {module_name} 失败: {e}")

                        await db_session.commit()

                    logger.info(f"✅ 成功迁移 {migrated} 个模块配置")
                else:
                    logger.info("YAML 中没有模块配置")
            else:
                logger.info("未找到 YAML 配置文件，跳过数据迁移")

        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        try:
            await db_component.stop_async()
        except Exception:
            pass  # 忽略停止时的错误


def main():
    """主函数。"""
    import argparse

    parser = argparse.ArgumentParser(description="模块数据源配置表迁移")
    parser.add_argument("--no-data", action="store_true", help="只创建表，不迁移数据")

    args = parser.parse_args()

    print("=" * 50)
    print("模块数据源配置表迁移脚本")
    print("=" * 50)

    success = asyncio.run(run_migration(migrate_data=not args.no_data))

    print("=" * 50)
    if success:
        print("✅ 迁移完成")
    else:
        print("❌ 迁移失败")
        exit(1)


if __name__ == "__main__":
    main()
