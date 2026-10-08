"""Zidoo UHD media player integration."""
from __future__ import annotations

from aiohttp import CookieJar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ZidooClient
from .const import CONF_OFF_MODE, CONF_PSK, DEFAULT_NAME, DEFAULT_OFF_MODE
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
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZidooConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: ZidooConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ZidooConfigEntry) -> bool:
    """v1 -> v2: the old default (standby key) does not work on every model; use the power key."""
    if entry.version == 1:
        options = {**entry.options, CONF_OFF_MODE: DEFAULT_OFF_MODE}
        hass.config_entries.async_update_entry(entry, options=options, version=2)
    return True
