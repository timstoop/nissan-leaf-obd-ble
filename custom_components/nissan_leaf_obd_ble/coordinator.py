"""Coodinator for Nissan Leaf OBD BLE."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.bluetooth.api import async_address_present
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from py_nissan_leaf_obd_ble import NissanLeafObdBleApiClient
from .const import DOMAIN
from ._debug_agent import agent_log

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

DEFAULT_FAST_POLL = 10  # pick sane defaults for your integration
DEFAULT_SLOW_POLL = 300
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
        # #region agent log
        agent_log(
            "coordinator:_async_update_data",
            "enter",
            {"address": self._address},
            "H2_H4",
        )
        # #endregion

        # Check if the device is still available
        _LOGGER.debug("Check if the device is still available to connect")
        available = async_address_present(self.hass, self._address, connectable=True)
        # #region agent log
        agent_log(
            "coordinator:_async_update_data",
            "address_present",
            {"available": available},
            "H2",
        )
        # #endregion
        if not available:
            # Device out of range? Switch to active polling interval for when it reappears
            _LOGGER.debug("Car out of range? Switch to extra slow polling")
            self.update_interval = timedelta(seconds=self._xs_poll_interval)
            _LOGGER.debug(
                "Car out of range? Switch to ultra slow polling: interval = %s",
                self.update_interval,
            )
            if self.options.get("cache_values", False):
                return self._cache_data
            return {}

        try:
            # #region agent log
            agent_log(
                "coordinator:_async_update_data",
                "before_async_get_data",
                {},
                "H4",
            )
            # #endregion
            new_data = await asyncio.wait_for(
                self.api.async_get_data(self.options),
                timeout=self._fetch_timeout,
            )
            # #region agent log
            agent_log(
                "coordinator:_async_update_data",
                "after_async_get_data",
                {
                    "new_data_len": len(new_data) if new_data is not None else None,
                    "is_none": new_data is None,
                },
                "H4_H5",
            )
            # #endregion
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
            # #region agent log
            agent_log(
                "coordinator:_async_update_data",
                "fetch_timeout",
                {"timeout_s": self._fetch_timeout},
                "post-fix",
            )
            # #endregion
            raise UpdateFailed(
                f"BLE fetch timed out after {self._fetch_timeout}s"
            ) from err
        except Exception as err:
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
