"""Support for Lutron keypad buttons."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, ATTR_SUGGESTED_AREA, ATTR_VIA_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import DOMAIN as CASETA_DOMAIN, MANUFACTURER, UNASSIGNED_AREA
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron keypad buttons."""
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    device_registry = dr.async_get(hass)
    bridge = data.bridge
    bridge_device = data.bridge_device
    bridge_serial = bridge_device["serial"]

    keypad_devices = bridge.get_devices_by_domain("keypad")
    for keypad in keypad_devices:
        keypad_device_id = keypad["device_id"]
        area = keypad["area_name"]
        device_args: dict[str, Any] = {
            "name": f"{keypad['control_station_name']} {keypad['name']}",
            "manufacturer": MANUFACTURER,
            "config_entry_id": config_entry.entry_id,
            "identifiers": {(CASETA_DOMAIN, f"{bridge_serial}_{keypad_device_id}")},
            "model": f"{keypad['model']} ({keypad['type']})",
            "via_device": (CASETA_DOMAIN, bridge_device["serial"]),
        }
        if area != UNASSIGNED_AREA:
            device_args["suggested_area"] = area

        device_registry.async_get_or_create(**device_args)

        # Register buttons from this keypad
        button_entities = []
        for button_group in keypad["button_groups"].values():
            for button in button_group["buttons"].values():
                button["device_tree"] = {
                    "keypad_device_id": keypad_device_id,
                    "button_group_id": button_group["button_group_id"],
                }
                button_entities.append(
                    LutronCasetaButton(button, bridge, bridge_device, keypad)
                )
        async_add_entities(button_entities)


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron keypad button."""

    def __init__(self, device, bridge, bridge_device, keypad):
        """Set up the button.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        [:param]keypad the keypadon which this button exists
        """

        self._keypad_button_device_tree = device["device_tree"]
        device["serial"] = None
        device["model"] = keypad["model"]
        device["type"] = keypad["type"]
        super().__init__(device, bridge, bridge_device)
        self._attr_name = self._attr_device_info[
            ATTR_NAME
        ] = f"{keypad['area_name']} {keypad['control_station_name']} {keypad['name']} {device['name']}"
        self._attr_device_info[ATTR_SUGGESTED_AREA] = keypad["area_name"]
        self._attr_device_info[ATTR_VIA_DEVICE] = (
            CASETA_DOMAIN,
            f"{bridge_device['serial']}_{keypad['device_id']}",
        )

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(
            self._keypad_button_device_tree["keypad_device_id"],
            self._keypad_button_device_tree["button_group_id"],
            self.device_id,
        )
