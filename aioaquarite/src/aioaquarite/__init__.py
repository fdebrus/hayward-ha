"""Async Python client for the Hayward Aquarite pool API."""

from .auth import AquariteAuth
from .client import AquariteClient
from .exceptions import AquariteError, AuthenticationError, CommandError, ConnectionError

__all__ = [
    "AquariteAuth",
    "AquariteClient",
    "AquariteError",
    "AuthenticationError",
    "CommandError",
    "ConnectionError",
]
