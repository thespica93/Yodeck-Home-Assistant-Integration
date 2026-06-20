# YoDeck Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/thespica93/Yodeck-Home-Assistant-Integration.svg)](https://github.com/thespica93/Yodeck-Home-Assistant-Integration/releases)

Control and monitor your [YoDeck](https://yodeck.com) digital signage directly from Home Assistant. Schedule content, react to what's playing, and automate your screens alongside the rest of your smart home.

---

## Features

- **Schedule monitoring** — binary sensors go ON/OFF based on whether content is actively playing right now
- **Calendar integration** — see all YoDeck events in the HA calendar UI, including recurring events
- **Service actions** — add events to schedules and push them to screens from automations
- **Holiday scheduling** — pull events from any HA calendar (Google Calendar, holiday calendars) and schedule content around them with configurable day offsets
- **Smart duplicate handling** — if the same content already covers the requested date range, the existing event is extended rather than duplicated
- **Searchable dropdowns** — all schedules, screens, and content are exposed as HA select entities for use in the service UI and automations
- **Auto-refresh** — all data refreshes in parallel on a configurable interval (default 60 min); press the refresh button for an immediate update

---

## Entities

### Binary Sensors
One per schedule — `binary_sensor.yodeck_{schedule_name}`

- **State**: `on` when content is actively playing right now, `off` otherwise
- **Attributes**: `active_events`, `active_events_today`, `total_events`, `schedule_id`, `schedule_name`

### Sensors
| Entity | State | Attributes |
|--------|-------|------------|
| `sensor.yodeck_schedules` | Schedule count | ID → name map |
| `sensor.yodeck_screens` | Screen count | ID → name map |
| `sensor.yodeck_media` | Media count | ID → name map |
| `sensor.yodeck_playlists` | Playlist count | ID → name map |
| `sensor.yodeck_layouts` | Layout count | ID → name map |

### Select Entities (searchable dropdowns)
| Entity | Options |
|--------|---------|
| `select.yodeck_schedule` | All your YoDeck schedules |
| `select.yodeck_screen` | All your YoDeck screens |
| `select.yodeck_media` | All media files |
| `select.yodeck_playlist` | All playlists |
| `select.yodeck_layout` | All layouts |
| `select.yodeck_content` | All content combined with type prefix (`media: …`, `playlist: …`, `layout: …`) |

### Calendar
One per schedule — `calendar.yodeck_{schedule_name}`

Shows all events (including recurring) in the HA calendar UI.

### Button
- `button.yodeck_refresh` — force an immediate data refresh

---

## Services

### `yodeck.add_schedule_event`
Add an event to a YoDeck schedule and push it to a screen.

| Field | Description |
|-------|-------------|
| `schedule` | Schedule (use `select.yodeck_schedule` or enter name/ID) |
| `content` | Content (use `select.yodeck_content` — auto-detects type from prefix) |
| `content_type` | Optional — only needed when typing a plain name/ID directly |
| `duration_preset` | Quick options: `today`, `1h`, `2h`, `4h`, `8h`, `12h`, `24h`, `3d`, `1w` |
| `start_datetime` | Start time (used when no preset) |
| `end_datetime` | End time (used when no preset) |
| `recurrence_type` | `once`, `daily`, `weekday`, `weekly`, `monthly`, `annually` |
| `priority` | 0–10 (default 5) |
| `screen` | Screen to push to (use `select.yodeck_screen` or enter name/ID) |
| `delay` | Seconds to wait before pushing (0–10) |

### `yodeck.schedule_from_calendar_event`
Find an event in any HA calendar and schedule YoDeck content around it.

| Field | Description |
|-------|-------------|
| `calendar_entity` | Any HA calendar entity (Google Calendar, holiday calendars, etc.) |
| `event_name` | Partial, case-insensitive search (e.g. `father` matches `Father's Day`) |
| `days_before` | Days before the event to start showing content (default 0) |
| `days_after` | Days after the event ends to stop showing content (default 0) |
| `look_ahead_days` | How far ahead to search (default 365) |
| `schedule` | YoDeck schedule to update |
| `content` | Content to show |
| `screen` | Screen to push to |

### List services
`yodeck.list_schedules`, `yodeck.list_media`, `yodeck.list_playlists`, `yodeck.list_layouts`, `yodeck.list_monitors` — log all available items with their IDs.

---

## Installation

### HACS (Recommended)

1. Open HACS → **Integrations**
2. Click the three dots → **Custom repositories**
3. Add `https://github.com/thespica93/Yodeck-Home-Assistant-Integration` as an **Integration**
4. Find **YoDeck** and click **Download**
5. Restart Home Assistant

### Manual

Copy the `custom_components/yodeck` folder into your HA `custom_components` directory and restart.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **YoDeck**
3. Enter your API token

### Getting your API token

1. Log in to [yodeck.com](https://yodeck.com)
2. **Account → Account Settings → Advanced Settings → API Tokens**
3. Click **Generate Token**, give it a name, select a role, click **Create Token**
4. Copy the token immediately — it won't be shown again

### Options

After setup, click **Configure** on the integration to change the poll interval (minimum 5 minutes, default 60 minutes).

---

## Automation Examples

### Turn on TV when content is scheduled

```yaml
automation:
  - alias: TV on when YoDeck is active
    trigger:
      platform: state
      entity_id: binary_sensor.yodeck_main_schedule
      to: "on"
    action:
      service: switch.turn_on
      target:
        entity_id: switch.tv_outlet
```

### Schedule holiday content from Google Calendar

```yaml
automation:
  - alias: Schedule Father's Day content
    trigger:
      platform: time
      at: "00:01:00"
    action:
      service: yodeck.schedule_from_calendar_event
      data:
        calendar_entity: calendar.google_holidays_in_united_states
        event_name: "father"
        days_before: 1
        days_after: 1
        schedule: Main Schedule
        content: select.yodeck_content
        screen: select.yodeck_screen
```

---

## Troubleshooting

**Integration not showing schedules**
- Verify your API token is correct
- Enable debug logging: `custom_components.yodeck: debug` in `configuration.yaml`

**Sensors unavailable**
- Check internet connectivity and that the YoDeck API is reachable
- Press `button.yodeck_refresh` to force a data reload

**Service dropdown is empty**
- The select entities populate on the first coordinator refresh — press `button.yodeck_refresh` if they appear empty after install

---

## API Rate Limits

- Free tier: 14 requests / 10 seconds
- Standard tier: 21 requests / 10 seconds
- High tier: 33 requests / 10 seconds

The integration fetches all resource types in a single parallel burst per refresh cycle, well within all tier limits.

---

## Disclaimer

This integration is not officially affiliated with or endorsed by YoDeck. YoDeck is a trademark of YoKenSoft Ltd.

## License

MIT — see [LICENSE](LICENSE)
