"""Orion core extension package.

This package holds optional, admin-gated Orion extensions such as the
self-writing module. It is intentionally lightweight and only imported on
demand so the default startup path stays fast.
"""

__all__ = ["core"]