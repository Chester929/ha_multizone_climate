"""Unit tests for safety checker."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from custom_components.multizone_climate.core.safety import SafetyChecker


class TestSafetyChecker:
    """Test safety checker logic."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "min_valves_open": 2,
        }

    @pytest.fixture
    def safety_checker(self, mock_redis_client, config):
        """Create safety checker instance."""
        return SafetyChecker(mock_redis_client, config)

    @pytest.mark.asyncio
    async def test_sufficient_valves_open(self, safety_checker):
        """
        Test no action when sufficient valves are open.
        
        Scenario:
            - min_valves_open = 2
            - 2 valves already open
            - Expected: no action needed
        """
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "open",
                "is_fallback_valve": True,
                "priority": 0,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "open",
                "is_fallback_valve": False,
                "priority": 0,
            },
        ]
        
        valves_to_open = await safety_checker.check_minimum_valves(zones)
        
        assert len(valves_to_open) == 0

    @pytest.mark.asyncio
    async def test_insufficient_valves_forces_fallback(self, safety_checker):
        """
        Test that fallback valves are forced open when below minimum.
        
        Scenario:
            - min_valves_open = 2
            - 0 valves open
            - Expected: 2 fallback valves forced open
        """
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 10,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 5,
            },
            {
                "id": "living",
                "valve_id": "switch.living_valve",
                "valve_state": "closed",
                "is_fallback_valve": False,
                "priority": 0,
            },
        ]
        
        valves_to_open = await safety_checker.check_minimum_valves(zones)
        
        assert len(valves_to_open) == 2
        assert "switch.bedroom_valve" in valves_to_open
        assert "switch.kitchen_valve" in valves_to_open

    @pytest.mark.asyncio
    async def test_priority_order_for_fallback(self, safety_checker):
        """
        Test that fallback valves are selected by priority.
        
        Scenario:
            - min_valves_open = 1
            - Multiple fallback valves
            - Expected: highest priority selected
        """
        # Update config for this test
        safety_checker.config["min_valves_open"] = 1
        
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 10,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 5,
            },
        ]
        
        valves_to_open = await safety_checker.check_minimum_valves(zones)
        
        assert len(valves_to_open) == 1
        # Should select bedroom (priority 10) over kitchen (priority 5)
        assert valves_to_open[0] == "switch.bedroom_valve"

    @pytest.mark.asyncio
    async def test_partial_shortage_fills_gap(self, safety_checker):
        """
        Test that only the shortage is filled.
        
        Scenario:
            - min_valves_open = 2
            - 1 valve already open
            - Expected: 1 fallback valve forced open
        """
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "open",
                "is_fallback_valve": False,
                "priority": 0,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 10,
            },
            {
                "id": "living",
                "valve_id": "switch.living_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 5,
            },
        ]
        
        valves_to_open = await safety_checker.check_minimum_valves(zones)
        
        assert len(valves_to_open) == 1
        # Should select kitchen (priority 10)
        assert valves_to_open[0] == "switch.kitchen_valve"

    @pytest.mark.asyncio
    async def test_no_fallback_valves_available(self, safety_checker):
        """
        Test behavior when no fallback valves are available.
        
        Scenario:
            - min_valves_open = 2
            - 0 valves open
            - No fallback valves configured
            - Expected: empty list (can't force any valves)
        """
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "closed",
                "is_fallback_valve": False,
                "priority": 0,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "closed",
                "is_fallback_valve": False,
                "priority": 0,
            },
        ]
        
        valves_to_open = await safety_checker.check_minimum_valves(zones)
        
        # No fallback valves available, so can't force any open
        assert len(valves_to_open) == 0

    @pytest.mark.asyncio
    async def test_counts_open_valves_correctly(self, safety_checker):
        """
        Test that open valve counting is accurate.
        
        Scenario:
            - min_valves_open = 2
            - Mix of open and closed valves
            - Expected: correct count
        """
        zones = [
            {
                "id": "bedroom",
                "valve_id": "switch.bedroom_valve",
                "valve_state": "open",
                "is_fallback_valve": True,
                "priority": 0,
            },
            {
                "id": "kitchen",
                "valve_id": "switch.kitchen_valve",
                "valve_state": "closed",
                "is_fallback_valve": True,
                "priority": 0,
            },
            {
                "id": "living",
                "valve_id": "switch.living_valve",
                "valve_state": "open",
                "is_fallback_valve": False,
                "priority": 0,
            },
        ]
        
        count = safety_checker._count_open_valves(zones)
        
        assert count == 2
