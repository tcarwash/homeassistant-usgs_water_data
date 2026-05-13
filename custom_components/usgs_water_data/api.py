"""API client for USGS Water Data OGC API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

BASE_URL = "https://api.waterdata.usgs.gov/ogcapi/v0"
_LOGGER = logging.getLogger(__name__)
_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 2.0  # seconds; doubled on each retry


class USGSWaterDataApiClient:
    """Client for the USGS Water Data API."""

    def __init__(self, session: ClientSession, api_key: str | None = None) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_key = api_key.strip() if api_key else None

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Issue a GET request and return JSON payload, retrying on 429."""
        request_params = {"f": "json", **(params or {})}
        url = f"{BASE_URL}{path}"
        request_headers = {"X_api_key": self._api_key} if self._api_key else None
        delay = _RETRY_BASE_DELAY

        for attempt in range(_MAX_RETRIES):
            try:
                async with self._session.get(
                    url,
                    params=request_params,
                    headers=request_headers,
                    timeout=30,
                ) as response:
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", delay))
                        _LOGGER.warning(
                            "Rate-limited by USGS API (%s), retrying in %.1fs (attempt %d/%d)",
                            path,
                            retry_after,
                            attempt + 1,
                            _MAX_RETRIES,
                        )
                        await asyncio.sleep(retry_after)
                        delay *= 2
                        continue
                    response.raise_for_status()
                    return await response.json()
            except ClientResponseError as err:
                if attempt < _MAX_RETRIES - 1 and err.status == 429:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(
                    f"USGS API request failed for {path}: {err}"
                ) from err
            except ClientError as err:
                raise RuntimeError(
                    f"USGS API request failed for {path}: {err}"
                ) from err

        raise RuntimeError(f"USGS API request failed for {path}: exceeded retry limit")

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
