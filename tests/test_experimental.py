"""Tests for the experimental options (aioaquarite 0.14 beta).

Each option switches on something the first-party web client has been
observed to do. They are all off by default, and these tests pin both
sides: off changes nothing, on does exactly the documented thing.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

pytest.importorskip("homeassistant")

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)

from aioaquarite import AquariteError  # noqa: E402
from custom_components.aquarite.button import (  # noqa: E402
    AquariteLEDPulseButtonEntity,
)
from custom_components.aquarite.const import (  # noqa: E402
    CONF_EXPERIMENTAL_FRAGMENT_WRITES,
    CONF_EXPERIMENTAL_LED_ENDPOINT,
    CONF_EXPERIMENTAL_REQUEST_UPDATES,
    CONF_HEALTH_CHECK_INTERVAL,
    DOMAIN,
    LED_PULSE_DELAY,
)
from custom_components.aquarite.coordinator import (  # noqa: E402
    AquariteDataUpdateCoordinator,
)

PATCH_AUTH = "custom_components.aquarite.AquariteAuth"
PATCH_CLIENT = "custom_components.aquarite.AquariteClient"
PATCH_SESSION = "custom_components.aquarite.async_get_clientsession"


def _entry(hass: HomeAssistant, options: dict) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=MOCK_USERNAME.lower(),
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


def _mock_api(mock_pool_data) -> AsyncMock:
    api = AsyncMock()
    subscription = MagicMock()
    subscription.aclose = AsyncMock()
    api.get_pools = AsyncMock(return_value={MOCK_POOL_ID: MOCK_POOL_NAME})
    api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    api.subscribe_pool_resilient = AsyncMock(return_value=subscription)
    api.subscribe_user_pools_resilient = AsyncMock(return_value=subscription)
    return api


def _coordinator(hass, mock_pool_data, options) -> AquariteDataUpdateCoordinator:
    api = _mock_api(mock_pool_data)
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {CONF_HEALTH_CHECK_INTERVAL: 300, **options}
    entry.async_create_background_task = (
        lambda hass_, coro, name: hass_.async_create_task(coro)
    )
    coord = AquariteDataUpdateCoordinator(
        hass, entry, AsyncMock(), api, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    coord.data = mock_pool_data
    return coord


# ── options flow ──────────────────────────────────────────────────


async def test_experimental_options_default_to_off(hass: HomeAssistant) -> None:
    entry = _entry(hass, {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    defaults = result["data_schema"]({})

    assert defaults[CONF_EXPERIMENTAL_FRAGMENT_WRITES] is False
    assert defaults[CONF_EXPERIMENTAL_LED_ENDPOINT] is False
    assert defaults[CONF_EXPERIMENTAL_REQUEST_UPDATES] is False


async def test_experimental_options_can_be_enabled(hass: HomeAssistant) -> None:
    entry = _entry(hass, {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HEALTH_CHECK_INTERVAL: 300,
            CONF_EXPERIMENTAL_FRAGMENT_WRITES: True,
            CONF_EXPERIMENTAL_LED_ENDPOINT: True,
            CONF_EXPERIMENTAL_REQUEST_UPDATES: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EXPERIMENTAL_FRAGMENT_WRITES] is True
    assert entry.options[CONF_EXPERIMENTAL_LED_ENDPOINT] is True
    assert entry.options[CONF_EXPERIMENTAL_REQUEST_UPDATES] is True


# ── fragment writes: the client's write mode follows the option ───


@pytest.mark.parametrize(
    ("options", "expected_mode"),
    [
        ({}, "branch"),
        ({CONF_EXPERIMENTAL_FRAGMENT_WRITES: False}, "branch"),
        ({CONF_EXPERIMENTAL_FRAGMENT_WRITES: True}, "fragment"),
    ],
)
async def test_client_write_mode_follows_the_option(
    hass: HomeAssistant, mock_pool_data, options, expected_mode
) -> None:
    entry = _entry(hass, options)
    with (
        patch(PATCH_AUTH, return_value=AsyncMock()),
        patch(PATCH_CLIENT, return_value=_mock_api(mock_pool_data)) as client_cls,
        patch(PATCH_SESSION, return_value=MagicMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert client_cls.call_args.kwargs["write_mode"] == expected_mode

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# ── update requests (PUP) ─────────────────────────────────────────


async def test_no_update_request_when_the_option_is_off(
    hass: HomeAssistant, mock_pool_data
) -> None:
    coord = _coordinator(hass, mock_pool_data, {})
    await coord.subscribe()
    await hass.async_block_till_done()

    coord.api.request_updates.assert_not_awaited()
    await coord.async_shutdown()


async def test_update_requests_follow_the_web_client_schedule(
    hass: HomeAssistant, mock_pool_data
) -> None:
    """One request on connect, then 10 and 20 minutes later: three in all."""
    coord = _coordinator(
        hass, mock_pool_data, {CONF_EXPERIMENTAL_REQUEST_UPDATES: True}
    )
    await coord.subscribe()
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 1
    coord.api.request_updates.assert_awaited_with(MOCK_POOL_ID)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=601))
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1201))
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 3

    # Nothing further is scheduled.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 3
    await coord.async_shutdown()


async def test_shutdown_cancels_pending_update_requests(
    hass: HomeAssistant, mock_pool_data
) -> None:
    coord = _coordinator(
        hass, mock_pool_data, {CONF_EXPERIMENTAL_REQUEST_UPDATES: True}
    )
    await coord.subscribe()
    await hass.async_block_till_done()
    await coord.async_shutdown()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 1


async def test_update_request_repeats_when_the_controller_comes_back(
    hass: HomeAssistant, mock_pool_data
) -> None:
    coord = _coordinator(
        hass, mock_pool_data, {CONF_EXPERIMENTAL_REQUEST_UPDATES: True}
    )
    await coord.subscribe()
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 1

    coord._async_handle_push({"present": False})
    coord._async_handle_push({"present": False})
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 1  # still away

    coord._async_handle_push({"present": True})
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 2  # came back

    coord._async_handle_push({"present": True})
    await hass.async_block_till_done()
    assert coord.api.request_updates.await_count == 2  # no repeat while present
    await coord.async_shutdown()


async def test_failed_update_request_does_not_raise(
    hass: HomeAssistant, mock_pool_data
) -> None:
    coord = _coordinator(
        hass, mock_pool_data, {CONF_EXPERIMENTAL_REQUEST_UPDATES: True}
    )
    coord.api.request_updates = AsyncMock(side_effect=AquariteError("boom"))
    await coord.subscribe()
    await hass.async_block_till_done()

    coord.api.request_updates.assert_awaited_once()
    await coord.async_shutdown()


# ── LED button ────────────────────────────────────────────────────


def _button_self(options: dict, light_on: bool) -> MagicMock:
    button = MagicMock()
    button.entity_id = "button.pool_led"
    button.coordinator.pool_id = MOCK_POOL_ID
    button.coordinator.config_entry.options = options
    button.coordinator.get_value = MagicMock(return_value=1 if light_on else 0)
    button.coordinator.api = AsyncMock()
    button.coordinator.async_set_values = AsyncMock()
    return button


async def test_led_button_uses_the_cloud_call_when_enabled() -> None:
    button = _button_self({CONF_EXPERIMENTAL_LED_ENDPOINT: True}, light_on=True)

    await AquariteLEDPulseButtonEntity.async_press(button)

    button.coordinator.api.change_led_color.assert_awaited_once_with(MOCK_POOL_ID)
    button.coordinator.api.pulse.assert_not_awaited()
    button.coordinator.async_set_values.assert_not_awaited()


async def test_led_button_pulses_by_default_when_the_light_is_on() -> None:
    button = _button_self({}, light_on=True)

    await AquariteLEDPulseButtonEntity.async_press(button)

    button.coordinator.api.pulse.assert_awaited_once_with(
        MOCK_POOL_ID, "light.status", 0, 1, LED_PULSE_DELAY
    )
    button.coordinator.api.change_led_color.assert_not_awaited()


async def test_led_button_turns_the_light_on_by_default_when_it_is_off() -> None:
    button = _button_self({}, light_on=False)

    await AquariteLEDPulseButtonEntity.async_press(button)

    button.coordinator.async_set_values.assert_awaited_once_with({"light.status": 1})
    button.coordinator.api.change_led_color.assert_not_awaited()
