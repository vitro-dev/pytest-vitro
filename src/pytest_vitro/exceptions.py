"""pytest-vitro exception."""

from __future__ import annotations

from vitro.exceptions import VitroError


class VitroPluginError(VitroError):
    """Raise this on vitro plugin related error."""
