"""Tests for the Aquarite coordinator.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
Run with: pytest tests/test_coordinator.py (requires HA test environment)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_POOL_ID

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

    mock_api = AsyncMock()
    mock_api.subscribe_pool = AsyncMock(return_value=MagicMock())
    mock_api.set_value = AsyncMock()
    mock_api.set_values = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {}

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID
    )
    coord.data = mock_pool_data
    return coord


async def test_subscribe(coordinator: AquariteDataUpdateCoordinator) -> None:
    """Test subscribe calls the API."""
    await coordinator.subscribe()
    coordinator.api.subscribe_pool.assert_called_once()


async def test_refresh_subscription(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test refresh_subscription unsubscribes and resubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.refresh_subscription()

    mock_to_thread.assert_called_once_with(mock_watch.unsubscribe)
    coordinator.api.subscribe_pool.assert_called_once()


async def test_async_shutdown(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown cancels tasks and unsubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    async def _run_forever() -> None:
        await asyncio.sleep(3600)

    health_task = asyncio.get_running_loop().create_task(_run_forever())
    token_task = asyncio.get_running_loop().create_task(_run_forever())
    coordinator._health_task = health_task
    coordinator._token_task = token_task

    with patch("asyncio.to_thread", new_callable=AsyncMock):
        await coordinator.async_shutdown()

    assert health_task.cancelled()
    assert token_task.cancelled()


async def test_async_set_values_delegates_to_api(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """async_set_values is a thin pass-through to AquariteClient.set_values.

    The library validates the branch, sends the command, and mirrors
    accepted changes into the cached pool document itself (since 0.7.0) —
    the coordinator no longer needs to duplicate that logic.
    """
    updates = {"light.mode": 0, "light.status": 1}

    await coordinator.async_set_values(updates)

    coordinator.api.set_values.assert_awaited_once_with(MOCK_POOL_ID, updates)
    # Written values are applied optimistically pending Firestore confirmation
    assert coordinator.get_value("light.mode") == 0
    assert coordinator.get_value("light.status") == 1
    # Cancel the optimistic TTL timers so no timer outlives the test
    await coordinator.async_shutdown()


async def test_stale_push_does_not_revert_optimistic_write(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """A Firestore push carrying the pre-write value must not flip the UI back.

    The Hayward cloud takes seconds to echo a write back through
    Firestore; snapshots emitted in between still carry the OLD value.
    Inside the TTL window the optimistic value must win.
    """
    from copy import deepcopy

    stale_snapshot = deepcopy(coordinator.data)  # light.status == 0

    await coordinator.async_set_values({"light.status": 1})
    assert coordinator.get_value("light.status") == 1

    coordinator._apply_remote_data(stale_snapshot)

    assert coordinator.get_value("light.status") == 1
    await coordinator.async_shutdown()


async def test_confirming_push_clears_optimistic_entry(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """A push that agrees with the optimistic value clears the pending entry."""
    from copy import deepcopy

    await coordinator.async_set_values({"light.status": 1})
    assert "light.status" in coordinator._pending_optimistic

    confirming = deepcopy(coordinator.data)
    confirming["light"]["status"] = 1
    coordinator._apply_remote_data(confirming)

    assert "light.status" not in coordinator._pending_optimistic
    assert not coordinator._optimistic_handles
    assert coordinator.get_value("light.status") == 1
    await coordinator.async_shutdown()


async def test_confirming_push_matches_tolerantly(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Firestore may echo the value as a string/bool variant; still confirms."""
    from copy import deepcopy

    await coordinator.async_set_values({"light.status": 1})

    confirming = deepcopy(coordinator.data)
    confirming["light"]["status"] = "1"  # string echo of the int we wrote
    coordinator._apply_remote_data(confirming)

    assert "light.status" not in coordinator._pending_optimistic
    await coordinator.async_shutdown()


async def test_expired_optimistic_write_triggers_refresh(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """TTL firing without a confirming push drops the entry and refreshes."""
    coordinator.api.fetch_pool_data = AsyncMock(return_value=coordinator.data)

    await coordinator.async_set_values({"light.status": 1})
    assert "light.status" in coordinator._pending_optimistic

    # In reality _expire_optimistic is invoked BY the TTL timer (already
    # fired); cancel the armed timer before invoking it manually.
    coordinator._optimistic_handles["light.status"].cancel()

    with patch.object(
        coordinator, "async_refresh", new_callable=AsyncMock
    ) as mock_refresh:
        coordinator._expire_optimistic("light.status")
        await coordinator.hass.async_block_till_done()

    assert "light.status" not in coordinator._pending_optimistic
    mock_refresh.assert_awaited_once()
    await coordinator.async_shutdown()


async def test_shutdown_cancels_optimistic_timers(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Shutdown must cancel TTL timers and clear pending optimistic state."""
    await coordinator.async_set_values({"light.status": 1})
    assert coordinator._optimistic_handles

    await coordinator.async_shutdown()

    assert not coordinator._optimistic_handles
    assert not coordinator._pending_optimistic


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
