"""Select platform for YoDeck — provides searchable dropdowns for all resource types."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    """Set up YoDeck select entities."""
    coordinator: YoDeckDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        YoDeckScheduleSelect(coordinator),
        YoDeckScreenSelect(coordinator),
        YoDeckMediaSelect(coordinator),
        YoDeckPlaylistSelect(coordinator),
        YoDeckLayoutSelect(coordinator),
        YoDeckContentSelect(coordinator),
    ])


class YoDeckResourceSelect(CoordinatorEntity[YoDeckDataUpdateCoordinator], SelectEntity):
    """Base select entity that stays in sync with coordinator data."""

    _data_key: str
    _attr_current_option: str | None = None

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._refresh_options()

    def _refresh_options(self) -> None:
        items: list[dict[str, Any]] = (
            self.coordinator.data.get(self._data_key, [])
            if self.coordinator.data
            else []
        )
        self._attr_options = [i["name"] for i in items if i.get("name")]
        if self._attr_current_option not in self._attr_options:
            self._attr_current_option = self._attr_options[0] if self._attr_options else None

    def _handle_coordinator_update(self) -> None:
        self._refresh_options()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class YoDeckScheduleSelect(YoDeckResourceSelect):
    """Searchable dropdown of all YoDeck schedules."""

    _data_key = "schedules"
    _attr_name = "YoDeck Schedule"
    _attr_icon = "mdi:calendar-multiple"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_schedule_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)


class YoDeckScreenSelect(YoDeckResourceSelect):
    """Searchable dropdown of all YoDeck screens."""

    _data_key = "screens"
    _attr_name = "YoDeck Screen"
    _attr_icon = "mdi:monitor"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_screen_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)


class YoDeckMediaSelect(YoDeckResourceSelect):
    """Searchable dropdown of all YoDeck media files."""

    _data_key = "media"
    _attr_name = "YoDeck Media"
    _attr_icon = "mdi:file-video"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_media_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)


class YoDeckPlaylistSelect(YoDeckResourceSelect):
    """Searchable dropdown of all YoDeck playlists."""

    _data_key = "playlists"
    _attr_name = "YoDeck Playlist"
    _attr_icon = "mdi:playlist-play"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_playlist_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)


class YoDeckLayoutSelect(YoDeckResourceSelect):
    """Searchable dropdown of all YoDeck layouts."""

    _data_key = "layouts"
    _attr_name = "YoDeck Layout"
    _attr_icon = "mdi:view-dashboard"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_layout_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)


class YoDeckContentSelect(CoordinatorEntity[YoDeckDataUpdateCoordinator], SelectEntity):
    """Combined searchable dropdown of all content (media + playlists + layouts).

    Options are prefixed with their type so the service handler can infer
    content_type automatically: "media: Christmas Video", "playlist: Holiday Mix".
    """

    _attr_name = "YoDeck Content"
    _attr_icon = "mdi:play-box-multiple"

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        self._attr_unique_id = f"yodeck_content_select_{coordinator.config_entry.entry_id}"
        super().__init__(coordinator)
        self._attr_current_option: str | None = None
        self._refresh_options()

    def _refresh_options(self) -> None:
        data = self.coordinator.data or {}
        options: list[str] = []
        for item in data.get("media", []):
            if item.get("name"):
                options.append(f"media: {item['name']}")
        for item in data.get("playlists", []):
            if item.get("name"):
                options.append(f"playlist: {item['name']}")
        for item in data.get("layouts", []):
            if item.get("name"):
                options.append(f"layout: {item['name']}")
        self._attr_options = options
        if self._attr_current_option not in self._attr_options:
            self._attr_current_option = options[0] if options else None

    def _handle_coordinator_update(self) -> None:
        self._refresh_options()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
