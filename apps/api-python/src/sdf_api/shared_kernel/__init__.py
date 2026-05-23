"""Shared kernel — cross-BC value objects and ports.

Domain-grade per ADR-0023 (same forbidden imports as ``contexts/*/domain``):
no IO, no validation libraries, no system reads. The only sanctioned content is
cross-cutting value objects (identity types, :class:`~sdf_api.shared_kernel.timestamp.Timestamp`)
and cross-cutting Port Protocols under :mod:`sdf_api.shared_kernel.ports`.
"""
