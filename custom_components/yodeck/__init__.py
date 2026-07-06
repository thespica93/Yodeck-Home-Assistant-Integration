"""The YoDeck integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import YoDeckDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SELECT, Platform.SENSOR]

SERVICE_ADD_SCHEDULE_EVENT = "add_schedule_event"
SERVICE_SCHEDULE_FROM_CALENDAR = "schedule_from_calendar_event"
SERVICE_LIST_SCHEDULES = "list_schedules"
SERVICE_LIST_MEDIA = "list_media"
SERVICE_LIST_PLAYLISTS = "list_playlists"
SERVICE_LIST_LAYOUTS = "list_layouts"
SERVICE_LIST_MONITORS = "list_monitors"

SERVICE_SCHEDULE_FROM_CALENDAR_SCHEMA = vol.Schema({
    vol.Required("calendar_entity"): cv.entity_id,
    vol.Required("event_name"): cv.string,
    vol.Optional("days_before", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
    vol.Optional("days_after", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
    vol.Optional("look_ahead_days", default=365): vol.All(vol.Coerce(int), vol.Range(min=1, max=730)),
    vol.Required("schedule"): cv.string,
    vol.Optional("content_type"): vol.In(["media", "playlist", "layout"]),
    vol.Required("content"): cv.string,
    vol.Required("screen"): cv.string,
    vol.Optional("priority", default=5): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
    vol.Optional("delay", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
})

SERVICE_ADD_SCHEDULE_EVENT_SCHEMA = vol.Schema({
    vol.Required("schedule"): cv.string,
    vol.Optional("content_type"): vol.In(["media", "playlist", "layout"]),
    vol.Required("content"): cv.string,
    vol.Optional("duration_preset"): vol.In(["today", "1h", "2h", "4h", "8h", "12h", "24h", "3d", "1w"]),
    vol.Optional("start_datetime"): cv.datetime,
    vol.Optional("end_datetime"): cv.datetime,
    vol.Required("recurrence_type"): vol.In(["once", "daily", "weekday", "weekly", "monthly", "annually"]),
    vol.Optional("priority", default=5): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
    # vol.Optional("fitting", default="fit"): vol.In(["fit", "crop", "stretch"]),  # Not working yet
    vol.Required("screen"): cv.string,
    vol.Optional("delay", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
})


def _resolve_select_entity(value: str, hass: HomeAssistant) -> str:
    """If value is a select entity_id, return its current state; otherwise return as-is.

    Allows service fields to accept either a plain name/ID string or a
    select.yodeck_* entity_id — whichever the UI or automation provides.
    """
    if "." in value:
        state = hass.states.get(value)
        if state and state.state not in ("unknown", "unavailable", ""):
            return state.state
    return value


_CONTENT_PREFIXES: dict[str, str] = {
    "media: ": "media",
    "playlist: ": "playlist",
    "layout: ": "layout",
}


def _parse_content(raw: str, fallback_type: str | None) -> tuple[str, str]:
    """Return (content_type, content_name) from a raw content value.

    If the value has a type prefix from YoDeckContentSelect (e.g. "media: Xmas Video"),
    the prefix is stripped and the type is extracted. Otherwise falls back to
    the explicit content_type field (needed for plain-name/ID input from YAML automations).
    """
    for prefix, ctype in _CONTENT_PREFIXES.items():
        if raw.startswith(prefix):
            return ctype, raw[len(prefix):]
    if fallback_type:
        return fallback_type, raw
    raise HomeAssistantError(
        "content_type is required when content is entered as a plain name or ID "
        "(it can be omitted when using the select.yodeck_content entity)"
    )


def _resolve_id_or_name(value: str, items: list[dict[str, Any]], item_type: str) -> int:
    """Resolve an ID or name to an ID.

    Args:
        value: Either a numeric ID as string or a name
        items: List of items (schedules, media, etc.)
        item_type: Type of item for error messages (e.g., "schedule", "media")

    Returns:
        The numeric ID

    Raises:
        HomeAssistantError: If the ID/name cannot be resolved
    """
    # Try to parse as an integer ID first
    try:
        return int(value)
    except ValueError:
        pass

    # Search by name (case-insensitive)
    value_lower = value.lower()
    for item in items:
        item_name = item.get("name", "")
        if item_name.lower() == value_lower:
            return item.get("id")

    # Not found
    raise HomeAssistantError(
        f"{item_type.capitalize()} '{value}' not found. "
        f"Please check sensor.yodeck_{item_type}s for available options."
    )


def _get_recurrence_pattern(recurrence_type: str, start_dt: datetime) -> tuple[str, str]:
    """Convert recurrence type to YoDeck recurrence and days_of_week pattern."""
    if recurrence_type == "once":
        return ("o", "1111111")  # Once with no day restriction
    elif recurrence_type == "daily":
        return ("d", "1111111")  # Daily, all days
    elif recurrence_type == "weekday":
        return ("d", "1111100")  # Daily, Mon-Fri only
    elif recurrence_type == "weekly":
        # Weekly on the same day as start date
        day_index = start_dt.weekday()  # 0=Monday, 6=Sunday
        days = ["0"] * 7
        days[day_index] = "1"
        return ("w", "".join(days))
    elif recurrence_type == "monthly":
        return ("m", "1111111")  # Monthly
    elif recurrence_type == "annually":
        return ("y", "1111111")  # Yearly
    return ("o", "1111111")  # Default to once


def _merge_or_append_event(
    existing_events: list[dict[str, Any]],
    new_event: dict[str, Any],
    content_id: int,
    start: datetime,
    end: datetime,
) -> tuple[list[dict[str, Any]], bool]:
    """Merge new date range into an existing event for the same content if they overlap.

    Returns (updated_events_list, was_merged). When was_merged is True the existing
    event was extended in-place to cover the union of both date ranges. When False
    the new event was appended as a brand-new entry.
    """
    updated = list(existing_events)
    for i, event in enumerate(updated):
        if event.get("source", {}).get("source_id") != content_id:
            continue
        try:
            ev_start = datetime.fromisoformat(event["start"]).replace(tzinfo=None)
            ev_end = datetime.fromisoformat(event["end"]).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        # <= so that touching/adjacent events are also merged
        if start <= ev_end and ev_start <= end:
            new_duration = int((end - start).total_seconds() / 60)
            updated[i] = {
                **event,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "duration": new_duration,
            }
            return updated, True
    return updated + [new_event], False


async def _notify(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message, "notification_id": notification_id},
    )


async def _handle_list_schedules(call: ServiceCall, hass: HomeAssistant) -> None:
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))
    try:
        results = (await coordinator.api.get_schedules()).get("results", [])
        lines = [f"- **{s['name']}** (ID: {s['id']})" for s in results]
        await _notify(hass, "YoDeck Schedules", "\n".join(lines) or "None found.", "yodeck_list_schedules")
    except Exception as err:
        raise HomeAssistantError(f"Failed to list schedules: {err}") from err


async def _handle_list_media(call: ServiceCall, hass: HomeAssistant) -> None:
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))
    try:
        results = (await coordinator.api.get_media()).get("results", [])
        lines = [f"- **{m['name']}** (ID: {m['id']})" for m in results]
        await _notify(hass, "YoDeck Media", "\n".join(lines) or "None found.", "yodeck_list_media")
    except Exception as err:
        raise HomeAssistantError(f"Failed to list media: {err}") from err


async def _handle_list_playlists(call: ServiceCall, hass: HomeAssistant) -> None:
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))
    try:
        results = (await coordinator.api.get_playlists()).get("results", [])
        lines = [f"- **{p['name']}** (ID: {p['id']})" for p in results]
        await _notify(hass, "YoDeck Playlists", "\n".join(lines) or "None found.", "yodeck_list_playlists")
    except Exception as err:
        raise HomeAssistantError(f"Failed to list playlists: {err}") from err


async def _handle_list_layouts(call: ServiceCall, hass: HomeAssistant) -> None:
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))
    try:
        results = (await coordinator.api.get_layouts()).get("results", [])
        lines = [f"- **{l['name']}** (ID: {l['id']})" for l in results]
        await _notify(hass, "YoDeck Layouts", "\n".join(lines) or "None found.", "yodeck_list_layouts")
    except Exception as err:
        raise HomeAssistantError(f"Failed to list layouts: {err}") from err


async def _handle_list_monitors(call: ServiceCall, hass: HomeAssistant) -> None:
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))
    try:
        results = (await coordinator.api.get_monitors()).get("results", [])
        lines = [f"- **{m['name']}** (ID: {m['id']})" for m in results]
        await _notify(hass, "YoDeck Screens", "\n".join(lines) or "None found.", "yodeck_list_monitors")
    except Exception as err:
        raise HomeAssistantError(f"Failed to list monitors: {err}") from err


async def _handle_schedule_from_calendar_event(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the schedule_from_calendar_event service call."""
    calendar_entity_id = call.data["calendar_entity"]
    event_name = call.data["event_name"]
    days_before = call.data.get("days_before", 0)
    days_after = call.data.get("days_after", 0)
    look_ahead_days = call.data.get("look_ahead_days", 365)
    schedule_input = _resolve_select_entity(call.data["schedule"], hass)
    content_raw = _resolve_select_entity(call.data["content"], hass)
    content_type, content_input = _parse_content(content_raw, call.data.get("content_type"))
    screen_input = _resolve_select_entity(call.data["screen"], hass)
    priority = call.data.get("priority", 5)
    delay = call.data.get("delay", 0)

    now = dt_util.now()
    search_end = now + timedelta(days=look_ahead_days)

    # Fetch events from the HA calendar via the built-in calendar.get_events service
    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": calendar_entity_id,
                "start_date_time": now.isoformat(),
                "end_date_time": search_end.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:
        raise HomeAssistantError(
            f"Failed to fetch events from calendar '{calendar_entity_id}': {err}"
        ) from err

    events = response.get(calendar_entity_id, {}).get("events", [])

    if not events:
        raise HomeAssistantError(
            f"No events found in '{calendar_entity_id}' within the next {look_ahead_days} days"
        )

    # Find first event whose summary contains the search term (case-insensitive)
    event_name_lower = event_name.lower()
    matched_event = None
    for event in events:
        if event_name_lower in event.get("summary", "").lower():
            matched_event = event
            break

    if matched_event is None:
        available = [e.get("summary", "") for e in events[:10]]
        raise HomeAssistantError(
            f"No event matching '{event_name}' found in '{calendar_entity_id}' "
            f"within the next {look_ahead_days} days. "
            f"Available events (first 10): {available}"
        )

    _LOGGER.info(
        "Found calendar event '%s' starting %s",
        matched_event.get("summary"), matched_event.get("start"),
    )

    # Parse start/end — HA returns {"date": "YYYY-MM-DD"} or {"dateTime": "ISO string"}
    def _parse_calendar_dt(field: dict) -> datetime:
        if "dateTime" in field:
            parsed = datetime.fromisoformat(field["dateTime"])
            return dt_util.as_local(parsed).replace(tzinfo=None) if parsed.tzinfo else parsed
        d = datetime.strptime(field["date"], "%Y-%m-%d").date()
        return datetime.combine(d, datetime.min.time())

    event_start = _parse_calendar_dt(matched_event["start"])
    event_end = _parse_calendar_dt(matched_event["end"])

    schedule_start = event_start - timedelta(days=days_before)
    schedule_end = event_end + timedelta(days=days_after)

    _LOGGER.info(
        "Scheduling content window: %s → %s (%d days before, %d days after '%s')",
        schedule_start, schedule_end, days_before, days_after, matched_event.get("summary"),
    )

    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")
    coordinator = next(iter(coordinators.values()))

    duration = int((schedule_end - schedule_start).total_seconds() / 60)

    try:
        schedules_response = await coordinator.api.get_schedules()
        schedules = schedules_response.get("results", [])
        schedule_id = _resolve_id_or_name(schedule_input, schedules, "schedule")

        current_schedule = next((s for s in schedules if s.get("id") == schedule_id), None)
        if not current_schedule:
            raise HomeAssistantError(f"Schedule with ID {schedule_id} not found")

        if content_type == "media":
            content_response = await coordinator.api.get_media()
        elif content_type == "playlist":
            content_response = await coordinator.api.get_playlists()
        elif content_type == "layout":
            content_response = await coordinator.api.get_layouts()
        else:
            raise HomeAssistantError(f"Invalid content type: {content_type}")

        content_list = content_response.get("results", [])
        content_id = _resolve_id_or_name(content_input, content_list, content_type)

        new_event = {
            "source": {
                "source_id": content_id,
                "source_type": content_type,
            },
            "start": schedule_start.isoformat(),
            "end": schedule_end.isoformat(),
            "duration": duration,
            "priority": priority,
            "recurrence": "o",
            "days_of_week": "1111111",
        }

        existing_events = current_schedule.get("events", [])
        merged_events, was_merged = _merge_or_append_event(
            existing_events, new_event, content_id, schedule_start, schedule_end
        )

        if was_merged:
            _LOGGER.info(
                "Extended existing event for content %s in schedule %s to %s → %s",
                content_id, schedule_id, schedule_start, schedule_end,
            )

        update_data = {
            "name": current_schedule["name"],
            "events": merged_events,
        }
        if "workspace" in current_schedule:
            update_data["workspace"] = current_schedule["workspace"]
        if "filler_content" in current_schedule:
            update_data["filler_content"] = current_schedule["filler_content"]

        _LOGGER.debug("Sending calendar-based event to YoDeck: %s", new_event)
        await coordinator.api.update_schedule(schedule_id, update_data)

        if delay > 0:
            await asyncio.sleep(delay)

        all_screens = coordinator.data.get("screens", [])
        screen_id = _resolve_id_or_name(screen_input, all_screens, "screen")
        screen_name = next(
            (s.get("name", "Unknown") for s in all_screens if s.get("id") == screen_id),
            "Unknown",
        )

        await coordinator.api.push_to_screen(screen_id)
        await coordinator.api.refresh_screenshot(screen_id)
        await coordinator.async_request_refresh()

        _LOGGER.info(
            "Scheduled content around '%s' on screen %s (%s): %s → %s",
            matched_event.get("summary"), screen_id, screen_name, schedule_start, schedule_end,
        )

    except HomeAssistantError:
        raise
    except Exception as err:
        _LOGGER.error("Error scheduling from calendar event: %s", err)
        raise HomeAssistantError(f"Failed to schedule from calendar event: {err}") from err


async def _handle_add_schedule_event(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the add_schedule_event service call."""
    schedule_input = _resolve_select_entity(call.data["schedule"], hass)
    content_raw = _resolve_select_entity(call.data["content"], hass)
    content_type, content_input = _parse_content(content_raw, call.data.get("content_type"))
    recurrence_type = call.data["recurrence_type"]
    priority = call.data.get("priority", 5)
    # fitting = call.data.get("fitting", "fit")  # Not working yet
    screen_input = _resolve_select_entity(call.data["screen"], hass)
    delay = call.data.get("delay", 0)
    duration_preset = call.data.get("duration_preset")

    # Resolve start/end datetimes from preset or explicit fields
    _PRESET_MINUTES = {
        "1h": 60, "2h": 120, "4h": 240, "8h": 480,
        "12h": 720, "24h": 1440, "3d": 4320, "1w": 10080,
    }

    if duration_preset == "today":
        # Full day in local time: today 00:00 → tomorrow 00:00
        today = dt_util.now().date()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())
    elif duration_preset in _PRESET_MINUTES:
        raw_start = call.data.get("start_datetime")
        if raw_start is None:
            start_dt = dt_util.now().replace(tzinfo=None)
        elif getattr(raw_start, "tzinfo", None) is not None:
            start_dt = dt_util.as_local(raw_start).replace(tzinfo=None)
        else:
            start_dt = raw_start
        end_dt = start_dt + timedelta(minutes=_PRESET_MINUTES[duration_preset])
    else:
        # Manual mode — both fields required
        raw_start = call.data.get("start_datetime")
        raw_end = call.data.get("end_datetime")
        if raw_start is None or raw_end is None:
            raise HomeAssistantError(
                "start_datetime and end_datetime are required when duration_preset is not set"
            )
        start_dt = dt_util.as_local(raw_start).replace(tzinfo=None) if getattr(raw_start, "tzinfo", None) else raw_start
        end_dt = dt_util.as_local(raw_end).replace(tzinfo=None) if getattr(raw_end, "tzinfo", None) else raw_end

    # Get the coordinator from the first available entry
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    # Get the first coordinator (assume single instance for now)
    coordinator = next(iter(coordinators.values()))

    # Calculate duration in minutes
    duration = int((end_dt - start_dt).total_seconds() / 60)

    # Get recurrence pattern
    recurrence, days_of_week = _get_recurrence_pattern(recurrence_type, start_dt)

    # Fetch the current schedule to get existing events
    try:
        schedules_response = await coordinator.api.get_schedules()
        schedules = schedules_response.get("results", [])

        # Resolve schedule ID from input (ID or name)
        schedule_id = _resolve_id_or_name(schedule_input, schedules, "schedule")

        current_schedule = None
        for sched in schedules:
            if sched.get("id") == schedule_id:
                current_schedule = sched
                break

        if not current_schedule:
            raise HomeAssistantError(f"Schedule with ID {schedule_id} not found")

        # Fetch content list based on type to resolve content ID
        if content_type == "media":
            content_response = await coordinator.api.get_media()
        elif content_type == "playlist":
            content_response = await coordinator.api.get_playlists()
        elif content_type == "layout":
            content_response = await coordinator.api.get_layouts()
        else:
            raise HomeAssistantError(f"Invalid content type: {content_type}")

        content_list = content_response.get("results", [])

        # Resolve content ID from input (ID or name)
        content_id = _resolve_id_or_name(content_input, content_list, content_type)

        # # Map fitting values to what YoDeck expects  # Not working yet
        # fitting_map = {
        #     "fit": "fit",
        #     "crop": "crop",
        #     "stretch": "stretch"
        # }

        # Create the new event
        new_event = {
            "source": {
                "source_id": content_id,
                "source_type": content_type,
                # "fitting": fitting_map.get(fitting, "fit"),  # Not working yet
            },
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "duration": duration,
            "priority": priority,
            "recurrence": recurrence,
            "days_of_week": days_of_week,
        }

        # _LOGGER.debug("Created event with fitting=%s for content %s", fitting, content_id)  # Not working yet

        # Add the new event — extend an existing one if the same content overlaps this window
        existing_events = current_schedule.get("events", [])
        updated_events, was_merged = _merge_or_append_event(
            existing_events, new_event, content_id, start_dt, end_dt
        )

        if was_merged:
            _LOGGER.info(
                "Extended existing event for content %s in schedule %s to %s → %s",
                content_id, schedule_id, start_dt, end_dt,
            )

        # Prepare the update payload - preserve all existing fields
        update_data = {
            "name": current_schedule["name"],
            "events": updated_events,
        }

        # Preserve important fields from the original schedule
        if "workspace" in current_schedule:
            update_data["workspace"] = current_schedule["workspace"]
        if "filler_content" in current_schedule:
            update_data["filler_content"] = current_schedule["filler_content"]

        # Log the event data for debugging
        _LOGGER.debug("Sending event to YoDeck API: %s", new_event)
        _LOGGER.debug("Full schedule update payload: %s", update_data)

        # Update the schedule
        await coordinator.api.update_schedule(schedule_id, update_data)

        # Wait for the schedule update to propagate (if delay is configured)
        if delay > 0:
            _LOGGER.debug("Waiting %d seconds before pushing to screens...", delay)
            await asyncio.sleep(delay)

        # Get screens from cached coordinator data
        all_screens = coordinator.data.get("screens", [])

        # Resolve screen ID from input (ID or name)
        screen_id = _resolve_id_or_name(screen_input, all_screens, "screen")

        # Find the screen details
        screen_name = "Unknown"
        for screen in all_screens:
            if screen.get("id") == screen_id:
                screen_name = screen.get("name", "Unknown")
                break

        # Push to the specified screen
        try:
            await coordinator.api.push_to_screen(screen_id)
            _LOGGER.info("Pushed schedule to screen %s (%s)", screen_id, screen_name)
            # Refresh screenshot to ensure the new content is displayed
            await coordinator.api.refresh_screenshot(screen_id)
            _LOGGER.info("Refreshed screenshot for screen %s (%s)", screen_id, screen_name)
        except Exception as push_err:
            _LOGGER.error("Failed to push/refresh screen %s (%s): %s", screen_id, screen_name, push_err)
            raise HomeAssistantError(f"Failed to push to screen: {push_err}") from push_err

        # Refresh the coordinator to get updated data
        await coordinator.async_request_refresh()

        _LOGGER.info("Successfully added event to schedule %s and pushed to screen %s (%s)",
                    schedule_id, screen_id, screen_name)

    except Exception as err:
        _LOGGER.error("Error adding event to schedule: %s", err)
        raise HomeAssistantError(f"Failed to add event: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YoDeck from a config entry."""
    api_token = entry.data[CONF_API_TOKEN]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    coordinator = YoDeckDataUpdateCoordinator(hass, session, api_token, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady("Unable to connect to YoDeck API")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Register services
    async def handle_list_schedules(call: ServiceCall) -> None:
        """Handle list schedules service call."""
        await _handle_list_schedules(call, hass)

    async def handle_list_media(call: ServiceCall) -> None:
        """Handle list media service call."""
        await _handle_list_media(call, hass)

    async def handle_list_playlists(call: ServiceCall) -> None:
        """Handle list playlists service call."""
        await _handle_list_playlists(call, hass)

    async def handle_list_layouts(call: ServiceCall) -> None:
        """Handle list layouts service call."""
        await _handle_list_layouts(call, hass)

    async def handle_list_monitors(call: ServiceCall) -> None:
        """Handle list monitors service call."""
        await _handle_list_monitors(call, hass)

    async def handle_add_schedule_event(call: ServiceCall) -> None:
        """Handle add schedule event service call."""
        await _handle_add_schedule_event(call, hass)

    async def handle_schedule_from_calendar_event(call: ServiceCall) -> None:
        """Handle schedule from calendar event service call."""
        await _handle_schedule_from_calendar_event(call, hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_SCHEDULES,
        handle_list_schedules,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_MEDIA,
        handle_list_media,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_PLAYLISTS,
        handle_list_playlists,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_LAYOUTS,
        handle_list_layouts,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_MONITORS,
        handle_list_monitors,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SCHEDULE_EVENT,
        handle_add_schedule_event,
        schema=SERVICE_ADD_SCHEDULE_EVENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCHEDULE_FROM_CALENDAR,
        handle_schedule_from_calendar_event,
        schema=SERVICE_SCHEDULE_FROM_CALENDAR_SCHEMA,
    )

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_LIST_SCHEDULES)
            hass.services.async_remove(DOMAIN, SERVICE_LIST_MEDIA)
            hass.services.async_remove(DOMAIN, SERVICE_LIST_PLAYLISTS)
            hass.services.async_remove(DOMAIN, SERVICE_LIST_LAYOUTS)
            hass.services.async_remove(DOMAIN, SERVICE_LIST_MONITORS)
            hass.services.async_remove(DOMAIN, SERVICE_ADD_SCHEDULE_EVENT)
            hass.services.async_remove(DOMAIN, SERVICE_SCHEDULE_FROM_CALENDAR)

    return unload_ok
