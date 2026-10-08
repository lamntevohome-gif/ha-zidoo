"""Base entity for Zidoo."""
from __future__ import annotations

from homeassistant.const import CONF_MAC
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZidooCoordinator


class ZidooEntity(CoordinatorEntity[ZidooCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZidooCoordinator, entry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        info = coordinator.client.info
        connections = set()
        if mac := entry.data.get(CONF_MAC):
            connections.add((dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            connections=connections,
            name=entry.title,
            manufacturer="Zidoo",
            model=info.get("model") or "UHD8000",
            sw_version=info.get("firmware"),
            configuration_url=f"http://{coordinator.client.host}:9529",
        )

    @property
    def online(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.online)
