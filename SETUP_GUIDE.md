# YoDeck Home Assistant Integration - Setup Guide

## What This Integration Does

This integration connects your YoDeck account to Home Assistant and creates **binary sensors** based on your YoDeck schedules. These sensors turn **ON** when you have content scheduled for today, and **OFF** when nothing is scheduled.

Perfect for automating your TV outlet! 🎉

## Quick Start

### 1. Install the Integration

**Option A: Manual Installation (Recommended for testing)**
1. Copy the entire `custom_components/yodeck` folder to your Home Assistant's `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "YoDeck"
5. Enter your API token: `yodeck:5Iou2uTj9ROh10otooCSd5W_JDg2GexZlbZ0o9VYidn9DOHZUOkkYwKgiLXDNuDI`

**Option B: HACS (For long-term use)**
1. Push this repository to GitLab/GitHub
2. Add as a custom repository in HACS
3. Install from HACS
4. Restart and configure

### 2. What You'll Get

After setup, you'll see a binary sensor for each of your schedules:

- **`binary_sensor.yodeck_schedule_1`** - Your main schedule

This sensor will be:
- **ON** when you have events scheduled for today (like your holiday countdowns)
- **OFF** when nothing is scheduled

### 3. Create the Automation

Add this to your `automations.yaml` or create via the UI:

```yaml
automation:
  - alias: "Control TV based on YoDeck schedule"
    description: "Turn TV outlet on/off based on whether content is scheduled"
    trigger:
      - platform: state
        entity_id: binary_sensor.yodeck_schedule_1
    action:
      - service: "switch.turn_{{ 'on' if trigger.to_state.state == 'on' else 'off' }}"
        target:
          entity_id: switch.tv_outlet  # Change this to your actual outlet entity
```

### 4. Verify It's Working

1. Check Developer Tools → States
2. Look for `binary_sensor.yodeck_schedule_1`
3. Click on it to see:
   - **State**: `on` or `off`
   - **Attributes**:
     - `active_events_today`: How many events are scheduled for today
     - `active_events`: List of what's scheduled (names, types, durations)

## Understanding Your Schedule Data

Based on your actual schedule, you have these events:
- **New Years Day Video** - Plays January 1st
- **Halloween Countdown** - Yearly recurring starting Sept 15
- **Christmas Countdown** - Yearly recurring starting Nov 15
- **Halloween Day** - Plays October 31st
- **Christmas Slide** - Plays December 25th
- **New Years Countdown** - Plays December 31st

The binary sensor checks:
1. Is today within the event's date range?
2. Does the recurrence pattern match today?
3. Is it enabled for today's day of the week?

If ANY event matches, the sensor turns **ON**, which triggers your automation to turn on the TV outlet!

## Troubleshooting

### Sensor Shows "Unavailable"
- Check Home Assistant logs for errors
- Verify your API token is correct
- Make sure you have internet connectivity

### Sensor is Always OFF
- Check that your schedule actually has events for today
- Enable debug logging to see what the integration sees:
  ```yaml
  logger:
    default: warning
    logs:
      custom_components.yodeck: debug
  ```

### Automation Not Triggering
- Replace `switch.tv_outlet` with your actual outlet entity ID
- Check in Developer Tools → States to find the correct entity ID for your outlet

## What's Next?

Future enhancements could include:
- Screen status monitoring (is the screen online?)
- Current playing content detection
- Schedule management (create/edit schedules from HA)
- Support for multiple schedules
- Time-based triggers (turn on TV 5 minutes before content starts)

## Need Help?

1. Check Home Assistant logs: Settings → System → Logs
2. Enable debug logging (see above)
3. Check the [YoDeck API docs](https://app.yodeck.com/api-docs/)
