"""Zidoo UHD media player integration."""
from __future__ import annotations

from aiohttp import CookieJar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ZidooClient
from .const import CONF_PSK, DEFAULT_NAME
from .coordinator import ZidooCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE, Platform.SELECT, Platform.BUTTON]

type ZidooConfigEntry = ConfigEntry[ZidooCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ZidooConfigEntry) -> bool:
    session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    client = ZidooClient(session, entry.data[CONF_HOST], entry.data.get(CONF_PSK, ""))
    if mac := entry.data.get(CONF_MAC):
        client.macs.add(mac)

    coordinator = ZidooCoordinator(hass, client, entry.data.get(CONF_NAME, DEFAULT_NAME))
    # The player may be in standby at startup; that is a valid state, not an error.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZidooConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ZidooConfigEntry) -> bool:
    """v1/v2 -> v3: power commands are fixed now (ON = Wake-on-LAN, OFF = Key.PowerOn.Poweroff)."""
    if entry.version < 3:
        options = {k: v for k, v in entry.options.items() if k != "off_mode"}
        hass.config_entries.async_update_entry(entry, options=options, version=3)
    return True
