"""Sensor platform for YoDeck."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YoDeckDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoDeck sensor based on a config entry."""
    coordinator: YoDeckDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create sensors for schedules, screens, media, playlists, and layouts
    entities = [
        YoDeckSchedulesSensor(coordinator),
        YoDeckScreensSensor(coordinator),
        YoDeckMediaSensor(coordinator),
        YoDeckPlaylistsSensor(coordinator),
        YoDeckLayoutsSensor(coordinator),
    ]

    async_add_entities(entities)


class YoDeckSchedulesSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available schedules."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_schedules_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Schedules"
        self._attr_icon = "mdi:calendar-multiple"

    @property
    def native_value(self) -> int:
        """Return the number of schedules."""
        schedules = self.coordinator.data.get("schedules", [])
        return len(schedules)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return schedules as attributes."""
        schedules = self.coordinator.data.get("schedules", [])
        schedule_dict = {}
        for schedule in schedules:
            schedule_id = schedule.get("id")
            schedule_name = schedule.get("name")
            if schedule_id and schedule_name:
                schedule_dict[str(schedule_id)] = schedule_name

        return {"schedules": schedule_dict}


class YoDeckScreensSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available screens."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_screens_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Screens"
        self._attr_icon = "mdi:monitor"

    @property
    def native_value(self) -> int:
        """Return the number of screens."""
        screens = self.coordinator.data.get("screens", [])
        return len(screens)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return screens as attributes."""
        screens = self.coordinator.data.get("screens", [])
        screens_dict = {}
        for screen in screens:
            screen_id = screen.get("id")
            screen_name = screen.get("name")
            if screen_id and screen_name:
                screens_dict[str(screen_id)] = screen_name

        return {"screens": screens_dict}


class YoDeckMediaSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available media."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_media_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Media"
        self._attr_icon = "mdi:file-video"
        self._media_data: list[dict[str, Any]] = []

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        await self._fetch_media()

    async def _fetch_media(self) -> None:
        """Fetch media data from API."""
        try:
            _LOGGER.debug("Fetching media data from YoDeck API")
            media_response = await self.coordinator.api.get_media()
            self._media_data = media_response.get("results", [])
            _LOGGER.info("Fetched %d media items", len(self._media_data))
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Error fetching media: %s", err)
            self._media_data = []

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update triggered for media sensor")
        self.hass.async_create_task(self._fetch_media())
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        """Return the number of media items."""
        return len(self._media_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return media as attributes."""
        media_dict = {}
        for media in self._media_data:
            media_id = media.get("id")
            media_name = media.get("name")
            if media_id and media_name:
                media_dict[str(media_id)] = media_name

        return {"media": media_dict}


class YoDeckPlaylistsSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available playlists."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_playlists_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Playlists"
        self._attr_icon = "mdi:playlist-play"
        self._playlists_data: list[dict[str, Any]] = []

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        await self._fetch_playlists()

    async def _fetch_playlists(self) -> None:
        """Fetch playlists data from API."""
        try:
            _LOGGER.debug("Fetching playlists data from YoDeck API")
            playlists_response = await self.coordinator.api.get_playlists()
            self._playlists_data = playlists_response.get("results", [])
            _LOGGER.info("Fetched %d playlists", len(self._playlists_data))
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Error fetching playlists: %s", err)
            self._playlists_data = []

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update triggered for playlists sensor")
        self.hass.async_create_task(self._fetch_playlists())
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        """Return the number of playlists."""
        return len(self._playlists_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return playlists as attributes."""
        playlists_dict = {}
        for playlist in self._playlists_data:
            playlist_id = playlist.get("id")
            playlist_name = playlist.get("name")
            if playlist_id and playlist_name:
                playlists_dict[str(playlist_id)] = playlist_name

        return {"playlists": playlists_dict}


class YoDeckLayoutsSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available layouts."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_layouts_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Layouts"
        self._attr_icon = "mdi:view-dashboard"
        self._layouts_data: list[dict[str, Any]] = []

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        await self._fetch_layouts()

    async def _fetch_layouts(self) -> None:
        """Fetch layouts data from API."""
        try:
            _LOGGER.debug("Fetching layouts data from YoDeck API")
            layouts_response = await self.coordinator.api.get_layouts()
            self._layouts_data = layouts_response.get("results", [])
            _LOGGER.info("Fetched %d layouts", len(self._layouts_data))
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Error fetching layouts: %s", err)
            self._layouts_data = []

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update triggered for layouts sensor")
        self.hass.async_create_task(self._fetch_layouts())
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        """Return the number of layouts."""
        return len(self._layouts_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return layouts as attributes."""
        layouts_dict = {}
        for layout in self._layouts_data:
            layout_id = layout.get("id")
            layout_name = layout.get("name")
            if layout_id and layout_name:
                layouts_dict[str(layout_id)] = layout_name

        return {"layouts": layouts_dict}
