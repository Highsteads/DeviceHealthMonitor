---
title: Getting started
nav_order: 2
---

# Getting started

This takes a few minutes, and you only do it once.

## What you need

- Indigo 2022.1 or later.
- The **Pushover** plugin for Indigo, installed, enabled and already sending messages to your phone. Device Health Monitor sends every message through it, so without it the plugin still checks your devices and writes to the Event Log, but nothing reaches your phone.
- Devices from one or more of the plugins it knows how to judge — Zigbee2MQTT Bridge, Shelly Direct, Indigo's own Z-Wave, Ecowitt Weather Station, ESPHome Bridge or RAMSES ESP. The [What it watches](what-it-watches.md) page lists them. The plugin watchdog works with almost any plugin that runs devices.

It needs no account, password or key of its own.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/DeviceHealthMonitor/releases/latest) and download `DeviceHealthMonitor.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `DeviceHealthMonitor.indigoPlugin`
3. Double-click `DeviceHealthMonitor.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes.

## 2. Check the settings

Open **Plugins → Device Health Monitor → Configure**.

The settings it starts with suit most houses: a check every 10 minutes, a day of silence allowed for a battery Z-Wave device, a day without any change for an Ecowitt sensor, and 12 hours of silence for a Zigbee device. The plugin watchdog is switched on, but in its trial mode, **Dry-run**, so it will only tell you what it would restart.

Click **Save**. Every setting is explained on the [Settings](settings.md) page.

## 3. Check it works

When the plugin starts, the Event Log has one line saying it has started, with how many kinds of device it knows, whether the watchdog is on and in trial mode, and how many devices are left out, quiet or allowed to be away.

The first time it runs it also writes two files into a folder called `Indigo/DeviceHealthMonitor` inside the Documents folder of the Mac user that runs Indigo, and says so in the log. One is where you list [quiet and away devices](quiet-and-excluded.md), the other holds the [watchdog's rules](watchdog.md).

The first check runs 30 seconds after the plugin starts. To run one straight away, choose **Plugins → Device Health Monitor → Scan Devices Now**.

- If every device is well, the check writes nothing at all.
- If a device has gone quiet, the Event Log has a line starting **[OFFLINE]** with its name and the reason, and a Pushover message arrives headed **Device Health: 1 offline**, with the device and the reason underneath.

The first check in a house that has never been watched often finds a few devices that died long ago. Choose **Plugins → Device Health Monitor → Show Offline/Stale Devices** to list them, and the [Quiet, away and left-out devices](quiet-and-excluded.md) page explains what to do about any that are quiet on purpose.

If nothing reaches your phone when you expect it to, the [When something goes wrong](troubleshooting.md) page goes through the usual causes.
