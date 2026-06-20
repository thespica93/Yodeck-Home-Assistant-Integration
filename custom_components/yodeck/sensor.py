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
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_media_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Media"
        self._attr_icon = "mdi:file-video"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("media", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "media": {
                str(m["id"]): m["name"]
                for m in self.coordinator.data.get("media", [])
                if m.get("id") and m.get("name")
            }
        }


class YoDeckPlaylistsSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available playlists."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_playlists_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Playlists"
        self._attr_icon = "mdi:playlist-play"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("playlists", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "playlists": {
                str(p["id"]): p["name"]
                for p in self.coordinator.data.get("playlists", [])
                if p.get("id") and p.get("name")
            }
        }


class YoDeckLayoutsSensor(CoordinatorEntity[YoDeckDataUpdateCoordinator], SensorEntity):
    """Sensor that lists all available layouts."""

    def __init__(self, coordinator: YoDeckDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"yodeck_layouts_{coordinator.config_entry.entry_id}"
        self._attr_name = "YoDeck Layouts"
        self._attr_icon = "mdi:view-dashboard"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("layouts", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "layouts": {
                str(l["id"]): l["name"]
                for l in self.coordinator.data.get("layouts", [])
                if l.get("id") and l.get("name")
            }
        }
