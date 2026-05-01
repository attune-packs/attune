class MetaPackError(Exception):
    """Base error for attune meta-pack actions."""


class ClientNotGeneratedError(MetaPackError):
    """Raised when the vendored OpenAPI client has not been generated yet."""


class ClientDependencyError(MetaPackError):
    """Raised when the vendored client exists but its Python deps are missing."""
