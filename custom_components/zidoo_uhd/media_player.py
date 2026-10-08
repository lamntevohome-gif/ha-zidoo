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
from .const import (
    CONF_OFF_MODE,
    DEFAULT_OFF_MODE,
    OFF_KEYS,
    SOURCE_HOME,
    SOURCE_MUSIC,
    SOURCE_VIDEO,
)
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

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "media_player")

    @property
    def _data(self):
        return self.coordinator.data

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        data = self._data
        if data and data.volume_max:
            return FEATURES | MediaPlayerEntityFeature.VOLUME_SET
        return FEATURES

    @property
    def volume_level(self) -> float | None:
        data = self._data
        if not data or data.volume is None or not data.volume_max:
            return None
        span = data.volume_max - data.volume_min
        return max(0.0, min(1.0, (data.volume - data.volume_min) / span)) if span else None

    @property
    def is_volume_muted(self) -> bool | None:
        return self._data.muted if self._data else None

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
        return [SOURCE_HOME, *self.coordinator.client.apps]

    @property
    def source(self) -> str | None:
        data = self._data
        if not data or not data.online:
            return None
        if data.mode == "video":
            return SOURCE_VIDEO
        if data.mode == "music":
            return SOURCE_MUSIC
        return self.coordinator.last_app

    @property
    def _source_origin(self) -> str | None:
        data = self._data
        if data and data.online and data.mode:
            return "player"  # reported by the Zidoo API
        if self.coordinator.last_app:
            return "home_assistant"  # last app opened from Home Assistant
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        attrs: dict[str, Any] = {
            "mode": data.mode if data else None,
            "source_origin": self._source_origin,
        }
        if data and data.volume is not None:
            attrs.update(
                volume_raw=data.volume,
                volume_max=data.volume_max,
                volume_output=data.volume_output,
            )
        if data and data.mode == "video":
            attrs.update({k: v for k, v in data.video_info.items() if v not in (None, "")})
        return attrs

    # ------------------------------------------------------------- commands
    async def async_turn_on(self) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        mode = self._entry.options.get(CONF_OFF_MODE, DEFAULT_OFF_MODE)
        key = OFF_KEYS.get(mode, OFF_KEYS[DEFAULT_OFF_MODE])
        await self._run(self.coordinator.client.turn_off(key))
        self.coordinator.set_last_app(None)

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

    async def async_set_volume_level(self, volume: float) -> None:
        data = self._data
        if not data or not data.volume_max:
            raise HomeAssistantError("Zidoo không báo mức âm lượng cho ngõ ra hiện tại")
        level = round(data.volume_min + volume * (data.volume_max - data.volume_min))
        await self._run(self.coordinator.client.set_volume(level), refresh=False)
        data.volume = level  # optimistic; confirmed by the next poll
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        await self._run(self.coordinator.client.send_key("Key.VolumeUp"))

    async def async_volume_down(self) -> None:
        await self._run(self.coordinator.client.send_key("Key.VolumeDown"))

    async def async_mute_volume(self, mute: bool) -> None:
        # The API only offers a mute toggle key: send it only when the state must change.
        data = self._data
        if data and data.muted is not None and data.muted == mute:
            return
        await self._run(self.coordinator.client.send_key("Key.Mute"), refresh=False)
        if data and data.muted is not None:
            data.muted = mute  # optimistic; confirmed by the next poll
            self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        if source == SOURCE_HOME:
            await self._run(self.coordinator.client.send_key("Key.Home"))
        else:
            await self._run(self.coordinator.client.open_app(source))
        self.coordinator.set_last_app(source)

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        await self._run(self.coordinator.client.play_path(media_id))
