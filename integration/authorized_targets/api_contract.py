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


def deterministic_schema():
    observation = {"type": "object", "required": ["result", "statement", "evidence_ids"],
        "properties": {
            "result": {"enum": ["PASS", "FAIL_WITH_EVIDENCE", "UNKNOWN", "NOT_APPLICABLE", "ACCESS_BLOCKED"]},
            "statement": {"type": "string"}, "evidence_ids": {"type": "array"}}}
    row = {"type": "object", "required": ["observation", "reason"], "properties": {
        "observation": observation, "reason": {"type": ["string", "null"]},
        "citations": {"type": "array", "items": {"type": "object"}}}}
    rule = {"type": "object", "required": ["rule_id", "buyer_task", "observations"], "properties": {
        "rule_id": {"type": "string"}, "buyer_task": {"type": "string"},
        "observations": {"type": "array", "items": row}}}
    task = {"type": "object", "required": ["task", "rules"], "properties": {
        "task": {"enum": ["DISCOVER", "UNDERSTAND", "TRUST", "INQUIRE", "SEARCH_TECHNICAL"]},
        "rules": {"type": "array", "items": rule}}}
    return {"type": ["object", "null"],
        "description": "Committed rule rows remain available in AI_PENDING and AI_UNAVAILABLE. Original industrial fields retained. Not AI claims or dimension scores.",
        "properties": {"native_execution_ref": {"type": "string"},
            "rule_evaluator_version": {"type": "string"},
            "buyer_tasks": {"type": "array", "minItems": 5, "maxItems": 5, "items": task}}}


def openapi():
    return {
        "openapi": "3.1.0",
        "info": {"title": "VRAE Diagnosis API", "version": "1.0.0"},
        "servers": [{"url": "https://{host}", "variables": {"host": {"default": "vrae-api:8769"}}}],
        "security": [{"serviceBearer": []}],
        "components": {
            "securitySchemes": {"serviceBearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "ApiError": {"type": "object", "required": ["api_version", "error"]},
                "AutomaticDiagnosis": {
                    "type": "object", "properties": {
                        "deterministic_diagnosis": deterministic_schema(),
                        "customer_presentation": {"type": "object", "required": [
                            "contract", "is_report", "formal_human_review", "rules_available", "tasks"],
                            "properties": {"contract": {"const": "vrae.diagnosis-presentation.v1"},
                                "is_report": {"const": False}, "formal_human_review": {"const": False},
                                "rules_available": {"type": "boolean"}, "tasks": {"type": "array"},
                                "procurement_review": {"type": "object", "required": [
                                    "contract", "review_ref", "configuration_ref", "products"],
                                    "description": "Versioned source-bound procurement review for new 1.0.6 tasks; no rule PASS, verified SKU or engineering approval."}},
                            "description": "Bilingual copy with pointers to original observations; not new facts, scores or human approval. Available independently of AI claims."},
                        "page_scope": {"type": ["object", "null"], "properties": {
                            name: {"type": "array", "items": {"type": "object"}} for name in (
                                "visited_pages", "failed_attempt_records", "unvisited_candidates", "unknown_coverage")},
                            "description": "Display actual visited pages as evidence; collapse inventory-only candidates separately. A record without HTTP status does not prove dispatch or a website failure."},
                        "analysis_outcome": {"enum": ["PENDING", "NOT_RUN", "COMPLETED",
                            "INSUFFICIENT_EVIDENCE", "NOT_DISPATCHED", "PROVIDER_FAILED",
                            "VALIDATION_REJECTED", "UNAVAILABLE"]},
                        "capture_summary": {"type": ["object", "null"], "properties": {
                            **{k: {"type": "integer", "minimum": 0} for k in (
                                "candidate_urls", "page_records", "fetched_pages",
                                "unvisited_candidates", "http_requests_including_robots",
                                "timeout_page_records")},
                            "inventory_truncated": {"type": "boolean"},
                            "unvisited_is_defect": {"const": False}}},
                        "model": {"type": ["object", "null"], "properties": {
                            "reason": {"type": ["string", "null"]},
                            "provider_attempts": {"type": ["integer", "null"], "minimum": 0},
                            "real_model_calls": {"type": ["integer", "null"], "minimum": 0},
                            "cost_status": {"type": ["string", "null"]},
                            "failure_stage": {"type": ["string", "null"]}}},
                    },
                    "description": "Additive result fields. Candidates include unvisited URLs; page records can precede dispatch. Legacy unknown usage remains unknown. UNKNOWN is not a site defect.",
                },
            },
        },
        "paths": {
            "/v1/diagnosis-sessions": {
                "post": {"summary": "Trusted mTLS BFF creates an isolated diagnosis session; no invitation",
                    "requestBody": {"required": True, "description": "Empty JSON object; no subject/tenant/invitation input"},
                    "responses": {"200": {"description": "Secure HttpOnly cookie and X-CSRF-Token"},
                        "403": {"description": "Service identity/delegation denied"},
                        "429": {"description": "Bounded session capacity"}}}
            },
            "/v1/diagnoses": {
                "post": {"summary": "URL and one combined authorization -> original PG queue",
                    "responses": {"202": {"description": "Admitted"},
                        "403": {"description": "Authorization denied"}}}
            },
            "/v1/audits/{audit_ref}/diagnosis": {
                "get": {"summary": "Same-subject automated diagnosis, citations and suggestions",
                    "description": "Render deterministic_diagnosis.buyer_tasks independently of AI state/claims/diagnosis_complete. Render analysis_outcome, capture_summary, and model.failure_stage separately; unvisited is not a defect. Existing outer state and diagnosis_complete gate are retained.",
                    "x-vrae-response-schema": {"$ref": "#/components/schemas/AutomaticDiagnosis"},
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
