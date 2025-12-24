# Hayward AquaRite integration for Home Assistant
Home Assistant integration for controlling and monitoring Hayward-branded pool controllers (Dagen / Vistapool / Sugarvalley / Poolwatch / Kripsol / AquaRite).

## Requirements
- A supported controller with a Wi-Fi module connected to the internet.
- The controller must already be linked to a cloud account.
- Enable the Home Assistant `application_credentials` integration so the Aquarite API
  key can be stored securely and reused for token refreshes.

## Installation
You can install the integration through HACS or manually.

### Option 1: HACS (recommended)
1. In Home Assistant, open **HACS → Integrations**.
2. Search for **Aquarite** and install the integration.
3. Restart Home Assistant when prompted.

### Option 2: Manual installation
1. Download this repository.
2. Copy the `custom_components` folder into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.

### Configuration
1. In Home Assistant, go to **Settings → Devices & Services**.
2. Click **Add Integration** and search for **Aquarite**.
3. When prompted, enter your cloud account username and password.
4. Choose the pool controller you want to add.

Sensors are automatically created once the integration is configured.

## Dashboard examples
Example dashboard inspired by the great work of https://github.com/alexdelprete/HA-NeoPool-MQTT

![Dashboard example](https://github.com/user-attachments/assets/11c6467f-6a9e-4469-af36-3613e40a6b92)

Based on the selected filtration mode, the display shows different data points:

**Intel**
<br>
<img src="https://github.com/user-attachments/assets/c5a3b070-072d-421b-955f-a41667d738b7" width="600">

**Smart**
<br>
<img src="https://github.com/user-attachments/assets/b9cb0f21-34a3-4c25-9332-02eee6988963" width="600">

You can also sync your pool controller time with Home Assistant by calling the provided service:

![Time sync service](https://github.com/user-attachments/assets/5b9896b1-b5b8-481f-933e-4e7482072fab)

# Credits

Special thanks to:

- @djerik, who started the work on this integration.
- @alexdelprete for the NeoPool local integration, great ideas, and further inspiration. https://github.com/alexdelprete/HA-NeoPool-MQTT
- @curzon01 for the fantastic dashboard.

# Issues/Discussion

For discussions or requests, please refer to [this Home Assistant community thread](https://community.home-assistant.io/t/custom-component-hayward-aquarite/728136).

<a href="https://buymeacoffee.com/fdebrus" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/black_img.png" alt="Buy Me A Coffee" style="height: auto !important;width: auto !important;" ></a><br>

## License

This project is licensed under a Non-Commercial License – see the [LICENSE](LICENSE) file for details.

**Disclaimer:**
This project is not affiliated with, endorsed by, or sponsored by Hayward Industries, Inc. “Hayward” is a registered trademark of its respective owner. Any mention of “Hayward” is for compatibility or descriptive purposes only.
