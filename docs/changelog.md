---
title: Version history
nav_order: 10
---

# Version history

The newest version is at the top.

## 2.11.0 — 27 September 2026

- **A Shelly Gen 1 device that stops answering is reported.** The plugin looked for a sign of life that Shelly Gen 1 devices do not have, took its absence as good news, and so never reported one. It now also goes by Indigo's error mark, which is how Shelly Gen 1 shows a Shelly that has gone. Shelly Gen 1 is back on the list of plugins it watches.
- **Auto-discovered default stale threshold works.** It was copied into the watchdog's rules file the first time the plugin ran, and the copy was used from then on, so changing the setting did nothing.
- **Better built-in watchdog limits in a later version now reach you.** A new rules file held a copy of the built-in limits as they were on the day it was written. It now starts empty and holds only your own changes. An older file is tidied once, keeping every change you made, with a copy of it saved beside it.
- **Dry-run no longer sends a message at every check** while a plugin looks failed. It keeps to the same cooldown and daily limit as a real restart.
- **Show Plugin Info lists all seven plugins** whose devices it watches. ESPHome Bridge and RAMSES ESP were missing.

## 2.10.2 — 19 September 2026

A Zigbee device is treated as battery-powered if Zigbee2MQTT says it runs on a battery, as well as if it has ever reported a battery level. A Shelly button here had joined the network without ever reporting a battery level, so it was being asked directly — which a sleeping device cannot answer — and then reported as having ignored the question. It is still reported, because it really has gone, but for the right reason.

## 2.10.1 — 19 September 2026

While the plugin is waiting for a Zigbee device to answer, it no longer treats the device as well. Before, a device already reported offline was announced as recovered while the question was still unanswered, and then reported as a fresh fault at the next check.

## 2.10.0 — 19 September 2026

- **A mains Zigbee device is asked whether it is there before it is called offline.** It must ignore a direct request on two checks in a row before anything reaches your phone. A bedside lamp had been reported offline one morning a minute before it was dimmed from Indigo.
- Battery Zigbee devices are not asked, because a sleeping device cannot answer.

## 2.9.0 — 18 September 2026

- **Zigbee2MQTT's offline mark has a grace period,** set with the new **Grace before trusting an offline flag** setting, 30 minutes to start with. A loose Zigbee light had been sending thirteen messages a day, because one missed check by Zigbee2MQTT was enough to mark it offline.
- A device held back by the grace four or more times in a day is named once in the Event Log as **[FLAPPING]**.
- **The Zigbee silence limit works.** It had been measuring a clock that Indigo refreshes whenever the Zigbee plugin writes to a device, even a dead one, so it could never report anything. It now goes by the time the device itself last spoke.

## 2.8.1 — 13 September 2026

The watchdog no longer restarts Z-Wave Controller Backup for being quiet. Its one device only changes when you run a backup, so it is now checked only for having crashed.

## 2.8.0 — 12 September 2026

**Evohome radiator valves are watched.** When RAMSES ESP marks a room in error because its valve has gone silent, the room is reported like any other offline device. A heating gateway failure that takes every room with it sends one message, not one per room.

## 2.7.2 — 11 September 2026

The note inside the plugin of where its code lives on GitHub uses the same spelling as other Indigo plugins. Nothing else changed.

## 2.7.1 — 9 September 2026

A Z-Wave node that ignores three status requests in a row is not asked again until it next speaks, and the Event Log says so once. Two repeaters here refused every request, which would have put two errors in the log every few hours for ever.

## 2.7.0 — 9 September 2026

**A dead mains Z-Wave node is noticed.** Once a mains node has been quiet for longer than **Mains device quiet time**, the plugin sends it a status request, and a node that does not answer is reported at the next check. Three nodes here had been off the network for 91, 231 and 629 days without a word, because silence alone cannot tell a dead node from an unused one.

## 2.6.0 — 9 September 2026

**ESPHome devices are watched,** judged on whether ESPHome Bridge shows them connected. A freezer monitor had been off the network all evening with nothing said. An away tolerance on an ESPHome device is measured from the time the device itself last spoke.

## 2.5.2 — 7 September 2026

The help text in the settings dialog wraps, instead of being cut off mid-sentence. No setting or behaviour changed.

## 2.5.1 — 3 September 2026

The watchdog allows DahuaEvents four hours of quiet instead of one. Its cameras only speak when something happens, so a quiet night had been causing restarts of cameras that were working.

## 2.5.0 — 27 August 2026

A plugin whose devices only send, and never hear anything back, can be checked only for having crashed, never for being quiet. Broadlink RF, which drives the living room fire, had been restarted three times on a night nobody used the fire. Humax Aura is treated the same way.

## 2.4.0 — 10 August 2026

**Away tolerance.** A device can be allowed to be switched off for a set time, such as a washing machine plug turned off at the wall between washes, while one that never comes back is still reported. Before, the only choice was to leave the device out altogether, and a dead tumble dryer plug had gone unnoticed for five days on that list. **Show Quiet Devices** lists the tolerances too.

## 2.3.2 — 8 August 2026

The **About** item in the Plugins menu opens this project's page. It went nowhere before.

## 2.3.1 — 27 July 2026

An alert is cleared when its device is deleted, or added to the left-out list by editing the file, so the list of outstanding alerts no longer keeps entries nothing can clear.

## 2.3.0 — 27 July 2026

- **Quiet devices.** A sensor that is quiet by design can be given its own silence limit, or none, in `quiet_devices.json`, without hiding a fault its own plugin reports.
- A device is only marked as reported once the message has actually been sent, so a Pushover failure is retried rather than lost.
- Changes to the watchdog's built-in limits reach an install that already had the rules file.
- A cleared number in the settings no longer stops the plugin loading.

## 2.2.2 — 21 July 2026

The shared helper file inside the plugin was brought up to date. No behaviour changed.

## 2.2.1 — 21 July 2026

Warnings and errors appear in the Event Log as warnings and errors. Before, they all appeared as ordinary lines.

## 2.2 — 19 June 2026

A watchdog limit for a plugin that no longer exists was removed.

## 2.1 — 19 June 2026

The watchdog treats EcoFlow Cloud as wedged after an hour of quiet instead of twelve, now that it checks its devices every few seconds.

## 2.0 — 29 May 2026

- **The plugin watchdog**, which finds the plugins that run your devices and restarts one that has crashed or stopped hearing from its devices, starting in Dry-run.
- Z-Wave devices are judged on whether Indigo has marked them in error, rather than on silence, which had been reporting healthy but unused lights.

## 1.1 — 29 April 2026

The left-out list, and the menu items to manage it.

## 1.0 — 29 April 2026

First release: a check of every device, with one Pushover message for everything found offline.
