"""Unofficial TeuxDeux REST client (httpx + pydantic)."""

from .client import BASE_URL, TeuxDeuxClient, TeuxDeuxError
from .models import SOMEDAY_YEAR, Todo, User

__version__ = "0.1.0"
__all__ = [
    "TeuxDeuxClient",
    "TeuxDeuxError",
    "BASE_URL",
    "Todo",
    "User",
    "SOMEDAY_YEAR",
]
