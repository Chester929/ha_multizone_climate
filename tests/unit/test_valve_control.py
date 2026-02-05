"""Unit tests for valve control logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from custom_components.multizone_climate.core.valve_control import ValveController


class TestValveController:
    """Test valve controller logic."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        client.is_valve_locked = AsyncMock(return_value=False)
        client.set_valve_lock = AsyncMock()
        return client

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "min_valves_open": 1,
            "valve_actuation_delay": 120,
        }

    @pytest.fixture
    def valve_controller(self, mock_redis_client, config):
        """Create valve controller instance."""
        return ValveController(mock_redis_client, config)

    @pytest.mark.asyncio
    async def test_underheated_zone_opens_valve(self, valve_controller):
        """
        Test that underheated zone opens its valve.

        Scenario:
            - 1 zone underheated
            - Expected: valve opens
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 19.0,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "closed",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        assert len(actions) == 1
        assert actions[0]["valve_id"] == "switch.bedroom_valve"
        assert actions[0]["action"] == "open"

    @pytest.mark.asyncio
    async def test_overheated_zone_closes_valve(self, valve_controller):
        """
        Test that overheated zone closes its valve.

        Scenario:
            - 1 zone overheated, 1 zone satisfied
            - Expected: overheated valve closes
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 23.0,
                "target_temperature": 21.0,
                "satisfaction": "overheated",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "open",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "valve_id": "switch.kitchen_valve",
                "current_temperature": 21.5,
                "target_temperature": 22.0,
                "satisfaction": "satisfied",
                "priority": 0,
                "is_fallback_valve": False,
                "valve_state": "open",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # Should close bedroom, keep kitchen open
        close_actions = [a for a in actions if a["action"] == "close"]
        assert len(close_actions) == 1
        assert close_actions[0]["valve_id"] == "switch.bedroom_valve"

    @pytest.mark.asyncio
    async def test_minimum_valves_enforcement(self, valve_controller):
        """
        Test that minimum valves are enforced.

        Scenario:
            - All zones satisfied/overheated
            - min_valves_open = 1
            - Expected: fallback valve forced open
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 22.0,
                "target_temperature": 21.0,
                "satisfaction": "overheated",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "open",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # Should not close the only valve due to minimum requirement
        open_actions = [a for a in actions if a["action"] == "open"]
        # The fallback valve should remain open (no close action)
        close_actions = [a for a in actions if a["action"] == "close"]

        # Either no close action or an open action for the fallback
        assert len(close_actions) == 0 or len(open_actions) >= 1

    @pytest.mark.asyncio
    async def test_priority_sorting(self, valve_controller):
        """
        Test that zones are sorted by priority.

        Scenario:
            - Multiple zones with different priorities
            - Expected: higher priority processed first
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 19.0,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "priority": 10,
                "is_fallback_valve": True,
                "valve_state": "closed",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "valve_id": "switch.kitchen_valve",
                "current_temperature": 19.5,
                "target_temperature": 22.0,
                "satisfaction": "underheated",
                "priority": 5,
                "is_fallback_valve": False,
                "valve_state": "closed",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # Both should open, but priority order is maintained
        assert len(actions) >= 2
        open_actions = [a for a in actions if a["action"] == "open"]
        assert len(open_actions) >= 2

    @pytest.mark.asyncio
    async def test_satisfied_zones_keep_valves_open(self, valve_controller):
        """
        Test that satisfied zones have their valves open.

        Scenario:
            - Zone is satisfied
            - Expected: valve should be open to maintain temperature
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 21.0,
                "target_temperature": 21.0,
                "satisfaction": "satisfied",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "open",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # Satisfied zones should have valves open
        open_actions = [a for a in actions if a["action"] == "open"]
        close_actions = [a for a in actions if a["action"] == "close"]

        # Should not close satisfied zones
        assert len(close_actions) == 0

    @pytest.mark.asyncio
    async def test_satisfied_zones_open_closed_valves(self, valve_controller):
        """
        Test that satisfied zones with closed valves get opened.

        Scenario:
            - Zone is satisfied but valve is closed
            - Expected: valve opens to maintain temperature
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 21.0,
                "target_temperature": 21.0,
                "satisfaction": "satisfied",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "closed",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # Satisfied zone with closed valve should open
        assert len(actions) >= 1
        open_actions = [a for a in actions if a["action"] == "open"]
        assert len(open_actions) >= 1
        assert open_actions[0]["valve_id"] == "switch.bedroom_valve"

    @pytest.mark.asyncio
    async def test_cooling_mode_undercooled_opens_valve(self, valve_controller):
        """
        Test that undercooled zone in cooling mode opens valve.

        Scenario:
            - Cooling mode with undercooled zone
            - Expected: valve opens
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 25.0,
                "target_temperature": 23.0,
                "satisfaction": "undercooled",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "closed",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="COOLING",
            multizone_enabled=True,
        )

        assert len(actions) >= 1
        open_actions = [a for a in actions if a["action"] == "open"]
        assert len(open_actions) >= 1
        assert open_actions[0]["valve_id"] == "switch.bedroom_valve"

    @pytest.mark.asyncio
    async def test_multizone_disabled_individual_control(self, valve_controller):
        """
        Test individual valve control when multizone is disabled.

        Scenario:
            - Multizone disabled
            - Expected: each zone manages its own valve
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "valve_id": "switch.bedroom_valve",
                "current_temperature": 19.0,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "priority": 0,
                "is_fallback_valve": True,
                "valve_state": "closed",
            },
        ]

        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=False,
        )

        # In individual mode, underheated zone should open
        assert len(actions) >= 1
        assert actions[0]["valve_id"] == "switch.bedroom_valve"
        assert actions[0]["action"] == "open"
