"""
数据库配置模型。
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class MainDatabaseConfig(BaseModel):
    """主数据库配置。"""

    enabled: bool = Field(default=True, description="是否启用数据库")
    type: Literal["postgresql", "mysql", "sqlite"] = Field(
        default="postgresql", description="数据库类型"
    )
    host: str = Field(default="localhost", description="数据库主机地址")
    port: int = Field(default=5432, description="数据库端口")
    database: str = Field(default="deepsearch", description="数据库名称")
    username: str = Field(default="postgres", description="用户名")
    password: str = Field(default="", description="密码")
    path: str = Field(default="./data/deepsearch.db", description="SQLite数据库文件路径")
    auto_connect: bool = Field(default=False, description="启动时自动连接数据库")
    echo: bool = Field(default=False, description="SQLAlchemy ����SQL�������")

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


class CacheDatabaseWSLConfig(BaseModel):
    """WSL 环境下的 Redis 集成配置。"""

    enabled: bool = Field(default=False, description="是否启用 WSL 模式自动解析 Redis")
    distro: str = Field(default="Ubuntu", description="WSL 发行版名称（如 Ubuntu）")
    auto_resolve_ip: bool = Field(default=True, description="是否自动解析 WSL IP 并覆盖 Redis host")
    service_name: str = Field(
        default="redis-server", description="WSL ���� service ���������õ� Redis ��������"
    )
    user: Optional[str] = Field(default="root", description="WSL ���� Redis ʱʹ�õ��û�(���� -u ����)")


class CacheDatabaseConfig(BaseModel):
    """缓存数据库配置（Redis）。"""

    enabled: bool = Field(default=True, description="是否启用缓存")
    host: str = Field(default="localhost", description="Redis主机地址")
    port: int = Field(default=6379, description="Redis端口")
    username: str = Field(default="", description="Redis用户名（可选，ACL）")
    password: str = Field(default="", description="Redis密码")
    db: int = Field(default=0, description="Redis数据库索引")
    pool_size: int = Field(default=10, description="连接池大小")

    # 连接池高级配置
    socket_timeout: int = Field(default=5, description="Socket超时时间（秒）")
    socket_connect_timeout: int = Field(default=5, description="Socket连接超时时间（秒）")
    socket_keepalive: bool = Field(default=True, description="是否启用TCP keepalive")
    retry_on_timeout: bool = Field(default=True, description="超时是否重试")
    health_check_interval: int = Field(default=30, description="健康检查间隔（秒）")

    # 连接池行为配置
    max_idle_time: int = Field(default=300, description="最大空闲时间（秒）")
    idle_check_interval: int = Field(default=60, description="空闲检查间隔（秒）")

    # Windows 自动启动控制
    auto_start_windows: bool = Field(
        default=True,
        description="Windows 启动程序时是否自动检查并尝试启动 Redis",
    )
    windows_service_names: List[str] = Field(
        default_factory=lambda: ["Redis", "redis"],
        description="Windows 服务名称候选列表，用于通过 sc 启动 Redis",
    )
    startup_binary_path: Optional[str] = Field(
        default=None,
        description="Redis 可执行文件路径（如手动部署的 redis-server.exe）",
    )
    startup_arguments: List[str] = Field(
        default_factory=list,
        description="启动 Redis 时附加的命令行参数",
    )
    startup_command: Optional[List[str]] = Field(
        default=None,
        description="自定义启动命令（例如通过 wsl.exe 触发 redis-server）",
    )

    wsl: Optional[CacheDatabaseWSLConfig] = Field(
        default=None, description="WSL 环境下的 Redis 集成配置"
    )

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
    path: str = Field(default="./data/analytics/market.duckdb", description="DuckDB数据库文件路径")
    memory_limit: str = Field(default="4GB", description="内存限制")
    threads: int = Field(default=4, description="线程数")
    temp_directory: str = Field(default="./data/analytics/temp", description="临时文件目录")
    auto_sync: bool = Field(default=True, description="自动同步数据")
    sync_interval: int = Field(default=3600, description="同步间隔（秒）")


class DatabaseConfig(BaseModel):
    """数据库配置。"""

    # 保留原有的url字段以保持向后兼容
    url: Optional[str] = Field(default=None, description="数据库连接URL（已废弃）")

    # 新的配置结构
    main: MainDatabaseConfig = Field(default_factory=MainDatabaseConfig, description="主数据库配置")
    cache: CacheDatabaseConfig = Field(
        default_factory=CacheDatabaseConfig, description="缓存数据库配置"
    )
    analytics: AnalyticsDatabaseConfig = Field(
        default_factory=AnalyticsDatabaseConfig, description="分析数据库配置"
    )

    def get_main_url(self) -> Optional[str]:
        """获取主数据库连接URL。"""
        # 如果设置了url字段，优先使用（向后兼容）
        if self.url:
            return self.url
        return self.main.get_url()
