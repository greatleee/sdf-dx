"""Cross-cutting Port Protocols shared by every bounded context (ADR-0022).

One Protocol per file. These declare *what the shell must provide* to the
domain/use-case layer (e.g. the wall clock); concrete bindings live in adapters
and are wired in ``composition.py``.
"""
