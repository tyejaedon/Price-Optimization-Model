"""Canonical ASGI application entrypoint for uvicorn (AGENTS.md & Render deployment).

Supports both local development/smoke tests and hosted deployment on Render (M13.4).
Exposes the FastAPI instance as ``app``.
"""

from __future__ import annotations

from src.api.serve import app

__all__ = ["app"]
