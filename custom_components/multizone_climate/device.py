"""Device class for main climate device."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class MainClimateDeviceInfo:
    """Device information for main climate device."""

    @staticmethod
    def get_device_info() -> DeviceInfo:
        """
        Get device info for main climate device.
        
        Returns:
            DeviceInfo: Device information
        """
        return DeviceInfo(
            identifiers={(DOMAIN, "multizone_climate_main")},
            name="Multizone Climate",
            manufacturer="Chester929",
            model="Multizone Climate Controller",
            sw_version="0.1.0",
        )
