"""
统一的API响应格式工具

提供标准化的API响应格式，确保前后端接口一致性
"""
from typing import Any, Dict, Optional, Union
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """错误详情模型"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class APIResponse:
    """统一API响应格式"""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "操作成功",
        **kwargs
    ) -> JSONResponse:
        """
        成功响应
        
        Args:
            data: 响应数据
            message: 成功消息
            **kwargs: 额外的响应字段
            
        Returns:
            JSONResponse
        """
        response = {
            "success": True,
            "data": data,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        return JSONResponse(content=response, status_code=200)
    
    @staticmethod
    def error(
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400,
        **kwargs
    ) -> JSONResponse:
        """
        错误响应
        
        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情
            status_code: HTTP状态码
            **kwargs: 额外的响应字段
            
        Returns:
            JSONResponse
        """
        response = {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            },
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        return JSONResponse(content=response, status_code=status_code)
    
    @staticmethod
    def paginated(
        data: list,
        total: int,
        page: int = 1,
        page_size: int = 20,
        message: str = "查询成功",
        **kwargs
    ) -> JSONResponse:
        """
        分页响应
        
        Args:
            data: 数据列表
            total: 总数
            page: 当前页
            page_size: 每页大小
            message: 成功消息
            **kwargs: 额外的响应字段
            
        Returns:
            JSONResponse
        """
        response = {
            "success": True,
            "data": {
                "items": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            },
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        return JSONResponse(content=response, status_code=200)


class APIException(HTTPException):
    """
    统一的API异常类
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(status_code=status_code, detail=message)
    
    def to_response(self) -> JSONResponse:
        """转换为响应格式"""
        return APIResponse.error(
            code=self.code,
            message=self.message,
            details=self.details,
            status_code=self.status_code
        )


# 预定义的错误代码
class ErrorCodes:
    """标准错误代码"""
    
    # 通用错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    
    # 数据源相关
    DATASOURCE_NOT_FOUND = "DATASOURCE_NOT_FOUND"
    DATASOURCE_CONNECTION_FAILED = "DATASOURCE_CONNECTION_FAILED"
    DATASOURCE_ALREADY_EXISTS = "DATASOURCE_ALREADY_EXISTS"
    DATASOURCE_IN_USE = "DATASOURCE_IN_USE"
    
    # 数据库相关
    DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
    DATABASE_CONNECTION_FAILED = "DATABASE_CONNECTION_FAILED"
    DATABASE_ALREADY_EXISTS = "DATABASE_ALREADY_EXISTS"
    DATABASE_IN_USE = "DATABASE_IN_USE"
    
    # 配置相关
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"