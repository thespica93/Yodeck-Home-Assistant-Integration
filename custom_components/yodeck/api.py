"""YoDeck API Client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class YoDeckApiError(Exception):
    """Base exception for YoDeck API errors."""


class YoDeckAuthError(YoDeckApiError):
    """Exception for authentication errors."""


class YoDeckRateLimitError(YoDeckApiError):
    """Exception for rate limit errors."""


class YoDeckApiClient:
    """YoDeck API Client."""

    def __init__(self, session: aiohttp.ClientSession, api_token: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_token = api_token
        self._headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make a request to the YoDeck API."""
        url = f"{API_BASE_URL}/{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                **kwargs,
            ) as response:
                if response.status == 401:
                    raise YoDeckAuthError("Invalid API token")
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    raise YoDeckRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds"
                    )

                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientError as err:
            raise YoDeckApiError(f"Error communicating with YoDeck API: {err}") from err

    async def get_monitors(self) -> dict[str, Any]:
        """Get all monitors (screens)."""
        return await self._request("GET", "screens")

    async def get_schedules(self) -> dict[str, Any]:
        """Get all schedules."""
        return await self._request("GET", "schedules")

    async def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        """Get a single schedule with full details including all events."""
        return await self._request("GET", f"schedules/{schedule_id}")

    async def get_media(self) -> dict[str, Any]:
        """Get all media files."""
        return await self._request("GET", "media")

    async def get_playlists(self) -> dict[str, Any]:
        """Get all playlists."""
        return await self._request("GET", "playlists")

    async def get_layouts(self) -> dict[str, Any]:
        """Get all layouts."""
        return await self._request("GET", "layouts")

    async def update_schedule(self, schedule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Update a schedule by ID."""
        return await self._request("PUT", f"schedules/{schedule_id}", json=data)

    async def push_to_screen(self, screen_id: int) -> dict[str, Any]:
        """Push updates to a specific screen."""
        return await self._request("POST", f"screens/{screen_id}/push")

    async def refresh_screenshot(self, screen_id: int) -> dict[str, Any]:
        """Refresh the screenshot for a specific screen."""
        return await self._request("POST", f"screens/{screen_id}/refresh-screenshot")

    async def verify_token(self) -> bool:
        """Verify the API token is valid."""
        try:
            await self.get_schedules()
            return True
        except YoDeckAuthError:
            return False
        except YoDeckApiError as err:
            _LOGGER.error("Error verifying token: %s", err)
            return False
