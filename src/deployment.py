"""Backward-compatibility shim for legacy src.deployment -> src.api.deployment."""
from src.api.deployment import *  # noqa: F401, F403
from src.api.deployment import app  # noqa: F401
