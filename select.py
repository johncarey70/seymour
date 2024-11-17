"""Select platform for Seymour Screen Masking Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN as SEYMOUR_DOMAIN
from .entity import SeymourEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .pySeymour.device import SeymourScreenController as Device

SELECTS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="motor_id",
        name="Select Motor to be Controlled",
        icon="mdi:engine",
        options=[],
    ),
    SelectEntityDescription(
        key="movement_code",
        name="Select Motor Movement Mode",
        icon="mdi:cog",
        options=[],
    ),
    SelectEntityDescription(
        key="ratio",
        name="Set Screen Mask Aspect Ratio",
        icon="mdi:aspect-ratio",
        options=[],
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    device_entry = hass.data[SEYMOUR_DOMAIN][config_entry.entry_id]
    device = device_entry["device"]
    async_add_entities(SeymourSelect(device, description) for description in SELECTS)


class SeymourSelect(SeymourEntity, SelectEntity):
    """Representation of Seymour Select."""

    def __init__(
        self,
        device: Device,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize select."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self.device = device

        # Set initial options and states
        self.set_states()

    @property
    def icon(self) -> str:
        """Dynamically set icon based on the current option."""
        if self.entity_description.key == "movement_code":
            movement_code = self.device.mask_ratio_settings.current_movement_code
            if movement_code == "J":
                return "mdi:run"
            if movement_code == "P":
                return "mdi:percent"
        return self.entity_description.icon

    @property
    def current_option(self) -> str:
        """Return the current option based on the key."""
        key_map = {
            "ratio": lambda: (
                self.device.mask_ratio_settings.ratios.get(
                    int(self.device.mask_ratio_settings.current_ratio), None
                ).label
                if self.device.mask_ratio_settings.current_ratio
                in self.device.mask_ratio_settings.ratios
                else ""
            ),
            "motor_id": lambda: self.device.mask_ratio_settings.motors.get(
                self.device.mask_ratio_settings.current_motor_id, ""
            ),
            "movement_code": lambda: (
                self.device.mask_ratio_settings.movement_codes.get(
                    self.device.mask_ratio_settings.current_movement_code, ""
                )
                if self.device.mask_ratio_settings.current_movement_code is not None
                else "Move Motor(s) to Limit"
            ),
        }
        return key_map.get(self.entity_description.key, lambda: "")()

    async def async_select_option(self, option: str) -> None:
        """Set the selected option based on the key."""
        if self.entity_description.key == "ratio":
            for key, value in self.device.mask_ratio_settings.ratios.items():
                if value.label == option:  # Match the label correctly
                    # Ensure select_ratio exists and call it with the ratio key
                    if hasattr(self.device, "select_ratio"):
                        await self.device.select_ratio(key)
                        return
                    else:
                        _LOGGER.error("Device does not support ratio selection")
                        return
        elif self.entity_description.key == "motor_id":
            for key, value in self.device.mask_ratio_settings.motors.items():
                if value == option:
                    if hasattr(self.device, "select_motor"):
                        await self.device.select_motor(key)
                        return
        elif self.entity_description.key == "movement_code":
            if option is None or option == "N":
                await self.device.select_movement_mode(None)
                return
            for key, value in self.device.mask_ratio_settings.movement_codes.items():
                if value == option:
                    await self.device.select_movement_mode(key)
                    return
        else:
            _LOGGER.error("Invalid option selected: %s", option)

    def set_states(self) -> None:
        """Set all the states from the device to the entity."""
        if self.entity_description.key == "ratio":
            self._attr_options = [
                info.label for info in self.device.mask_ratio_settings.ratios.values()
            ]
        elif self.entity_description.key == "motor_id":
            self._attr_options = list(self.device.mask_ratio_settings.motors.values())
        elif self.entity_description.key == "movement_code":
            self._attr_options = list(
                self.device.mask_ratio_settings.movement_codes.values()
            )
