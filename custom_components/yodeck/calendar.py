"""Calendar platform for YoDeck."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    """Set up YoDeck calendar entities from a config entry."""
    coordinator: YoDeckDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[YoDeckCalendarEntity] = []
    for schedule in coordinator.data.get("schedules", []):
        schedule_id = schedule.get("id")
        if schedule_id:
            entities.append(
                YoDeckCalendarEntity(
                    coordinator,
                    schedule_id,
                    schedule.get("name", f"Schedule {schedule_id}"),
                )
            )

    async_add_entities(entities)


def _parse_yodeck_dt(dt_str: str) -> datetime | None:
    """Parse a YoDeck datetime string to a naive local datetime.

    YoDeck stores times in local time but appends a Z suffix (misleading).
    We strip the timezone marker and treat the value as local time.
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "").replace("+00:00", ""))
    except (ValueError, AttributeError):
        return None


def _localize(naive_dt: datetime) -> datetime:
    """Attach HA's configured timezone to a naive local datetime."""
    return naive_dt.replace(tzinfo=dt_util.get_default_time_zone())


def _to_naive_local(dt: datetime) -> datetime:
    """Convert a timezone-aware datetime to a naive local datetime."""
    return dt_util.as_local(dt).replace(tzinfo=None)


class YoDeckCalendarEntity(
    CoordinatorEntity[YoDeckDataUpdateCoordinator], CalendarEntity
):
    """A YoDeck schedule exposed as a Home Assistant calendar entity."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: YoDeckDataUpdateCoordinator,
        schedule_id: int,
        schedule_name: str,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._schedule_id = schedule_id
        self._schedule_name = schedule_name
        self._attr_unique_id = f"yodeck_calendar_{schedule_id}"
        self._attr_name = f"YoDeck {schedule_name}"

    def _get_schedule(self) -> dict[str, Any] | None:
        """Return this schedule's data from the coordinator."""
        for schedule in self.coordinator.data.get("schedules", []):
            if schedule.get("id") == self._schedule_id:
                return schedule
        return None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current active event, or the next upcoming event."""
        now = dt_util.now()
        range_start_naive = _to_naive_local(now)
        range_end_naive = range_start_naive + timedelta(days=365)

        schedule = self._get_schedule()
        if not schedule:
            return None

        candidates = self._expand_schedule(schedule, range_start_naive, range_end_naive)
        for evt in sorted(candidates, key=lambda e: e.start):
            if evt.end >= now:
                return evt
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all calendar events within the given date range."""
        start_naive = _to_naive_local(start_date)
        end_naive = _to_naive_local(end_date)

        schedule = self._get_schedule()
        if not schedule:
            return []

        return sorted(
            self._expand_schedule(schedule, start_naive, end_naive),
            key=lambda e: e.start,
        )

    def _expand_schedule(
        self,
        schedule: dict[str, Any],
        range_start: datetime,
        range_end: datetime,
    ) -> list[CalendarEvent]:
        """Generate CalendarEvent instances for all events in a schedule."""
        results: list[CalendarEvent] = []
        schedule_name = schedule.get("name", self._schedule_name)
        for event in schedule.get("events", []):
            results.extend(self._expand_event(event, schedule_name, range_start, range_end))
        return results

    def _expand_event(  # noqa: C901
        self,
        event: dict[str, Any],
        schedule_name: str,
        range_start: datetime,
        range_end: datetime,
    ) -> list[CalendarEvent]:
        """Expand a YoDeck event into CalendarEvent instances within the range."""
        start_dt = _parse_yodeck_dt(event.get("start"))
        end_dt = _parse_yodeck_dt(event.get("end"))
        if not start_dt:
            return []

        duration_mins: int = event.get("duration", 0)
        recurrence: str = event.get("recurrence", "o")
        days_of_week: str = event.get("days_of_week", "1111111")

        source = event.get("source", {})
        raw_name: str = source.get("source_name", "Unknown")
        # Strip internal metadata YoDeck appends in parentheses (e.g. "Flyers(auto-media-123-crop)")
        source_name = raw_name.split("(")[0].strip() or raw_name
        source_type: str = source.get("source_type", "media")
        summary = source_name

        def make_event(inst_start: datetime) -> CalendarEvent:
            if duration_mins > 0:
                inst_end = inst_start + timedelta(minutes=duration_mins)
            elif end_dt:
                inst_end = inst_start.replace(
                    hour=end_dt.hour, minute=end_dt.minute, second=end_dt.second
                )
                if inst_end <= inst_start:
                    inst_end = inst_start + timedelta(days=1)
            else:
                inst_end = inst_start + timedelta(hours=1)
            end_str = _localize(inst_end).strftime("%I:%M %p").lstrip("0")
            description = (
                f"{source_type.capitalize()} \u00b7 {schedule_name}\n"
                f"Ends: {end_str}"
            )
            return CalendarEvent(
                summary=summary,
                start=_localize(inst_start),
                end=_localize(inst_end),
                description=description,
            )

        def in_range(inst_start: datetime, inst_end: datetime) -> bool:
            return inst_start < range_end and inst_end > range_start

        def check_dow(dt: datetime) -> bool:
            dow = dt.weekday()  # 0=Monday, 6=Sunday
            return len(days_of_week) > dow and days_of_week[dow] == "1"

        def safe_replace_year(dt: datetime, year: int) -> datetime:
            try:
                return dt.replace(year=year)
            except ValueError:
                return dt.replace(year=year, day=28)  # Feb 29 → Feb 28

        results: list[CalendarEvent] = []

        if recurrence == "o":
            # If the stored span is > 365 days, YoDeck treats it as annually repeating
            event_span = (end_dt - start_dt).days if end_dt else 0
            if event_span > 365:
                for year in range(range_start.year - 1, range_end.year + 1):
                    inst_start = safe_replace_year(start_dt, year)
                    inst_end = inst_start + timedelta(minutes=duration_mins) if duration_mins > 0 else inst_start + timedelta(days=1)
                    if in_range(inst_start, inst_end) and check_dow(inst_start):
                        results.append(make_event(inst_start))
            else:
                actual_end = (
                    start_dt + timedelta(minutes=duration_mins)
                    if duration_mins > 0
                    else (end_dt or start_dt + timedelta(hours=1))
                )
                if in_range(start_dt, actual_end) and check_dow(start_dt):
                    results.append(make_event(start_dt))

        elif recurrence == "y":
            end_dt_bound = end_dt or start_dt.replace(year=start_dt.year + 50)
            for year in range(range_start.year - 1, range_end.year + 1):
                if not (start_dt.year <= year <= end_dt_bound.year):
                    continue
                inst_start = safe_replace_year(start_dt, year)
                inst_end = inst_start + timedelta(minutes=duration_mins) if duration_mins > 0 else inst_start + timedelta(days=1)
                if in_range(inst_start, inst_end) and check_dow(inst_start):
                    results.append(make_event(inst_start))

        elif recurrence in ("d", "w"):
            # Walk day-by-day through the overlap of the event's validity and the requested range
            walk_end_dt = end_dt or (start_dt + timedelta(days=3650))
            walk_start = max(range_start.date(), start_dt.date())
            walk_end = min(range_end.date(), walk_end_dt.date())
            current = walk_start
            while current <= walk_end:
                inst_start = start_dt.replace(
                    year=current.year, month=current.month, day=current.day
                )
                inst_end = inst_start + timedelta(minutes=duration_mins) if duration_mins > 0 else inst_start + timedelta(days=1)
                if in_range(inst_start, inst_end) and check_dow(inst_start):
                    results.append(make_event(inst_start))
                current += timedelta(days=1)

        elif recurrence == "m":
            target_day = start_dt.day
            walk_end_dt = end_dt or (start_dt + timedelta(days=3650))
            year = range_start.year
            month = range_start.month
            while True:
                try:
                    candidate_date = date(year, month, target_day)
                except ValueError:
                    candidate_date = None  # Day doesn't exist this month (e.g. Feb 30)

                if candidate_date:
                    inst_start = start_dt.replace(year=year, month=month, day=target_day)
                    inst_end = inst_start + timedelta(minutes=duration_mins) if duration_mins > 0 else inst_start + timedelta(days=1)
                    if inst_start >= range_end:
                        break
                    if (
                        in_range(inst_start, inst_end)
                        and check_dow(inst_start)
                        and start_dt.date() <= candidate_date <= walk_end_dt.date()
                    ):
                        results.append(make_event(inst_start))

                # Advance to next month
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                if date(year, month, 1) > range_end.date():
                    break

        return results

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return (
            self.coordinator.last_update_success
            and self._get_schedule() is not None
        )
