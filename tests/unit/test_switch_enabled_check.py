"""Test switch zone enabled check."""

import pytest
from unittest.mock import MagicMock, AsyncMock
import sys
from pathlib import Path

# Add custom_components path
multizone_climate_path = Path(__file__).parent.parent.parent / "multizone_climate"
sys.path.insert(0, str(multizone_climate_path))

from custom_components.multizone_climate.switch import MultizoneEnableSwitch


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "zones": {
            "zone1": {
                "enabled": "true",
                "name": "Zone 1",
            },
            "zone2": {
                "enabled": "false",
                "name": "Zone 2",
            },
        },
        "config": {
            "multizone_enabled": "false",
        },
    }

    def get_config():
        return coordinator.data.get("config", {})

    coordinator.get_config = get_config
    coordinator.async_request_refresh = AsyncMock()
    coordinator.hass = MagicMock()
    coordinator.hass.loop.time = lambda: 1234567890

    return coordinator


@pytest.fixture
def mock_redis_client():
    """Create a mock redis client."""
    redis_client = MagicMock()
    redis_client.set_config = AsyncMock()
    redis_client.enqueue_job = AsyncMock()
    return redis_client


@pytest.mark.asyncio
async def test_switch_recognizes_enabled_zone(mock_coordinator, mock_redis_client):
    """Test that switch recognizes zones with enabled='true'."""
    switch = MultizoneEnableSwitch(mock_coordinator, mock_redis_client)

    # Should allow turning on when at least one zone is enabled
    await switch.async_turn_on()

    # Verify that set_config was called
    assert mock_redis_client.set_config.called


@pytest.mark.asyncio
async def test_switch_rejects_when_no_enabled_zones(mock_coordinator, mock_redis_client):
    """Test that switch rejects when no zones are enabled."""
    # Set all zones to disabled
    mock_coordinator.data["zones"]["zone1"]["enabled"] = "false"

    switch = MultizoneEnableSwitch(mock_coordinator, mock_redis_client)

    # Should not allow turning on when no zones are enabled
    await switch.async_turn_on()

    # Verify that set_config was NOT called
    assert not mock_redis_client.set_config.called


@pytest.mark.asyncio
async def test_switch_handles_various_enabled_values(mock_coordinator, mock_redis_client):
    """Test that switch handles different enabled value formats."""
    # Test with "True"
    mock_coordinator.data["zones"]["zone1"]["enabled"] = "True"
    switch = MultizoneEnableSwitch(mock_coordinator, mock_redis_client)
    await switch.async_turn_on()
    assert mock_redis_client.set_config.called

    # Reset
    mock_redis_client.set_config.reset_mock()

    # Test with "1"
    mock_coordinator.data["zones"]["zone1"]["enabled"] = "1"
    switch = MultizoneEnableSwitch(mock_coordinator, mock_redis_client)
    await switch.async_turn_on()
    assert mock_redis_client.set_config.called
