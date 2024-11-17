"""Base Entity for Seymour Screen Masking Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN as SEYMOUR_DOMAIN,
    MANUFACTURER,
    NAME as SEYMOUR_NAME,
    SEYMOUR_UPDATE_SIGNAL,
)

if TYPE_CHECKING:
    from .pySeymour.device import SeymourScreenController as Device

_LOGGER = logging.getLogger(__name__)


class SeymourEntity(Entity):
    """Defines a base Seymour entity."""

    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        """Initialize entity."""
        self._device = device

        self._attr_unique_id = self._device.system_info.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(SEYMOUR_DOMAIN, self._device.system_info.serial_number)},
            hw_version=self._device.system_info.protocol_version,
            name=f"{SEYMOUR_NAME}",
            manufacturer=MANUFACTURER,
            model=device.system_info.screen_model,
            serial_number=self._device.system_info.serial_number,
            suggested_area="Theater",
            configuration_url="https://www.seymourscreenexcellence.com/screens.php",
        )

    def set_states(self) -> None:
        """Set all the states from the device to the entity."""

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""

        @callback
        def _update() -> None:
            """Update states for the current zone."""
            self.set_states()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SEYMOUR_UPDATE_SIGNAL}",
                _update,
            )
        )
