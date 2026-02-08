# PetTracer Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [PetTracer](https://www.pettracer.com/) GPS pet trackers.

## Features

- 📍 **GPS Location Tracking** - See your pet's location on the Home Assistant map
- 📶 **Signal Strength Monitoring** - Track GPS signal strength in real-time
- 🔋 **Battery Level** - Monitor tracker battery status
- 📊 **Multiple Sensors** - Signal percentage, dBm, battery, and signal level
- 🔄 **Auto-refresh** - Data updates every 60 seconds
- 🐕 **Multi-device Support** - Works with multiple trackers on one account

## Entities

### Device Tracker
Your pet will appear as a device tracker on the Home Assistant map with GPS coordinates.

### Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Signal Strength | Signal strength as percentage | % |
| Signal dBm | Signal strength in decibels | dBm |
| Signal Level | Text (excellent/good/fair/poor/none) | - |
| Battery | Tracker battery level | % |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/max246/hacs-pettracer`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "PetTracer" and install

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/pettracer` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "PetTracer"
4. Enter your PetTracer account email and password
5. Your trackers will be automatically discovered

## Signal Level Thresholds

| Level | Percentage |
|-------|------------|
| Excellent | > 70% |
| Good | 50-70% |
| Fair | 30-50% |
| Poor | 5-30% |
| None | < 5% |

## Example Automations

### Alert when signal is weak

```yaml
automation:
  - alias: "Pet Tracker Signal Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.tracker_signal_strength
        below: 30
        for: "00:05:00"
    action:
      - service: notify.mobile_app
        data:
          message: "⚠️ Pet tracker signal is weak ({{ states('sensor.tracker_signal_strength') }}%)"
```

### Log signal strength history

```yaml
sensor:
  - platform: statistics
    entity_id: sensor.tracker_signal_dbm
    name: "Tracker Signal 24h Average"
    state_characteristic: mean
    max_age:
      hours: 24
```

## Technical Details

This integration uses the PetTracer REST API to poll device data. The signal strength is calculated using the same formulas as the official PetTracer portal:

- **Raw RSSI to dBm**: `(255 & value) / 2 - 130`
- **dBm to Percent**: `100 × 1.35 × (1 - dBm / -130)`

## Troubleshooting

### "Invalid credentials" error
Make sure you're using the same email and password as the PetTracer mobile app or web portal.

### No devices found
Ensure your tracker is registered and visible in the PetTracer app.

### Data not updating
Check the Home Assistant logs for any API errors. The integration retries automatically on connection failures.

## Support

- 🐛 [Report a bug](https://github.com/max246/hacs-pettracer/issues)
- 💬 [Discord](https://discord.gg/home-assistant)

## License

MIT License - See [LICENSE](LICENSE) for details.
