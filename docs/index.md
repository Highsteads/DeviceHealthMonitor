---
title: Home
nav_order: 1
---

# Device Health Monitor for Indigo

This plugin keeps an eye on the devices in [Indigo](https://www.indigodomo.com) that talk to the house over a network or a radio — Zigbee lights and sensors, Shelly plugs, Z-Wave switches, weather sensors and the like — and sends a message to your phone through Pushover when one of them stops answering. It also watches the plugins behind those devices, and can restart one that has stopped working.

It has no devices, actions or triggers of its own. You install it, choose a few settings, and it works in the background.

## What it does for you

- **Checks every device it knows how to judge** every 10 minutes, or every 5, 15 or 30 if you prefer, and uses the right test for each kind of device, because a Zigbee lamp, a Z-Wave repeater and an Evohome radiator valve each show a fault in a different way.
- **Sends one message for everything that has gone quiet** in that check, rather than one per device, and tells you about each outage once, not every 10 minutes.
- **Asks a mains-powered Zigbee light or Z-Wave node whether it is there** before calling it offline, because a light nobody has used for a while is quiet but perfectly healthy.
- **Lets a device be quiet or away by design.** A cupboard door sensor that reports twice a week can be given days of silence, and a washing machine plug that is switched off at the wall between washes can be allowed to be away for a fortnight, while one that never comes back is still reported.
- **Watches the plugins themselves.** If a plugin that runs your devices has stopped, or has stopped hearing from every one of its devices, the plugin watchdog can restart it and tell you it has. It starts in a trial mode where it only tells you what it would restart.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and get your first message | [Getting started](getting-started.md) |
| Know which devices it watches and how it judges each one | [What it watches](what-it-watches.md) |
| Understand what the plugin is doing behind the scenes | [How it works](how-it-works.md) |
| Give a device more silence, allow it to be switched off, or leave it out | [Quiet, away and left-out devices](quiet-and-excluded.md) |
| Let the plugin restart a plugin that has stopped | [The plugin watchdog](watchdog.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Sort out a problem | [When something goes wrong](troubleshooting.md) |
| See what changed in each version | [Version history](changelog.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/DeviceHealthMonitor/releases/latest).
