"""Data coordinator for USGS Water Data."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import USGSWaterDataApiClient

LOGGER = logging.getLogger(__name__)


def _feature_properties(feature: dict[str, Any]) -> dict[str, Any]:
    """Return normalized properties from a GeoJSON feature."""
    result = dict(feature.get("properties", {}))
    feature_id = feature.get("id")
    if feature_id is not None:
        result.setdefault("id", feature_id)
    geometry = feature.get("geometry")
    if geometry is not None:
        result.setdefault("geometry", geometry)
    return result


class USGSWaterDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate USGS Water Data API polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: USGSWaterDataApiClient,
        monitoring_location_id: str,
        history_days: int,
        record_limit: int,
        update_interval: timedelta,
    ) -> None:
        """Initialize coordinator."""
        self.api = api
        self.monitoring_location_id = monitoring_location_id
        self.history_days = max(0, history_days)
        self.record_limit = max(1, record_limit)

        super().__init__(
            hass,
            logger=LOGGER,
            name=f"usgs_water_data_{monitoring_location_id}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data for the configured monitoring location."""
        datetime_filter = None
        if self.history_days:
            start = datetime.now(timezone.utc) - timedelta(days=self.history_days)
            start_iso = start.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            datetime_filter = f"{start_iso}/.."

        try:
            tasks = [
                self.api.get_monitoring_location(self.monitoring_location_id),
                self.api.get_collection_items(
                    "combined-metadata",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
                self.api.get_collection_items(
                    "time-series-metadata",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
                self.api.get_collection_items(
                    "field-measurements-metadata",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
                self.api.get_collection_items(
                    "latest-continuous",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
                self.api.get_collection_items(
                    "latest-daily",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
                self.api.get_collection_items(
                    "field-measurements",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                    extra_params=(
                        {"datetime": datetime_filter} if datetime_filter else None
                    ),
                ),
                self.api.get_collection_items(
                    "peaks",
                    self.monitoring_location_id,
                    limit=self.record_limit,
                ),
            ]
            (
                monitoring_location,
                combined_metadata,
                time_series_metadata,
                field_measurement_metadata,
                latest_continuous,
                latest_daily,
                field_measurements,
                peaks,
            ) = await asyncio.gather(*tasks)

            history_continuous: list[dict[str, Any]] = []
            history_daily: list[dict[str, Any]] = []
            if datetime_filter:
                history_continuous, history_daily = await asyncio.gather(
                    self.api.get_collection_items(
                        "continuous",
                        self.monitoring_location_id,
                        limit=self.record_limit,
                        extra_params={"datetime": datetime_filter},
                    ),
                    self.api.get_collection_items(
                        "daily",
                        self.monitoring_location_id,
                        limit=self.record_limit,
                        extra_params={"datetime": datetime_filter},
                    ),
                )
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from USGS API: {err}") from err

        return {
            "monitoring_location": _feature_properties(monitoring_location),
            "combined_metadata": [
                _feature_properties(item) for item in combined_metadata
            ],
            "time_series_metadata": [
                _feature_properties(item) for item in time_series_metadata
            ],
            "field_measurement_metadata": [
                _feature_properties(item) for item in field_measurement_metadata
            ],
            "latest_continuous": [
                _feature_properties(item) for item in latest_continuous
            ],
            "latest_daily": [_feature_properties(item) for item in latest_daily],
            "history_continuous": [
                _feature_properties(item) for item in history_continuous
            ],
            "history_daily": [_feature_properties(item) for item in history_daily],
            "field_measurements": [
                _feature_properties(item) for item in field_measurements
            ],
            "peaks": [_feature_properties(item) for item in peaks],
        }
