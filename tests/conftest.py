"""Shared fixtures for the Home Assistant integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = "pytest_homeassistant_custom_component"

from custom_components.reolink_talk.const import DOMAIN  # noqa: E402

HOST = "192.0.2.10"
SERIAL = "SERIAL123"
USER = "admin"
PASSWORD = "p@ss w&rd#1"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from this repository."""
    yield


@pytest.fixture
def reachable() -> Generator[AsyncMock]:
    """Make the doorbell answer on its HTTP port (the coordinator check)."""
    writer = MagicMock()
    with patch(
        "custom_components.reolink_talk.coordinator.asyncio.open_connection",
        AsyncMock(return_value=(MagicMock(), writer)),
    ) as mock:
        yield mock


@pytest.fixture
def validate() -> Generator[AsyncMock]:
    """Make the doorbell login in the config flow succeed."""
    with patch(
        "custom_components.reolink_talk.config_flow._async_validate",
        AsyncMock(return_value={"serial": SERIAL, "name": "Front door"}),
    ) as mock:
        yield mock


@pytest.fixture
def entry() -> MockConfigEntry:
    """A configured doorbell."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Front door",
        unique_id=SERIAL,
        data={"host": HOST, "username": USER, "password": PASSWORD},
    )
