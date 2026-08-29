"""Regression tests for filtration timer speed reads (aioaquarite issue #17).

`filtration.timerVel1/2/3` carry a three-state pump speed (0 slow,
1 medium, 2 high). aioaquarite < 0.9.2 coerced them to bool, so `high`
came back as None and these selects showed `unknown`.

These tests go through the real `AquariteClient.get_value` coercion and
the real select entity, so they fail if the library ever regresses or
the pin drops below 0.9.2.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from aioaquarite import AquariteClient  # noqa: E402

from custom_components.aquarite.select import (  # noqa: E402
    TIMER_SPEED_OPTIONS,
    AquariteSelectEntity,
)


def _coercing_coordinator(data: dict[str, Any]) -> MagicMock:
    """Coordinator double whose get_value applies the real coercion."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.pool_id = MOCK_POOL_ID
    coordinator.pool_name = MOCK_POOL_NAME
    coordinator.get_value = lambda path, default=None: AquariteClient.get_value(
        data, path, default
    )
    return coordinator


def _timer_select(index: int, raw: Any) -> AquariteSelectEntity:
    """Build the real timer-speed select entity over a raw stored value."""
    coordinator = _coercing_coordinator({"filtration": {f"timerVel{index}": raw}})
    return AquariteSelectEntity(
        coordinator,
        MOCK_POOL_ID,
        MOCK_POOL_NAME,
        f"Filtration Timer Speed {index}",
        f"filtration_timer_speed_{index}",
        f"filtration.timerVel{index}",
        TIMER_SPEED_OPTIONS,
    )


@pytest.mark.parametrize("index", [1, 2, 3])
@pytest.mark.parametrize(
    "raw, expected",
    [(0, "slow"), (1, "medium"), (2, "high")],
)
def test_timer_speed_reads_all_three_states(
    index: int, raw: int, expected: str
) -> None:
    """All three speeds read back; `high` used to return None."""
    assert _timer_select(index, raw).current_option == expected


@pytest.mark.parametrize("index", [1, 2, 3])
def test_timer_speed_reads_high_sent_as_string(index: int) -> None:
    """Some firmware revisions send numeric scalars as strings."""
    assert _timer_select(index, "2").current_option == "high"


def test_timer_speed_matches_pump_speed_semantics() -> None:
    """The timer speeds share `filtration.manVel`'s 0/1/2 encoding."""
    data = {"filtration": {"manVel": 2, "timerVel1": 2}}
    assert AquariteClient.get_value(data, "filtration.manVel") == 2
    assert AquariteClient.get_value(data, "filtration.timerVel1") == 2
