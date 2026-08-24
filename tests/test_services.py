"""Tests for the Aquarite integration's registered services.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
Run with: pytest tests/test_services.py (requires HA test environment)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from aioaquarite import CommandError  # noqa: E402
from custom_components.aquarite.const import DOMAIN  # noqa: E402

PATCH_AUTH = "custom_components.aquarite.AquariteAuth"
PATCH_CLIENT = "custom_components.aquarite.AquariteClient"

SAMPLE_SERIES = [[{"field": 885, "seconds": 1777447486}]]


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, mock_pool_data):
    """Set up a real Aquarite config entry with mocked auth/api.

    The auth/API objects are fully mocked so no real Firestore/gRPC
    machinery is touched; the resilient subscription is a mock handle
    whose aclose() the unload path awaits.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=MOCK_USERNAME.lower(),
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        options={},
    )
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.is_token_expiring = MagicMock(return_value=False)
    mock_auth.calculate_sleep_duration = MagicMock(return_value=3600)
    mock_auth.get_client = AsyncMock(return_value=(MagicMock(), False))

    mock_subscription = MagicMock()
    mock_subscription.aclose = AsyncMock()
    mock_user_subscription = MagicMock()
    mock_user_subscription.aclose = AsyncMock()

    mock_api = AsyncMock()
    mock_api.get_pools = AsyncMock(return_value={MOCK_POOL_ID: MOCK_POOL_NAME})
    mock_api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    mock_api.subscribe_pool_resilient = AsyncMock(return_value=mock_subscription)
    mock_api.subscribe_user_pools_resilient = AsyncMock(
        return_value=mock_user_subscription
    )
    mock_api.get_pool_stats = AsyncMock(return_value=SAMPLE_SERIES)

    with (
        patch(PATCH_AUTH, return_value=mock_auth),
        patch(PATCH_CLIENT, return_value=mock_api),
        # A real aiohttp session spawns a pycares resolver thread that can
        # linger past the test; the session is unused with auth mocked.
        patch(
            "custom_components.aquarite.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, mock_api


async def test_get_pool_stats_service_registered(
    hass: HomeAssistant, loaded_entry
) -> None:
    """Service is registered once the entry is loaded."""
    assert hass.services.has_service(DOMAIN, "get_pool_stats")


async def test_get_pool_stats_service_returns_series(
    hass: HomeAssistant, loaded_entry
) -> None:
    """A successful call routes to AquariteClient.get_pool_stats and returns its series."""
    _entry, mock_api = loaded_entry

    response = await hass.services.async_call(
        DOMAIN,
        "get_pool_stats",
        {"pool_id": MOCK_POOL_ID, "type": "ph", "period": 14},
        blocking=True,
        return_response=True,
    )

    mock_api.get_pool_stats.assert_awaited_once_with(MOCK_POOL_ID, "ph", 14)
    assert response == {"series": SAMPLE_SERIES}


async def test_get_pool_stats_service_defaults_period(
    hass: HomeAssistant, loaded_entry
) -> None:
    """Omitting period falls back to the 30-day default."""
    _entry, mock_api = loaded_entry

    await hass.services.async_call(
        DOMAIN,
        "get_pool_stats",
        {"pool_id": MOCK_POOL_ID, "type": "temp"},
        blocking=True,
        return_response=True,
    )

    mock_api.get_pool_stats.assert_awaited_once_with(MOCK_POOL_ID, "temp", 30)


async def test_get_pool_stats_service_unknown_pool_raises(
    hass: HomeAssistant, loaded_entry
) -> None:
    """An unknown pool_id raises a validation error instead of silently no-op-ing."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_pool_stats",
            {"pool_id": "not-a-real-pool", "type": "ph"},
            blocking=True,
            return_response=True,
        )


async def test_get_pool_stats_service_wraps_api_error(
    hass: HomeAssistant, loaded_entry
) -> None:
    """An AquariteError from the library surfaces as a HomeAssistantError."""
    _entry, mock_api = loaded_entry
    mock_api.get_pool_stats.side_effect = CommandError("boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_pool_stats",
            {"pool_id": MOCK_POOL_ID, "type": "ph"},
            blocking=True,
            return_response=True,
        )


async def test_get_pool_stats_service_removed_after_unload(
    hass: HomeAssistant, loaded_entry
) -> None:
    """The last loaded entry unloading removes the service."""
    entry, _mock_api = loaded_entry

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "get_pool_stats")
    assert not hass.services.has_service(DOMAIN, "sync_pool_time")
