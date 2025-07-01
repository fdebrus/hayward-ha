# Hayward AquaRite integration for Home Assistant
Dagen / Vistapool / Sugarvalley / Poolwatch / Kripsol

## Requirements
- An Dagen / Vistapool / Sugarvalley / Poolwatch / Kripsol / AquaRite with wifi module connected to the internet.
- The controller must be added to an cloud account.

## Installation
Component is installed via HACS or alternative by downloading the files and placing them in your custom_components folder.

Afterwards you can go to the Integrations sections and click the add integration button. Search for Aquarite and choose to add the integration.

- First step will ask you to enter you username and password. 
- Second step will ask you to choose the pool (controller) you want to add

It will automatically add all the sensors to your Home Assistant installation.

Example dashboard, inspired from the great work of https://github.com/alexdelprete/HA-NeoPool-MQTT

![image](https://github.com/user-attachments/assets/11c6467f-6a9e-4469-af36-3613e40a6b92)

Based on the selected filtration mode, display will show different datapoints:

**Intel**
<br>
<img src="https://github.com/user-attachments/assets/c5a3b070-072d-421b-955f-a41667d738b7" width="600">

**Smart**
<br>
<img src="https://github.com/user-attachments/assets/b9cb0f21-34a3-4c25-9332-02eee6988963" width="600">


# Credits

Big thanks to 

@djerik who started the work on this integration, source of my work.

@alexdelprete for the work done on the local integration of NeoPool, great idea's and further inspiration. https://github.com/alexdelprete/HA-NeoPool-MQTT

@curzon01 for a fanstastic dashboard.

# Issues/Discussion

For discussions/general requests, please refer to [this](https://community.home-assistant.io/t/custom-component-hayward-aquarite/728136) thread in HA community.

<a href="https://buymeacoffee.com/fdebrus" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/black_img.png" alt="Buy Me A Coffee" style="height: auto !important;width: auto !important;" ></a><br>

## License

This project is licensed under a Non-Commercial License – see the [LICENSE](LICENSE) file for details.

**Disclaimer:**  
This project is not affiliated with, endorsed by, or sponsored by Hayward Industries, Inc. “Hayward” is a registered trademark of its respective owner. Any mention of “Hayward” is for compatibility or descriptive purposes only.
