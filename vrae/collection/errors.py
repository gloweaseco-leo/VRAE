"""Safe, bounded error vocabulary; never expose remote bodies or secrets in errors."""

CODES = {
    "INVALID_URL", "SOURCE_NOT_ALLOWED", "POLICY_REQUIRED", "POLICY_REVOKED",
    "POLICY_EXPIRED", "FORBIDDEN_TENANT", "SSRF_BLOCKED", "DNS_FAILED",
    "TLS_FAILED", "NETWORK_ERROR", "HTTP_PROTOCOL_ERROR", "METHOD_NOT_ALLOWED",
    "REDIRECT_BLOCKED", "REDIRECT_LIMIT", "LIMIT_EXCEEDED", "TIMEOUT", "CANCELLED",
    "HOST_BUSY", "ROBOTS_DISALLOWED", "ROBOTS_UNKNOWN", "ACCESS_BLOCKED",
    "HTTP_ERROR", "CONTENT_TYPE_INVALID", "CONTENT_ENCODING_INVALID",
    "EVIDENCE_INSUFFICIENT", "EVIDENCE_INTEGRITY", "INPUT_INVALID",
}


class CollectionError(ValueError):
    def __init__(self, code: str):
        if code not in CODES:
            raise ValueError("Unknown collection error code")
        self.code = code
        self.trace: list[dict] = []
        super().__init__(code)

    def document(self) -> dict:
        return {"schema_version": "1.0", "code": self.code,
                "safe_message": self.code, "retryable": False}
