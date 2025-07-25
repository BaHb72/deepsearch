"""
ZeroMQ configuration models.
"""
from pydantic import BaseModel

from deepsearch.constants import (
    DEFAULT_RECV_BUFFER,
    DEFAULT_SEND_BUFFER,
    DEFAULT_ZMQ_PUB_PORT,
    DEFAULT_ZMQ_SUB_PORT,
)


class ZeroMQConfig(BaseModel):
    """ZeroMQ message bus configuration."""
    host: str = "127.0.0.1"
    pub_port: int = DEFAULT_ZMQ_PUB_PORT
    sub_port: int = DEFAULT_ZMQ_SUB_PORT
    send_hwm: int = DEFAULT_SEND_BUFFER
    recv_hwm: int = DEFAULT_RECV_BUFFER
    verbose: bool = True
