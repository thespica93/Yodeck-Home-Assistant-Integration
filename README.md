# YoDeck Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A Home Assistant integration for YoDeck digital signage that monitors your schedules and automates your TV outlet based on scheduled content.

## Features

- 📅 **Schedule Monitoring**: Track when content is scheduled to play
- 🔌 **Smart Outlet Control**: Automatically turn on/off your TV based on schedule state
- 📊 **Rich Attributes**: See what content is scheduled for today with priority and duration
- 🔄 **Auto-Discovery**: Automatically discovers all schedules on your YoDeck account

## Entities

### Binary Sensors
- **YoDeck [Schedule Name]**: Turns ON when there's content scheduled for today, OFF when nothing is scheduled
  - Attributes include:
    - `active_events_today`: Count of events scheduled for today
    - `active_events`: List of scheduled content with names, types, priorities, and durations
    - `total_events`: Total number of events in the schedule

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add the repository URL: `https://github.com/yourusername/yodeck-ha`
6. Select category: "Integration"
7. Click "Add"
8. Find "YoDeck" in the integration list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/yodeck` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "YoDeck"
4. Enter your YoDeck API token

### Getting Your API Token

1. Log in to your [YoDeck account](https://yodeck.com)
2. Click on **Account** in the top navigation bar
3. Select **Account Settings** from the menu
4. In the **Advanced Settings** section, click **API Tokens**
5. Click **Generate Token**
6. Enter a name for the token (e.g., "Home Assistant")
7. Select a role (the token will have the permissions of that role)
8. Click **Create Token**
9. **Copy the token** and save it securely (you won't be able to see it again!)

## Usage Examples

### Automate TV Power Based on Schedule

Turn on your TV outlet when something is scheduled, turn it off when nothing is scheduled:

```yaml
automation:
  - alias: "Turn on TV when YoDeck has scheduled content"
    trigger:
      - platform: state
        entity_id: binary_sensor.yodeck_schedule_1
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.tv_outlet

  - alias: "Turn off TV when YoDeck schedule is empty"
    trigger:
      - platform: state
        entity_id: binary_sensor.yodeck_schedule_1
        to: "off"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.tv_outlet
```

### Single Automation (Simpler)

```yaml
automation:
  - alias: "Control TV based on YoDeck schedule"
    trigger:
      - platform: state
        entity_id: binary_sensor.yodeck_schedule_1
    action:
      - service: "switch.turn_{{ 'on' if trigger.to_state.state == 'on' else 'off' }}"
        target:
          entity_id: switch.tv_outlet
```

### Show Schedule Card

Display current schedule status and what's playing today:

```yaml
type: entities
entities:
  - entity: binary_sensor.yodeck_schedule_1
    secondary_info: last-changed
  - type: attribute
    entity: binary_sensor.yodeck_schedule_1
    attribute: active_events_today
    name: Events Today
  - type: attribute
    entity: binary_sensor.yodeck_schedule_1
    attribute: active_events
    name: Scheduled Content
```

## API Rate Limits

The YoDeck API has rate limiting:
- **Free tier**: 14 requests per 10 seconds per token
- **Standard tier**: 21 requests per 10 seconds per token
- **High tier**: 33 requests per 10 seconds per token

This integration polls every 5 minutes by default, which is well within all rate limits.

## Troubleshooting

### Integration Not Showing Schedules

1. Verify your API token is correct
2. Check that your YoDeck account has schedules configured
3. Enable debug logging to see API responses:

```yaml
logger:
  default: warning
  logs:
    custom_components.yodeck: debug
```

### Sensors Showing "Unavailable"

- Check your internet connection
- Verify the YoDeck API is accessible
- Check Home Assistant logs for error messages

## Supported YoDeck Features

- ✅ Schedule monitoring
- ✅ Active event detection (today's scheduled content)
- ✅ Event details (name, type, priority, duration)
- 🚧 Schedule management (create/edit schedules - planned)
- 🚧 Screen status monitoring (planned)
- 🚧 Content management (planned)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not officially affiliated with or endorsed by YoDeck. YoDeck is a trademark of YoKenSoft Ltd.

## Support

- 🐛 [Report a Bug](https://github.com/yourusername/yodeck-ha/issues)
- 💡 [Request a Feature](https://github.com/yourusername/yodeck-ha/issues)
- 📖 [YoDeck API Documentation](https://api.yodeck.com/)
