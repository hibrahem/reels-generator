"""Errors raised while configuring or invoking a clip-selection provider."""

from __future__ import annotations


class SelectionUnavailable(RuntimeError):
    """The selection provider is not usable (e.g. its API key env var is not set)."""
