"""Sensor platform for USGS Water Data."""

from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)


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
    _LOGGER.debug("Built time_series_metadata name map with %d entries", len(name_map))
    return name_map


def _build_ts_metadata_map(
    coordinator: USGSWaterDataCoordinator,
) -> dict[str, dict[str, Any]]:
    """Build a map of time_series_id -> metadata fields from time-series-metadata."""
    metadata_map: dict[str, dict[str, Any]] = {}
    for record in coordinator.data.get("time_series_metadata", []):
        ts_id = record.get("time_series_id") or record.get("id")
        if not ts_id:
            continue
        metadata_map[str(ts_id)] = {
            "parameter_name": record.get("parameter_name"),
            "statistic_id": record.get("statistic_id"),
            "computation_identifier": record.get("computation_identifier"),
            "parameter_code": record.get("parameter_code"),
            "sublocation_identifier": record.get("sublocation_identifier"),
        }
    return metadata_map


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: USGSWaterDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    location_id = entry.data[CONF_MONITORING_LOCATION_ID]

    entities: list[SensorEntity] = [USGSSummarySensor(coordinator, location_id)]

    if coordinator.data is None:
        _LOGGER.warning(
            "Coordinator data not yet available for %s; deferring series sensor setup",
            location_id,
        )
    else:
        ts_name_map = _build_ts_name_map(coordinator)
        ts_metadata_map = _build_ts_metadata_map(coordinator)

        series_entities: dict[str, USGSSeriesSensor] = {}
        for source in SERIES_SOURCES:
            for record in coordinator.data.get(source.source_key, []):
                if not record:
                    continue
                series_id = record.get(source.id_field)
                if not series_id:
                    continue

                series_id = str(series_id)
                # Deduplicate across sources by series_id alone
                if series_id in series_entities:
                    continue

                _LOGGER.debug(
                    "Creating sensor for %s: series_id=%s, source=%s",
                    location_id,
                    series_id,
                    source.source_key,
                )
                series_entities[series_id] = USGSSeriesSensor(
                    coordinator=coordinator,
                    location_id=location_id,
                    source=source,
                    series_id=series_id,
                    ts_name_map=ts_name_map,
                    ts_metadata_map=ts_metadata_map,
                )

        _LOGGER.info(
            "Setting up %d series sensors + 1 summary for %s",
            len(series_entities),
            location_id,
        )
        # Log data availability for debugging
        for source in SERIES_SOURCES:
            count = len(coordinator.data.get(source.source_key, []))
            _LOGGER.debug("%s has %d records", source.source_key, count)
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
        ts_metadata_map: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize series sensor."""
        super().__init__(coordinator, location_id)
        self._source = source
        self._series_id = series_id
        # Unique ID is scoped to the monitoring location + series ID only,
        # independent of config entry IDs or source collection names.
        self._attr_unique_id = f"{location_id}_{series_id}"

        # Build a disambiguated display name so multiple time series for the same
        # parameter (e.g., discharge/gage height) remain distinguishable.
        initial_record = self._find_record_in(coordinator.data)
        series_meta = (ts_metadata_map or {}).get(series_id, {})
        param_code = (initial_record or {}).get("parameter_code") or series_meta.get(
            "parameter_code"
        )
        param_name = (
            series_meta.get("parameter_name")
            or (ts_name_map or {}).get(series_id)
            or (initial_record or {}).get("parameter_name")
            or (f"Parameter {param_code}" if param_code else None)
            or f"Series {series_id}"
        )
        statistic_id = (initial_record or {}).get("statistic_id") or series_meta.get(
            "statistic_id"
        )
        computation_identifier = series_meta.get("computation_identifier")
        sublocation_identifier = (initial_record or {}).get(
            "sublocation_identifier"
        ) or series_meta.get("sublocation_identifier")

        qualifiers = [source.label]
        if statistic_id:
            qualifiers.append(f"stat {statistic_id}")
        if computation_identifier:
            qualifiers.append(str(computation_identifier))
        if sublocation_identifier:
            qualifiers.append(f"sub {sublocation_identifier}")

        qualifier_text = ", ".join(qualifiers)
        self._attr_name = f"{param_name} ({qualifier_text})"

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
