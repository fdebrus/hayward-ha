"""Tests for the Aquarite coordinator.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
Run with: pytest tests/test_coordinator.py (requires HA test environment)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_POOL_ID

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from aioaquarite import AquariteError  # noqa: E402
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402

from custom_components.aquarite.coordinator import (  # noqa: E402
    AquariteDataUpdateCoordinator,
)


@pytest.fixture
def coordinator(
    hass,
    mock_pool_data,
) -> AquariteDataUpdateCoordinator:
    """Create a coordinator with mock dependencies."""
    mock_auth = AsyncMock()

    mock_api = AsyncMock()
    mock_api.subscribe_pool_resilient = AsyncMock(return_value=MagicMock())
    mock_api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    mock_api.set_value = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {}

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID
    )
    coord.data = mock_pool_data
    return coord


async def test_subscribe(coordinator: AquariteDataUpdateCoordinator) -> None:
    """Test subscribe uses the library's resilient subscription."""
    await coordinator.subscribe()
    coordinator.api.subscribe_pool_resilient.assert_called_once()
    assert coordinator.subscription is not None


async def test_async_update_data(
    coordinator: AquariteDataUpdateCoordinator,
    mock_pool_data,
) -> None:
    """Test the initial/manual refresh fetches pool data."""
    result = await coordinator._async_update_data()
    assert result == mock_pool_data
    coordinator.api.fetch_pool_data.assert_called_once_with(MOCK_POOL_ID)


async def test_async_update_data_raises_update_failed(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test a library error is translated into UpdateFailed."""
    coordinator.api.fetch_pool_data = AsyncMock(side_effect=AquariteError("boom"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_shutdown(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown closes the resilient subscription."""
    mock_subscription = AsyncMock()
    coordinator.subscription = mock_subscription

    await coordinator.async_shutdown()

    mock_subscription.aclose.assert_called_once()
    assert coordinator.subscription is None


async def test_set_pool_time_to_now(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test set_pool_time_to_now writes a local timestamp."""
    with patch("custom_components.aquarite.coordinator.dt_util") as mock_dt:
        tz = timezone(timedelta(hours=2))
        fake_now = datetime(2026, 4, 12, 14, 30, 0, tzinfo=tz)
        mock_dt.now.return_value = fake_now

        await coordinator.set_pool_time_to_now()

    coordinator.api.set_value.assert_called_once()
    call_args = coordinator.api.set_value.call_args
    assert call_args[0][0] == MOCK_POOL_ID
    assert call_args[0][1] == "main.localTime"

    utc_timestamp = int(fake_now.timestamp())
    expected = utc_timestamp + 7200
    assert call_args[0][2] == expected
