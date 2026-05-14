from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import InnovaEnergieCoordinator

PLATFORMS = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_ICONS_REGISTERED = False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    global _ICONS_REGISTERED
    if not _ICONS_REGISTERED:
        base = Path(__file__).parent
        paths = []
        for filename in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
            file = base / filename
            if file.exists():
                paths.append(StaticPathConfig(
                    f"/api/brands/integration/{DOMAIN}/{filename}",
                    str(file),
                    cache_headers=False,
                ))
        if paths:
            await hass.http.async_register_static_paths(paths)
            _ICONS_REGISTERED = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = InnovaEnergieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
