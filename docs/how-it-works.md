---
title: How it works
nav_order: 4
---

# How it works

You do not need to know any of this to use the plugin. It is here for anyone who likes to know what is going on.

## The check

Every 10 minutes, or whatever **Scan interval** you choose, the plugin goes through every enabled device in Indigo. For each one that belongs to a plugin it knows, it applies that kind of device's test, which the [What it watches](what-it-watches.md) page describes. When the device check is done, the [plugin watchdog](watchdog.md) has its turn.

Before each check it re-reads the lists of quiet, away and left-out devices and the watchdog's rules, so a change you make to any of those files takes effect at the next check, without a restart.

The first check runs 30 seconds after the plugin starts, to give Indigo time to finish loading its devices.

## One message, once

Everything found offline in one check goes into a single Pushover message, headed with how many devices it covers, such as **Device Health: 3 offline**, with each device and its reason on a line of its own. The message uses Pushover's vibrate sound.

Each outage is sent once. A device that stays offline is not sent again at the next check, or the one after, however long it stays away. The plugin remembers which devices it has already told you about, and keeps that list when Indigo or the plugin restarts, so a restart does not send them all again.

A device is only added to that list once the message has actually gone. If the Pushover plugin is disabled or the message fails, the Event Log says so and the plugin tries again at every check until it gets through.

## Coming back

When a device that you were told about is well again, the Event Log has a line starting **[RECOVERED]** with its name. No message is sent to your phone for a recovery. If the same device goes offline again later, that is a new outage, and you are told about it.

If you delete a device, or add it to the list of left-out devices, while it is on the list of outstanding alerts, the plugin takes it off that list at the next check.

## Asking before accusing

Some devices are quiet simply because nothing has asked them anything. A mains Zigbee lamp that nobody has used, or a Z-Wave repeater, can go a long time without a word and be perfectly healthy. Silence alone cannot tell such a device from a dead one.

So for mains Zigbee devices and mains Z-Wave nodes, silence does not raise an alert. It makes the plugin send the device a status request, the same as pressing **Send Status Request** in Indigo:

- **A Zigbee device** that is there answers within seconds. One that ignores the request on two checks in a row is reported.
- **A Z-Wave node** that does not answer is marked in error by Indigo itself, and the next check reports it.

Battery devices are never asked, because a sleeping device cannot answer, and a request that cannot arrive proves nothing. For those, silence is the only sign, which is why they have their own silence limits.

## How long a device has been away

When you give a device an [away tolerance](quiet-and-excluded.md#devices-that-are-switched-off-on-purpose), the plugin measures how long the device has been away from the last time it genuinely spoke, not from when the plugin first noticed. The plugin's own notice would be forgotten at every restart, which could hand a dead device a fresh grace period each time. The last time a device spoke cannot be reset by anything the plugin does.

For Zigbee and ESPHome devices, that is the time the device itself last spoke, as their plugins record it. For everything else it is the time Indigo last heard from the device.

A device that has never spoken at all is reported straight away, whatever its tolerance, because there is no starting point to measure from, and a device that has never spoken has not been paired properly.

## What goes in the log

The Indigo Event Log has a line when the plugin starts, one for each device found offline and each one that recovers, and one each time a message is sent or fails. A check that finds nothing writes nothing. Tick **Enable debug logging** in the settings to see a summary of every check and more detail about each decision.
