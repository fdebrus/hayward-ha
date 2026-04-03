"""Exceptions for the aioaquarite library."""


class AquariteError(Exception):
    """Base exception for aioaquarite."""


class AuthenticationError(AquariteError):
    """Raised when authentication fails."""


class ConnectionError(AquariteError):
    """Raised when a connection error occurs."""


class CommandError(AquariteError):
    """Raised when a pool command fails."""
