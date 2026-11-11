"""Role and tenant gates: every domain write requires a scoped actor."""

from .errors import DomainError

_PERMISSIONS = {
    "submit": {"OWNER", "OPERATOR", "SERVICE"},
    "review": {"OWNER", "REVIEWER"},
    "share": {"OWNER"},
    "revoke_share": {"OWNER"},
    "handoff": {"OWNER", "SERVICE"},
    "read_evidence": {"OWNER", "REVIEWER", "OPERATOR", "WORKER"},
}


def require_access(actor: dict, resource_tenant: str, action: str) -> None:
    if actor.get("tenant_id") != resource_tenant:
        raise DomainError("FORBIDDEN_TENANT", "Cross-tenant access denied")
    if actor.get("role") not in _PERMISSIONS.get(action, set()):
        raise DomainError("FORBIDDEN_ROLE", "Actor is not permitted to perform action")
