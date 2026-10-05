---
title: Settings
nav_order: 7
---

# Settings

Open these with **Plugins → Device Health Monitor → Configure**. A change takes effect as soon as you click **Save**, apart from **Scan interval**, which takes effect after the check already waiting has run.

## How often to check

| Setting | What it does |
|---|---|
| **Scan interval** | How often the plugin checks your devices and the watchdog checks your plugins: every 5, 10, 15 or 30 minutes. It starts at 10. |

## Z-Wave

| Setting | What it does |
|---|---|
| **Battery device threshold (hours)** | How long a battery Z-Wave device may say nothing before it is reported. It starts at 24. |
| **Mains device quiet time (hours)** | How long a mains Z-Wave node may be quiet before the plugin sends it a status request to see if it is there. This is not a limit that raises an alert by itself — a node that answers is fine, and one that does not is marked in error by Indigo and reported at the next check. It starts at 6. Setting it to 0 stops the requests, and then a dead mains node goes unnoticed until something else sends it a command. |

## Ecowitt

| Setting | What it does |
|---|---|
| **Ecowitt no-reading threshold (hours)** | How long an Ecowitt gateway or sensor may go without sending a reading before it is reported. It starts at 24. |

## Zigbee2MQTT

| Setting | What it does |
|---|---|
| **Z2M device stale threshold (hours)** | How long a Zigbee device may say nothing before it is reported, or for a mains device, before it is asked directly. It starts at 12, which is long enough for battery sensors that report rarely. |
| **Grace before trusting an offline flag (minutes)** | When Zigbee2MQTT marks a device offline, how long the device must also have been silent before the plugin believes it. It starts at 30. Setting it to 0 means every offline mark is acted on as soon as it is seen. A mains device is still asked directly before it is reported, whatever this is set to. |

## Plugin watchdog

| Setting | What it does |
|---|---|
| **Enable plugin watchdog** | Switches the [plugin watchdog](watchdog.md) on or off. It starts ticked. |
| **Dry-run (log/alert only, no real restarts)** | Ticked, the watchdog only tells you what it would restart. Unticked, it restarts plugins for real. It starts ticked. Leave it ticked until you have seen a few of its messages and agree with them. **Toggle Watchdog Dry-Run Mode** in the plugin menu does the same thing. |
| **Auto-discovered default stale threshold (minutes)** | How long a plugin with no limit of its own may go without hearing from any of its devices before the watchdog treats it as wedged. It starts at 60. A change takes effect at the next check. |

## Debug logging

| Setting | What it does |
|---|---|
| **Enable debug logging** | Adds a line to the Event Log for every check and every decision. Only useful when chasing a problem, as it adds a lot of lines. |

## The three files

Some things are set in files rather than in this dialog, because they apply to single devices or single plugins. All three are in a folder called `Indigo/DeviceHealthMonitor` inside the Documents folder of the Mac user that runs Indigo, and the plugin re-reads them before every check.

| File | What it holds | Explained on |
|---|---|---|
| `quiet_devices.json` | Quiet devices and away tolerances | [Quiet, away and left-out devices](quiet-and-excluded.md) |
| `exclusions.json` | Devices left out altogether | [Quiet, away and left-out devices](quiet-and-excluded.md#leaving-a-device-out-altogether) |
| `watchdog_plugins.json` | The watchdog's rules | [The plugin watchdog](watchdog.md#changing-the-rules) |

## Passwords and keys

This plugin needs none. Messages go through the Pushover plugin, which holds your Pushover details.
