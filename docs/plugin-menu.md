---
title: The plugin menu
nav_order: 8
---

# The plugin menu

These are under **Plugins → Device Health Monitor**. Each one writes its answer to the Indigo Event Log.

## Devices

| Menu item | What it does |
|---|---|
| **Scan Devices Now** | Checks every device straight away instead of waiting for the next check, and sends a message for anything newly found offline. |
| **Show Offline/Stale Devices** | Lists every device you have been told about that has not yet recovered, with how long it has been offline and since when. A device deleted since is named as deleted. |
| **Add All Offline Devices to Exclusions** | Adds every device on that list to the left-out list, `exclusions.json`, and clears its alert, so it is not checked again. The [Quiet, away and left-out devices](quiet-and-excluded.md) page explains why an away tolerance is often the better choice. |
| **Show Exclusions** | Lists the names on the left-out list and where the file is. |
| **Show Quiet Devices** | Re-reads `quiet_devices.json` and lists each quiet device with the silence it is allowed, and each away tolerance with how long the device may be away. It names any entry whose ID no longer belongs to a device. |
| **Clear Alert State (Reset All)** | Forgets every outstanding alert. Any device still offline is found again at the next check and you are told about it afresh. |

## Plugin watchdog

| Menu item | What it does |
|---|---|
| **Run Watchdog Check Now** | Re-reads the watchdog's rules and checks every watched plugin straight away. |
| **Show Watchdog Status** | Writes the plugin's details to the log, then lists every plugin being watched with how it looks now, its time limit, whether that limit is its own or the general one, and any restarts today. A crashed or wedged plugin is shown as a warning. |
| **Toggle Watchdog Dry-Run Mode** | Switches the watchdog between only telling you what it would restart and restarting plugins for real. The change is written to the log as a warning either way, and it is saved in the plugin's settings. |
| **Reset Watchdog Restart Counters** | Clears every plugin's restart count for the day and its cooldown, so the watchdog may restart it again straight away. Use it once you have sorted out a plugin that reached its daily limit. |

## Help

| Menu item | What it does |
|---|---|
| **Show Plugin Info** | Writes the plugin's version, details of your Mac and Indigo, and a summary of its settings, outstanding alerts, left-out, quiet and away devices, and watchdog state to the log, which is useful to include if you ask for help on the Indigo forum. |
