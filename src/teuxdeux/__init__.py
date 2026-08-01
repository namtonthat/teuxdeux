"""Unofficial TeuxDeux REST client (httpx + dataclasses)."""

from .client import BASE_URL, TeuxDeuxClient, TeuxDeuxError
from .models import Todo, User

__version__ = "0.1.0"
__all__ = [
    "BASE_URL",
    "TeuxDeuxClient",
    "TeuxDeuxError",
    "Todo",
    "User",
]
