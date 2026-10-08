"""Config flow for Zidoo UHD."""
from __future__ import annotations

from typing import Any

from aiohttp import CookieJar
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .api import ZidooClient, ZidooError
from .const import CONF_OFF_MODE, CONF_PSK, DEFAULT_NAME, DOMAIN, OFF_POWEROFF, OFF_STANDBY


class ZidooConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            psk = user_input.get(CONF_PSK, "").strip()
            session = async_create_clientsession(self.hass, cookie_jar=CookieJar(unsafe=True))
            client = ZidooClient(session, host, psk)
            try:
                info = await client.get_model()
            except ZidooError:
                errors["base"] = "cannot_connect"
            else:
                mac = info.get("net_mac") or info.get("wif_mac")
                if mac:
                    await self.async_set_unique_id(format_mac(mac))
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                else:
                    self._async_abort_entries_match({CONF_HOST: host})
                name = user_input.get(CONF_NAME) or info.get("model") or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_PSK: psk, CONF_NAME: name, CONF_MAC: mac},
                    options={CONF_OFF_MODE: OFF_STANDBY},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_PSK, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ZidooOptionsFlow()


class ZidooOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_OFF_MODE, OFF_STANDBY)
        schema = vol.Schema(
            {
                vol.Required(CONF_OFF_MODE, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=[OFF_STANDBY, OFF_POWEROFF], translation_key=CONF_OFF_MODE
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
