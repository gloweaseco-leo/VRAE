"""S2 interfaces share the original executor; no second rule or report engine."""
from .contract import (
    CONTRACT_VERSION, UX_RULES, ReadOnlyAdapter, adapter_request,
    resolve_input, verify_adapter_request,
)

__all__ = ['CONTRACT_VERSION', 'UX_RULES', 'ReadOnlyAdapter', 'adapter_request',
           'resolve_input', 'verify_adapter_request']
