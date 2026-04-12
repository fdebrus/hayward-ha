# Hayward AquaRite for Home Assistant

<p align="left">
  <a href="https://www.buymeacoffee.com/fdebrus"><img src="https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-FFDD00?style=flat&logo=buymeacoffee" alt="Donate"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-Hayward-blue?style=flat&logo=homeassistant" alt="Hayward for Home Assistant">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat" alt="HACS Custom"></a>
  <a href="https://github.com/fdebrus/hayward-ha"><img src="https://img.shields.io/badge/Maintainer-fdebrus-green?style=flat" alt="Maintainer"></a>
  <a href="https://github.com/fdebrus/hayward-ha/releases"><img src="https://img.shields.io/github/v/release/fdebrus/hayward-ha?style=flat&label=release" alt="Release"></a>
  <a href="https://github.com/fdebrus/hayward-ha/issues"><img src="https://img.shields.io/github/issues/fdebrus/hayward-ha?style=flat" alt="Issues"></a>
  <a href="https://github.com/fdebrus/hayward-ha/stargazers"><img src="https://img.shields.io/github/stars/fdebrus/hayward-ha?style=flat" alt="Stars"></a>
  <a href="https://github.com/fdebrus/hayward-ha/actions/workflows/tests.yml"><img src="https://github.com/fdebrus/hayward-ha/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
</p>


Home Assistant custom integration for monitoring and controlling **Hayward-branded pool controllers**, including:

- AquaRite  
- Dagen  
- Vistapool  
- Sugar Valley  
- Poolwatch  
- Kripsol  

The integration connects to the **official Hayward cloud API** and exposes your pool equipment as native Home Assistant entities.

## Features

- Secure cloud authentication using your existing Hayward account  
- Automatic discovery of linked pool controllers  
- Real-time data updates via cloud push (no polling)  
- Background token refresh and health monitoring  
- Reconfigure credentials without removing the integration  
- Downloadable diagnostics for troubleshooting  
- Configurable options (health check interval) via the integration's Configure menu  
- Multi-language support (English, Dutch, Danish)  

### Sensors

- Water temperature  
- pH, ORP (Rx), chlorine (Cl), CD, UV module readings  
- Electrolysis / hydrolysis production level  
- Filtration intel time  
- Wi-Fi signal strength (diagnostic, disabled by default)  
- Pool location and name  

### Controls

- **Switches**: filtration on/off, electrolysis cover/boost, 4 auxiliary relays, heating climate toggle, smart mode freeze protection  
- **Number setpoints**: pH low/max, Rx setpoint, electrolysis level, Intel/Heat/Smart mode temperatures  
- **Select**: pump mode (Manual / Auto / Heat / Smart / Intel), pump speed, filtration timer speeds 1-3 (Slow / Medium / High)  
- **Time**: filtration interval 1-3 start/end times — set your filtration schedule directly from Home Assistant  
- **Light**: pool light on/off  
- **Button**: _LED pulse_ — advances the pool LED to its next color (requires LED hardware; mirrors the "Next" button in the Hayward app)  

### Binary sensors

- Filtration, backwash, and heating status  
- pH acid/base pump status, chlorine pump, Rx pump  
- pH pump alarm, acid tank level, hydrolysis flow status  
- Module presence (CD, CL, RX, pH, IO, hydrolysis)  
- Electrolysis/hydrolysis low, connectivity  

### Services

- **Sync pool time**: synchronize the pool controller's internal clock with Home Assistant's timezone  

### Platforms overview

| Platform | Count | Description |
|----------|-------|-------------|
| `sensor` | 7+ | Temperature, pH, Rx, Cl, CD, UV, electrolysis, intel time, RSSI, location |
| `binary_sensor` | 13+ | Filtration/heating/backwash status, pump states, module presence, tank levels |
| `switch` | 7+ | Filtration, electrolysis cover/boost, relays, heating climate, freeze protection |
| `number` | 5+ | pH, Rx, electrolysis setpoints, mode temperatures |
| `select` | 5 | Pump mode, pump speed, filtration timer speeds 1-3 |
| `time` | 6 | Filtration interval 1-3 start/end times |
| `light` | 1 | Pool light on/off |
| `button` | 0-1 | LED color advance (only with LED hardware) |
| `device_tracker` | 1 | Pool GPS location |

Entity counts vary based on installed modules (CD, CL, pH, RX, UV, hydrolysis) and enabled features (Heat, Smart mode).

## Requirements

- A supported Hayward-compatible pool controller  
- A Wi-Fi module connected to the internet  
- The controller must already be linked to your Hayward cloud account  
- Home Assistant 2024.1.0 or later  

## Installation

You can install the integration using **HACS** (recommended) or manually.

### Option 1: Install via HACS (recommended)

1. Open **Home Assistant → HACS → Integrations**
2. Click the **three dots menu** (top right) → **Custom repositories**
3. Add `https://github.com/fdebrus/hayward-ha` with category **Integration**
4. Search for **Aquarite** and install
5. Restart Home Assistant when prompted

### Option 2: Manual installation

1. Download or clone this repository
2. Copy the `custom_components/aquarite` directory into your Home Assistant `custom_components` folder
3. Restart Home Assistant

## Configuration

1. In Home Assistant, go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Aquarite**
4. Enter your Hayward cloud **username and password**
5. Select the pool controller you want to add

All supported entities are created automatically once the integration is set up.

### Reconfiguring credentials

If you need to update your Hayward credentials:

1. Go to **Settings → Devices & Services**
2. Find the **Aquarite** integration
3. Click the **three dots menu** → **Reconfigure**
4. Enter your new credentials

### Configuring options

After setup, you can adjust integration settings:

1. Go to **Settings → Devices & Services**
2. Find the **Aquarite** integration
3. Click the **three dots menu** → **Configure**
4. Adjust the **health check interval** (60–3600 seconds, default 300)

### Downloading diagnostics

For troubleshooting, you can download diagnostics data (credentials and personal info are automatically redacted):

1. Go to **Settings → Devices & Services**
2. Click on the **Aquarite** device
3. Click **Download diagnostics**

## Dashboard examples

Example dashboard inspired by the excellent work from  
https://github.com/alexdelprete/HA-NeoPool-MQTT

![Dashboard example](https://github.com/user-attachments/assets/11c6467f-6a9e-4469-af36-3613e40a6b92)

### Intel mode

<img src="https://github.com/user-attachments/assets/c5a3b070-072d-421b-955f-a41667d738b7" width="600">

### Smart mode

<img src="https://github.com/user-attachments/assets/b9cb0f21-34a3-4c25-9332-02eee6988963" width="600">

## Time synchronization service

The integration exposes a service allowing you to **synchronize the pool controller's internal clock** with Home Assistant's timezone.

This is useful to ensure correct scheduling and reporting, especially after power outages or controller restarts.

![Time sync service](https://github.com/user-attachments/assets/5b9896b1-b5b8-481f-933e-4e7482072fab)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Entities show "Unavailable" | Check your internet connection and verify the controller is online in the Hayward app. The integration will automatically reconnect. |
| Reauth notification appears | Your credentials may have changed or expired. Click the notification to re-enter your username and password. |
| Entities not updating | The integration uses real-time cloud push. If updates stop, try reloading the integration from Settings → Devices & Services. |
| HACS can't find the integration | Make sure you added the custom repository URL first (see installation steps above). |

## Development

The integration includes a test suite that runs automatically via GitHub Actions on every push and pull request.

To run tests locally:

```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component aioaquarite==0.1.0
python -m pytest tests/ -v
```

Requires Python 3.12 or later.

## Credits

Special thanks to:

- **@djerik** -- original work and early foundation of this integration  
- **@alexdelprete** -- NeoPool MQTT integration, design ideas, and inspiration https://github.com/alexdelprete/HA-NeoPool-MQTT  
- **@curzon01** -- dashboard design and UX inspiration  

## Issues & Discussion

For support, feature requests, and discussions, please use the Home Assistant community thread:

https://community.home-assistant.io/t/custom-component-hayward-aquarite/728136

## Trademark Notice

Hayward is a trademark of Hayward Industries, Inc. This project is an independent community effort and is not affiliated with, endorsed by, or sponsored by Hayward Industries, Inc.

## License

This project is provided for personal and other non-commercial use only. You may
view, copy, modify, and share the code and documentation for non-commercial
purposes. Commercial use of this software is not permitted without prior written
permission from the maintainers. The software is provided "as is" without
warranties of any kind.
