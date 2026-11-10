"""Safe domain errors, whose codes are constrained by ErrorCode.schema.json."""


class DomainError(ValueError):
    """An expected, fail-closed domain refusal."""

    def __init__(self, code: str, message: str = "Domain operation refused") -> None:
        self.code = code
        super().__init__(message)
