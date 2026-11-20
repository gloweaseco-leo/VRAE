"""Small versioned service contract. Existing VF-B business messages are retained."""

VERSION = "vrae.diagnosis-api.v1"
ERRORS = {
    "ACCESS_DENIED": (403, False),
    "CONFLICT": (409, False),
    "RATE_LIMITED": (429, True),
    "UNAVAILABLE": (503, True),
    "NOT_FOUND": (404, False),
    "INVALID_INPUT": (400, False),
}


def error(code):
    status, retry = ERRORS[code]
    return {
        "api_version": VERSION,
        "error": {"code": code, "http_status": status, "retryable": retry},
    }


def openapi():
    return {
        "openapi": "3.1.0",
        "info": {"title": "VRAE Diagnosis API", "version": "1.0.0"},
        "servers": [{"url": "https://{host}", "variables": {"host": {"default": "vrae-api:8769"}}}],
        "security": [{"serviceBearer": []}],
        "components": {
            "securitySchemes": {"serviceBearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {"ApiError": {"type": "object", "required": ["api_version", "error"]}},
        },
        "paths": {
            "/v1/diagnoses": {
                "post": {"summary": "URL and one combined authorization -> original PG queue",
                    "responses": {"202": {"description": "Admitted"},
                        "403": {"description": "Authorization denied"}}}
            },
            "/v1/audits/{audit_ref}/diagnosis": {
                "get": {"summary": "Same-subject automated diagnosis, citations and suggestions",
                    "responses": {"200": {"description": "Diagnosis or explicit unavailable"},
                        "202": {"description": "Capture or model pending"},
                        "403": {"description": "Current subject/source denied"}}}
            },
            "/health/live": {
                "get": {
                    "summary": "Process liveness; no task data",
                    "responses": {"200": {"description": "LIVE"}},
                }
            },
            "/health/ready": {
                "get": {
                    "summary": "Current service binding and PG readiness",
                    "responses": {
                        "200": {"description": "READY"},
                        "503": {"description": "UNAVAILABLE"},
                    },
                }
            },
            "/v1/invitation-session": {
                "post": {
                    "summary": "Consume one-use invitation; return Secure cookie/CSRF",
                    "responses": {
                        "200": {"description": "Session created"},
                        "403": {"description": "Denied"},
                    },
                }
            },
            "/v1/source-plans/{target_id}": {
                "get": {
                    "summary": "Current invitation-scoped source policy for signing; never permission issuance",
                    "parameters": [
                        {
                            "name": "target_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Current source context"},
                        "403": {"description": "Denied"},
                    },
                }
            },
            "/v1/audit-requests": {
                "post": {
                    "summary": "Frozen VFSubmit -> PG COMMIT -> VFAccepted",
                    "responses": {
                        str(s): {"description": d}
                        for s, d in [
                            (202, "Admitted"),
                            (403, "Denied"),
                            (409, "Idempotency conflict"),
                            (429, "Capacity"),
                            (503, "Storage unavailable"),
                        ]
                    },
                }
            },
            "/v1/audits/{audit_ref}": {
                "get": {
                    "summary": "Current subject task status",
                    "parameters": [
                        {
                            "name": "audit_ref",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "VFStatus"},
                        "403": {"description": "Denied"},
                    },
                }
            },
            "/v1/audits/{audit_ref}/report": {
                "get": {
                    "summary": "Qualified report through configured existing C2 authority",
                    "parameters": [
                        {
                            "name": "audit_ref",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        str(s): {"description": d}
                        for s, d in [
                            (200, "Current permitted report"),
                            (403, "Unapproved or denied"),
                            (409, "Version changed"),
                            (503, "Authority unavailable"),
                        ]
                    },
                }
            },
            "/v1/audits/{audit_ref}/return-tokens": {
                "post": {
                    "summary": "Mint task/subject-bound one-use recovery token; never report grant",
                    "parameters": [
                        {
                            "name": "audit_ref",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "201": {"description": "Private token"},
                        "403": {"description": "Denied"},
                    },
                }
            },
            "/v1/return-sessions": {
                "post": {
                    "summary": "Exchange unused return token for current cookie/CSRF",
                    "responses": {
                        "200": {"description": "Session restored"},
                        "403": {"description": "Denied/expired/replayed"},
                    },
                }
            },
            "/v1/openapi.json": {
                "get": {
                    "summary": "This versioned contract",
                    "responses": {"200": {"description": "OpenAPI"}},
                }
            },
            "/v1/errors": {
                "get": {
                    "summary": "Safe error catalog; no caller/target data",
                    "responses": {"200": {"description": "Error codes"}},
                }
            },
        },
    }
