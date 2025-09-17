"""
数据源状态和配置验证API
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from deepsearch.config import get_config
from deepsearch.config.validator import validate_config
from deepsearch.infrastructure.providers.managers.data_source_manager import get_data_source_manager
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes

router = APIRouter(prefix="/api/data-sources", tags=["数据源管理"])


@router.get("/status")
async def get_data_source_status():
    """
    获取所有数据源的状态
    
    返回各数据源的配置状态、可用性、延迟等信息
    """
    try:
        # 获取数据源管理器
        manager = get_data_source_manager()

        # 确保已初始化
        if not manager.initialized:
            await manager.initialize()

        # 获取状态报告
        status = manager.get_status_report()

        return APIResponse.success(status)
    except Exception as e:
        logger.error(f"获取数据源状态失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"获取数据源状态失败: {str(e)}",
            status_code=500
        )


@router.get("/config/validate")
async def validate_configuration():
    """
    验证当前配置
    
    检查配置的一致性、冲突和潜在问题
    """
    try:
        config = get_config()
        validator = validate_config(config)

        summary = validator.get_summary()

        # 如果有错误，返回400状态码
        if summary["has_errors"]:
            return APIResponse.error(
                code=ErrorCodes.VALIDATION_ERROR,
                message="配置验证发现错误",
                data=summary,
                status_code=400
            )

        # 如果有警告，返回200但标记warning
        if summary["warnings"] > 0:
            return APIResponse.success(
                data=summary,
                message="配置验证发现警告"
            )

        # 一切正常
        return APIResponse.success(
            data=summary,
            message="配置验证通过"
        )

    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"配置验证失败: {str(e)}",
            status_code=500
        )


@router.post("/refresh")
async def refresh_data_sources():
    """
    刷新数据源
    
    重新初始化所有数据源，用于配置更改后
    """
    try:
        manager = get_data_source_manager()

        # 重新初始化
        await manager.initialize()

        # 获取新状态
        status = manager.get_status_report()

        return APIResponse.success(
            data=status,
            message="数据源已刷新"
        )
    except Exception as e:
        logger.error(f"刷新数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"刷新数据源失败: {str(e)}",
            status_code=500
        )


@router.get("/config/current")
async def get_current_config():
    """
    获取当前数据源配置
    
    返回配置文件中的数据源相关配置
    """
    try:
        config = get_config()

        result = {
            "qmt": None,
            "data_providers": None
        }

        # QMT配置
        if hasattr(config, 'qmt') and config.qmt:
            result["qmt"] = {
                "enabled": config.qmt.enabled,
                "tcp_port": config.qmt.receiver.tcp_port if hasattr(config.qmt, 'receiver') else None,
                "fallback_enabled": getattr(config.qmt, 'fallback_enabled', False),
                "only_mode": getattr(config.qmt, 'only_mode', False)
            }

        # 数据提供者配置
        if hasattr(config, 'data_providers') and config.data_providers:
            providers = config.data_providers
            result["data_providers"] = {}

            # AKShare配置
            if hasattr(providers, 'akshare_proxy'):
                result["data_providers"]["akshare"] = {
                    "enabled": providers.akshare_proxy.get('enabled', False),
                    "priority": providers.akshare_proxy.get('priority', 999)
                }

            # CloudFlare配置
            if hasattr(providers, 'cloudflare_proxy'):
                result["data_providers"]["cloudflare"] = {
                    "enabled": providers.cloudflare_proxy.get('enabled', False),
                    "priority": providers.cloudflare_proxy.get('priority', 999),
                    "worker_url": providers.cloudflare_proxy.get('worker_url', '')
                }

        return APIResponse.success(result)

    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取配置失败: {str(e)}",
            status_code=500
        )


@router.get("/test/{symbol}")
async def test_data_source(symbol: str, source: str = None):
    """
    测试特定数据源
    
    Args:
        symbol: 股票代码
        source: 数据源名称（可选，不指定则测试所有）
    """
    try:
        from deepsearch.infrastructure.providers.managers.data_source_manager import DataSourceType

        manager = get_data_source_manager()

        if not manager.initialized:
            await manager.initialize()

        # 如果指定了数据源
        if source:
            try:
                source_type = DataSourceType(source)
            except ValueError:
                return APIResponse.error(
                    code=ErrorCodes.DATASOURCE_NOT_FOUND,
                    message=f"未知的数据源类型: {source}",
                    status_code=404
                )

            # 测试指定数据源
            result = await manager.get_data(
                data_type="realtime_quote",
                symbol=symbol,
                preferred_source=source_type
            )

            if result is not None and not result.empty:
                return APIResponse.success(
                    data=result,
                    message=f"数据源 {source} 测试成功"
                )
            else:
                return APIResponse.error(
                    code=ErrorCodes.DATASOURCE_TEST_FAILED,
                    message=f"数据源 {source} 测试失败",
                    status_code=500
                )

        # 测试所有可用数据源
        results = {}
        for source_type in manager.get_available_sources():
            try:
                result = await manager.get_data(
                    data_type="realtime_quote",
                    symbol=symbol,
                    preferred_source=source_type
                )
                results[source_type.value] = {
                    "success": result is not None,
                    "data": result if result else None
                }
            except Exception as e:
                results[source_type.value] = {
                    "success": False,
                    "error": str(e)
                }

        return APIResponse.success(
            data=results,
            message="数据源测试完成"
        )

    except Exception as e:
        logger.error(f"测试数据源失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"测试数据源失败: {str(e)}",
            status_code=500
        )
