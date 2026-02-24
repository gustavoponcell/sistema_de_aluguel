"""Custom service layer errors."""


class ServiceError(Exception):
    """Base error for service-layer failures."""


class ValidationError(ServiceError):
    """Raised when a business rule validation fails."""


class NotFoundError(ServiceError):
    """Raised when an entity is not found."""
