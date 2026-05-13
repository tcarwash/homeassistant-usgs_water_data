"""The USGS Water Data integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import USGSWaterDataApiClient
from .const import (
    CONF_HISTORY_DAYS,
    CONF_MONITORING_LOCATION_ID,
    CONF_RECORD_LIMIT,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_RECORD_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import USGSWaterDataCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the USGS Water Data component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up USGS Water Data from a config entry."""
    session = async_get_clientsession(hass)
    api = USGSWaterDataApiClient(session)

    monitoring_location_id = entry.data[CONF_MONITORING_LOCATION_ID]
    history_days = entry.options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)
    record_limit = entry.options.get(CONF_RECORD_LIMIT, DEFAULT_RECORD_LIMIT)
    scan_interval_minutes = entry.options.get(
        CONF_SCAN_INTERVAL_MINUTES,
        int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
    )
    scan_interval = timedelta(minutes=max(1, scan_interval_minutes))

    coordinator = USGSWaterDataCoordinator(
        hass=hass,
        api=api,
        monitoring_location_id=monitoring_location_id,
        history_days=history_days,
        record_limit=record_limit,
        update_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady("Could not fetch USGS data")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
