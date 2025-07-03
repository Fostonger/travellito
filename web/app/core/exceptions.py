from typing import Any, Optional, Dict


class BaseError(Exception):
    """Base exception class for the application"""
    
    def __init__(
        self, 
        message: str = "An error occurred",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(BaseError):
    """Exception raised when an entity is not found"""
    
    def __init__(self, entity: str, id: Any):
        super().__init__(
            message=f"{entity} with id {id} not found",
            status_code=404,
            details={"entity": entity, "id": id}
        )


class ValidationError(BaseError):
    """Exception raised for validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            status_code=400,
            details=details
        )


class AuthenticationError(BaseError):
    """Exception raised for authentication errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(BaseError):
    """Exception raised for authorization errors"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message=message, status_code=403)


class ConflictError(BaseError):
    """Exception raised for conflict errors"""
    
    def __init__(self, message: str):
        super().__init__(message=message, status_code=409)


class BusinessLogicError(BaseError):
    """Exception raised for business logic violations"""
    
    def __init__(self, message: str, rule: Optional[str] = None):
        details = {"rule": rule} if rule else {}
        super().__init__(
            message=message,
            status_code=422,
            details=details
        )


class ExternalServiceError(BaseError):
    """Exception raised when external service fails"""
    
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"External service error: {message}",
            status_code=503,
            details={"service": service}
        ) 