"""Unit tests for binary sensor entities."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.multizone_climate.binary_sensor import MinimumValvesSensor


class TestMinimumValvesSensor:
    """Test minimum valves binary sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.async_add_listener = MagicMock(return_value=lambda: None)
        return coordinator

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry"
        return entry

    @pytest.fixture
    def sensor(self, mock_coordinator, mock_config_entry):
        """Create sensor instance."""
        return MinimumValvesSensor(mock_coordinator, mock_config_entry)

    def test_is_on_with_proper_int_config_value(self, sensor, mock_coordinator):
        """
        Test is_on with properly typed config (from Go backend).

        Scenario:
            - min_valves_open as integer 2 (properly converted by backend)
            - 2 valves currently open
            - Expected: returns True (requirement met)
        """
        # Mock coordinator data with zones
        mock_coordinator.data = {
            "zones": {
                "zone1": {"valve_state": "open"},
                "zone2": {"valve_state": "open"},
                "zone3": {"valve_state": "closed"},
            }
        }

        # Mock config with integer value (as converted by Go backend)
        mock_coordinator.get_config = MagicMock(
            return_value={"min_valves_open": 2}
        )

        result = sensor.is_on
        assert result is True

    def test_is_on_with_proper_int_value_requirement_not_met(
        self, sensor, mock_coordinator
    ):
        """
        Test is_on with properly typed config when requirement not met.

        Scenario:
            - min_valves_open as integer 3 (properly converted by backend)
            - Only 1 valve currently open
            - Expected: returns False (requirement not met)
        """
        # Mock coordinator data with zones
        mock_coordinator.data = {
            "zones": {
                "zone1": {"valve_state": "open"},
                "zone2": {"valve_state": "closed"},
            }
        }

        # Mock config with integer value (as converted by Go backend)
        mock_coordinator.get_config = MagicMock(
            return_value={"min_valves_open": 3}
        )

        result = sensor.is_on
        assert result is False

    def test_is_on_with_int_config_value(self, sensor, mock_coordinator):
        """
        Test is_on still works with integer min_valves_open.

        Scenario:
            - min_valves_open as integer 2
            - 2 valves currently open
            - Expected: returns True
        """
        # Mock coordinator data with zones
        mock_coordinator.data = {
            "zones": {
                "zone1": {"valve_state": "open"},
                "zone2": {"valve_state": "open"},
            }
        }

        # Mock config with integer value
        mock_coordinator.get_config = MagicMock(return_value={"min_valves_open": 2})

        result = sensor.is_on
        assert result is True

    def test_is_on_no_config(self, sensor, mock_coordinator):
        """
        Test is_on when config is not available.

        Expected: returns True (default to OK)
        """
        # Mock coordinator with data but no config
        mock_coordinator.data = {
            "zones": {
                "zone1": {"valve_state": "closed"},
            }
        }
        mock_coordinator.get_config = MagicMock(return_value=None)

        result = sensor.is_on
        assert result is True

    def test_is_on_no_zones(self, sensor, mock_coordinator):
        """
        Test is_on when no zones exist.

        Expected: returns False
        """
        # Mock coordinator with empty zones
        mock_coordinator.data = {"zones": {}}
        mock_coordinator.get_config = MagicMock(
            return_value={"min_valves_open": "1"}
        )

        result = sensor.is_on
        assert result is False

    def test_is_on_no_data(self, sensor, mock_coordinator):
        """
        Test is_on when coordinator has no data.

        Expected: returns False
        """
        mock_coordinator.data = None

        result = sensor.is_on
        assert result is False
