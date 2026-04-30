"""Coodinator for Nissan Leaf OBD BLE."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from bleak_retry_connector import BleakOutOfConnectionSlotsError
from py_nissan_leaf_obd_ble import NissanLeafObdBleApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# when the device is in range, and the car is on, poll quickly to get
# as much data as we can before it turns off
FAST_POLL_INTERVAL = timedelta(seconds=10)

# when the device is in range, but the car is off, we need to poll
# occasionally to see whether the car has be turned back on. On some cars
# this causes a relay to click every time, so this interval needs to be
# as long as possible to prevent excessive wear on the relay.
SLOW_POLL_INTERVAL = timedelta(minutes=5)

# when the device is out of range, use ultra slow polling since a bluetooth
# advertisement message will kick it back into life when back in range.
# see __init__.py: _async_specific_device_found()
ULTRA_SLOW_POLL_INTERVAL = timedelta(hours=1)

DEFAULT_FAST_POLL = 10   # poll interval when car is on
DEFAULT_SLOW_POLL = 300  # car off or connection error: retry every 5 min
DEFAULT_XS_POLL = 3600
DEFAULT_CACHE_VALUES = True
# Cap BLE read duration so HA's request_refresh debouncer lock is not held forever;
# otherwise BLE advertisements trigger async_request_refresh() but it no-ops (~70ms).
DEFAULT_FETCH_TIMEOUT = 90


class NissanLeafObdBleDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self, hass: HomeAssistant, address: str, api: NissanLeafObdBleApiClient, options
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FAST_POLL_INTERVAL,
            always_update=True,
        )
        self._address = address
        self.api = api
        self._cache_data: dict[str, Any] = {}
        self.options = options

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""

        # Prefer a connectable advertisement, but fall back to any seen advertisement.
        # Using async_address_present(connectable=True) as the sole gate causes the
        # coordinator to switch to xs_poll whenever the dongle stops advertising after
        # a GATT session ends -- which it does every time -- so it never reconnects
        # until the next HA restart. If the device was seen at all, attempt a connection
        # and let establish_connection fail naturally if it is truly unreachable.
        # Refresh the stored device object if a fresh advertisement is available.
        # Prefer connectable, fall back to any seen advertisement. If neither is
        # in the registry (dongle stopped advertising after last session), keep
        # the existing self.api._ble_device from __init__ and attempt anyway --
        # bleak_retry_connector will still try to connect via the proxy.
        # Only xs_poll if we have no device object at all (never been set up).
        _LOGGER.debug("Looking up BLE device for address %s", self._address)
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address.upper(), connectable=True
        ) or bluetooth.async_ble_device_from_address(
            self.hass, self._address.upper(), connectable=False
        )
        if ble_device:
            self.api._ble_device = ble_device

        if self.api._ble_device is None:
            _LOGGER.debug(
                "No BLE device object available, switching to xs_poll: %s",
                timedelta(seconds=self._xs_poll_interval),
            )
            self.update_interval = timedelta(seconds=self._xs_poll_interval)
            if self._cache_values and self._cache_data:
                return self._cache_data
            return {}

        try:
            new_data = await asyncio.wait_for(
                self.api.async_get_data(self.options),
                timeout=self._fetch_timeout,
            )
            if new_data is None:
                raise UpdateFailed("Failed to connect to OBD device")
            if len(new_data) == 0:
                # Car is probably off. Switch to slow polling inteval
                self.update_interval = timedelta(seconds=self._slow_poll_interval)
                _LOGGER.debug(
                    "Car is probably off, switch to slow polling: interval = %s",
                    self.update_interval,
                )
            else:
                self.update_interval = timedelta(seconds=self._fast_poll_interval)
                _LOGGER.debug(
                    "Car is on, polling: interval = %s",
                    self.update_interval,
                )
        except TimeoutError as err:
            self.update_interval = timedelta(seconds=self._slow_poll_interval)
            _LOGGER.debug("BLE fetch timed out, backing off to slow poll: %s", self.update_interval)
            if self._cache_values and self._cache_data:
                return self._cache_data
            raise UpdateFailed(
                f"BLE fetch timed out after {self._fetch_timeout}s"
            ) from err
        except BleakOutOfConnectionSlotsError:
            # Proxy has no free BLE connection slots; retrying every 5 min just makes it
            # worse. Clear the device reference so we enter xs_poll and go dormant until
            # the next BLE advertisement wakes us up via _async_specific_device_found.
            self.api._ble_device = None
            self.update_interval = timedelta(seconds=self._xs_poll_interval)
            _LOGGER.warning("BLE proxy out of connection slots; suspending until next advertisement")
            if self._cache_values and self._cache_data:
                return self._cache_data
            return {}
        except Exception as err:
            self.update_interval = timedelta(seconds=self._slow_poll_interval)
            _LOGGER.debug("BLE fetch error (%s), backing off to slow poll: %s", err, self.update_interval)
            if self._cache_values and self._cache_data:
                return self._cache_data
            raise UpdateFailed(f"Unable to fetch data: {err}") from err
        else:
            if self.options.get("cache_values", False):
                self._cache_data.update(new_data)
                return self._cache_data
            return new_data

    @property
    def options(self):
        """User configuration options."""
        return self._options

    @options.setter
    def options(self, options):
        """Set the configuration options."""
        self._options = options
        self._fast_poll_interval = options.get("fast_poll", DEFAULT_FAST_POLL)
        self._slow_poll_interval = options.get("slow_poll", DEFAULT_SLOW_POLL)
        self._xs_poll_interval = options.get("xs_poll", DEFAULT_XS_POLL)
        self._cache_values = options.get("cache_values", DEFAULT_CACHE_VALUES)
        self._fetch_timeout = float(
            options.get("fetch_timeout", DEFAULT_FETCH_TIMEOUT)
        )
