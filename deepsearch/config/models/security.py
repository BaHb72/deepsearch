"""
Security configuration models.
"""

from typing import Optional

from pydantic import BaseModel


class SecurityConfig(BaseModel):
    """Security configuration."""

    enable_tls: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
