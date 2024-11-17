"""Config flow for Seymour Integration."""

import logging
import uuid

import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.usb import UsbServiceInfo
from homeassistant.core import callback

from .const import DOMAIN
from .pySeymour.constants import BAUDRATE
from .pySeymour.device import SeymourScreenController as Device

_LOGGER = logging.getLogger(__name__)


class SerialConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the serial port configuration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user enters the serial port."""
        errors = {}
        available_ports = self._discover_serial_ports()
        _LOGGER.debug("Discovered serial ports: %s", available_ports)

        if user_input is not None:
            port = user_input["serial_port"]

            if not self._is_valid_port(port):
                errors["base"] = "invalid_port"
            else:
                try:
                    info = await self._configure_device(port)
                except TimeoutError as e:
                    errors["base"] = "connection_failed"
                    _LOGGER.error("Failed to connect to device: %s", e)
                else:
                    await self.async_set_unique_id(info["serial_number"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Seymour Controller ({port})", data=info
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "serial_port",
                        default=available_ports[0]
                        if available_ports
                        else "/dev/ttyUSB0",
                    ): vol.In(available_ports or ["/dev/ttyUSB0"])
                }
            ),
            description_placeholders={"example_port": "/dev/ttyUSB0"},
            errors=errors,
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo):
        """Handle USB discovery."""
        _LOGGER.debug("Discovered USB device: %s", discovery_info)

        # Extract USB device details
        port = discovery_info.device
        serial_number = discovery_info.serial_number or str(uuid.uuid4())
        vid = discovery_info.vid
        pid = discovery_info.pid

        if not all([port, serial_number, vid, pid]):
            _LOGGER.error("Invalid USB discovery info: %s", discovery_info)
            return self.async_abort(reason="invalid_discovery_info")

        _LOGGER.debug(
            "USB device details: VID=%s, PID=%s, Serial=%s, Port=%s",
            vid,
            pid,
            serial_number,
            port,
        )

        # Check if the device is already configured
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        # Query the device to validate communication
        try:
            device_response = await self._query_serial_device(port)
            if device_response is None:
                _LOGGER.error("Failed to query the USB device at port: %s", port)
                return self.async_abort(reason="device_unresponsive")
        except serial.SerialException as e:
            _LOGGER.error("Serial communication error on port %s: %s", port, e)
            return self.async_abort(reason="serial_communication_error")
        except UnicodeDecodeError as e:
            _LOGGER.error(
                "Failed to decode response from device on port %s: %s", port, e
            )
            return self.async_abort(reason="invalid_device_response")
        except ValueError as e:
            _LOGGER.error("Unexpected data format from device on port %s: %s", port, e)
            return self.async_abort(reason="data_format_error")
        except OSError as e:
            _LOGGER.error("Operating system error while accessing port %s: %s", port, e)
            return self.async_abort(reason="os_error")

        # Store discovery data for user confirmation
        self.context["title_placeholders"] = {
            "title": "Seymour Screen Excellence",
            "serial_port": port,
            "name": device_response[3:19],
            "type": "",
        }
        self.context["discovery_info"] = discovery_info

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm addition of the discovered device."""
        errors = {}

        # Retrieve discovery info from the context
        discovery_info: UsbServiceInfo = self.context["discovery_info"]
        port = discovery_info.device
        serial_number = discovery_info.serial_number or str(uuid.uuid4())

        if user_input is not None:
            try:
                info = await self._configure_device(port)
            except TimeoutError as e:
                errors["base"] = "connection_failed"
                _LOGGER.error("Failed to connect to device at %s: %s", port, e)
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Seymour Controller ({port})",
                    data=info,
                )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"serial_port": port},
            errors=errors,
            data_schema=vol.Schema({}),
        )

    async def _configure_device(self, port):
        """Configure the device and retrieve its system information."""
        device = Device(port, None)
        await device.connect(read_info=True)
        return {
            "height": device.system_info.height,
            "mask_ids": device.system_info.mask_ids,
            "protocol_version": device.system_info.protocol_version,
            "screen_model": device.system_info.screen_model,
            "serial_number": device.system_info.serial_number,
            "serial_port": port,
            "width": device.system_info.width,
        }

    @staticmethod
    @callback
    def _is_valid_port(port: str):
        """Validate the provided port string."""
        return port.startswith("/dev/")

    @staticmethod
    @callback
    def _discover_serial_ports():
        """Discover available serial ports."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            _LOGGER.debug("Port details: %s", port)
        return [port.device for port in ports if port.device]

    @staticmethod
    async def _query_serial_device(port):
        """Query the device connected to the serial port to identify it."""
        try:
            with serial.Serial(port, baudrate=BAUDRATE, timeout=2) as ser:
                ser.write(b"[01Y]")
                response = ser.read_until(b"]").decode().strip()
                if response.startswith("[01") and response.endswith("]"):
                    _LOGGER.debug("Device identified on port %s: %s", port, response)
                    return response
                _LOGGER.debug("Unexpected response on port %s: %s", port, response)
        except serial.SerialException as e:
            _LOGGER.error("Serial exception on port %s: %s", port, e)
        except UnicodeDecodeError as e:
            _LOGGER.error("Unicode decode error on port %s: %s", port, e)
        except ValueError as e:
            _LOGGER.error("Value error on port %s: %s", port, e)
        except OSError as e:
            _LOGGER.error("OSError on port %s: %s", port, e)

        _LOGGER.debug("Device not identified on port %s", port)
        return None
