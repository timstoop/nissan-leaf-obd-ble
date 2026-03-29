"""Custom integration to integrate Nissan Leaf OBD BLE with Home Assistant.

For more details about this integration, please refer to
https://github.com/pbutterworth/nissan-leaf-obd-ble
"""

import logging

from bleak_retry_connector import get_device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from py_nissan_leaf_obd_ble import NissanLeafObdBleApiClient
from .const import DOMAIN, PLATFORMS, STARTUP_MESSAGE
from .coordinator import NissanLeafObdBleDataUpdateCoordinator
from ._debug_agent import agent_log, set_debug_log_config_dir

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    # Debug NDJSON: primary path is <config>/nissan_leaf_debug_67a564.ndjson
    set_debug_log_config_dir(hass.config.config_dir)

    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find OBDBLE device with address {address}"
        )

    api = NissanLeafObdBleApiClient(ble_device)
    coordinator = NissanLeafObdBleDataUpdateCoordinator(
        hass, address=address, api=api, options=entry.options or {}
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _run_advert_wakeup() -> None:
        # #region agent log
        import time as _time_monotonic

        t0 = _time_monotonic.monotonic()
        agent_log(
            "__init__:_run_advert_wakeup",
            "task_start",
            {"address": address},
            "H1",
        )
        try:
            await coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            agent_log(
                "__init__:_run_advert_wakeup",
                "task_exception",
                {"err_type": type(err).__name__, "err": str(err)[:200]},
                "H3",
            )
            raise
        dt = _time_monotonic.monotonic() - t0
        agent_log(
            "__init__:_run_advert_wakeup",
            "after_async_request_refresh",
            {"seconds": round(dt, 4)},
            "H1",
        )
        # #endregion

    @callback
    def _async_specific_device_found(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle re-discovery of the device."""
        _LOGGER.debug("New service_info: %s - %s", service_info, change)
        # #region agent log
        agent_log(
            "__init__:_async_specific_device_found",
            "callback_fired",
            {"change": str(change)},
            "H3",
        )
        # #endregion
        # have just discovered the device is back in range - ping the coordinator to update immediately
        hass.async_create_task(_run_advert_wakeup())

    # stuff to do when cleaning up
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_specific_device_found,
            {"address": address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )  # does the register callback, and returns a cancel callback for cleanup
    )

    async def update_options_listener(hass: HomeAssistant | None, entry: ConfigEntry):
        """Handle options update."""
        coordinator.options = entry.options

    entry.async_on_unload(
        entry.add_update_listener(update_options_listener)
    )  # add the listener for when the user changes options

    # entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
