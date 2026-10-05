---
title: What it watches
nav_order: 3
---

# What it watches

The plugin checks enabled devices that belong to the plugins below. Everything else in Indigo — virtual devices, timers, HomeKit bridges, devices from other plugins — is left alone by this check, although the [plugin watchdog](watchdog.md) can still look after the plugins behind them.

A disabled device is never checked.

| Your devices | Through | How the plugin judges them |
|---|---|---|
| **Zigbee** lights, plugs and sensors | Zigbee2MQTT Bridge | How long since the device last spoke, and whether Zigbee2MQTT has marked it offline. A mains device is asked directly before it is reported. |
| **Shelly** Plus, Pro, Gen 3 and Gen 4 | Shelly Direct | Whether Shelly Direct shows it as online. |
| **Shelly Gen 1** relays and plugs | Shelly Gen 1 | Whether Shelly Gen 1 has marked it in error because it stopped answering. |
| **Z-Wave** | Indigo's own Z-Wave | Whether Indigo has marked it in error, and for a battery device, how long since it last spoke. A quiet mains node is asked whether it is there. |
| **Ecowitt** weather sensors | Ecowitt Weather Station | How long since it last sent a reading. |
| **ESPHome** devices | ESPHome Bridge | Whether ESPHome Bridge shows it as connected. |
| **Evohome radiator valves** | RAMSES ESP | Whether RAMSES ESP has marked the room in error because its valve has gone silent. |

## Zigbee

A Zigbee device is reported when either of these is true:

- **It has said nothing for longer than Z2M device stale threshold**, 12 hours to start with. The plugin goes by the time the device itself last spoke, as Zigbee2MQTT Bridge records it.
- **Zigbee2MQTT has marked it offline, and it has also been silent for longer than Grace before trusting an offline flag**, 30 minutes to start with. Zigbee2MQTT can mark a mains device offline when a single check of its own goes unanswered, so on a device with a weak radio link the mark comes and goes. The grace stops each of those reaching your phone.

**A mains-powered device is then asked directly** before anything reaches your phone. The plugin sends it a status request, the same as Indigo's **Send Status Request** button, and a device that is there answers within seconds. Only a device that ignores the request on two checks in a row is reported. A lamp nobody has touched for an hour is quiet because nothing has asked it anything, not because it has gone, and this is what tells the two apart.

**A battery device is reported without being asked**, because a sleeping sensor cannot answer, so asking proves nothing. The plugin treats a device as battery-powered if it has ever reported a battery level, or if Zigbee2MQTT says it runs on a battery.

If the plugin holds back an offline verdict on a device four or more times in one day, it writes one warning to the Event Log that day starting **[FLAPPING]**, naming the device. It does not send it to your phone. A device that keeps being called offline has a radio link worth a look.

## Shelly

A Shelly Plus, Pro, Gen 3 or Gen 4 device is reported at the first check after Shelly Direct shows it offline.

A Shelly Gen 1 device is reported at the first check after Shelly Gen 1 marks it in error. It does that when the Shelly has missed a few polls in a row, or when a different Shelly answers at its address. Either Shelly plugin marking a device in error gets it reported.

## Z-Wave

- **Any Z-Wave device that Indigo has marked in error** is reported. Indigo marks a node in error when it fails to answer a command.
- **A battery device that has said nothing for longer than Battery device threshold**, 24 hours to start with, is reported. Battery Z-Wave devices wake up and report on a regular cycle, so a long silence means a flat battery or a device that has dropped off the network. One that has never spoken at all is reported too.
- **A mains device is never reported just for being quiet.** A light or a repeater that nobody uses can be silent for months and be perfectly healthy. Instead, once a mains node has been quiet for longer than **Mains device quiet time**, 6 hours to start with, the plugin sends it a status request. If the node does not answer, Indigo marks it in error, and the next check reports it. Each node is asked at most once in each quiet-time period.

Some Z-Wave nodes refuse a status request altogether. When a node has ignored three in a row, the plugin writes one warning to the Event Log saying it will not ask again, and stops asking until the node next speaks. Indigo marking it in error still gets it reported.

## Ecowitt

An Ecowitt gateway or sensor is reported when it has sent no reading for longer than **Ecowitt no-reading threshold**, 24 hours to start with. The plugin reads the time of the last reading that Ecowitt Weather Station records for each device.

Ecowitt Weather Station marks a device offline after a few minutes without data. That alone does not raise an alert, because a gateway that restarts would otherwise send a message every time. It counts only for a device that has never sent a reading at all, which is reported at the next check.

## ESPHome

An ESPHome device is reported at the first check after ESPHome Bridge shows it disconnected. It is never judged on silence, because an ESPHome sensor only sends a reading when the reading changes, so a freezer monitor at a steady load can be quiet for a long time and be perfectly well.

## Evohome radiator valves

A RAMSES ESP device is reported when RAMSES ESP has marked it in error, which it does to a room when the radiator valve in that room has gone silent. For this to work, the RAMSES ESP setting **Mark the zone device in error when a valve goes silent** must be ticked, which it is to start with.

The room itself is never judged on silence, because the heating controller keeps its temperature up to date every few minutes, even when the valve in it has said nothing for days.

If the heating gateway fails and every room goes into error at once, you get one message listing them, not one per room.

## Devices that are quiet, away or left out on purpose

Any of these checks can be relaxed for one device — a longer silence for a sensor that is quiet by design, a time it may be away for a plug switched off at the wall, or leaving it out altogether. The [Quiet, away and left-out devices](quiet-and-excluded.md) page explains how.
