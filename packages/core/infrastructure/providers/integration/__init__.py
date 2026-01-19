"""
Provider 集成模块
"""

from .fastapi import get_provider_container, provider_lifespan

__all__ = [
    "provider_lifespan",
    "get_provider_container",
]
