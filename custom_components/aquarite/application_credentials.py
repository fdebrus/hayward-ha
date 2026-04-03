"""Authentication bridge between Home Assistant and the aioaquarite library."""

from aioaquarite import AuthenticationError

# Re-export for backward compatibility with existing HA integration code
UnauthorizedException = AuthenticationError
