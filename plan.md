# YoDeck HA Integration — Project Plan

> **Session rules:**
> - Read this file at the start of every new session before doing any work.
> - Add every new task here before starting it.
> - Mark tasks `[x]` as soon as they are completed.
> - Keep this document the single source of truth for what has been done and what is next.
> - **Every push must be a new GitHub release.** Bump `manifest.json` version, commit, push, then run `& "C:\Program Files\GitHub CLI\gh.exe" release create vX.Y.Z --title "..." --notes "..."` to create the matching release tag.

## Completed

### Core Infrastructure
- [x] Config flow (API token entry, connection test)
- [x] Data coordinator with configurable scan interval (default 60min, min 5min)
- [x] API client (`api.py`) — GET/PUT/POST with auth header `Token label:value`
- [x] Rate limit handling (HTTP 429 + Retry-After)
- [x] Constants file (`const.py`)
- [x] HACS compatibility — `manifest.json`, `icon.png`, `hacs.json`
- [x] Icon at `custom_components/yodeck/icon.png` for HA integration card
- [x] GitHub releases for HACS auto-update detection
- [x] Version 0.3.0

### Platforms
- [x] **Sensor** — 5 sensors: Schedules, Screens, Media, Playlists, Layouts (count + ID→name map in attributes)
- [x] **Binary Sensor** — one per schedule; ON when an event is currently active; attributes include active event details (name, type, priority, duration, start/end)
- [x] **Button** — `button.yodeck_refresh` to force coordinator refresh
- [x] **Calendar** — one calendar entity per schedule; expands recurring events into HA calendar UI; handles all recurrence types

### Services
- [x] `list_schedules` — logs all schedule IDs and names
- [x] `list_media` — logs all media IDs, names, and types
- [x] `list_playlists` — logs all playlist IDs and names
- [x] `list_layouts` — logs all layout IDs and names
- [x] `list_monitors` — logs all screen IDs, names, and assigned schedules
- [x] `add_schedule_event` — adds an event to a schedule and pushes to a screen
  - [x] Accepts ID or friendly name for schedule, content, and screen
  - [x] `duration_preset` shortcuts (today, 1h, 2h, 4h, 8h, 12h, 24h, 3d, 1w)
  - [x] Manual `start_datetime` / `end_datetime` fallback
  - [x] `recurrence_type`: once, daily, weekday, weekly, monthly, annually
  - [x] `priority` (0–10)
  - [x] Optional `delay` before push (0–10 seconds)
  - [x] Screenshot refresh after push
  - [x] Duplicate guard — silently skips if same content already covers the window
- [x] `schedule_from_calendar_event` — schedules content around a named HA calendar event
  - [x] Entity selector for any connected HA calendar (Google, local, holiday, etc.)
  - [x] Partial case-insensitive event name search (e.g. `"father"` matches `"Father's Day"`)
  - [x] `days_before` / `days_after` offsets around the event date
  - [x] `look_ahead_days` configurable search window (default 365)
  - [x] Duplicate guard — silently skips if same content already covers the window
  - [x] Error lists first 10 available events if name not found

### Recurrence & Timezone Handling
- [x] All recurrence codes mapped: `o` (once/annually), `y` (yearly), `d` (daily), `w` (weekly), `m` (monthly)
- [x] `days_of_week` string format (`"1111111"` Mon–Sun) honoured in binary sensors and calendar
- [x] Multi-year events treated as annual repeats
- [x] YoDeck's fake-UTC timestamps (local time with Z suffix) correctly handled

---

## Pending / In Progress

### Bug Fixes
- [ ] **Fitting options** (`fit` / `crop` / `stretch`) — commented out; YoDeck API field name/values need investigation before re-enabling

### Improvements

#### Services
- [ ] **`delete_schedule_event` service** — remove a specific event from a schedule by index or content name
- [ ] **`clear_schedule` service** — remove all events from a schedule (useful for resetting)
- [ ] **`create_schedule` service** — create a brand-new schedule via API
- [ ] **`list_*` services return persistent notifications** — instead of only logging, surface results as HA persistent notifications so users can see them in the UI without checking logs

#### Sensors / Entities
- [ ] **Active-content sensor per schedule** — a sensor (or binary_sensor attribute) that shows exactly what content is playing right now on each schedule (name, type, time remaining)
- [ ] **Screen "now playing" sensor** — per-screen sensor showing which schedule is assigned and whether content is active
- [ ] **Last-push timestamp attribute** — track when a schedule was last pushed to a screen

#### Options Flow
- [ ] **Options flow for scan interval** — let users change the poll interval after setup (currently only settable at config time)
- [ ] **Options flow for default screen** — save a default screen so `add_schedule_event` can omit it

#### Error Handling & UX
- [ ] **Persistent notifications on service failure** — surface API errors as HA notifications instead of only raising `ServiceValidationError`
- [ ] **Connection status binary sensor** — `binary_sensor.yodeck_connected` that goes OFF when the API is unreachable

#### Developer / Release
- [ ] **Re-enable fitting options** — investigate correct YoDeck API field name and valid values, then uncomment the disabled code
- [ ] **Unit tests** — basic tests for ID/name resolution, recurrence expansion, and timezone conversion
- [ ] **HACS default submission** — once stable, submit to HACS default repository list
