"""Unit tests for valve state change automation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from homeassistant.core import Event

from custom_components.multizone_climate.automations.valve_state_change import (
    ValveStateChangeAutomation,
)


class TestValveStateChangeAutomation:
    """Test the ValveStateChangeAutomation class."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.async_create_task = MagicMock()
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
                    "valve_switch_entity_id": "switch.bedroom_valve",
                    "valve_state": "closed",
                },
                {
                    "id": "zone2",
                    "name": "Living Room",
                    "valve_switch_entity_id": "switch.living_room_valve",
                    "valve_state": "opened",
                },
            ]
        )
        redis_client.set_zone_state = AsyncMock()
        return redis_client

    @pytest.fixture
    def automation(self, mock_hass, mock_redis_client):
        """Create automation instance."""
        return ValveStateChangeAutomation(mock_hass, mock_redis_client)

    @pytest.mark.asyncio
    async def test_setup_registers_listeners(self, automation, mock_redis_client):
        """Test that setup registers listeners for all valve switches and builds mapping."""
        with patch(
            "custom_components.multizone_climate.automations.valve_state_change.async_track_state_change_event"
        ) as mock_track:
            mock_track.return_value = MagicMock()

            await automation.setup()

            # Verify that async_track_state_change_event was called with valve entity IDs
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            entity_ids = call_args[0][1]
            assert "switch.bedroom_valve" in entity_ids
            assert "switch.living_room_valve" in entity_ids
            assert len(automation._cancel_listeners) == 1

            # Verify mapping was built
            assert automation._entity_to_zone["switch.bedroom_valve"] == "zone1"
            assert automation._entity_to_zone["switch.living_room_valve"] == "zone2"

    @pytest.mark.asyncio
    async def test_valve_state_on_to_opened(self, automation, mock_redis_client):
        """Test that valve state 'on' is mapped to 'opened' in Redis."""
        # Set up mapping
        automation._entity_to_zone = {"switch.bedroom_valve": "zone1"}
        
        # Reset the mock to have a fresh state for this test
        mock_redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "valve_switch_entity_id": "switch.bedroom_valve",
                "valve_state": "closed",
            }
        )

        # Create a mock event with state change from off to on
        event_data = {
            "entity_id": "switch.bedroom_valve",
            "old_state": MagicMock(state="off"),
            "new_state": MagicMock(state="on"),
        }
        event = MagicMock()
        event.data = event_data

        # Call the handler
        automation._handle_valve_state_change(event)

        # Verify async_create_task was called
        automation.hass.async_create_task.assert_called_once()

        # Execute the task
        task_coro = automation.hass.async_create_task.call_args[0][0]
        await task_coro

        # Verify Redis was updated with "opened"
        mock_redis_client.set_zone_state.assert_called_once()
        updated_state = mock_redis_client.set_zone_state.call_args[0][1]
        assert updated_state["valve_state"] == "opened"

    @pytest.mark.asyncio
    async def test_valve_state_off_to_closed(self, automation, mock_redis_client):
        """Test that valve state 'off' is mapped to 'closed' in Redis."""
        # Set up mapping
        automation._entity_to_zone = {"switch.bedroom_valve": "zone1"}
        
        # Reset the mock to have a fresh state for this test
        mock_redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "valve_switch_entity_id": "switch.bedroom_valve",
                "valve_state": "opened",
            }
        )

        # Create a mock event with state change from on to off
        event_data = {
            "entity_id": "switch.bedroom_valve",
            "old_state": MagicMock(state="on"),
            "new_state": MagicMock(state="off"),
        }
        event = MagicMock()
        event.data = event_data

        # Call the handler
        automation._handle_valve_state_change(event)

        # Verify async_create_task was called
        automation.hass.async_create_task.assert_called_once()

        # Execute the task
        task_coro = automation.hass.async_create_task.call_args[0][0]
        await task_coro

        # Verify Redis was updated with "closed"
        mock_redis_client.set_zone_state.assert_called_once()
        updated_state = mock_redis_client.set_zone_state.call_args[0][1]
        assert updated_state["valve_state"] == "closed"

    @pytest.mark.asyncio
    async def test_valve_state_unknown_ignored(self, automation, mock_redis_client):
        """Test that unknown valve states are ignored."""
        # Create a mock event with unknown state
        event_data = {
            "entity_id": "switch.bedroom_valve",
            "old_state": MagicMock(state="off"),
            "new_state": MagicMock(state="unavailable"),
        }
        event = MagicMock()
        event.data = event_data

        # Call the handler
        automation._handle_valve_state_change(event)

        # Verify async_create_task was NOT called
        automation.hass.async_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_valve_state_no_change_ignored(self, automation):
        """Test that events with no actual state change are ignored."""
        # Create a mock event where state didn't change
        event_data = {
            "entity_id": "switch.bedroom_valve",
            "old_state": MagicMock(state="on"),
            "new_state": MagicMock(state="on"),
        }
        event = MagicMock()
        event.data = event_data

        # Call the handler
        automation._handle_valve_state_change(event)

        # Verify async_create_task was NOT called
        automation.hass.async_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_valve_state_new_state_none_ignored(self, automation):
        """Test that events with new_state=None are ignored (entity removed)."""
        # Create a mock event with new_state=None
        event_data = {
            "entity_id": "switch.bedroom_valve",
            "old_state": MagicMock(state="on"),
            "new_state": None,
        }
        event = MagicMock()
        event.data = event_data

        # Call the handler
        automation._handle_valve_state_change(event)

        # Verify async_create_task was NOT called
        automation.hass.async_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_valve_state_no_matching_zone(
        self, automation, mock_redis_client
    ):
        """Test that update handles case where no zone matches the entity_id."""
        # Set up mapping with a different valve switch
        automation._entity_to_zone = {"switch.different_valve": "zone1"}

        # Call update with a non-matching entity_id
        await automation._update_valve_state_in_redis(
            "switch.nonexistent_valve", "opened"
        )

        # Verify Redis was NOT updated
        mock_redis_client.set_zone_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_cancels_listeners(self, automation):
        """Test that stop() cancels all listeners and clears mapping."""
        # Add some mock cancel functions
        cancel_func1 = MagicMock()
        cancel_func2 = MagicMock()
        automation._cancel_listeners = [cancel_func1, cancel_func2]
        automation._entity_to_zone = {"switch.valve1": "zone1", "switch.valve2": "zone2"}

        await automation.stop()

        # Verify all cancel functions were called
        cancel_func1.assert_called_once()
        cancel_func2.assert_called_once()
        assert len(automation._cancel_listeners) == 0
        # Verify mapping was cleared
        assert len(automation._entity_to_zone) == 0
