"""Constants for Nissan Leaf OBD BLE."""

# Base component constants
from homeassistant.const import Platform

NAME = "Nissan Leaf OBD BLE"
DOMAIN = "nissan_leaf_obd_ble"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.3.1b2"

ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"
ISSUE_URL = "https://github.com/pbutterworth/nissan-leaf-obd-ble/issues"

# Platforms
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SERVICE_UUID = "service_uuid"
CONF_CHARACTERISTIC_UUID_READ = "characteristic_uuid_read"
CONF_CHARACTERISTIC_UUID_WRITE = "characteristic_uuid_write"

# Defaults (LeLink2 / OBDBLE adapters)
DEFAULT_NAME = DOMAIN
DEFAULT_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
DEFAULT_CHARACTERISTIC_UUID_READ = "0000ffe1-0000-1000-8000-00805f9b34fb"
DEFAULT_CHARACTERISTIC_UUID_WRITE = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Vgate iCar Pro 2S (IOS-Vlink) UUIDs
ICAR_PRO_2S_SERVICE_UUID = "000018f0-0000-1000-8000-00805f9b34fb"
ICAR_PRO_2S_CHARACTERISTIC_UUID_READ = "00002af0-0000-1000-8000-00805f9b34fb"
ICAR_PRO_2S_CHARACTERISTIC_UUID_WRITE = "00002af1-0000-1000-8000-00805f9b34fb"

# Maps BLE local name prefix -> UUID options for known adapters.
# Add a new entry here to support an additional adapter without touching config_flow.py.
DEVICE_UUID_PROFILES: dict[str, dict[str, str]] = {
    "IOS-Vlink": {
        CONF_SERVICE_UUID: ICAR_PRO_2S_SERVICE_UUID,
        CONF_CHARACTERISTIC_UUID_READ: ICAR_PRO_2S_CHARACTERISTIC_UUID_READ,
        CONF_CHARACTERISTIC_UUID_WRITE: ICAR_PRO_2S_CHARACTERISTIC_UUID_WRITE,
    },
}


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
