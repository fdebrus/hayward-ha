"""Tests for the Aquarite coordinator.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
Run with: pytest tests/test_coordinator.py (requires HA test environment)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from custom_components.aquarite.coordinator import AquariteDataUpdateCoordinator  # noqa: E402


@pytest.fixture
def coordinator(
    hass,
    mock_pool_data,
) -> AquariteDataUpdateCoordinator:
    """Create a coordinator with mock dependencies."""
    mock_auth = AsyncMock()
    mock_auth.is_token_expiring = MagicMock(return_value=False)
    mock_auth.calculate_sleep_duration = MagicMock(return_value=3600)
    mock_auth.get_client = AsyncMock(return_value=(MagicMock(), False))

    mock_subscription = MagicMock()
    mock_subscription.aclose = AsyncMock()

    mock_api = AsyncMock()
    mock_api.subscribe_pool_resilient = AsyncMock(return_value=mock_subscription)
    mock_api.set_value = AsyncMock()
    mock_api.set_values = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {"health_check_interval": 300}

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    coord.data = mock_pool_data
    return coord


async def test_subscribe(coordinator: AquariteDataUpdateCoordinator) -> None:
    """subscribe() opens a resilient subscription with the configured interval."""
    await coordinator.subscribe()
    coordinator.api.subscribe_pool_resilient.assert_awaited_once()
    call = coordinator.api.subscribe_pool_resilient.await_args
    assert call.args[0] == MOCK_POOL_ID
    assert call.args[1] == coordinator._async_handle_push
    assert call.kwargs["health_check_interval"] == 300
    assert call.kwargs["on_health"] == coordinator._on_health
    assert coordinator.subscription is not None


async def test_push_callback_publishes_library_data(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """The data callback is a plain publish: the library already
    reconciled the snapshot (or write echo) before delivering it."""
    delivered = {"light": {"status": 1}}

    coordinator._async_handle_push(delivered)

    assert coordinator.data is delivered
    assert coordinator.last_update_success is True


async def test_unhealthy_connection_marks_entities_unavailable(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """on_health(False) flips last_update_success so entities go unavailable."""
    coordinator.last_update_success = True

    coordinator._on_health(False)

    assert coordinator.last_update_success is False


async def test_healthy_connection_triggers_refresh(
    coordinator: AquariteDataUpdateCoordinator, mock_pool_data
) -> None:
    """on_health(True) schedules an authoritative refresh restoring availability."""
    coordinator._on_health(False)
    assert coordinator.last_update_success is False

    coordinator.api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    coordinator._on_health(True)
    await coordinator.hass.async_block_till_done()

    coordinator.api.fetch_pool_data.assert_awaited_once_with(MOCK_POOL_ID)
    assert coordinator.last_update_success is True


async def test_async_shutdown_closes_subscription(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Shutdown closes the resilient subscription."""
    await coordinator.subscribe()
    subscription = coordinator.subscription

    await coordinator.async_shutdown()

    subscription.aclose.assert_awaited_once()
    assert coordinator.subscription is None


async def test_async_set_values_delegates_to_api(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """async_set_values is a thin pass-through to AquariteClient.set_values.

    Since aioaquarite 0.13.0 the library records the written values as
    pending, delivers the updated data to the subscription callback the
    moment the cloud acks the command, suppresses stale pre-write
    snapshots, and heals unconfirmed writes with an authoritative fetch
    after a TTL — the coordinator carries no optimistic layer of its
    own. Those behaviours are covered by the library's reconciliation
    test suite.
    """
    updates = {"light.mode": 0, "light.status": 1}

    await coordinator.async_set_values(updates)

    coordinator.api.set_values.assert_awaited_once_with(MOCK_POOL_ID, updates)


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
