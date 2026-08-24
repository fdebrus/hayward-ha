"""Tests for the Aquarite config flow (v2: one entry per Hayward account).

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
They validate the config flow, reauth, reconfigure, options flow, and the
v1 (per-pool) to v2 (per-account) entry migration with duplicate cleanup.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from aioaquarite import AquariteError, AuthenticationError  # noqa: E402

from custom_components.aquarite.const import (  # noqa: E402
    CONF_HEALTH_CHECK_INTERVAL,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DOMAIN,
)

PATCH_FLOW_AUTH = "custom_components.aquarite.config_flow.AquariteAuth"
PATCH_FLOW_CLIENT = "custom_components.aquarite.config_flow.AquariteClient"
PATCH_INIT_AUTH = "custom_components.aquarite.AquariteAuth"
PATCH_INIT_CLIENT = "custom_components.aquarite.AquariteClient"
PATCH_SETUP = "custom_components.aquarite.async_setup_entry"
PATCH_UNLOAD = "custom_components.aquarite.async_unload_entry"


@pytest.fixture
def mock_setup_entry():
    """Prevent actual setup and teardown during config flow tests."""
    with (
        patch(PATCH_SETUP, return_value=True) as mock,
        patch(PATCH_UNLOAD, return_value=True),
    ):
        yield mock


@pytest.fixture(autouse=True)
def mock_clientsession():
    """Avoid creating real aiohttp sessions (auth is mocked everywhere).

    A real session spawns a pycares resolver thread that lingers past the
    test and trips the harness's leaked-thread check.
    """
    with (
        patch(
            "custom_components.aquarite.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.aquarite.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        yield


def _mock_auth_and_client(pools=None):
    """Return patched auth and client context managers for the config flow."""
    if pools is None:
        pools = {MOCK_POOL_ID: MOCK_POOL_NAME}
    auth = AsyncMock()
    client = AsyncMock()
    client.get_pools.return_value = pools
    return (
        patch(PATCH_FLOW_AUTH, return_value=auth),
        patch(PATCH_FLOW_CLIENT, return_value=client),
        auth,
    )


async def _create_account_entry(hass: HomeAssistant):
    """Drive the user flow to a created account entry, return the result."""
    patch_auth, patch_client, _ = _mock_auth_and_client()
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
    return result


# ── User Step ─────────────────────────────────────────────────────


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the auth form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_creates_account_entry(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A single credentials step creates one entry for the whole account."""
    result = await _create_account_entry(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == MOCK_USERNAME.lower()
    assert entry.version == 2


async def test_auth_error(hass: HomeAssistant) -> None:
    """Test authentication error is handled."""
    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


async def test_cannot_connect_error(hass: HomeAssistant) -> None:
    """Test a transport-level library error is handled."""
    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AquariteError("boom")
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error during auth is handled."""
    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = RuntimeError("Connection refused")
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown_error"}


async def test_no_pools_found(hass: HomeAssistant) -> None:
    """Test no pools found error."""
    patch_auth, patch_client, _ = _mock_auth_and_client(pools={})
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools_found"}


async def test_duplicate_account_aborts(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Adding the same account twice aborts (case-insensitively)."""
    result = await _create_account_entry(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    patch_auth, patch_client, _ = _mock_auth_and_client()
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME.upper(), CONF_PASSWORD: "otherpass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ── Reauth Flow ───────────────────────────────────────────────────


async def _start_reauth_flow(hass: HomeAssistant, entry) -> dict:
    """Start a reauth flow for a real (non-mock) config entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )


async def test_reauth_flow_updates_password(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Reauth asks only for a password and keeps the account identity."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await _start_reauth_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth_cls.return_value = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "newpass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == MOCK_USERNAME
    assert entry.data[CONF_PASSWORD] == "newpass"


async def test_reauth_flow_auth_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reauth flow handles auth error."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await _start_reauth_flow(hass, entry)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


# ── Reconfigure Flow ──────────────────────────────────────────────


async def _start_reconfigure_flow(hass: HomeAssistant, entry) -> dict:
    """Start a reconfigure flow for a real (non-mock) config entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )


async def test_reconfigure_flow_updates_password(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Reconfigure asks only for a password and keeps the account identity."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await _start_reconfigure_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth_cls.return_value = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "updatedpass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USERNAME] == MOCK_USERNAME
    assert entry.data[CONF_PASSWORD] == "updatedpass"


async def test_reconfigure_flow_auth_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reconfigure flow handles auth error."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_FLOW_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await _start_reconfigure_flow(hass, entry)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


# ── Options Flow ──────────────────────────────────────────────────


async def test_options_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the options flow allows changing health check interval."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HEALTH_CHECK_INTERVAL: 600},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HEALTH_CHECK_INTERVAL] == 600


async def test_options_flow_default(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow uses default health check interval."""
    await _create_account_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    schema_dict = schema({})
    assert schema_dict[CONF_HEALTH_CHECK_INTERVAL] == DEFAULT_HEALTH_CHECK_INTERVAL


# ── v1 → v2 Migration ─────────────────────────────────────────────


def _v1_entry(entry_id: str, pool_id: str, username: str = MOCK_USERNAME):
    """Return a v1-format (per-pool) MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        version=1,
        title=MOCK_POOL_NAME,
        unique_id=pool_id,
        data={
            CONF_USERNAME: username,
            CONF_PASSWORD: MOCK_PASSWORD,
            "pool_id": pool_id,
        },
    )


async def test_migrate_v1_entry(hass: HomeAssistant, mock_setup_entry) -> None:
    """A v1 per-pool entry migrates to the account-level format."""
    entry = _v1_entry("entry1", MOCK_POOL_ID)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == MOCK_USERNAME.lower()
    assert entry.title == MOCK_USERNAME
    assert entry.data == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }


async def test_migrate_removes_duplicate_account_entries(
    hass: HomeAssistant, mock_pool_data
) -> None:
    """Two v1 entries of one account collapse to a single account entry."""
    winner = _v1_entry("entry1", MOCK_POOL_ID)
    loser = _v1_entry("entry2", "OTHERPOOL9876")
    winner.add_to_hass(hass)
    loser.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_subscription = MagicMock()
    mock_subscription.aclose = AsyncMock()
    mock_user_subscription = MagicMock()
    mock_user_subscription.aclose = AsyncMock()

    mock_api = AsyncMock()
    mock_api.get_pools = AsyncMock(
        return_value={MOCK_POOL_ID: MOCK_POOL_NAME, "OTHERPOOL9876": "Spa"}
    )
    mock_api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    mock_api.subscribe_pool_resilient = AsyncMock(return_value=mock_subscription)
    mock_api.subscribe_user_pools_resilient = AsyncMock(
        return_value=mock_user_subscription
    )

    with (
        patch(PATCH_INIT_AUTH, return_value=mock_auth),
        patch(PATCH_INIT_CLIENT, return_value=mock_api),
    ):
        # Loading the component sets up every entry of the domain, so this
        # migrates both entries and triggers the duplicate cleanup.
        await hass.config_entries.async_setup(winner.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].entry_id == "entry1"
    assert entries[0].unique_id == MOCK_USERNAME.lower()
    # The surviving entry manages BOTH pools of the account
    assert set(entries[0].runtime_data.coordinators) == {
        MOCK_POOL_ID,
        "OTHERPOOL9876",
    }

    await hass.config_entries.async_unload(winner.entry_id)
    await hass.async_block_till_done()
