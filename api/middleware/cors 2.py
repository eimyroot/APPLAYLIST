"""Deprecated duplicate retained only because remote deletion was blocked.

The canonical implementation lives in :mod:`api.middleware.cors`.
"""

from api.middleware.cors import install_cors

__all__ = ["install_cors"]
