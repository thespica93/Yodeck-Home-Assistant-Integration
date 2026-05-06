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

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]

SERVICE_ADD_SCHEDULE_EVENT = "add_schedule_event"
SERVICE_LIST_SCHEDULES = "list_schedules"
SERVICE_LIST_MEDIA = "list_media"
SERVICE_LIST_PLAYLISTS = "list_playlists"
SERVICE_LIST_LAYOUTS = "list_layouts"
SERVICE_LIST_MONITORS = "list_monitors"

SERVICE_ADD_SCHEDULE_EVENT_SCHEMA = vol.Schema({
    vol.Required("schedule"): cv.string,  # Accept ID or name
    vol.Required("content_type"): vol.In(["media", "playlist", "layout"]),
    vol.Required("content"): cv.string,  # Accept ID or name
    vol.Required("start_datetime"): cv.datetime,
    vol.Required("end_datetime"): cv.datetime,
    vol.Required("recurrence_type"): vol.In(["once", "daily", "weekday", "weekly", "monthly", "annually"]),
    vol.Optional("priority", default=5): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
    vol.Optional("fitting", default="fit"): vol.In(["fit", "crop", "stretch"]),
    vol.Required("screen"): cv.string,  # Accept ID or name
    vol.Optional("delay", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
})


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


async def _handle_list_schedules(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the list_schedules service call."""
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    coordinator = next(iter(coordinators.values()))

    try:
        schedules_response = await coordinator.api.get_schedules()
        schedules = schedules_response.get("results", [])

        _LOGGER.info("=== Available YoDeck Schedules ===")
        for schedule in schedules:
            _LOGGER.info("ID: %s | Name: %s", schedule.get("id"), schedule.get("name"))

    except Exception as err:
        _LOGGER.error("Error listing schedules: %s", err)
        raise HomeAssistantError(f"Failed to list schedules: {err}") from err


async def _handle_list_media(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the list_media service call."""
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    coordinator = next(iter(coordinators.values()))

    try:
        media_response = await coordinator.api.get_media()
        media_list = media_response.get("results", [])

        _LOGGER.info("=== Available YoDeck Media ===")
        for media in media_list:
            _LOGGER.info("ID: %s | Name: %s | Type: %s",
                        media.get("id"), media.get("name"), media.get("type"))

    except Exception as err:
        _LOGGER.error("Error listing media: %s", err)
        raise HomeAssistantError(f"Failed to list media: {err}") from err


async def _handle_list_playlists(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the list_playlists service call."""
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    coordinator = next(iter(coordinators.values()))

    try:
        playlists_response = await coordinator.api.get_playlists()
        playlists = playlists_response.get("results", [])

        _LOGGER.info("=== Available YoDeck Playlists ===")
        for playlist in playlists:
            _LOGGER.info("ID: %s | Name: %s", playlist.get("id"), playlist.get("name"))

    except Exception as err:
        _LOGGER.error("Error listing playlists: %s", err)
        raise HomeAssistantError(f"Failed to list playlists: {err}") from err


async def _handle_list_layouts(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the list_layouts service call."""
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    coordinator = next(iter(coordinators.values()))

    try:
        layouts_response = await coordinator.api.get_layouts()
        layouts = layouts_response.get("results", [])

        _LOGGER.info("=== Available YoDeck Layouts ===")
        for layout in layouts:
            _LOGGER.info("ID: %s | Name: %s", layout.get("id"), layout.get("name"))

    except Exception as err:
        _LOGGER.error("Error listing layouts: %s", err)
        raise HomeAssistantError(f"Failed to list layouts: {err}") from err


async def _handle_list_monitors(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the list_monitors service call."""
    coordinators = hass.data[DOMAIN]
    if not coordinators:
        raise HomeAssistantError("YoDeck integration not set up")

    coordinator = next(iter(coordinators.values()))

    try:
        monitors_response = await coordinator.api.get_monitors()
        monitors = monitors_response.get("results", [])

        _LOGGER.info("=== Available YoDeck Monitors/Screens ===")
        for monitor in monitors:
            _LOGGER.info("ID: %s | Name: %s | Schedule: %s",
                        monitor.get("id"), monitor.get("name"), monitor.get("schedule"))

    except Exception as err:
        _LOGGER.error("Error listing monitors: %s", err)
        raise HomeAssistantError(f"Failed to list monitors: {err}") from err


async def _handle_add_schedule_event(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the add_schedule_event service call."""
    schedule_input = call.data["schedule"]
    content_type = call.data["content_type"]
    content_input = call.data["content"]
    recurrence_type = call.data["recurrence_type"]
    priority = call.data.get("priority", 5)
    fitting = call.data.get("fitting", "fit")
    screen_input = call.data["screen"]
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

        # Map fitting values to what YoDeck expects
        # YoDeck might use different values than our UI labels
        fitting_map = {
            "fit": "fit",
            "crop": "crop",
            "stretch": "stretch"
        }

        # Create the new event
        new_event = {
            "source": {
                "source_id": content_id,
                "source_type": content_type,
                "fitting": fitting_map.get(fitting, "fit"),
            },
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "duration": duration,
            "priority": priority,
            "recurrence": recurrence,
            "days_of_week": days_of_week,
        }

        _LOGGER.debug("Created event with fitting=%s for content %s", fitting, content_id)

        # Add the new event to existing events
        existing_events = current_schedule.get("events", [])
        updated_events = existing_events + [new_event]

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

    return unload_ok
