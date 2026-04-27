"""Binary sensor platform for YoDeck."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import YoDeckDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoDeck binary sensor based on a config entry."""
    coordinator: YoDeckDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[YoDeckScheduleBinarySensor] = []
    for schedule in coordinator.data.get("schedules", []):
        schedule_id = schedule.get("id")
        if schedule_id:
            entities.append(
                YoDeckScheduleBinarySensor(
                    coordinator,
                    schedule_id,
                    schedule.get("name", f"Schedule {schedule_id}"),
                )
            )

    async_add_entities(entities)


class YoDeckScheduleBinarySensor(
    CoordinatorEntity[YoDeckDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a YoDeck schedule binary sensor."""

    def __init__(
        self,
        coordinator: YoDeckDataUpdateCoordinator,
        schedule_id: int,
        schedule_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._schedule_id = schedule_id
        self._attr_unique_id = f"yodeck_schedule_{schedule_id}"
        self._attr_name = f"YoDeck {schedule_name}"
        self._attr_icon = "mdi:calendar-clock"

    def _get_schedule_data(self) -> dict[str, Any] | None:
        """Get schedule data from coordinator."""
        for schedule in self.coordinator.data.get("schedules", []):
            if schedule.get("id") == self._schedule_id:
                return schedule
        return None

    def _get_event_window(
        self, event: dict[str, Any], now: datetime
    ) -> tuple[datetime, datetime] | None:
        """Return (window_start, window_end) if the event is active now, else None.

        YoDeck stores times in local time but labels them as UTC (Z suffix).
        We strip timezone info and compare as naive local datetimes.
        """
        start_str = event.get("start")
        end_str = event.get("end")
        if not start_str or not end_str:
            return None

        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "").replace("+00:00", ""))
            end_dt = datetime.fromisoformat(end_str.replace("Z", "").replace("+00:00", ""))
        except (ValueError, AttributeError):
            return None

        duration = event.get("duration", 0)  # minutes
        recurrence = event.get("recurrence", "o")
        days_of_week_str = event.get("days_of_week", "1111111")

        _LOGGER.debug(
            "Checking event: start=%s, end=%s, recurrence=%s, duration=%s min, now=%s",
            start_dt, end_dt, recurrence, duration, now
        )

        def check_dow(dt: datetime) -> bool:
            dow = dt.weekday()
            return len(days_of_week_str) > dow and days_of_week_str[dow] == "1"

        def project_to_year(dt: datetime, year: int) -> datetime:
            try:
                return dt.replace(year=year)
            except ValueError:
                return dt.replace(year=year, day=28)

        def check_window(ws: datetime, we: datetime) -> tuple[datetime, datetime] | None:
            if ws <= now < we and check_dow(now):
                return (ws, we)
            return None

        if recurrence == "o":
            event_span_days = (end_dt - start_dt).days
            if event_span_days > 365:
                this_year_start = project_to_year(start_dt, now.year)
                this_year_end = this_year_start + timedelta(minutes=duration) if duration > 0 else this_year_start + timedelta(days=1)
                result = check_window(this_year_start, this_year_end)
                if result:
                    return result
                prev_year_start = project_to_year(start_dt, now.year - 1)
                prev_year_end = prev_year_start + timedelta(minutes=duration) if duration > 0 else prev_year_start + timedelta(days=1)
                return check_window(prev_year_start, prev_year_end)
            else:
                actual_end = start_dt + timedelta(minutes=duration) if duration > 0 else end_dt
                return check_window(start_dt, actual_end)

        elif recurrence == "y":
            if start_dt.year <= now.year <= end_dt.year:
                this_year_start = project_to_year(start_dt, now.year)
                this_year_end = this_year_start + timedelta(minutes=duration) if duration > 0 else this_year_start + timedelta(days=1)
                result = check_window(this_year_start, this_year_end)
                if result:
                    return result
                if now.year - 1 >= start_dt.year:
                    prev_year_start = project_to_year(start_dt, now.year - 1)
                    prev_year_end = prev_year_start + timedelta(minutes=duration) if duration > 0 else prev_year_start + timedelta(days=1)
                    return check_window(prev_year_start, prev_year_end)

        elif recurrence == "d":
            if start_dt.date() <= now.date() <= end_dt.date():
                today_start = start_dt.replace(year=now.year, month=now.month, day=now.day)
                today_end = today_start + timedelta(minutes=duration) if duration > 0 else today_start + timedelta(days=1)
                result = check_window(today_start, today_end)
                if result:
                    return result
                yesterday = now.date() - timedelta(days=1)
                if start_dt.date() <= yesterday:
                    yesterday_start = start_dt.replace(year=yesterday.year, month=yesterday.month, day=yesterday.day)
                    yesterday_end = yesterday_start + timedelta(minutes=duration) if duration > 0 else yesterday_start + timedelta(days=1)
                    return check_window(yesterday_start, yesterday_end)

        elif recurrence == "w":
            if start_dt.date() <= now.date() <= end_dt.date():
                today_start = start_dt.replace(year=now.year, month=now.month, day=now.day)
                today_end = today_start + timedelta(minutes=duration) if duration > 0 else today_start + timedelta(days=1)
                return check_window(today_start, today_end)

        elif recurrence == "m":
            if start_dt.date() <= now.date() <= end_dt.date() and now.day == start_dt.day:
                today_start = start_dt.replace(year=now.year, month=now.month, day=now.day)
                today_end = today_start + timedelta(minutes=duration) if duration > 0 else today_start + timedelta(days=1)
                return check_window(today_start, today_end)

        return None

    def _is_event_active_now(self, event: dict[str, Any], now: datetime) -> bool:
        """Return True if the event is active at the given local datetime."""
        return self._get_event_window(event, now) is not None

    def _has_active_event_now(self) -> bool:
        """Check if there's an active event right now."""
        schedule = self._get_schedule_data()
        if not schedule:
            return False

        events = schedule.get("events", [])
        if not events:
            return False

        # Use local time - YoDeck stores times in local time (Z suffix is misleading)
        now = dt_util.now().replace(tzinfo=None)
        for event in events:
            if self._is_event_active_now(event, now):
                return True

        return False

    @property
    def is_on(self) -> bool:
        """Return true if there's an active schedule right now."""
        return self._has_active_event_now()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        schedule = self._get_schedule_data()
        if not schedule:
            return None

        events = schedule.get("events", [])
        now = dt_util.now().replace(tzinfo=None)
        active_events = []

        for event in events:
            window = self._get_event_window(event, now)
            if window:
                source = event.get("source", {})
                window_start, window_end = window
                active_events.append({
                    "name": source.get("source_name", "Unknown"),
                    "type": source.get("source_type", "Unknown"),
                    "priority": event.get("priority", 0),
                    "duration_minutes": event.get("duration", 0),
                    "start": window_start.strftime("%B %-d, %Y %I:%M %p"),
                    "end": window_end.strftime("%B %-d, %Y %I:%M %p"),
                })

        return {
            "schedule_id": self._schedule_id,
            "schedule_name": schedule.get("name"),
            "total_events": len(events),
            "active_events_today": len(active_events),
            "active_events": active_events,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._get_schedule_data() is not None
        )
