"""Support for Lutron keypad buttons."""
from __future__ import annotations

import logging
from typing import Any

from pylutron_caseta import BUTTON_STATUS_PRESSED

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_VIA_DEVICE,
)
from homeassistant.core import HomeAssistant, async_get_hass, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import (
    ACTION_PRESS,
    ACTION_RELEASE,
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_BUTTON_ID,
    ATTR_BUTTON_NAME,
    ATTR_BUTTON_NUMBER,
    ATTR_DEVICE_NAME,
    ATTR_KEYPAD_ID,
    ATTR_MODEL,
    ATTR_SERIAL,
    ATTR_TYPE,
    DOMAIN as CASETA_DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
    UNASSIGNED_AREA,
)
from .models import LutronCasetaData

_LOGGER = logging.getLogger(__name__)


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
        if keypad.get("area_name") is None:
            # legacy Caseta Pico device - ignore
            continue
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
                    LutronCasetaButton(
                        button, bridge, bridge_device, keypad, device_registry
                    )
                )
        async_add_entities(button_entities)


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron keypad button."""

    def __init__(self, device, bridge, bridge_device, keypad, device_registry):
        """Set up the button.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        [:param]keypad the keypadon which this button exists
        """
        self._device_registry = device_registry
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

        bridge_serial = bridge_device["serial"]
        identifier = (
            f'{bridge_serial}_{self._keypad_button_device_tree["keypad_device_id"]}'
        )

        @callback
        def _async_button_event(
            button_id, button_group_id, keypad_device_id, event_type
        ):
            if not (device := bridge.get_device_by_id(keypad_device_id)):
                _LOGGER.error(
                    "In LutronCasetaButton._async_button_event could not find device for keypad ID %s",
                    keypad_device_id,
                )
                return

            if not (button_group := device["button_groups"].get(button_group_id)):
                _LOGGER.error(
                    "In LutronCasetaButton._async_button_event could not find button group for ID %s",
                    button_group_id,
                )
                return

            if not (button := button_group["buttons"].get(button_id)):
                _LOGGER.error(
                    "In LutronCasetaButton._async_button_event could not find button for ID %s",
                    button_id,
                )
                return

            if event_type == BUTTON_STATUS_PRESSED:
                action = ACTION_PRESS
            else:
                action = ACTION_RELEASE

            hass = async_get_hass()
            dev_reg = dr.async_get(hass)
            hass_device = dev_reg.async_get_device({(CASETA_DOMAIN, identifier)})

            hass.bus.async_fire(
                LUTRON_CASETA_BUTTON_EVENT,
                {
                    ATTR_SERIAL: device["serial"],
                    ATTR_TYPE: device["type"],
                    ATTR_MODEL: device["model"],
                    ATTR_BUTTON_NUMBER: button["button_number"],
                    ATTR_DEVICE_NAME: device["control_station_name"],
                    ATTR_KEYPAD_ID: device["device_id"],
                    ATTR_BUTTON_NAME: button["name"],
                    ATTR_BUTTON_ID: button["device_id"],
                    ATTR_DEVICE_ID: hass_device.id,
                    ATTR_AREA_NAME: device["area_name"],
                    ATTR_ACTION: action,
                },
            )

        self._smartbridge.add_button_subscriber(
            str(device["device_id"]),
            lambda event_type, button_id=device[
                "device_id"
            ], button_group_id=self._keypad_button_device_tree[
                "button_group_id"
            ], keypad_device_id=self._keypad_button_device_tree[
                "keypad_device_id"
            ],: _async_button_event(  # noqa: E231 / flake8 and black are in conflict
                button_id, button_group_id, keypad_device_id, event_type
            ),
        )

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(
            self._keypad_button_device_tree["keypad_device_id"],
            self._keypad_button_device_tree["button_group_id"],
            self.device_id,
        )
