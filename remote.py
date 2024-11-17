"""Remote platform for Seymour Screen Masking Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN as SEYMOUR_DOMAIN
from .entity import SeymourEntity
from .pySeymour.constants import MOTOR_IDS

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .pySeymour.device import SeymourScreenController as Device

VALID_COMMANDS = {
    "clear",
    "halt",
    "home",
    "diagnostics",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    device_entry = hass.data[SEYMOUR_DOMAIN][config_entry.entry_id]
    device: Device = device_entry["device"]
    entity = SeymourRemote(device)
    async_add_entities([entity])

    ratio_id_list = []

    for ratio_key in device.mask_ratio_settings.ratios:
        ratio_id_list.append(ratio_key)
        service_name = f"set_aspect_ratio_{ratio_key}"

        async def set_aspect_ratio(call, ratio_key=ratio_key):
            """Service to set aspect ratio using the key."""
            await entity.async_send_command("set_aspect_ratio", AR=ratio_key)

        hass.services.async_register(SEYMOUR_DOMAIN, service_name, set_aspect_ratio)
        _LOGGER.debug("Registered service: %s with AR key: %s", service_name, ratio_key)

    hass.services.async_register(
        SEYMOUR_DOMAIN,
        "move_motors",
        entity.move_motors_service,
        schema=vol.Schema(
            {
                vol.Required("direction"): vol.In(["in", "out"]),
                vol.Required("motor_id"): vol.In(list(MOTOR_IDS.keys())),
                vol.Optional("movement_code", default=None): vol.Any(None, "J", "P"),
            }
        ),
    )

    hass.services.async_register(
        SEYMOUR_DOMAIN,
        "home_motors",
        entity.home_motors_service,
        schema=vol.Schema(
            {
                vol.Required("motor_id"): vol.In(list(MOTOR_IDS.keys())),
            }
        ),
    )

    hass.services.async_register(
        SEYMOUR_DOMAIN,
        "halt_motors",
        entity.halt_motors_service,
        schema=vol.Schema(
            {
                vol.Required("motor_id"): vol.In(list(MOTOR_IDS.keys())),
            }
        ),
    )

    hass.services.async_register(
        SEYMOUR_DOMAIN,
        "calibrate_motors",
        entity.calibrate_motors_service,
        schema=vol.Schema(
            {
                vol.Required("motor_id"): vol.In(list(MOTOR_IDS.keys())),
            }
        ),
    )

    options = ratio_id_list + list(range(990, 1000))

    hass.services.async_register(
        SEYMOUR_DOMAIN,
        "update_ratio",
        entity.update_ratio_service,
        schema=vol.Schema({vol.Required("ratio_id"): vol.In(options)}),
    )


class SeymourRemote(SeymourEntity, RemoteEntity):
    """Representation of a Seymour Controller without on/off switch."""

    _attr_has_entity_name = True
    _attr_name = "Remote"

    def __init__(self, device) -> None:
        """Initialize the Seymour remote."""
        super().__init__(device)
        self._available = True
        self._supported_features = RemoteEntityFeature.ACTIVITY
        self.device: Device = device

    @property
    def state(self) -> str | None:  # noqa: property override
        """Override the state to prevent switch behavior."""
        return ""

    @property
    def is_on(self) -> bool:  # noqa: property override
        """Override the is_on property to prevent toggles."""
        return True

    @property
    def supported_features(self) -> int:
        """Disable all features to remove the on/off switch."""
        return self._supported_features

    @property
    def assumed_state(self) -> bool:
        """Indicate that this entity does not have a definite state."""
        return True

    @property
    def available(self) -> bool:
        """Ensure the remote entity is marked as available."""
        return self._available

    async def async_send_command(
        self, command: str, AR: str = "", **kwargs: Any
    ) -> None:
        """Send a command to the remote, with optional AR argument for select_ar."""

        if command == "set_aspect_ratio":
            if not AR:
                raise HomeAssistantError(
                    "AR parameter is required for select_ar command"
                )
            _LOGGER.debug("Sending command: %s with AR: %s", command, AR)
            try:
                await self.device.select_ratio(AR)
            except ConnectionError as conn_err:
                _LOGGER.error(
                    "Connection error while sending select_ratio: %s", conn_err
                )
            except ValueError as val_err:
                _LOGGER.error("Invalid value for AR in select_ratio: %s", val_err)
            except HomeAssistantError as ha_err:
                _LOGGER.error(
                    "Home Assistant specific error in select_ratio: %s", ha_err
                )
        else:
            for cmd in command:
                if cmd not in VALID_COMMANDS:
                    raise HomeAssistantError(f"{cmd} is not a known command")
                _LOGGER.debug("Sending Remote Command: %s", cmd)
                await getattr(self._device, cmd)()

    async def move_motors_service(self, call: ServiceCall) -> None:
        """Handle the move_motors service call."""

        direction: str = call.data.get("direction")
        motor_id: str = call.data.get("motor_id")
        motor_description = MOTOR_IDS.get(motor_id, motor_id)
        movement_code: str | None = call.data.get("movement_code")
        _LOGGER.debug(
            "Moving motor(s) '%s' (%s) in direction: %s with movement code: %s",
            motor_id,
            motor_description,
            direction,
            movement_code,
        )

        try:
            self.device.mask_ratio_settings.current_movement_code = movement_code
            if direction == "in":
                await self.device.move_motors("in", motor_id)
            elif direction == "out":
                await self.device.move_motors("out", motor_id)
            else:
                _LOGGER.error("Invalid direction: %s", direction)
        except ConnectionError as conn_err:
            _LOGGER.error(
                "Connection error while moving motor(s) '%s': %s", motor_id, conn_err
            )
        except ValueError as val_err:
            _LOGGER.error("Invalid motor value or direction for movement: %s", val_err)

    async def home_motors_service(self, call: ServiceCall) -> None:
        """Handle the home_motors service call."""

        motor_id: str = call.data.get("motor_id")
        motor_description = MOTOR_IDS.get(motor_id, motor_id)
        _LOGGER.debug("Homing motor(s) '%s' (%s)", motor_id, motor_description)

        try:
            await self.device.home(motor_id)
        except ConnectionError as conn_err:
            _LOGGER.error(
                "Connection error while homing motor(s) '%s': %s", motor_id, conn_err
            )
        except ValueError as val_err:
            _LOGGER.error("Invalid motor value for homing: %s", val_err)

    async def halt_motors_service(self, call: ServiceCall) -> None:
        """Handle the halt_motors service call."""

        motor_id: str = call.data.get("motor_id")
        motor_description = MOTOR_IDS.get(motor_id, motor_id)
        _LOGGER.debug("Halting motor(s) '%s' (%s)", motor_id, motor_description)

        try:
            await self.device.halt(motor_id)
        except ConnectionError as conn_err:
            _LOGGER.error(
                "Connection error while halting motor(s) '%s': %s", motor_id, conn_err
            )
        except ValueError as val_err:
            _LOGGER.error("Invalid motor value for halting: %s", val_err)

    async def calibrate_motors_service(self, call: ServiceCall) -> None:
        """Handle the calibrate_motors service call."""

        motor_id: str = call.data.get("motor_id")
        motor_description = MOTOR_IDS.get(motor_id, motor_id)
        _LOGGER.debug("Calibrating Motor(s) '%s' (%s)", motor_id, motor_description)

        try:
            await self.device.calibrate(motor_id)
        except ConnectionError as conn_err:
            _LOGGER.error(
                "Connection error while calibrating motor(s) '%s': %s",
                motor_id,
                conn_err,
            )
        except ValueError as val_err:
            _LOGGER.error("Invalid motor value for calibrating: %s", val_err)

    async def update_ratio_service(self, call: ServiceCall) -> None:
        """Handle the update_ratio service call."""

        # Retrieve and validate the 3-byte integer ratio_id
        ratio_id: int = call.data.get("ratio_id")

        _LOGGER.debug("Updating ratio with ratio_id: %s", ratio_id)

        try:
            await self.device.update(ratio_id)
        except ConnectionError as conn_err:
            _LOGGER.error(
                "Connection error while updating ratio with ID '%s': %s",
                ratio_id,
                conn_err,
            )
        except ValueError as val_err:
            _LOGGER.error("Invalid ratio ID for update: %s", val_err)

    @property
    def should_poll(self) -> bool:
        """Disable polling as this entity does not require regular updates."""
        return False
