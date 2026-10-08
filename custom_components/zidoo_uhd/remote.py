"""Remote entity for Zidoo: send any key (home, ok, up, Key.Home, …)."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZidooConfigEntry
from .api import ZidooError
from .const import SOURCE_HOME, resolve_key
from .entity import ZidooEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ZidooConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ZidooRemote(entry.runtime_data, entry)])


class ZidooRemote(ZidooEntity, RemoteEntity):
    _attr_name = "Remote"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "remote")

    @property
    def is_on(self) -> bool:
        return self.online

    async def async_turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        await self.coordinator.client.wake_on_lan()
        try:
            await self.coordinator.client.send_key("Key.PowerOn")
        except ZidooError:
            pass
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, activity: str | None = None, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.send_key("Key.PowerOn.Standby")
        except ZidooError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        try:
            keys = [resolve_key(cmd) for cmd in command]
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        first = True
        for _ in range(repeats):
            for key in keys:
                if not first:
                    await asyncio.sleep(delay)
                first = False
                try:
                    await self.coordinator.client.send_key(key)
                except ZidooError as err:
                    raise HomeAssistantError(f"Zidoo: {err}") from err
                if key == "Key.Home":
                    self.coordinator.set_last_app(SOURCE_HOME)
