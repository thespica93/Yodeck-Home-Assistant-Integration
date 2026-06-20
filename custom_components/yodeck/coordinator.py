"""DataUpdateCoordinator for YoDeck."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YoDeckApiClient, YoDeckApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YoDeckDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching YoDeck data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        api_token: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize."""
        self.api = YoDeckApiClient(session, api_token)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def update_interval_seconds(self, interval: int) -> None:
        """Update the scan interval."""
        self.update_interval = timedelta(seconds=interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Fetch schedule list first to get all schedule IDs
            _LOGGER.debug("Fetching all YoDeck resources")
            (
                schedules_response,
                screens_response,
                media_response,
                playlists_response,
                layouts_response,
            ) = await asyncio.gather(
                self.api.get_schedules(),
                self.api.get_monitors(),
                self.api.get_media(),
                self.api.get_playlists(),
                self.api.get_layouts(),
            )

            schedule_list = schedules_response.get("results", [])
            screens = screens_response.get("results", [])
            media = media_response.get("results", [])
            playlists = playlists_response.get("results", [])
            layouts = layouts_response.get("results", [])

            # Fetch full schedule details (list endpoint may not include all events)
            schedules = []
            for schedule_summary in schedule_list:
                schedule_id = schedule_summary.get("id")
                if schedule_id:
                    try:
                        full_schedule = await self.api.get_schedule(schedule_id)
                        schedules.append(full_schedule)
                        _LOGGER.debug("Fetched schedule '%s' with %d events",
                                      full_schedule.get("name"), len(full_schedule.get("events", [])))
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch details for schedule %s: %s", schedule_id, err)
                        schedules.append(schedule_summary)

            _LOGGER.debug(
                "Fetched %d schedules, %d screens, %d media, %d playlists, %d layouts",
                len(schedules), len(screens), len(media), len(playlists), len(layouts),
            )

            return {
                "schedules": schedules,
                "screens": screens,
                "media": media,
                "playlists": playlists,
                "layouts": layouts,
            }

        except YoDeckApiError as err:
            _LOGGER.error("YoDeck API error during update: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during update: %s", err, exc_info=True)
            raise UpdateFailed(f"Unexpected error: {err}") from err
