"""Test USGS Water Data config flow."""

from custom_components.usgs_water_data.const import (
    CONF_HISTORY_DAYS,
    CONF_MONITORING_LOCATION_ID,
    CONF_RECORD_LIMIT,
    CONF_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)


async def test_user_flow_creates_entry(hass):
    """Test creating config entry through UI flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={
            CONF_MONITORING_LOCATION_ID: "usgs-02238500",
            CONF_HISTORY_DAYS: 5,
            CONF_RECORD_LIMIT: 50,
            CONF_SCAN_INTERVAL_MINUTES: 10,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "USGS USGS-02238500"
    assert result["data"] == {CONF_MONITORING_LOCATION_ID: "USGS-02238500"}
    assert result["options"] == {
        CONF_HISTORY_DAYS: 5,
        CONF_RECORD_LIMIT: 50,
        CONF_SCAN_INTERVAL_MINUTES: 10,
    }
