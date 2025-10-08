"""
ϵͳ��Ϣ API �˵�

�ṩϵͳ���ú�����ʱ��Ϣ��ѯ�ӿ�
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.config import get_config
from deepsearch.core.runtime.engine import MainEngine
from deepsearch.webui.dependencies import get_engine

router = APIRouter(prefix="/api/system", tags=["system"])


class ComponentSummary(BaseModel):
    """����ϵͳ���ؽڵ��״̬��Ϣ"""

    status: str | None = None
    type: str | None = None


class WebUIInfo(BaseModel):
    """WebUI ���ýṹ"""

    configured_port: int
    actual_port: int
    frontend_port: int


class MessageBusInfo(BaseModel):
    """��Ϣ����״̬���"""

    buses: list[str] = Field(default_factory=list)
    routes: list[list[str]] = Field(default_factory=list)


class VersionInfo(BaseModel):
    """�汾��Ϣ"""

    api: str
    system: str


class SystemInfoResponse(BaseModel):
    """ϵͳ��Ϣ�ӿڷ���ֵ"""

    webui: WebUIInfo
    mode: str
    running: bool
    uptime: float
    start_time: str | None = None
    components: dict[str, ComponentSummary] = Field(default_factory=dict)
    message_bus: MessageBusInfo
    environment: str
    version: VersionInfo


class WebUIPortResponse(BaseModel):
    """WebUI �˿ݷ���״̬"""

    configured: int
    actual: int
    changed: bool


class NotifyPortChangeResponse(BaseModel):
    """֪ͨ�˿ڱ仯�ӿڷ���ֵ"""

    success: bool
    port: int | None = None
    reason: str | None = None


def _normalize_bus_name(value: object) -> str:
    """��һ��Ϣ������ö�ٵ������ƣ����ڻ�ȡ��ʽ����"""

    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _ensure_port(value: object, fallback: int) -> int:
    """ȷ����������Ӧ�ò�˿ںţ�������ص����Ϸ� int"""

    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return fallback


def _ensure_str(value: object) -> str | None:
    """����ֵתΪ�ַ�����ֹ��������"""

    return value if isinstance(value, str) else None


def _ensure_float(value: object) -> float:
    """��������תΪ float �����޷�ת�ͷ��� 0.0"""

    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


@router.get("/info", response_model=SystemInfoResponse)
async def get_system_info(engine: MainEngine = Depends(get_engine)) -> SystemInfoResponse:
    """
    ��ȡϵͳ��Ϣ

    ������
    - ʵ�����е� WebUI �˿�
    - ϵͳ����ģʽ
    - ���״̬ժҪ
    - �汾��Ϣ
    """
    try:
        config = get_config()

        engine_status_raw = engine.get_status()

        bus_config = config.message_bus
        bus_types = [
            _normalize_bus_name(bus_cfg.type)
            for bus_cfg in bus_config.buses.values()
            if bus_cfg.enabled
        ]
        message_routes = [
            [_normalize_bus_name(bus) for bus in route.buses]
            for route in bus_config.routes
        ]

        configured_port = config.webui.backend_port
        actual_port = _ensure_port(engine_status_raw.get("webui_port"), configured_port)

        mode = _ensure_str(engine_status_raw.get("mode")) or "unknown"
        running = bool(engine_status_raw.get("running", False))
        uptime = _ensure_float(engine_status_raw.get("uptime"))
        start_time = _ensure_str(engine_status_raw.get("start_time"))

        components_raw = engine_status_raw.get("components")
        components: dict[str, ComponentSummary] = {}
        if isinstance(components_raw, Mapping):
            for name, info_raw in components_raw.items():
                if isinstance(info_raw, Mapping):
                    components[name] = ComponentSummary(
                        status=_ensure_str(info_raw.get("status")),
                        type=_ensure_str(info_raw.get("type")),
                    )
                else:
                    components[name] = ComponentSummary()

        system_info = SystemInfoResponse(
            webui=WebUIInfo(
                configured_port=configured_port,
                actual_port=actual_port,
                frontend_port=config.webui.frontend_port,
            ),
            mode=mode,
            running=running,
            uptime=uptime,
            start_time=start_time,
            components=components,
            message_bus=MessageBusInfo(buses=bus_types, routes=message_routes),
            environment=config.app.env,
            version=VersionInfo(api="1.0.0", system="DeepSearch 1.0"),
        )

        return system_info

    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webui_port", response_model=WebUIPortResponse)
async def get_webui_port(engine: MainEngine = Depends(get_engine)) -> WebUIPortResponse:
    """
    ��ȡ WebUI ʵ�����ж˿�

    ���˿ڱ�ռ���Զ��л�ʱ������ʵ��ʹ�õĶ˿�
    """
    try:
        config = get_config()
        engine_status_raw = engine.get_status()

        configured_port = config.webui.backend_port
        actual_port = _ensure_port(engine_status_raw.get("webui_port"), configured_port)

        return WebUIPortResponse(
            configured=configured_port,
            actual=actual_port,
            changed=actual_port != configured_port,
        )

    except Exception as e:
        logger.error(f"Failed to get WebUI port: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify_port_change", response_model=NotifyPortChangeResponse)
async def notify_port_change(port: int, engine: MainEngine = Depends(get_engine)) -> NotifyPortChangeResponse:
    """
    ֪ͨ�˿ڱ�����ڲ�ʹ�ã�

    �� WebUI �˿ڷ����仯ʱ��ͨ����Ϣ����֪ͨ�������
    """
    try:
        engine_status = engine.get_status()

        from deepsearch.core.components import MessageBusComponent

        component = engine.get_component(MessageBusComponent)
        if not isinstance(component, MessageBusComponent):
            logger.warning("Message bus not available for port change notification")
            return NotifyPortChangeResponse(success=False, reason="Message bus not available")

        bus = component.get_instance()
        if bus is None:
            logger.warning("Message bus instance not initialized")
            return NotifyPortChangeResponse(success=False, reason="Message bus not initialized")

        await bus.publish_async(
            "system.webui.port_changed",
            {
                "old_port": get_config().webui.backend_port,
                "new_port": port,
                "timestamp": _ensure_str(engine_status.get("start_time")),
            },
        )
        logger.info(f"WebUI port change notified: {port}")
        return NotifyPortChangeResponse(success=True, port=port)

    except Exception as e:
        logger.error(f"Failed to notify port change: {e}")
        raise HTTPException(status_code=500, detail=str(e))
