"""Sensor platform for Seymour Screen Masking Integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .const import DOMAIN as SEYMOUR_DOMAIN
from .entity import SeymourEntity
from .pySeymour.constants import MOTOR_IDS, STATUS_CODES

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .pySeymour.device import SeymourScreenController as Device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BaseEntityDescriptionMixin:
    """Mixin for required descriptor keys."""

    value_fn: Callable[[Device], StateType]


@dataclass(frozen=True)
class SeymourSensorEntityDescription(
    SensorEntityDescription, BaseEntityDescriptionMixin
):
    """Describes Seymour sensor entity."""

    motor_id: str | None = None  # Motor ID, e.g., 'T', 'B', 'L', 'R'
    motor_index: int | None = None  # Position in the info sequence


SENSOR_TYPES: tuple[SeymourSensorEntityDescription, ...] = (
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="current_ratio_id",
        name="Current Aspect Ratio",
        translation_key="current_ratio_id",
        value_fn=lambda device: device.current_ratio_status.ratio_id,
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="current_status_code",
        name="Current Status",
        translation_key="current_status_code",
        value_fn=lambda device: STATUS_CODES.get(
            device.current_ratio_status.status_code, "Unknown"
        ),
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:engine",
        key="num_motors",
        name="Number of Motors",
        translation_key="num_motors",
        value_fn=lambda device: device.current_motor_positions.num_motors,
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:aspect-ratio",
        key="num_ratios",
        name="Number of Ratios",
        translation_key="num_ratios",
        value_fn=lambda device: device.mask_ratio_settings.num_ratios,
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:arrow-expand-horizontal",
        key="width",
        name="Screen Width",
        translation_key="width",
        value_fn=lambda device: device.mask_ratio_settings.ratios[
            device.mask_ratio_settings.current_ratio
        ].width,
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:arrow-expand-vertical",
        key="height",
        name="Screen Height",
        translation_key="height",
        value_fn=lambda device: device.mask_ratio_settings.ratios[
            device.mask_ratio_settings.current_ratio
        ].height,
    ),
    SeymourSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:arrow-expand",
        key="diagonal",
        name="Screen Diagonal",
        translation_key="diagonal",
        value_fn=lambda device: device.mask_ratio_settings.ratios[
            device.mask_ratio_settings.current_ratio
        ].diagonal,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    device_entry = hass.data[SEYMOUR_DOMAIN][config_entry.entry_id]
    device: Device = device_entry["device"]

    sensor_descriptions = list(SENSOR_TYPES)

    if hasattr(device.system_info, "mask_ids") and device.system_info.mask_ids:
        for motor_id in device.system_info.mask_ids:
            motor_label = motor_id.upper()
            motor_desc = MOTOR_IDS.get(motor_label, motor_label)

            sensor_descriptions.append(
                SeymourSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    icon="mdi:axis-arrow",
                    key=f"motor_{motor_label}_position",
                    name=f"Motor {motor_desc} Position",
                    translation_key=f"motor_{motor_label}_position",
                    motor_id=motor_label,
                    motor_index=ord(motor_label) - ord("A"),
                    value_fn=lambda device: None,
                )
            )

            sensor_descriptions.append(
                SeymourSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    icon="mdi:axis-arrow",
                    key=f"motor_{motor_label}_adjustment",
                    name=f"Motor {motor_desc} Adjustment",
                    translation_key=f"motor_{motor_label}_adjustment",
                    motor_id=motor_label,
                    motor_index=ord(motor_label) - ord("A"),
                    value_fn=lambda device: None,
                )
            )

    if device.current_motor_positions and device.current_motor_positions.motors:
        for motor_id in device.current_motor_positions.motors:
            motor_desc = MOTOR_IDS.get(motor_id, motor_id)

            sensor_descriptions.append(
                SeymourSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    icon="mdi:axis-arrow",
                    key=f"motor_{motor_id}_current_position",
                    name=f"Current {motor_desc} Motor Position",
                    translation_key=f"motor_{motor_id}_current_position",
                    motor_id=motor_id,
                    value_fn=lambda device,
                    motor_id=motor_id: device.current_motor_positions.motors.get(
                        motor_id
                    ),
                )
            )

    async_add_entities(
        SeymourSensor(device, description) for description in sensor_descriptions
    )


class SeymourSensor(SeymourEntity, SensorEntity):
    """Representation of a Seymour sensor."""

    def __init__(
        self,
        device: Device,
        entity_description: SeymourSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"

        self.set_states()

    @property
    def native_value(self) -> StateType:
        """Return the latest value of the sensor."""
        if (
            self.entity_description.motor_id
            and self.entity_description.motor_index is not None
        ):
            try:
                # Retrieve the current ratio
                current_ratio_id = self._device.mask_ratio_settings.current_ratio
                current_ratio = self._device.mask_ratio_settings.ratios.get(
                    current_ratio_id
                )

                if not current_ratio:
                    _LOGGER.warning("Current ratio '%s' not found", current_ratio_id)
                    return None

                # Retrieve and validate mask IDs
                raw_mask_ids = self._device.system_info.mask_ids
                if not raw_mask_ids:
                    _LOGGER.warning("Mask IDs are missing or empty")
                    return None

                # Parse mask IDs into a list of motor labels
                if "," in raw_mask_ids:
                    mask_ids_list = [
                        id.strip().upper() for id in raw_mask_ids.split(",")
                    ]
                else:
                    mask_ids_list = list(raw_mask_ids.upper())  # Split into characters

                # Normalize the motor label
                motor_label = self.entity_description.motor_id.upper()
                if motor_label not in mask_ids_list:
                    _LOGGER.warning(
                        "Motor label '%s' is not in mask IDs %s",
                        motor_label,
                        mask_ids_list,
                    )
                    return None

                # Calculate motor index dynamically
                motor_index = mask_ids_list.index(motor_label) + 1

                # Get the MotorInfo for the calculated motor index
                motor_info = current_ratio.motors.get(motor_index)

                if not motor_info:
                    _LOGGER.warning(
                        "Motor info not found for motor index '%d' in ratio '%s'",
                        motor_index,
                        current_ratio_id,
                    )
                    return None

                # Retrieve and return position or adjustment based on the sensor key
                if "position" in self.entity_description.key:
                    if motor_info.position is not None:
                        return motor_info.position
                    _LOGGER.warning(
                        "Position is not set for motor index '%d' in ratio '%s'",
                        motor_index,
                        current_ratio_id,
                    )
                    return None
                elif "adjustment" in self.entity_description.key:
                    if motor_info.adjustment is not None:
                        return motor_info.adjustment
                    _LOGGER.warning(
                        "Adjustment is not set for motor index '%d' in ratio '%s'",
                        motor_index,
                        current_ratio_id,
                    )
                    return None

                _LOGGER.warning(
                    "Sensor key '%s' does not match 'position' or 'adjustment'",
                    self.entity_description.key,
                )
                return None
            except ValueError as error:
                _LOGGER.error(
                    "ValueError while calculating motor index for motor ID '%s': %s",
                    self.entity_description.motor_id,
                    error,
                )
                return None
            except KeyError as error:
                _LOGGER.error(
                    "KeyError while retrieving motor data for motor index '%s': %s",
                    motor_index,
                    error,
                )
                return None
            except TypeError as error:
                _LOGGER.error(
                    "TypeError while retrieving motor data for motor index '%s': %s",
                    motor_index,
                    error,
                )
                return None

        return self.entity_description.value_fn(self._device)
