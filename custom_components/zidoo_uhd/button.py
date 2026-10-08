"""Buttons for Zidoo."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZidooConfigEntry
from .api import ZidooClient, ZidooError
from .entity import ZidooEntity


@dataclass(frozen=True, kw_only=True)
class ZidooButtonDescription(ButtonEntityDescription):
    press: Callable[[ZidooClient], Coroutine[Any, Any, None]]


BUTTONS = (
    # Home key triggers HDMI-CEC One Touch Play: the TV switches to the Zidoo input.
    ZidooButtonDescription(key="tv_input", translation_key="tv_input", icon="mdi:television-play",
                           press=lambda c: c.send_key("Key.Home")),
    ZidooButtonDescription(key="next_chapter", translation_key="next_chapter",
                           icon="mdi:skip-forward-outline", press=lambda c: c.chapter(True)),
    ZidooButtonDescription(key="previous_chapter", translation_key="previous_chapter",
                           icon="mdi:skip-backward-outline", press=lambda c: c.chapter(False)),
    ZidooButtonDescription(key="reboot", device_class=ButtonDeviceClass.RESTART,
                           press=lambda c: c.send_key("Key.PowerOn.Reboot")),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ZidooConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(ZidooButton(entry.runtime_data, entry, d) for d in BUTTONS)


class ZidooButton(ZidooEntity, ButtonEntity):
    entity_description: ZidooButtonDescription

    def __init__(self, coordinator, entry, description: ZidooButtonDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.online

    async def async_press(self) -> None:
        try:
            await self.entity_description.press(self.coordinator.client)
        except ZidooError as err:
            raise HomeAssistantError(f"Zidoo: {err}") from err
        await self.coordinator.async_request_refresh()
