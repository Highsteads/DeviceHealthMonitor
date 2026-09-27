---
title: The plugin watchdog
nav_order: 6
---

# The plugin watchdog

The device check looks for single devices that have gone quiet. The watchdog looks one level up, at the plugins that run those devices, and restarts one that has stopped working. I added it after a Zigbee2MQTT Bridge lost its connection after a network blip and went silent, taking every Zigbee device with it.

It runs straight after each device check.

## Which plugins it watches

It finds them by itself. Any plugin that runs at least one enabled device with a record of when Indigo last heard from it is watched, unless it is on the list of plugins never to restart.

These are never restarted, because a restart would be wrong, pointless or too disruptive to do without you: Indigo's own Z-Wave, Virtual Devices, Timers and Pesters and Email+ plugins, HomeKitLink Siri, Pushover, a clock display, a lock manager, a temperature adapter, and plugins that work their devices out from other devices, such as Device Activity Monitor, Appliance Monitor and Universal Z-Wave Sensor. **Claude Bridge and Device Health Monitor itself** are never restarted, and nothing in the settings can change that.

**Plugins → Device Health Monitor → Show Watchdog Status** lists every plugin being watched and how it looks right now.

## What counts as a failure

- **Crashed** — the plugin is enabled in Indigo but not running.
- **Wedged** — the plugin is running, but none of its devices has been heard from within that plugin's time limit.

A plugin you have disabled, or one that is not installed, is left alone. A plugin the watchdog has just restarted is given five minutes to come back before it is judged again.

## What it does about it

- **In Dry-run**, which is how it starts, it writes a warning to the Event Log starting **[DRY RUN]** and sends a Pushover message saying what it would restart and why, but does not restart anything. It does this at every check for as long as the plugin still looks failed. Leave it like this until you have seen a few of these and agree with them.
- **Once Dry-run is off**, it restarts the plugin, writes a warning to the Event Log, and sends a Pushover message saying which restart of the day it was.

Each plugin has a **cooldown**, a number of minutes after a restart before it may be restarted again, and a **daily limit** on restarts. When a plugin is still failing after its daily limit, the watchdog stops restarting it and sends one high-priority Pushover message saying it **needs attention**. If a restart itself fails, you get a high-priority message about that too. The counts start again each day, or when you choose **Reset Watchdog Restart Counters**.

## Time limits

Plugins whose habits are known have limits of their own:

| Plugin | Wedged after | Cooldown | Restarts a day |
|---|---|---|---|
| Zigbee2MQTT Bridge | 5 minutes | 15 minutes | 6 |
| Tasmota Bridge | 8 minutes | 15 minutes | 6 |
| ESPHome Bridge | 10 minutes | 20 minutes | 4 |
| Sigenergy Manager | 10 minutes | 20 minutes | 4 |
| Shelly Direct | 15 minutes | 30 minutes | 3 |
| Ecowitt Weather Station | 20 minutes | 30 minutes | 3 |
| Shelly Gen 1 | 30 minutes | 60 minutes | 2 |
| EcoFlow Cloud | 60 minutes | 30 minutes | 3 |
| RAMSES ESP | 3 hours | 30 minutes | 3 |
| DahuaEvents | 4 hours | 30 minutes | 3 |
| Humax Aura | never | 60 minutes | 2 |
| Broadlink RF | never | 60 minutes | 2 |
| Z-Wave Controller Backup | never | 60 minutes | 2 |

**Never** means the plugin is only checked for having crashed, never for being quiet. Broadlink RF only sends and never hears anything back, Humax Aura only speaks while the television is in use, and Z-Wave Controller Backup only changes when you run a backup, so silence tells you nothing about any of them.

Any other plugin the watchdog finds is judged as wedged after **Auto-discovered default stale threshold**, 60 minutes to start with, with a 30-minute cooldown and three restarts a day. That is deliberately generous, so a plugin the watchdog has only just found is not restarted for being quiet.

## Changing the rules

The rules live in `watchdog_plugins.json`, in the same `Indigo/DeviceHealthMonitor` folder in the Documents folder of the Mac user that runs Indigo. The plugin writes it the first time it runs and re-reads it before every check, so a change takes effect at the next check.

Each plugin is named in the file by its identifier, the long dotted name its developer gave it, such as `com.clives.indigoplugin.shellydirect`. The file has four parts:

| Part | What it does |
|---|---|
| **overrides** | Limits for a particular plugin. The file starts with a copy of the built-in limits as they stood when it was written, which you can edit: `stale_minutes` (wedged after this many minutes, or `null` for never), `cooldown_minutes`, `max_per_day`, and `enabled` (`false` to stop watching that plugin). For a plugin you add yourself, you only need the ones you want to change, and anything you leave out keeps its built-in value. |
| **exclude** | Plugins never to restart. |
| **include** | Takes a plugin off the built-in never-restart list, if you do want it watched. Claude Bridge and this plugin cannot be taken off. |
| **discovered_default** | The limits for any plugin with no limits of its own. |

The number in **Auto-discovered default stale threshold** in the plugin's settings is copied into **discovered_default** when the file is first written, and from then on the figure in the file is the one used. To change it after that, change it in the file.

For example, to give Shelly Direct 30 minutes instead of 15, find its entry under **overrides**, or add one if it is not there, and change `stale_minutes`:

```json
"com.clives.indigoplugin.shellydirect": {
    "stale_minutes": 30,
    "cooldown_minutes": 30,
    "max_per_day": 3,
    "enabled": true
}
```

If the file cannot be read, the Event Log says so, and the watchdog uses its built-in rules until it is put right.
