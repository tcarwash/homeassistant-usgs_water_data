# USGS Water Data for Home Assistant

## Installation

Install this custom integration with HACS, then restart Home Assistant.

## Configuration

1. Go to Settings -> Devices & Services -> Add Integration.
2. Search for USGS Water Data.
3. Enter a `monitoring_location_id` (example: `USGS-02238500`).
4. Optionally tune:
   - `history_days`: How far back to fetch historical daily/continuous records.
   - `record_limit`: Maximum records requested per collection.
   - `scan_interval_minutes`: Polling interval.

## Data Exposed

For each configured monitoring location, the integration fetches and exposes data from:

- monitoring-locations
- combined-metadata
- time-series-metadata
- field-measurements-metadata
- latest-continuous
- latest-daily
- continuous (history window)
- daily (history window)
- field-measurements
- peaks

Entities created:

- One summary diagnostic sensor with site metadata and dataset counts.
- Multiple measurement sensors (continuous, daily, field, peak), one per discovered series.

Each measurement sensor includes the latest value, unit, and metadata attributes such as parameter code, statistic id, timestamp, qualifier, and approval status.
