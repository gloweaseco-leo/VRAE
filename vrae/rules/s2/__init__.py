"""Derived S2 projection; the unchanged original executor retains authority."""
from .contract import (
    CONTRACT_VERSION, PROJECTION_VERSION, STATIC_PROJECTION_VERSION, UX_RULES, ReadOnlyAdapter, adapter_request,
    resolve_input, verify_adapter_request, evaluate_s2, verify_s2_projection,
)

__all__ = ['CONTRACT_VERSION', 'UX_RULES', 'ReadOnlyAdapter', 'adapter_request',
           'resolve_input', 'verify_adapter_request', 'PROJECTION_VERSION',
           'evaluate_s2', 'verify_s2_projection', 'STATIC_PROJECTION_VERSION']
