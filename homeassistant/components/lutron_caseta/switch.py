"""Support for Lutron Caseta switches."""

from typing import Any

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, ATTR_SUGGESTED_AREA, ATTR_VIA_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN, MANUFACTURER, UNASSIGNED_AREA
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta switch platform.

    Adds switches from the Caseta bridge associated with the config_entry as
    switch entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    bridge_device = data.bridge_device
    switch_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        LutronCasetaLight(switch_device, bridge, bridge_device)
        for switch_device in switch_devices
    )

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

        # Register button LEDs from this keypad
        button_led_entities = []
        for button_group in keypad["button_groups"].values():
            for button in button_group["buttons"].values():
                button["device_tree"] = {
                    "keypad_device_id": keypad_device_id,
                    "button_group_id": button_group["button_group_id"],
                    "button_device_id": button["device_id"],
                }

                if button.get("led") is not None:
                    button_led_entities.append(
                        LutronCasetaKeypadLED(button, bridge, bridge_device, keypad)
                    )
        async_add_entities(button_led_entities)


class LutronCasetaLight(LutronCasetaDeviceUpdatableEntity, SwitchEntity):
    """Representation of a Lutron Caseta switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._smartbridge.turn_on(self.device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._smartbridge.turn_off(self.device_id)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device["current_state"] > 0


class LutronCasetaKeypadLED(LutronCasetaDeviceUpdatableEntity, SwitchEntity):
    """Representation of a Lutron keypad LED."""

    def __init__(self, button_device, bridge, bridge_device, keypad):
        """Set up the keypad LED.

        [:param]button_device the associated button's device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        [:param]keypad the keypadon which this button exists
        """

        device = button_device.copy()
        device["device_id"] = button_device["led"]["led_id"]
        device["name"] = f"{button_device['name']} LED"
        self._keypad_button_device_tree = button_device["device_tree"]
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._smartbridge.turn_led_on(
            self._keypad_button_device_tree["keypad_device_id"],
            self._keypad_button_device_tree["button_group_id"],
            self._keypad_button_device_tree["button_device_id"],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._smartbridge.turn_led_off(
            self._keypad_button_device_tree["keypad_device_id"],
            self._keypad_button_device_tree["button_group_id"],
            self._keypad_button_device_tree["button_device_id"],
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device["led"]["current_state"] > 0

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        if self.is_on:
            return "mdi:led-on"
        return "mdi:led-off"
