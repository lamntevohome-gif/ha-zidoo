"""Audio track, subtitle and audio output selects for Zidoo."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZidooConfigEntry
from .api import ZidooError
from .entity import ZidooEntity

SUB_OFF = "Off"


async def async_setup_entry(
    hass: HomeAssistant, entry: ZidooConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ZidooTrackSelect(coordinator, entry, "audio_track"),
            ZidooTrackSelect(coordinator, entry, "subtitle"),
            ZidooOutputSelect(coordinator, entry),
        ]
    )


def _label(index: int, title: str) -> str:
    return f"{index}: {title}"


class ZidooTrackSelect(ZidooEntity, SelectEntity):
    """Audio track or subtitle of the video currently playing."""

    def __init__(self, coordinator, entry, kind: str) -> None:
        super().__init__(coordinator, entry, kind)
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_icon = "mdi:subtitles" if kind == "subtitle" else "mdi:speaker-message"

    def _tracks(self) -> dict[int, str]:
        data = self.coordinator.data
        if not data or data.mode != "video":
            return {}
        return data.subtitle_tracks if self._kind == "subtitle" else data.audio_tracks

    @property
    def available(self) -> bool:
        return super().available and bool(self._tracks())

    @property
    def options(self) -> list[str]:
        return [_label(i, t) for i, t in self._tracks().items()]

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        index = data.subtitle_index if self._kind == "subtitle" else data.audio_index
        title = self._tracks().get(index) if index is not None else None
        return _label(index, title) if title is not None else None

    async def async_select_option(self, option: str) -> None:
        index = int(option.split(":", 1)[0])
        client = self.coordinator.client
        try:
            if self._kind == "subtitle":
                await client.set_subtitle(index)
            else:
                await client.set_audio_track(index)
        except ZidooError as err:
            raise HomeAssistantError(f"Zidoo: {err}") from err
        await self.coordinator.async_request_refresh()


class ZidooOutputSelect(ZidooEntity, SelectEntity):
    """Audio output (HDMI, HDMI audio, XLR/RCA analogue, SPDIF…)."""

    _attr_translation_key = "audio_output"
    _attr_icon = "mdi:audio-input-xlr"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "audio_output")

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return super().available and bool(data and data.online and data.outputs)

    @property
    def options(self) -> list[str]:
        data = self.coordinator.data
        return list(data.outputs) if data else []

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        return data.output_current if data else None

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data
        try:
            await self.coordinator.client.set_output(data.outputs[option])
        except (ZidooError, KeyError) as err:
            raise HomeAssistantError(f"Zidoo: {err}") from err
        data.output_current = option
        self.async_write_ha_state()
