"""Tests for the pool light scheduling entities (mode, frequency, from/to).

These cover the coordinator's branch-safe multi-value write (the Hayward
cloud command carries the whole branch rebuilt from the client cache, so
multi-field writes must be patched into the cache and sent as ONE command)
and the light mode / schedule entities built on top of it.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME, get_value

pytest.importorskip("homeassistant")

from homeassistant.exceptions import HomeAssistantError  # noqa: E402

from aioaquarite import AquariteClient  # noqa: E402
from aioaquarite.exceptions import CommandError  # noqa: E402

from custom_components.aquarite import select as select_module  # noqa: E402
from custom_components.aquarite import time as time_module  # noqa: E402
from custom_components.aquarite.coordinator import (  # noqa: E402
    AquariteDataUpdateCoordinator,
)
from custom_components.aquarite.select import (  # noqa: E402
    AquariteLightModeSelectEntity,
    AquariteValueMapSelectEntity,
)
from custom_components.aquarite.time import AquariteTimeEntity  # noqa: E402

LIGHT_NODE = {"status": 1, "mode": 1, "from": 79200, "to": 3600, "freq": 86400}


def _pool_data_with_light(mock_pool_data: dict[str, Any]) -> dict[str, Any]:
    """Return pool data whose light node has scheduling fields."""
    data = deepcopy(mock_pool_data)
    data["light"] = deepcopy(LIGHT_NODE)
    data["wifi"] = "gateway-1"
    return data


def _fake_coordinator(data: dict[str, Any]) -> MagicMock:
    """Return a coordinator double backed by a real pool-data dict."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.pool_id = MOCK_POOL_ID
    coordinator.get_value = lambda path, default=None: get_value(
        data, path, default
    )
    coordinator.api.set_value = AsyncMock()
    coordinator.async_set_values = AsyncMock()
    return coordinator


def _fake_entry(coordinator: MagicMock) -> MagicMock:
    """Return a config-entry double exposing the coordinator."""
    entry = MagicMock()
    entry.title = MOCK_POOL_NAME
    entry.runtime_data.coordinator = coordinator
    return entry


# ── Coordinator multi-value write ─────────────────────────────────


@pytest.fixture
def real_client_coordinator(
    hass, mock_pool_data
) -> tuple[AquariteDataUpdateCoordinator, AquariteClient, dict[str, Any]]:
    """Coordinator wired to a REAL AquariteClient (HTTP layer mocked)."""
    mock_auth = AsyncMock()
    mock_auth.is_token_expiring = MagicMock(return_value=False)
    mock_auth.get_client = AsyncMock(return_value=(MagicMock(), False))

    client = AquariteClient(mock_auth)
    pool_data = _pool_data_with_light(mock_pool_data)
    # Runtime wiring: coordinator.data and the client cache are the SAME dict
    # (fetch_pool_data / on_snapshot hand out one object to both).
    client.set_pool_data(MOCK_POOL_ID, pool_data)

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {}

    coordinator = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, client, MOCK_POOL_ID
    )
    coordinator.data = pool_data
    return coordinator, client, pool_data


async def test_set_values_sends_both_fields_in_one_command(
    real_client_coordinator,
) -> None:
    """Both patched fields must ride in a single cloud command payload."""
    coordinator, client, _ = real_client_coordinator

    with patch.object(client, "send_command", new=AsyncMock()) as mock_send:
        await coordinator.async_set_values({"light.mode": 0, "light.status": 0})

    mock_send.assert_awaited_once()
    payload = mock_send.await_args.args[0]
    changes = json.loads(payload["changes"])
    assert changes["light"]["mode"] == 0
    assert changes["light"]["status"] == 0
    # Untouched fields of the branch ride along unchanged
    assert changes["light"]["from"] == 79200
    assert changes["light"]["freq"] == 86400
    # The shared cache now reflects the write
    assert coordinator.get_value("light.mode") == 0
    assert coordinator.get_value("light.status") == 0


@pytest.mark.parametrize(
    "failure", [CommandError("boom"), asyncio.CancelledError()]
)
async def test_set_values_restores_cache_on_failure(
    real_client_coordinator, failure: BaseException
) -> None:
    """A failed or cancelled command must not leave phantom cache values."""
    coordinator, client, _ = real_client_coordinator

    failing_send = AsyncMock(side_effect=failure)
    with patch.object(client, "send_command", new=failing_send):
        with pytest.raises(type(failure)):
            await coordinator.async_set_values(
                {"light.mode": 0, "light.status": 0}
            )

    assert coordinator.get_value("light.mode") == 1
    assert coordinator.get_value("light.status") == 1


async def test_set_values_rejects_paths_across_branches(
    real_client_coordinator,
) -> None:
    """One command carries one branch; mixed-branch updates are a bug."""
    coordinator, _, _ = real_client_coordinator

    with pytest.raises(ValueError):
        await coordinator.async_set_values(
            {"light.mode": 0, "filtration.mode": 1}
        )


# ── Light mode select ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "status", "expected"),
    [(1, 0, "auto"), (1, 1, "auto"), (0, 1, "on"), (0, 0, "off")],
)
def test_light_mode_current_option(
    mock_pool_data, mode: int, status: int, expected: str
) -> None:
    """Mode wins over status; otherwise status picks on/off."""
    data = _pool_data_with_light(mock_pool_data)
    data["light"]["mode"] = mode
    data["light"]["status"] = status
    entity = AquariteLightModeSelectEntity(
        _fake_coordinator(data), MOCK_POOL_ID, MOCK_POOL_NAME
    )
    assert entity.current_option == expected


def test_light_mode_current_option_without_data(mock_pool_data) -> None:
    """Missing light fields must yield an unknown option, not a crash."""
    coordinator = _fake_coordinator(deepcopy(mock_pool_data))
    entity = AquariteLightModeSelectEntity(
        coordinator, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    assert entity.current_option is None


@pytest.mark.parametrize(
    ("option", "expected_updates"),
    [
        ("off", {"light.mode": 0, "light.status": 0}),
        ("on", {"light.mode": 0, "light.status": 1}),
        ("auto", {"light.mode": 1}),
    ],
)
async def test_light_mode_select_writes(
    mock_pool_data, option: str, expected_updates: dict[str, int]
) -> None:
    """Each option maps to the exact field set poolwatch proved out."""
    coordinator = _fake_coordinator(_pool_data_with_light(mock_pool_data))
    entity = AquariteLightModeSelectEntity(
        coordinator, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    await entity.async_select_option(option)
    coordinator.async_set_values.assert_awaited_once_with(expected_updates)


async def test_light_mode_select_wraps_errors(mock_pool_data) -> None:
    """API failures surface as HomeAssistantError."""
    coordinator = _fake_coordinator(_pool_data_with_light(mock_pool_data))
    coordinator.async_set_values.side_effect = CommandError("boom")
    entity = AquariteLightModeSelectEntity(
        coordinator, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("auto")


# ── Light schedule frequency select ───────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(86400, "daily"), (604800, "weekly"), (12345, None), (None, None)],
)
def test_frequency_select_maps_values(
    mock_pool_data, raw: int | None, expected: str | None
) -> None:
    """Frequency options map by raw value, unknown values stay unknown."""
    data = _pool_data_with_light(mock_pool_data)
    if raw is None:
        del data["light"]["freq"]
    else:
        data["light"]["freq"] = raw
    entity = AquariteValueMapSelectEntity(
        _fake_coordinator(data),
        MOCK_POOL_ID,
        MOCK_POOL_NAME,
        "Light Schedule Frequency",
        "light_schedule_frequency",
        "light.freq",
        select_module.LIGHT_FREQ_VALUES,
    )
    assert entity.current_option == expected


async def test_frequency_select_writes_raw_value(mock_pool_data) -> None:
    """Selecting an option writes its raw value through the branch-safe path."""
    coordinator = _fake_coordinator(_pool_data_with_light(mock_pool_data))
    entity = AquariteValueMapSelectEntity(
        coordinator,
        MOCK_POOL_ID,
        MOCK_POOL_NAME,
        "Light Schedule Frequency",
        "light_schedule_frequency",
        "light.freq",
        select_module.LIGHT_FREQ_VALUES,
    )
    await entity.async_select_option("weekly")
    coordinator.async_set_values.assert_awaited_once_with({"light.freq": 604800})


# ── Gated entity creation ─────────────────────────────────────────


async def _setup_unique_ids(hass, module, data: dict[str, Any]) -> set[str]:
    """Run a platform's setup against pool data, return the unique ids."""
    added: list = []
    await module.async_setup_entry(
        hass, _fake_entry(_fake_coordinator(data)), added.extend
    )
    return {entity.unique_id for entity in added}


async def test_time_setup_gates_light_entities(hass, mock_pool_data) -> None:
    """Light schedule times appear exactly when the pool exposes them."""
    baseline = await _setup_unique_ids(
        hass, time_module, deepcopy(mock_pool_data)
    )
    with_light = await _setup_unique_ids(
        hass, time_module, _pool_data_with_light(mock_pool_data)
    )
    assert not any("Light Schedule" in uid for uid in baseline)
    assert with_light == baseline | {
        f"{MOCK_POOL_ID}-Light Schedule From",
        f"{MOCK_POOL_ID}-Light Schedule To",
    }


async def test_select_setup_gates_light_entities(hass, mock_pool_data) -> None:
    """Light mode/frequency selects appear exactly when the pool exposes them."""
    baseline = await _setup_unique_ids(
        hass, select_module, deepcopy(mock_pool_data)
    )
    with_light = await _setup_unique_ids(
        hass, select_module, _pool_data_with_light(mock_pool_data)
    )
    assert not any("Light" in uid for uid in baseline)
    assert with_light == baseline | {
        f"{MOCK_POOL_ID}-Light Mode",
        f"{MOCK_POOL_ID}-Light Schedule Frequency",
    }


# ── Light schedule time entities (real class, real conversions) ──


def test_light_schedule_time_reads_seconds(mock_pool_data) -> None:
    """light.from seconds-since-midnight render as a time object."""
    coordinator = _fake_coordinator(_pool_data_with_light(mock_pool_data))
    entity = AquariteTimeEntity(
        coordinator,
        MOCK_POOL_ID,
        MOCK_POOL_NAME,
        "Light Schedule From",
        "light_schedule_from",
        "light.from",
    )
    assert entity.native_value == datetime.time(22, 0)


async def test_light_schedule_time_writes_seconds(mock_pool_data) -> None:
    """Setting a time writes seconds-since-midnight via the branch-safe path.

    Time entities MUST write through async_set_values: from/to live in one
    branch, and setting them back-to-back through plain set_value would
    revert the first write (the payload is rebuilt from the stale cache).
    """
    coordinator = _fake_coordinator(_pool_data_with_light(mock_pool_data))
    entity = AquariteTimeEntity(
        coordinator,
        MOCK_POOL_ID,
        MOCK_POOL_NAME,
        "Light Schedule To",
        "light_schedule_to",
        "light.to",
    )
    await entity.async_set_value(datetime.time(2, 30))
    coordinator.async_set_values.assert_awaited_once_with({"light.to": 9000})
