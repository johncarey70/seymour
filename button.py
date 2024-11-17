"""Button platform for Seymour Screen Masking Integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

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

    press_action: Callable[[Device], Coroutine[Any, Any, Any]]


@dataclass(frozen=True)
class SeymourButtonEntityDescription(
    ButtonEntityDescription, BaseEntityDescriptionMixin
):
    """Describes Trinnov button entity."""


BUTTONS: tuple[SeymourButtonEntityDescription, ...] = (
    SeymourButtonEntityDescription(
        icon="mdi:wrench",
        key="calibrate",
        name="Calibrate Motor(s)",
        press_action=lambda device: device.calibrate(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:octagon-outline",
        key="halt",
        name="Halt Motor(s)",
        press_action=lambda device: device.halt(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:home-circle-outline",
        key="home",
        name="Home Motor(s)",
        press_action=lambda device: device.home(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:arrow-collapse-horizontal",
        key="move_motors_in",
        name="Move Motor(s) In",
        press_action=lambda device: device.move_motors("in"),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:arrow-expand-horizontal",
        key="move_motors_out",
        name="Move Motor(s) Out",
        press_action=lambda device: device.move_motors("out"),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:refresh",
        key="positions",
        name="Get Motor Positions",
        press_action=lambda device: device.get_positions(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:refresh",
        key="settings_info",
        name="Get Settings Info",
        press_action=lambda device: device.get_settings_info(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:refresh",
        key="status",
        name="Get Ratio Status",
        press_action=lambda device: device.get_status(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:refresh",
        key="system_info",
        name="Get System Info",
        press_action=lambda device: device.get_system_info(),
    ),
    SeymourButtonEntityDescription(
        icon="mdi:resize",
        key="update_ratio",
        name="Update Selected Ratio",
        press_action=lambda device: device.update(),
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
    async_add_entities(SeymourButton(device, description) for description in BUTTONS)


class SeymourButton(SeymourEntity, ButtonEntity):
    """Representation of a Trinnov button."""

    _attr_has_entity_name = True

    entity_description: SeymourButtonEntityDescription

    def __init__(
        self,
        device: Device,
        entity_description: SeymourButtonEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self.device = device

    async def async_press(self) -> None:
        """Trigger the button action."""
        _LOGGER.debug("Button pressed: %s", self.entity_description.key)
        await self.entity_description.press_action(self.device)
