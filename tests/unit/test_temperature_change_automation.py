"""Unit tests for temperature change automation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from homeassistant.core import Event

from custom_components.multizone_climate.automations.temperature_change import (
    TemperatureChangeAutomation,
)


class TestTemperatureChangeAutomation:
    """Test the TemperatureChangeAutomation class."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_create_task = MagicMock()
        hass.loop = MagicMock()
        hass.loop.time = MagicMock(return_value=1234567890.0)
        return hass

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        redis_client = MagicMock()
        redis_client.get_zone_ids = AsyncMock(return_value=["zone1", "zone2"])
        redis_client.get_zone_state = AsyncMock(
            side_effect=[
                {
                    "id": "zone1",
                    "name": "Bedroom",
                    "temperature_sensor_entity_id": "sensor.bedroom_temp",
                },
                {
                    "id": "zone2",
                    "name": "Living Room",
                    "temperature_sensor_entity_id": "sensor.living_room_temp",
                },
            ]
        )
        redis_client.get_config = AsyncMock(
            return_value={
                "main_climate_entity_id": "climate.main_thermostat",
            }
        )
        redis_client.get_main_climate_state = AsyncMock(
            return_value={
                "entity_id": "climate.main_thermostat",
                "current_temperature": 21.0,
                "target_temperature": 22.0,
                "hvac_mode": "heat",
                "hvac_action": "heating",
            }
        )
        redis_client.set_main_climate_state = AsyncMock()
        redis_client.enqueue_job = AsyncMock()
        return redis_client

    @pytest.fixture
    def automation(self, mock_hass, mock_redis_client):
        """Create automation instance."""
        return TemperatureChangeAutomation(mock_hass, mock_redis_client)

    @pytest.mark.asyncio
    async def test_setup_registers_zone_sensors(self, automation, mock_redis_client):
        """Test that setup registers listeners for zone temperature sensors."""
        with patch(
            "custom_components.multizone_climate.automations.temperature_change.async_track_state_change_event"
        ) as mock_track:
            mock_track.return_value = MagicMock()

            await automation.setup()

            # Verify that async_track_state_change_event was called twice
            # Once for zone sensors, once for main climate
            assert mock_track.call_count == 2
            
            # First call should be for zone sensors
            first_call_args = mock_track.call_args_list[0]
            zone_entity_ids = first_call_args[0][1]
            assert "sensor.bedroom_temp" in zone_entity_ids
            assert "sensor.living_room_temp" in zone_entity_ids
            
            # Second call should be for main climate
            second_call_args = mock_track.call_args_list[1]
            main_entity_ids = second_call_args[0][1]
            assert "climate.main_thermostat" in main_entity_ids
            
            assert len(automation._cancel_listeners) == 2

    @pytest.mark.asyncio
    async def test_main_climate_temperature_update(self, automation, mock_redis_client):
        """Test that main climate current_temperature is updated in Redis."""
        # Create a mock event with new temperature
        event_data = {
            "entity_id": "climate.main_thermostat",
            "old_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.0, "hvac_action": "heating"},
            ),
            "new_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.5, "hvac_action": "heating"},
            ),
        }
        event = MagicMock()
        event.data = event_data

        # Call _update_main_climate_state directly
        await automation._update_main_climate_state(event)

        # Verify get_main_climate_state was called
        mock_redis_client.get_main_climate_state.assert_called_once()

        # Verify set_main_climate_state was called with updated temperature
        mock_redis_client.set_main_climate_state.assert_called_once()
        call_args = mock_redis_client.set_main_climate_state.call_args
        updated_state = call_args[0][0]
        
        # Check that current_temperature was updated
        assert updated_state["current_temperature"] == 21.5
        assert updated_state["hvac_mode"] == "heat"
        assert updated_state["hvac_action"] == "heating"

    @pytest.mark.asyncio
    async def test_main_climate_hvac_mode_update(self, automation, mock_redis_client):
        """Test that main climate hvac_mode is updated in Redis."""
        # Create a mock event with hvac mode change
        event_data = {
            "entity_id": "climate.main_thermostat",
            "old_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.5, "hvac_action": "heating"},
            ),
            "new_state": MagicMock(
                state="cool",
                attributes={"current_temperature": 21.5, "hvac_action": "cooling"},
            ),
        }
        event = MagicMock()
        event.data = event_data

        # Call _update_main_climate_state directly
        await automation._update_main_climate_state(event)

        # Verify set_main_climate_state was called with updated mode
        mock_redis_client.set_main_climate_state.assert_called_once()
        call_args = mock_redis_client.set_main_climate_state.call_args
        updated_state = call_args[0][0]
        
        # Check that hvac_mode and hvac_action were updated
        assert updated_state["hvac_mode"] == "cool"
        assert updated_state["hvac_action"] == "cooling"

    @pytest.mark.asyncio
    async def test_main_climate_change_handler(self, automation, mock_redis_client):
        """Test that main climate change handler triggers update and debouncing."""
        # Create a mock event
        event_data = {
            "entity_id": "climate.main_thermostat",
            "old_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.0, "hvac_action": "heating"},
            ),
            "new_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.5, "hvac_action": "heating"},
            ),
        }
        event = MagicMock()
        event.data = event_data

        with patch("asyncio.create_task") as mock_create_task:
            # Call the handler
            automation._handle_main_climate_change(event)

            # Verify async task was created for Redis update
            assert mock_create_task.call_count >= 1

    @pytest.mark.asyncio
    async def test_invalid_temperature_value(self, automation, mock_redis_client):
        """Test that invalid temperature values are handled gracefully."""
        # Create a mock event with invalid temperature
        event_data = {
            "entity_id": "climate.main_thermostat",
            "old_state": MagicMock(
                state="heat",
                attributes={"current_temperature": 21.0, "hvac_action": "heating"},
            ),
            "new_state": MagicMock(
                state="heat",
                attributes={"current_temperature": "invalid", "hvac_action": "heating"},
            ),
        }
        event = MagicMock()
        event.data = event_data

        # Call _update_main_climate_state directly - should not raise
        await automation._update_main_climate_state(event)

        # Verify set_main_climate_state was still called (with other updates)
        mock_redis_client.set_main_climate_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_new_state(self, automation, mock_redis_client):
        """Test that missing new_state is handled gracefully."""
        # Create a mock event without new_state
        event_data = {}
        event = MagicMock()
        event.data = event_data

        # Call _update_main_climate_state directly - should not raise
        await automation._update_main_climate_state(event)

        # Verify set_main_climate_state was not called
        mock_redis_client.set_main_climate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_cleanup(self, automation):
        """Test that stop() cleans up listeners and tasks."""
        # Create mock cancel functions
        mock_cancel1 = MagicMock()
        mock_cancel2 = MagicMock()
        automation._cancel_listeners = [mock_cancel1, mock_cancel2]

        # Create actual async task that can be awaited
        async def dummy_task():
            pass
        
        task = asyncio.create_task(dummy_task())
        automation._debounce_task = task

        # Call stop
        await automation.stop()

        # Verify listeners were cancelled
        mock_cancel1.assert_called_once()
        mock_cancel2.assert_called_once()
        assert len(automation._cancel_listeners) == 0

        # Task should be cancelled
        assert task.cancelled() or task.done()
