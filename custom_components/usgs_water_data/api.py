"""API client for USGS Water Data OGC API."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

BASE_URL = "https://api.waterdata.usgs.gov/ogcapi/v0"


class USGSWaterDataApiClient:
    """Client for the USGS Water Data API."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the API client."""
        self._session = session

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Issue a GET request and return JSON payload."""
        request_params = {"f": "json", **(params or {})}
        url = f"{BASE_URL}{path}"

        try:
            async with self._session.get(
                url, params=request_params, timeout=30
            ) as response:
                response.raise_for_status()
                return await response.json()
        except ClientError as err:
            raise RuntimeError(f"USGS API request failed for {path}: {err}") from err

    async def get_monitoring_location(
        self, monitoring_location_id: str
    ) -> dict[str, Any]:
        """Fetch metadata for a single monitoring location."""
        return await self._get(
            f"/collections/monitoring-locations/items/{monitoring_location_id}"
        )

    async def get_collection_items(
        self,
        collection: str,
        monitoring_location_id: str,
        *,
        limit: int,
        extra_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch collection items filtered by monitoring location ID."""
        params = {
            "monitoring_location_id": monitoring_location_id,
            "limit": limit,
            **(extra_params or {}),
        }
        payload = await self._get(f"/collections/{collection}/items", params=params)
        return payload.get("features", [])
