"""Switch platform for Seymour Screen Masking Integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from .const import DOMAIN as SEYMOUR_DOMAIN
from .entity import SeymourEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .pySeymour.device import SeymourScreenController as Device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BaseEntityDescriptionMixin:
    """Mixin for required descriptor keys."""


@dataclass(frozen=True)
class SwitchEntityDescription(SwitchEntityDescription, BaseEntityDescriptionMixin):
    """Describes Seymour Switch entity."""


SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        device_class=SwitchDeviceClass.SWITCH,
        key="jog_mode",
        name="Jog Mode",
        icon="mdi:run",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    device_entry = hass.data[SEYMOUR_DOMAIN][config_entry.entry_id]
    device = device_entry["device"]
    async_add_entities(SeymourSwitch(device, description) for description in SWITCHES)


class SeymourSwitch(SeymourEntity, SwitchEntity):
    """Representation of a Seymour switch."""

    def __init__(
        self,
        device: Device,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize switch."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self._device = device
        self.set_states()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable jog mode."""
        if self.entity_description.key == "jog_mode":
            await getattr(self._device, "toggle_jog")()
            self.set_states()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.entity_description.key == "jog_mode":
            await getattr(self._device, "toggle_jog")()
            self.set_states()

    @property
    def is_on(self) -> bool:
        """Return the current state of jog mode."""
        return self._attr_is_on

    def set_states(self) -> None:
        """Set all the states from the device to the entity."""
        if self.entity_description.key == "jog_mode":
            pass
            # self._attr_is_on = self._device.screen_settings.jog
