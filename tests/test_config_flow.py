"""Tests for the Aquarite config flow.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
They validate the config flow, reauth, reconfigure, and options flow steps.
Run with: pytest tests/test_config_flow.py (requires HA test environment)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.aquarite.const import (  # noqa: E402
    CONF_HEALTH_CHECK_INTERVAL,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def mock_setup_entry():
    """Prevent actual setup during config flow tests."""
    with patch(
        "custom_components.aquarite.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the auth form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_to_pool_step(hass: HomeAssistant) -> None:
    """Test transition from user step to pool selection."""
    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls, patch(
        "custom_components.aquarite.config_flow.AquariteClient"
    ) as mock_client_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools.return_value = {MOCK_POOL_ID: MOCK_POOL_NAME}
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pool"


async def test_full_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test the full config flow creates an entry."""
    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls, patch(
        "custom_components.aquarite.config_flow.AquariteClient"
    ) as mock_client_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools.return_value = {MOCK_POOL_ID: MOCK_POOL_NAME}
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_POOL_NAME
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        "pool_id": MOCK_POOL_ID,
    }


async def test_auth_error(hass: HomeAssistant) -> None:
    """Test authentication error is handled."""
    from aioaquarite import AuthenticationError

    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls:
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


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error during auth is handled."""
    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls:
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
    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls, patch(
        "custom_components.aquarite.config_flow.AquariteClient"
    ) as mock_client_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools.return_value = {}
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools_found"}


async def test_options_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the options flow allows changing health check interval."""
    with patch(
        "custom_components.aquarite.config_flow.AquariteAuth"
    ) as mock_auth_cls, patch(
        "custom_components.aquarite.config_flow.AquariteClient"
    ) as mock_client_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools.return_value = {MOCK_POOL_ID: MOCK_POOL_NAME}
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

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
