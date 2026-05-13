"""Sensor platform for USGS Water Data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MONITORING_LOCATION_ID, DOMAIN
from .coordinator import USGSWaterDataCoordinator


@dataclass(frozen=True)
class SeriesDescriptor:
    """Descriptor for a timeseries-backed sensor."""

    source_key: str
    id_field: str
    label: str


SERIES_SOURCES: tuple[SeriesDescriptor, ...] = (
    SeriesDescriptor("latest_continuous", "time_series_id", "Continuous"),
    SeriesDescriptor("latest_daily", "time_series_id", "Daily"),
    SeriesDescriptor("field_measurements", "field_measurements_series_id", "Field"),
    SeriesDescriptor("peaks", "time_series_id", "Peak"),
)


def _build_ts_name_map(coordinator: USGSWaterDataCoordinator) -> dict[str, str]:
    """Build a map of time_series_id -> parameter_name from metadata."""
    name_map: dict[str, str] = {}
    for record in coordinator.data.get("time_series_metadata", []):
        ts_id = record.get("time_series_id") or record.get("id")
        param_name = record.get("parameter_name")
        if ts_id and param_name:
            name_map[str(ts_id)] = param_name
    return name_map


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: USGSWaterDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    location_id = entry.data[CONF_MONITORING_LOCATION_ID]
    ts_name_map = _build_ts_name_map(coordinator)

    entities: list[SensorEntity] = [USGSSummarySensor(coordinator, location_id)]

    series_entities: dict[str, USGSSeriesSensor] = {}
    for source in SERIES_SOURCES:
        for record in coordinator.data.get(source.source_key, []):
            series_id = record.get(source.id_field)
            if not series_id:
                continue

            series_id = str(series_id)
            # Deduplicate across sources by series_id alone
            if series_id in series_entities:
                continue

            series_entities[series_id] = USGSSeriesSensor(
                coordinator=coordinator,
                location_id=location_id,
                source=source,
                series_id=series_id,
                ts_name_map=ts_name_map,
            )

    entities.extend(series_entities.values())
    async_add_entities(entities)


class USGSBaseEntity(CoordinatorEntity[USGSWaterDataCoordinator]):
    """Base class for USGS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: USGSWaterDataCoordinator, location_id: str) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._location_id = location_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location_id)},
            name=f"USGS {location_id}",
            manufacturer="USGS",
            model="Water Data API",
            configuration_url=(
                f"https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items/{location_id}"
            ),
        )


class USGSSummarySensor(USGSBaseEntity, SensorEntity):
    """Summary sensor for the selected monitoring location."""

    _attr_name = "Summary"
    _attr_icon = "mdi:waves"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: USGSWaterDataCoordinator, location_id: str) -> None:
        """Initialize summary sensor."""
        super().__init__(coordinator, location_id)
        self._attr_unique_id = f"{location_id}_summary"

    @property
    def native_value(self) -> int:
        """Return number of latest observations represented by this integration."""
        return sum(
            len(self.coordinator.data.get(key, []))
            for key in (
                "latest_continuous",
                "latest_daily",
                "field_measurements",
                "peaks",
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rich metadata and dataset counts."""
        monitoring_location = self.coordinator.data.get("monitoring_location", {})
        return {
            "monitoring_location_id": self._location_id,
            "monitoring_location_name": monitoring_location.get(
                "monitoring_location_name"
            ),
            "site_type": monitoring_location.get("site_type"),
            "state_name": monitoring_location.get("state_name"),
            "county_name": monitoring_location.get("county_name"),
            "timezone": monitoring_location.get("time_zone_abbreviation"),
            "coordinates": monitoring_location.get("geometry"),
            "datasets": {
                "combined_metadata": len(
                    self.coordinator.data.get("combined_metadata", [])
                ),
                "time_series_metadata": len(
                    self.coordinator.data.get("time_series_metadata", [])
                ),
                "field_measurement_metadata": len(
                    self.coordinator.data.get("field_measurement_metadata", [])
                ),
                "latest_continuous": len(
                    self.coordinator.data.get("latest_continuous", [])
                ),
                "latest_daily": len(self.coordinator.data.get("latest_daily", [])),
                "history_continuous": len(
                    self.coordinator.data.get("history_continuous", [])
                ),
                "history_daily": len(self.coordinator.data.get("history_daily", [])),
                "field_measurements": len(
                    self.coordinator.data.get("field_measurements", [])
                ),
                "peaks": len(self.coordinator.data.get("peaks", [])),
            },
        }


class USGSSeriesSensor(USGSBaseEntity, SensorEntity):
    """Sensor for a specific USGS timeseries/measurement stream."""

    _attr_icon = "mdi:chart-line"

    def __init__(
        self,
        coordinator: USGSWaterDataCoordinator,
        location_id: str,
        source: SeriesDescriptor,
        series_id: str,
        ts_name_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize series sensor."""
        super().__init__(coordinator, location_id)
        self._source = source
        self._series_id = series_id
        # Unique ID is scoped to the monitoring location + series ID only,
        # independent of config entry IDs or source collection names.
        self._attr_unique_id = f"{location_id}_{series_id}"
        # Human-readable name: prefer parameter_name from metadata, then
        # parameter_code from the record, then fall back to the raw series ID.
        initial_record = self._find_record_in(coordinator.data)
        param_code = (initial_record or {}).get("parameter_code", "")
        param_name = (
            (ts_name_map or {}).get(series_id)
            or (initial_record or {}).get("parameter_name")
            or (f"{source.label} {param_code}" if param_code else None)
            or f"{source.label} {series_id}"
        )
        self._attr_name = param_name

    def _find_record_in(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Look up the record for this series in the given data snapshot."""
        for record in data.get(self._source.source_key, []):
            if str(record.get(self._source.id_field)) == self._series_id:
                return record
        return None

    def _get_record(self) -> dict[str, Any] | None:
        """Return current record for this series sensor."""
        return self._find_record_in(self.coordinator.data)

    @property
    def native_value(self) -> Any:
        """Return the current value for the series."""
        record = self._get_record()
        if record is None:
            return None
        return record.get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the measurement unit for the series."""
        record = self._get_record()
        if record is None:
            return None
        return record.get("unit_of_measure")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata for this series."""
        record = self._get_record() or {}
        return {
            "source_collection": self._source.source_key,
            "series_id": self._series_id,
            "parameter_code": record.get("parameter_code"),
            "parameter_name": record.get("parameter_name"),
            "statistic_id": record.get("statistic_id"),
            "time": record.get("time"),
            "qualifier": record.get("qualifier"),
            "approval_status": record.get("approval_status"),
            "last_modified": record.get("last_modified"),
            "monitoring_location_id": record.get("monitoring_location_id"),
        }
