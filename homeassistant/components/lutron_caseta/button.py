"""Support for Lutron keypad buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron keypad buttons."""
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    bridge_device = data.bridge_device
    button_devices = bridge.get_buttons()

    async_add_entities(
        LutronCasetaButton(button_devices[button_device_id], bridge, bridge_device)
        for button_device_id in button_devices
    )


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron keypad button."""

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier if serial number is None."""
        if self.serial is None:
            return f"button_{self._bridge_unique_id}_{self.device_id}"
        return super().unique_id
