"""Async client for the Zidoo HTTP control API (port 9529)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import socket
from typing import Any

import aiohttp

from .const import API_PORT, POWER_OFF_KEY, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

STOPPED, PLAYING, PAUSED = "stopped", "playing", "paused"


class ZidooError(Exception):
    """Player did not answer or rejected the request."""


@dataclass
class ZidooState:
    online: bool = False
    mode: str | None = None  # "video", "music" or None
    status: str = STOPPED
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    path: str | None = None
    duration: float | None = None  # seconds
    position: float | None = None  # seconds
    video_info: dict[str, Any] = field(default_factory=dict)
    audio_index: int | None = None
    subtitle_index: int | None = None
    audio_tracks: dict[int, str] = field(default_factory=dict)
    subtitle_tracks: dict[int, str] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)  # name -> tag
    output_current: str | None = None
    volume: int | None = None
    volume_min: int = 0
    volume_max: int | None = None
    muted: bool | None = None
    volume_output: str | None = None  # e.g. "HDMI", "XLR"


def _tracks(items: list[dict] | None) -> dict[int, str]:
    result: dict[int, str] = {}
    for item in items or []:
        idx = item.get("index")
        if idx is not None:
            result[int(idx)] = str(item.get("title") or f"Track {idx}")
    return result


class ZidooClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, psk: str = "") -> None:
        self._session = session
        self.host = host
        self._base = f"http://{host}:{API_PORT}/"
        self._headers = {"Cache-Control": "no-cache"}
        if psk:
            self._headers["X-Auth-PSK"] = psk
        self.info: dict[str, Any] = {}
        self.macs: set[str] = set()
        self.apps: dict[str, str] = {}  # label -> package
        self._last_path: str | None = None

    # ------------------------------------------------------------ transport
    async def _get(self, path: str, params: dict[str, Any] | None = None,
                   timeout: float = REQUEST_TIMEOUT) -> dict[str, Any]:
        try:
            async with asyncio.timeout(timeout):
                async with self._session.get(
                    self._base + path, params=params, headers=self._headers
                ) as resp:
                    if resp.status != 200:
                        raise ZidooError(f"HTTP {resp.status} for {path}")
                    data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise ZidooError(f"{path}: {err}") from err
        if not isinstance(data, dict):
            raise ZidooError(f"Unexpected reply for {path}")
        return data

    async def _ok(self, path: str, params: dict[str, Any] | None = None) -> None:
        data = await self._get(path, params)
        if data.get("status") != 200:
            raise ZidooError(f"{path} returned status {data.get('status')}")

    # --------------------------------------------------------------- system
    async def get_model(self, timeout: float = 3) -> dict[str, Any]:
        data = await self._get("ZidooControlCenter/getModel", timeout=timeout)
        if data.get("status") != 200:
            raise ZidooError("getModel failed")
        self.info = data
        for key in ("net_mac", "wif_mac"):
            if mac := data.get(key):
                self.macs.add(mac)
        return data

    async def load_apps(self) -> dict[str, str]:
        data = await self._get("ZidooControlCenter/Apps/getApps")
        apps = {
            a["label"]: a["packageName"]
            for a in data.get("apps", [])
            if a.get("isCanOpen") and a.get("label") and a.get("packageName")
        }
        if apps:
            self.apps = dict(sorted(apps.items(), key=lambda kv: kv[0].lower()))
        return self.apps

    async def open_app(self, label: str) -> None:
        if label not in self.apps:
            await self.load_apps()
        package = self.apps.get(label, label)
        await self._ok("ZidooControlCenter/Apps/openApp", {"packageName": package})

    async def send_key(self, key: str) -> None:
        await self._ok("ZidooControlCenter/RemoteControl/sendkey", {"key": key})

    async def turn_on(self) -> None:
        """Power ON = Wake-on-LAN only.

        A magic packet is ignored by a running player, so this can never switch it off
        (unlike Key.PowerOn, which toggles).
        """
        await self.wake_on_lan()

    async def turn_off(self) -> None:
        """Power OFF = Key.PowerOn.Poweroff only (a one-way shutdown command).

        When the player is already off it has no IP address, so the request just fails.
        """
        try:
            await self.send_key(POWER_OFF_KEY)
        except ZidooError as err:
            _LOGGER.debug("Power-off not delivered (%s): player is probably already off", err)

    async def wake_on_lan(self, extra_mac: str | None = None) -> None:
        macs = set(self.macs)
        if extra_mac:
            macs.add(extra_mac)
        packets = []
        for mac in macs:
            raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
            if len(raw) == 6:
                packets.append(b"\xff" * 6 + raw * 16)
        if not packets:
            return

        # Global broadcast plus the /24 subnet broadcast of the player (e.g. 192.168.1.255),
        # which is what worked in the manual Wake-on-LAN test.
        targets = ["255.255.255.255"]
        parts = self.host.split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            targets.append(".".join(parts[:3] + ["255"]))

        def _send() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                for packet in packets:
                    for target in targets:
                        for port in (9, 7):
                            try:
                                sock.sendto(packet, (target, port))
                            except OSError as err:
                                _LOGGER.debug("WOL to %s:%s failed: %s", target, port, err)

        await asyncio.get_running_loop().run_in_executor(None, _send)

    # ---------------------------------------------------------------- state
    async def fetch_state(self, previous: ZidooState | None, with_outputs: bool) -> ZidooState:
        try:
            await self.get_model()
        except ZidooError:
            return ZidooState(online=False)

        state = ZidooState(online=True)
        music_data = await self._fetch_music_state()
        self._parse_volume(state, music_data)
        if not await self._fetch_video(state):
            self._fetch_music(state, music_data)

        if with_outputs or previous is None:
            await self._fetch_outputs(state)
        else:
            state.outputs, state.output_current = previous.outputs, previous.output_current

        # Track lists only change with the file: reuse them unless the path changed.
        if state.mode == "video":
            if previous and previous.path == state.path and previous.mode == "video":
                state.audio_tracks = previous.audio_tracks
                state.subtitle_tracks = previous.subtitle_tracks
            else:
                await self._fetch_tracks(state)
        return state

    async def _fetch_video(self, state: ZidooState) -> bool:
        try:
            data = await self._get("ZidooVideoPlay/getPlayStatus", timeout=2)
        except ZidooError:
            return False
        video = data.get("video")
        if data.get("status") != 200 or not video:
            return False
        state.mode = "video"
        state.status = PLAYING if video.get("status") == 1 else PAUSED
        state.title = video.get("title")
        state.path = video.get("path")
        self._last_path = state.path or self._last_path
        if (dur := video.get("duration")) is not None:
            state.duration = dur / 1000
        if (pos := video.get("currentPosition")) is not None:
            state.position = pos / 1000
        state.video_info = {
            "resolution": f"{video.get('width')}x{video.get('height')}"
            if video.get("width") else None,
            "fps": video.get("fps"),
            "bitrate": video.get("bitrate"),
            "audio_info": video.get("audioInfo"),
            "video_output": video.get("output"),
            "audio_track": (data.get("audio") or {}).get("information"),
            "subtitle": (data.get("subtitle") or {}).get("information"),
        }
        state.audio_index = (data.get("audio") or {}).get("index")
        state.subtitle_index = (data.get("subtitle") or {}).get("index")
        return True

    async def _fetch_music_state(self) -> dict[str, Any] | None:
        try:
            return await self._get("ZidooMusicControl/v2/getState", timeout=2)
        except ZidooError:
            return None

    @staticmethod
    def _parse_volume(state: ZidooState, data: dict[str, Any] | None) -> None:
        vol = (data or {}).get("volumeData")
        if not vol or not vol.get("isVolumeEnable", True):
            return
        # "currenttVolume" (sic) is the field name used by the Zidoo API.
        current = vol.get("currenttVolume", vol.get("currentVolume"))
        maximum = vol.get("maxVolume")
        if current is None or not maximum:
            return
        state.volume = int(current)
        state.volume_min = int(vol.get("minVolume") or 0)
        state.volume_max = int(maximum)
        state.muted = bool(vol.get("isMute"))
        state.volume_output = vol.get("volumeTag")

    def _fetch_music(self, state: ZidooState, data: dict[str, Any] | None) -> None:
        if not data:
            return
        music_state = data.get("state")
        music = data.get("playingMusic")
        if not music_state or not music:
            return
        state.mode = "music"
        state.status = PLAYING if music_state == 3 else PAUSED
        state.title = music.get("title")
        state.artist = music.get("artist")
        state.album = music.get("album")
        state.path = music.get("uri")
        if (dur := data.get("duration")) is not None:
            state.duration = dur / 1000
        if (pos := data.get("position")) is not None:
            state.position = pos / 1000

    async def _fetch_tracks(self, state: ZidooState) -> None:
        for path, attr in (
            ("ZidooVideoPlay/getAudioList", "audio_tracks"),
            ("ZidooVideoPlay/getSubtitleList", "subtitle_tracks"),
        ):
            try:
                data = await self._get(path, timeout=2)
            except ZidooError:
                continue
            # Firmware quirk: the audio list is also returned under "subtitles".
            items = data.get("audios") or data.get("subtitles") or []
            setattr(state, attr, _tracks(items))

    async def _fetch_outputs(self, state: ZidooState) -> None:
        try:
            data = await self._get("ZidooMusicControl/v2/getInputAndOutputList", timeout=2)
        except ZidooError:
            return
        if data.get("status") != 200:
            return
        all_outputs = data.get("outputData") or []
        state.outputs = {o["name"]: o.get("tag") for o in all_outputs if o.get("enable") and o.get("name")}
        idx = data.get("outputIndex")
        if isinstance(idx, int) and 0 <= idx < len(all_outputs):
            state.output_current = all_outputs[idx].get("name")

    # ------------------------------------------------------------- controls
    async def play(self, mode: str | None) -> None:
        if mode == "video":
            await self._ok("ZidooVideoPlay/changeStatus", {"status": 1})
        elif mode == "music":
            await self._ok("MusicControl/v2/playOrPause")
        elif self._last_path:
            await self.play_path(self._last_path)
        else:
            await self.send_key("Key.MediaPlay")

    async def pause(self, mode: str | None) -> None:
        if mode == "video":
            await self._ok("ZidooVideoPlay/changeStatus", {"status": 0})
        elif mode == "music":
            await self._ok("MusicControl/v2/playOrPause")
        else:
            await self.send_key("Key.MediaPause")

    async def next_track(self, mode: str | None) -> None:
        if mode == "music":
            await self._ok("MusicControl/v2/playNext")
        elif mode == "video":
            await self._ok("ZidooVideoPlay/changevideo", {"type": 0, "tag": 1})
        else:
            await self.send_key("Key.MediaNext")

    async def previous_track(self, mode: str | None) -> None:
        if mode == "music":
            await self._ok("MusicControl/v2/playLast")
        elif mode == "video":
            await self._ok("ZidooVideoPlay/changevideo", {"type": 0, "tag": 0})
        else:
            await self.send_key("Key.MediaPrev")

    async def chapter(self, forward: bool) -> None:
        await self._ok("ZidooVideoPlay/changevideo", {"type": 1, "tag": 1 if forward else 0})

    async def seek(self, mode: str | None, seconds: float) -> None:
        ms = int(seconds * 1000)
        if mode == "video":
            # "positon" (sic) is the parameter name used by the Zidoo API.
            await self._ok("ZidooVideoPlay/seekTo", {"positon": ms})
        elif mode == "music":
            await self._ok("ZidooMusicControl/seekTo", {"time": ms})

    async def set_audio_track(self, index: int) -> None:
        await self._ok("ZidooVideoPlay/setAudio", {"index": index})

    async def set_subtitle(self, index: int) -> None:
        await self._ok("ZidooVideoPlay/setSubtitle", {"index": index})

    async def set_output(self, tag: Any) -> None:
        await self._ok("ZidooMusicControl/v2/setOutInputList", {"tag": tag})

    async def set_volume(self, level: int) -> None:
        await self._ok("ZidooMusicControl/v2/setDevicesVolume", {"volume": level})

    async def play_path(self, path: str) -> None:
        """Play a file/URL known to the player (local path, smb://, nfs://, http://)."""
        await self._ok("ZidooFileControl/openFile", {"path": path, "videoplaymode": 0})
