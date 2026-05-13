"""Test USGS Water Data config flow."""

from unittest.mock import AsyncMock, patch

from custom_components.usgs_water_data.const import (
    CONF_API_KEY,
    CONF_HISTORY_DAYS,
    CONF_MONITORING_LOCATION_ID,
    CONF_RECORD_LIMIT,
    CONF_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_EMPTY_COORDINATOR_DATA = {
    "monitoring_location": {},
    "combined_metadata": [],
    "time_series_metadata": [],
    "field_measurement_metadata": [],
    "latest_continuous": [],
    "latest_daily": [],
    "history_continuous": [],
    "history_daily": [],
    "field_measurements": [],
    "peaks": [],
}


async def test_user_flow_creates_entry(hass):
    """Test creating config entry through UI flow."""
    with patch(
        "custom_components.usgs_water_data.coordinator.USGSWaterDataCoordinator._async_update_data",
        new=AsyncMock(return_value=_EMPTY_COORDINATOR_DATA),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                CONF_MONITORING_LOCATION_ID: "usgs-02238500",
                CONF_API_KEY: "abc123",
                CONF_HISTORY_DAYS: 5,
                CONF_RECORD_LIMIT: 50,
                CONF_SCAN_INTERVAL_MINUTES: 10,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "USGS USGS-02238500"
    assert result["data"] == {CONF_MONITORING_LOCATION_ID: "USGS-02238500"}
    assert result["options"] == {
        CONF_API_KEY: "abc123",
        CONF_HISTORY_DAYS: 5,
        CONF_RECORD_LIMIT: 50,
        CONF_SCAN_INTERVAL_MINUTES: 10,
    }
