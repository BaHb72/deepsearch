"""
数据库配置模型。
"""
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator


class MainDatabaseConfig(BaseModel):
    """主数据库配置。"""
    enabled: bool = Field(default=True, description="是否启用数据库")
    type: Literal["postgresql", "mysql", "sqlite"] = Field(
        default="postgresql",
        description="数据库类型"
    )
    host: str = Field(default="localhost", description="数据库主机地址")
    port: int = Field(default=5432, description="数据库端口")
    database: str = Field(default="deepsearch", description="数据库名称")
    username: str = Field(default="postgres", description="用户名")
    password: str = Field(default="", description="密码")
    path: str = Field(default="./data/deepsearch.db", description="SQLite数据库文件路径")
    auto_connect: bool = Field(default=False, description="启动时自动连接数据库")

    @field_validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("端口必须在1-65535之间")
        return v

    def get_url(self) -> Optional[str]:
        """构建数据库连接URL。
        
        如果密码以 "encrypted:" 开头，会自动解密。
        如果密码是 "***"，表示脱敏的密码，返回 None。
        """
        # 处理密码
        actual_password = self.password

        # 如果密码是脱敏的占位符，不能用于连接
        if self.password == "***":
            return None
            
        if self.password and self.password.startswith("encrypted:"):
            try:
                from deepsearch.config.crypto import decrypt_password
                encrypted_part = self.password[10:]  # 移除 "encrypted:" 前缀
                actual_password = decrypt_password(encrypted_part)
            except Exception as e:
                # 如果解密失败，使用原始密码
                import logging
                logging.warning(f"Failed to decrypt password: {e}")
                actual_password = self.password
        
        if self.type == "sqlite":
            return f"sqlite:///{self.path}"
        elif self.type == "postgresql":
            if actual_password:
                return f"postgresql://{self.username}:{actual_password}@{self.host}:{self.port}/{self.database}"
            return f"postgresql://{self.username}@{self.host}:{self.port}/{self.database}"
        elif self.type == "mysql":
            if actual_password:
                return f"mysql://{self.username}:{actual_password}@{self.host}:{self.port}/{self.database}"
            return f"mysql://{self.username}@{self.host}:{self.port}/{self.database}"
        return None


class CacheDatabaseConfig(BaseModel):
    """缓存数据库配置（Redis）。"""
    enabled: bool = Field(default=True, description="是否启用缓存")
    host: str = Field(default="localhost", description="Redis主机地址")
    port: int = Field(default=6379, description="Redis端口")
    password: str = Field(default="", description="Redis密码")
    db: int = Field(default=0, description="Redis数据库索引")
    pool_size: int = Field(default=10, description="连接池大小")

    @field_validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("端口必须在1-65535之间")
        return v

    @field_validator("db")
    def validate_db(cls, v):
        if not 0 <= v <= 15:
            raise ValueError("Redis数据库索引必须在0-15之间")
        return v


class AnalyticsDatabaseConfig(BaseModel):
    """分析数据库配置（DuckDB）。"""
    enabled: bool = Field(default=True, description="是否启用分析数据库")
    path: str = Field(default="./data/analytics.duckdb", description="DuckDB数据库文件路径")
    memory_limit: str = Field(default="4GB", description="内存限制")
    threads: int = Field(default=4, description="线程数")


class DatabaseConfig(BaseModel):
    """数据库配置。"""
    # 保留原有的url字段以保持向后兼容
    url: Optional[str] = Field(default=None, description="数据库连接URL（已废弃）")

    # 新的配置结构
    main: MainDatabaseConfig = Field(
        default_factory=MainDatabaseConfig,
        description="主数据库配置"
    )
    cache: CacheDatabaseConfig = Field(
        default_factory=CacheDatabaseConfig,
        description="缓存数据库配置"
    )
    analytics: AnalyticsDatabaseConfig = Field(
        default_factory=AnalyticsDatabaseConfig,
        description="分析数据库配置"
    )

    def get_main_url(self) -> Optional[str]:
        """获取主数据库连接URL。"""
        # 如果设置了url字段，优先使用（向后兼容）
        if self.url:
            return self.url
        return self.main.get_url()
