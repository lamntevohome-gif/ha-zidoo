"""Constants for the Zidoo UHD integration."""
from __future__ import annotations

DOMAIN = "zidoo_uhd"
DEFAULT_NAME = "Zidoo UHD8000"

SOURCE_VIDEO = "Video player"
SOURCE_MUSIC = "Music player"
SOURCE_HOME = "Home"
API_PORT = 9529

CONF_PSK = "psk"
POWER_OFF_KEY = "Key.PowerOn.Poweroff"  # discrete shutdown (ableRemoteShutdown)
WOL_BOOT_WAIT = 90  # seconds to follow the boot after Wake-on-LAN

SCAN_INTERVAL_ON = 2  # seconds while the player answers
SCAN_INTERVAL_OFF = 10  # seconds while it is off/unreachable
REQUEST_TIMEOUT = 4

# Friendly names accepted by remote.send_command -> Zidoo key codes.
# Any value starting with "Key." is passed through unchanged.
KEYS: dict[str, str] = {
    # Physical power button: toggles (turns a running player OFF). Use media_player.turn_on to wake.
    "power": "Key.PowerOn",
    "power_toggle": "Key.PowerOn",
    "standby": "Key.PowerOn.Standby",
    "power_off": "Key.PowerOn.Poweroff",
    "shutdown": "Key.PowerOn.Poweroff",
    "reboot": "Key.PowerOn.Reboot",
    "home": "Key.Home",
    "back": "Key.Back",
    "menu": "Key.Menu",
    "popup_menu": "Key.PopMenu",
    "info": "Key.Info",
    "up": "Key.Up",
    "down": "Key.Down",
    "left": "Key.Left",
    "right": "Key.Right",
    "ok": "Key.Ok",
    "enter": "Key.Ok",
    "select": "Key.Select",
    "play": "Key.MediaPlay",
    "pause": "Key.MediaPause",
    "play_pause": "Key.MediaPlay.Pause",
    "stop": "Key.MediaStop",
    "next": "Key.MediaNext",
    "previous": "Key.MediaPrev",
    "rewind": "Key.MediaBackward",
    "fast_forward": "Key.MediaForward",
    "volume_up": "Key.VolumeUp",
    "volume_down": "Key.VolumeDown",
    "mute": "Key.Mute",
    "subtitle": "Key.Subtitle",
    "audio": "Key.Audio",
    "repeat": "Key.Repeat",
    "resolution": "Key.Resolution",
    "page_up": "Key.PageUP",
    "page_down": "Key.PageDown",
    "red": "Key.UserDefine_A",
    "green": "Key.UserDefine_B",
    "yellow": "Key.UserDefine_C",
    "blue": "Key.UserDefine_D",
    "movie": "Key.movie",
    "music": "Key.music",
    "photo": "Key.photo",
    "file": "Key.file",
    "light": "Key.light",
    "mouse": "Key.Mouse",
    "screenshot": "Key.Screenshot",
    "app_switch": "Key.APP.Switch",
    "star": "Key.Star",
    "pound": "Key.Pound",
    **{str(n): f"Key.Number_{n}" for n in range(10)},
}


def resolve_key(command: str) -> str:
    command = command.strip()
    if command.startswith("Key."):
        return command
    lowered = command.lower().replace(" ", "_").replace("-", "_")
    if lowered.startswith("key_"):
        lowered = lowered[4:]
    if lowered not in KEYS:
        raise ValueError(f"Unknown Zidoo key: {command}")
    return KEYS[lowered]
