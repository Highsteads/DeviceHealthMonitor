---
title: Quiet, away and left-out devices
nav_order: 5
---

# Quiet, away and left-out devices

Some devices are quiet or switched off on purpose, and a monitor that reports them every day soon gets ignored. There are three ways to tell the plugin about them, from gentlest to strongest:

| You have | Use | What still gets reported |
|---|---|---|
| A sensor that only reports when something happens | A **quiet device** entry | A fault its own plugin reports, and silence longer than the time you set |
| A device that is switched off at the wall between uses | An **away tolerance** | Anything that lasts longer than the time you set |
| A device you never want to hear about | The **left-out list** | Nothing at all |

The first two live in one file, and the left-out list in another. Both are in a folder called `Indigo/DeviceHealthMonitor` inside the Documents folder of the Mac user that runs Indigo. They are plain text files you can open in TextEdit. The plugin re-reads them before every check, so a change takes effect at the next check, with no restart.

## Sensors that are quiet by design

A cupboard door sensor that reports when the door opens can go days without a word and be perfectly healthy, but the normal silence limits would call it offline. A **quiet device** entry gives that one device its own silence limit.

The entries go in `quiet_devices.json`, which the plugin writes the first time it runs, with notes and a worked example at the top. Add your own entries between the square brackets after `"quiet_devices":`, like this:

```json
"quiet_devices": [
    {"id": 123456789, "hours": 240, "note": "cupboard door, opens twice a week"},
    {"name": "Loft Hatch Contact", "hours": "never"}
]
```

- **id** is the device's ID number in Indigo. You can use **name** instead, the device's name exactly as Indigo shows it, with capitals not mattering. The ID is better, because it does not change if you rename the device.
- **hours** is how long the device may be silent before it is reported. It may be longer or shorter than the plugin's normal limit for that kind of device. `"never"` means it is never reported for being silent.
- **note** is for your own use. The plugin ignores it.

A quiet device entry changes the silence limit for Zigbee devices, battery Z-Wave devices and Ecowitt sensors. It never hides a fault the device's own plugin reports — Zigbee2MQTT marking it offline, Indigo marking a Z-Wave device in error, Shelly Direct showing it offline, ESPHome Bridge showing it disconnected, or RAMSES ESP marking a room in error. Those are the device's own plugin saying something is wrong, not the plugin guessing from silence. It also means a sensor with a flat battery still turns up in the end.

## Devices that are switched off on purpose

A washing machine plug that is turned off at the wall between washes is out of contact most of the week, and nothing is wrong. An **away tolerance** says how long a device may be away before you hear about it. The washing machine can sit switched off all week, while a plug that never comes back is still reported.

It goes in the same file, as `offline_hours`:

```json
"quiet_devices": [
    {"id": 987654321, "offline_hours": 336, "note": "washing machine plug, two weeks"}
]
```

- **offline_hours** is how long the device may be away, however it is found to be away — silent, marked offline, or in error. `"never"` means it is never reported while away.
- An entry can carry both **hours** and **offline_hours**.
- The time is measured from when the device last genuinely spoke, so restarting the plugin or Indigo does not start the clock again.
- A device that has never spoken at all is reported straight away, whatever the tolerance, because it has not been paired properly.

## Leaving a device out altogether

A left-out device is never checked, so it can never be reported. That includes the day it really does die, so use this only for a device you truly never want to hear about, and prefer an away tolerance for a device that is merely off a lot.

There are two ways to add devices to the list:

- Choose **Plugins → Device Health Monitor → Add All Offline Devices to Exclusions**. Everything currently on the list of outstanding alerts is added and its alert cleared.
- Or edit `exclusions.json` yourself. It lists device names:

```json
{
    "excluded_names": [
        "Garage Freezer Plug",
        "Spare Motion Sensor"
    ]
}
```

Names are matched with capitals not mattering. The list goes by name, so if you rename a device it is no longer left out. The file only exists once something has been added, by the menu item or by you.

## Checking what is in force

**Plugins → Device Health Monitor → Show Quiet Devices** lists every quiet device and away tolerance with the time it is allowed, and names any entry whose ID no longer belongs to a device. **Show Exclusions** lists the left-out names.

If an entry in `quiet_devices.json` cannot be understood — a word where a number should be, or no ID or name — the Event Log says which entry was skipped, and the others still work. If the whole file cannot be read, the Event Log says so, and every device is judged on the normal limits until it is put right.
