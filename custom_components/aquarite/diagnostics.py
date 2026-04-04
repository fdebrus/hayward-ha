"""Diagnostics support for Aquarite."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import AquariteConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "coordinator_data": coordinator.data,
    }
