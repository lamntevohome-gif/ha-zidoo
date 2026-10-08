"""Media player for Zidoo."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZidooConfigEntry
from .api import PLAYING, ZidooError
from .const import CONF_OFF_MODE, OFF_POWEROFF, OFF_STANDBY
from .entity import ZidooEntity

FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ZidooConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ZidooMediaPlayer(entry.runtime_data, entry)])


class ZidooMediaPlayer(ZidooEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = FEATURES

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "media_player")

    @property
    def _data(self):
        return self.coordinator.data

    async def _run(self, coro: Awaitable[Any], refresh: bool = True) -> None:
        try:
            await coro
        except ZidooError as err:
            raise HomeAssistantError(f"Zidoo: {err}") from err
        if refresh:
            await self.coordinator.async_request_refresh()

    # ---------------------------------------------------------------- state
    @property
    def state(self) -> MediaPlayerState:
        data = self._data
        if not data or not data.online:
            return MediaPlayerState.OFF
        if data.mode is None:
            return MediaPlayerState.ON
        return MediaPlayerState.PLAYING if data.status == PLAYING else MediaPlayerState.PAUSED

    @property
    def media_content_type(self) -> MediaType | None:
        if not self._data:
            return None
        return {"video": MediaType.VIDEO, "music": MediaType.MUSIC}.get(self._data.mode)

    @property
    def media_title(self) -> str | None:
        return self._data.title if self._data else None

    @property
    def media_artist(self) -> str | None:
        return self._data.artist if self._data else None

    @property
    def media_album_name(self) -> str | None:
        return self._data.album if self._data else None

    @property
    def media_content_id(self) -> str | None:
        return self._data.path if self._data else None

    @property
    def media_duration(self) -> int | None:
        dur = self._data.duration if self._data else None
        return int(dur) if dur else None

    @property
    def media_position(self) -> int | None:
        pos = self._data.position if self._data else None
        return int(pos) if pos is not None else None

    @property
    def media_position_updated_at(self):
        return self.coordinator.position_updated_at

    @property
    def source_list(self) -> list[str]:
        return list(self.coordinator.client.apps)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        attrs: dict[str, Any] = {"mode": data.mode if data else None}
        if data and data.mode == "video":
            attrs.update({k: v for k, v in data.video_info.items() if v not in (None, "")})
        return attrs

    # ------------------------------------------------------------- commands
    async def async_turn_on(self) -> None:
        client = self.coordinator.client
        await client.wake_on_lan()
        try:
            await client.send_key("Key.PowerOn")
        except ZidooError:
            pass  # expected while the player is still asleep; WOL does the job
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        mode = self._entry.options.get(CONF_OFF_MODE, OFF_STANDBY)
        key = "Key.PowerOn.Poweroff" if mode == OFF_POWEROFF else "Key.PowerOn.Standby"
        await self._run(self.coordinator.client.send_key(key))

    async def async_media_play(self) -> None:
        await self._run(self.coordinator.client.play(self._data.mode if self._data else None))

    async def async_media_pause(self) -> None:
        await self._run(self.coordinator.client.pause(self._data.mode if self._data else None))

    async def async_media_stop(self) -> None:
        await self._run(self.coordinator.client.send_key("Key.MediaStop"))

    async def async_media_next_track(self) -> None:
        await self._run(self.coordinator.client.next_track(self._data.mode if self._data else None))

    async def async_media_previous_track(self) -> None:
        await self._run(
            self.coordinator.client.previous_track(self._data.mode if self._data else None)
        )

    async def async_media_seek(self, position: float) -> None:
        await self._run(self.coordinator.client.seek(self._data.mode if self._data else None, position))

    async def async_volume_up(self) -> None:
        await self._run(self.coordinator.client.send_key("Key.VolumeUp"), refresh=False)

    async def async_volume_down(self) -> None:
        await self._run(self.coordinator.client.send_key("Key.VolumeDown"), refresh=False)

    async def async_mute_volume(self, mute: bool) -> None:
        # The API only offers a mute toggle key.
        await self._run(self.coordinator.client.send_key("Key.Mute"), refresh=False)

    async def async_select_source(self, source: str) -> None:
        await self._run(self.coordinator.client.open_app(source))

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        await self._run(self.coordinator.client.play_path(media_id))
