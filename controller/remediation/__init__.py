"""Shared remediation policy, store, executors and verification."""

from controller.remediation.policy import RemediationPolicy, resolve_mode, summarize
from controller.remediation.store import ProposalStore

_POLICY = None


def get_policy() -> RemediationPolicy:
    """Process-wide policy using the default store, topology registry and mode."""
    global _POLICY
    if _POLICY is None:
        _POLICY = RemediationPolicy()
    return _POLICY


__all__ = ["RemediationPolicy", "ProposalStore", "get_policy", "resolve_mode", "summarize"]
