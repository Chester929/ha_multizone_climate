"""Automations module initialization."""
from .temperature_change import TemperatureChangeAutomation
from .safety_timer import SafetyTimerAutomation

__all__ = [
    "TemperatureChangeAutomation",
    "SafetyTimerAutomation",
]
