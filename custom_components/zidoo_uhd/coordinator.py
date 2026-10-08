"""Polling coordinator for Zidoo players."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import ZidooClient, ZidooState
from .const import DOMAIN, SCAN_INTERVAL_OFF, SCAN_INTERVAL_ON

_LOGGER = logging.getLogger(__name__)
OUTPUT_REFRESH_EVERY = 15  # polls


class ZidooCoordinator(DataUpdateCoordinator[ZidooState]):
    def __init__(self, hass: HomeAssistant, client: ZidooClient, name: str) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_ON),
        )
        self.client = client
        self.position_updated_at = None
        self._polls = 0
        # Last app opened from Home Assistant (the API cannot report the foreground app).
        self.last_app: str | None = None

    async def async_turn_on(self) -> None:
        """Wake the player, then poll quickly so the state follows the boot."""
        if await self.client.turn_on():
            await self.async_request_refresh()
            return
        for _ in range(12):  # up to ~60 s for the player to boot
            await asyncio.sleep(5)
            await self.async_refresh()
            if self.data and self.data.online:
                return

    def set_last_app(self, app: str | None) -> None:
        self.last_app = app
        self.async_update_listeners()

    async def _async_update_data(self) -> ZidooState:
        previous = self.data
        self._polls += 1
        state = await self.client.fetch_state(
            previous, with_outputs=self._polls % OUTPUT_REFRESH_EVERY == 1
        )

        if state.online and (previous is None or not previous.online):
            # Player just came online: refresh the app list for source selection.
            try:
                await self.client.load_apps()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Could not load app list")

        if not state.online:
            self.last_app = None
        elif previous is not None and previous.mode and not state.mode:
            # Playback just ended: the player returns to its browser/launcher.
            self.last_app = None

        if state.position is not None and (
            previous is None or previous.position != state.position
        ):
            self.position_updated_at = dt_util.utcnow()

        self.update_interval = timedelta(
            seconds=SCAN_INTERVAL_ON if state.online else SCAN_INTERVAL_OFF
        )
        return state
