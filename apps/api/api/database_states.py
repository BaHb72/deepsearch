"""Pydantic schemas for database activation/connectivity states."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ActivationStateLiteral = Literal["active", "inactive", "pending", "error", "unknown"]
ConnectivityStateLiteral = Literal["connected", "connecting", "disconnected", "error", "unknown"]


class ActivationStateSchema(BaseModel):
    """Structure describing how a connection is configured."""

    state: ActivationStateLiteral = Field(default="unknown")
    enabled: bool = Field(default=False)
    updated_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None)


class ConnectivityStateSchema(BaseModel):
    """Structure describing runtime connectivity information."""

    state: ConnectivityStateLiteral = Field(default="unknown")
    last_success_at: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    retrying: bool = Field(default=False)


class DeprecatedStateSchema(BaseModel):
    """Legacy boolean/status fields kept for compatibility."""

    enabled: Optional[bool] = None
    connected: Optional[bool] = None
    status: Optional[str] = None


class DatabaseConnectionStateSchema(BaseModel):
    """Aggregate state returned by the API."""

    activation: ActivationStateSchema = Field(default_factory=ActivationStateSchema)
    connectivity: ConnectivityStateSchema = Field(default_factory=ConnectivityStateSchema)
    deprecated: DeprecatedStateSchema = Field(default_factory=DeprecatedStateSchema)
