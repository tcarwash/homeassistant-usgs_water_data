"""Constants for the USGS Water Data integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "usgs_water_data"

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_API_KEY = "api_key"
CONF_MONITORING_LOCATION_ID = "monitoring_location_id"
CONF_HISTORY_DAYS = "history_days"
CONF_RECORD_LIMIT = "record_limit"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"

DEFAULT_HISTORY_DAYS = 7
DEFAULT_RECORD_LIMIT = 100
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
