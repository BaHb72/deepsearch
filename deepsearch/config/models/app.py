"""
应用程序配置模型。
"""
from typing import Literal

from pydantic import BaseModel

from deepsearch.constants import APP_AUTHOR, APP_NAME

AppEnvironment = Literal["dev", "prod"]


class AppConfig(BaseModel):
    """应用程序配置。"""
    name: str = APP_NAME
    author: str = APP_AUTHOR
    env: AppEnvironment = "prod"
