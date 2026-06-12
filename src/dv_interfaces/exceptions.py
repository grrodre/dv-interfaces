class ErrorDVInterface(Exception):
    """Base exception for all dv-interfaces errors."""


class ErrorConnectionDVInterface(ErrorDVInterface):
    """Raised when a connection to the device cannot be established or is lost."""

    def __init__(
        self, message: str, *, host: str | None = None, port: int | None = None
    ) -> None:
        super().__init__(message)
        self.host = host
        self.port = port


class ErrorReadDVInterface(ErrorDVInterface):
    """Raised when a register read fails."""


class ErrorTurnOnDVInterface(ErrorDVInterface):
    """Raised when turning the plant on fails."""


class ErrorTurnOffDVInterface(ErrorDVInterface):
    """Raised when turning the plant off fails."""


class ErrorLimitingDVInterface(ErrorDVInterface):
    """Raised when setting a power limitation fails."""


class ErrorUnsupportedOperationDVInterface(ErrorDVInterface):
    """Raised when a driver does not support a requested operation."""
