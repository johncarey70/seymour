"""The Seymour Screen Masking Controller Integration."""

from __future__ import annotations

import asyncio
import logging
from pprint import pformat

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.loader import async_get_integration

from .const import DOMAIN, NAME, SEYMOUR_UPDATE_SIGNAL, STARTUP_MESSAGE
from .pySeymour.device import SeymourScreenController as Device, SystemInfo

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Seymour from a config entry."""

    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(STARTUP_MESSAGE, NAME, integration.version)

    @callback
    def seymour_update_callback(message: str) -> None:
        """Receive notification from transport that new data exists."""
        async_dispatcher_send(hass, SEYMOUR_UPDATE_SIGNAL)

    device = Device(entry.data["serial_port"], seymour_update_callback)
    device.system_info = SystemInfo(**entry.data)
    _LOGGER.debug("System Info:\n%s", pformat(device.system_info.to_dict()))

    try:
        await device.connect()
        await device.get_settings_info()
        await device.get_status()
        await device.get_positions()

        timeout = 10  # seconds
        interval = 0.5  # check every 0.5 seconds
        elapsed_time = 0

        while not device.current_motor_positions.num_motors and elapsed_time < timeout:
            await asyncio.sleep(interval)
            elapsed_time += interval

        if not device.current_motor_positions.num_motors:
            _LOGGER.error("Timed out waiting for motor positions to be populated")
            return False
    except TimeoutError as e:
        _LOGGER.error("Connection to Seymour device timed out: %s", e)
        return False
    except OSError as e:
        _LOGGER.error("OS error while connecting to Seymour device: %s", e)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "device": device,
        "disconnect": None,
    }

    async def disconnect() -> None:
        """Close the connection to the Seymour device when Home Assistant stops or entry is unloaded."""
        await device.close()

    hass.data[DOMAIN][entry.entry_id]["disconnect"] = disconnect

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        disconnect = hass.data[DOMAIN][entry.entry_id].get("disconnect")
        if disconnect:
            await disconnect()

    hass.data[DOMAIN].pop(entry.entry_id, None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
