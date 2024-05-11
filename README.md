# Hayward AquaRite integration for Home Assistant

## Requirements
- An Hayward AquaRite with wifi module connected to the internet.
- The controller must be added to an Hayward account.

## Installation
Component is installed via HACS or alternative by downloading the files and placing them in your custom_components folder.

Afterwards you can go to the Integrations sections and click the add integration button. Search for Aquarite and choose to add the integration.

- First step will ask you to enter you username and password. 
- Second step will ask you to choose the pool (controller) you want to add

It will automatically add all the sensors to your Home Assistant installation.

Example dashboard, inspired from the great work of https://github.com/alexdelprete/HA-NeoPool-MQTT

![image](https://github.com/fdebrus/hayward-ha/assets/33791533/ef570ca5-d4dd-4a3d-b5c1-e1379c1d6a14)

# Credits

Big thanks to 

@djerik who started the work on this integration, source of my work.

@alexdelprete for the work done on the local integration of NeoPool, great idea's and further inspiration. https://github.com/alexdelprete/HA-NeoPool-MQTT

@curzon01 for a fanstastic dashboard.

# Issues/Discussion

For discussions/general requests, please refer to [this](https://community.home-assistant.io/t/custom-component-hayward-aquarite/728136) thread in HA community.

