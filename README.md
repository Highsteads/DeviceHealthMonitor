# Device Health Monitor

**Version:** 2.8.0 | **Author:** CliveS & Claude | **Platform:** Indigo 2022.1 or later

An Indigo home automation plugin that (1) continuously monitors all physical devices for offline or stale status and sends consolidated Pushover alerts, and (2) auto-discovers comms plugins and restarts any that crash or wedge — a plugin watchdog (v2.0).

## What It Monitors

| Protocol | Source Plugin | Health Check |
|---|---|---|
| Zigbee (via Z2M) | Zigbee2MQTTBridge | `lastSuccessfulComm` freshness (availability can sit stale at "online") |
| Shelly Gen2/3/4 | ShellyDirect | `deviceOnline` state (True/False) |
| Shelly Gen1 | ShellyGen1 | `deviceOnline` state (True/False) |
| Z-Wave | Indigo native | Indigo's `errorState` for mains, `lastSuccessfulComm` threshold for battery |
| Ecowitt | Ecowitt plugin | `lastChanged` timestamp vs threshold (proxy) |
| ESPHome | ESPHomeBridge | the bridge's own `connected` flag, never silence |
| Evohome radiator valves | RAMSES_ESP | the zone's `errorState`, never silence |

Everything else is ignored by the *device-level* scan above (HomeKit bridges, virtual devices, timers, etc.). The **plugin watchdog** (below) is a separate layer that watches comms plugins themselves — whether the plugin is running at all — rather than the devices behind them.

Two of those rows are judged on a flag rather than on how long since the device was heard from, and that is deliberate. An ESPHome sensor publishes only when its reading changes, so a freezer sitting at a steady load is legitimately quiet. An Evohome zone is the opposite problem: the gateway keeps the zone device up to date every few minutes, so its clock stays fresh while the radiator valve in that room has said nothing for days. In both cases silence is not evidence, and the owning plugin already knows the answer.

## Features

- Runs a background scan on a configurable interval (5–30 min)
- Protocol-aware health checks — uses the right signal for each device type
- **Quiet devices** — a per-device threshold for sensors that are silent by design
- **One-shot alerting**: alerts fire once per outage, not every scan cycle, and a device
  is only marked as alerted once the notification has actually been delivered
- Consolidated Pushover notification (all new offline devices in one message)
- Alert state persists across plugin restarts
- "Scan Devices Now", "Show Offline/Stale Devices" and "Show Quiet Devices" menu items

## Quiet devices

Some sensors report only when something happens. A cupboard presence sensor that fires
when the door opens goes days without a word and is perfectly healthy — but every
threshold above would call it offline, and a monitor that cries wolf gets swiped away
without being read.

Give any such device a threshold of its own in
`~/Documents/Indigo/DeviceHealthMonitor/quiet_devices.json`, written on first run:

```json
{
    "quiet_devices": [
        {"id": 123456789, "hours": 240, "note": "cupboard door, opens twice a week"},
        {"name": "Loft Hatch Contact", "hours": "never"}
    ]
}
```

Each entry takes a device `id` (preferred) or `name`, plus `hours` — which may be higher
**or lower** than the protocol default — or `"never"` to stop alerting on silence
altogether. Edits apply on the next scan, with no restart.

Two things it deliberately does not do. It does not silence a **hard fault**: an
`errorState`, a z2m `availability=offline` or a Shelly `deviceOnline=False` still alerts,
because those are the stack reporting a problem rather than us inferring one from
silence. And it is a longer threshold rather than an exemption, so a flat battery still
surfaces in the end. To ignore a device outright, list it in `exclusions.json` instead.

## Plugin Watchdog (v2.0)

As well as alerting on individual offline devices, the plugin auto-discovers every plugin that owns communicating devices and restarts any that have failed:

- **Crashed** — the plugin is enabled but not running
- **Wedged** — the plugin is running but its newest device has not communicated within that plugin's threshold (the failure mode where an MQTT bridge keeps a dead socket and goes silent)

Safety:

- **Denylist** — native Z-Wave, virtual/derived/timer/bridge/notification plugins are never restarted. Claude Bridge and this plugin are excluded in code and cannot be re-included.
- **Tuned thresholds** where a plugin's cadence is known, a generous default elsewhere, so a newly-discovered plugin is never nuisance-restarted
- **Per-plugin cooldown and daily cap**, with a "needs manual attention" alert if a plugin keeps failing past its cap
- **Dry-run by default** — logs and Pushovers what it *would* restart without acting, until you switch it to live
- **Pushover on every action**

Tune the policy live (no restart needed) in `~/Documents/Indigo/DeviceHealthMonitor/watchdog_plugins.json`. Menu items: Run Watchdog Check Now, Show Watchdog Status, Toggle Watchdog Dry-Run Mode, Reset Watchdog Restart Counters.

## Installation

1. Go to the Releases page and download `DeviceHealthMonitor.indigoPlugin.zip`
2. Unzip — you will get `DeviceHealthMonitor.indigoPlugin`
3. Double-click `DeviceHealthMonitor.indigoPlugin` — Indigo will install it automatically

## Configuration

Open Plugin > Device Health Monitor > Configure:

- **Scan interval** — how often to scan (5/10/15/30 min, default 10)
- **Z-Wave battery threshold** — hours before alerting on a battery Z-Wave device (default 24)
- **Z-Wave mains threshold** — retired, nothing reads it. Mains Z-Wave health is judged by
  Indigo's own `errorState` instead, because `lastSuccessfulComm` on an un-polled mains
  node only tracks time since last used — an idle-but-alive light reads stale for days.
- **Ecowitt threshold** — hours since last state change before alerting (default 24)
- **Z2M stale threshold** — hours without communication before alerting (default 12)
- **Enable plugin watchdog** — turn the whole watchdog layer on or off (default on)
- **Dry-run** — the watchdog logs and Pushovers what it *would* restart, without acting
  (default on)
- **Auto-discovered default stale threshold** — the wedge threshold in minutes for a
  discovered plugin with no tuned override (default 60)
- **Debug logging** — verbose scan output

Per-device staleness lives in `quiet_devices.json`, not here — see **Quiet devices** above.

## Plugin menu

**Plugins → Device Health Monitor →**

| Menu item | What it does |
|-----------|--------------|
| **Scan Devices Now** | Run a full device scan straight away instead of waiting for the next interval. |
| **Show Offline/Stale Devices** | List every device currently alerting, with how long it has been quiet. A device deleted since it alerted is named as such. |
| **Add All Offline Devices to Exclusions** | Write the names of everything currently alerting into `exclusions.json` and clear their alerts, so they are left out of future scans. |
| **Show Exclusions** | List the excluded device names and the file they come from. |
| **Show Quiet Devices** | Re-read `quiet_devices.json` and list each device with the silence it is allowed, or that it never alerts on silence. |
| **Clear Alert State (Reset All)** | Forget every outstanding alert so the next scan starts fresh. |
| **Run Watchdog Check Now** | Re-read `watchdog_plugins.json` and run one watchdog pass immediately. |
| **Show Watchdog Status** | Dump the full banner, then every discovered plugin with its threshold, its restarts today and any cooldown in force. |
| **Toggle Watchdog Dry-Run Mode** | Switch between logging what the watchdog would restart and actually restarting it. Logged as a warning either way, because it matters. |
| **Reset Watchdog Restart Counters** | Clear the per-plugin restart counts and cooldowns. |
| **Show Plugin Info** | Log the full plugin and environment banner, plus the thresholds, exclusions and watchdog state, for a support post. |

## Credentials — `IndigoSecrets.py` vs `IndigoSecrets_example.py`

**Not applicable to this plugin** — it reads no external APIs and needs no
credentials. The `IndigoSecrets_example.py` file may be shipped in the bundle
for ecosystem consistency, but there is nothing to fill in for this plugin.

Other CliveS Indigo plugins read sensitive values from a shared master file
at `/Library/Application Support/Perceptive Automation/IndigoSecrets.py`.
See e.g. the Ecowitt or EcoFlow Cloud plugin READMEs for the full
credentials documentation.
## Requirements

- Indigo 2022.1 or later (Python 3.10+)
- Pushover plugin (io.thechad.indigoplugin.pushover) — for alerts
- One or more of: Zigbee2MQTTBridge, ShellyDirect, ShellyGen1, Z-Wave devices, Ecowitt plugin

## Development

```bash
python3 -m pytest tests -q
```

No Indigo server and no hardware needed — see `tests/README.md`.

## Recent changes

**v2.8.0** - **Your radiator valves are now watched.** The Evohome plugin learned this week to tell whether each radiator valve is still answering and what its battery is doing, and it marks the room in error when one goes quiet. Nothing was reading that. It wrote a single line to the log, which is recorded but never sent to your phone, so a dead valve would have been found and then told to nobody. This plugin now watches those rooms alongside everything else, and a silent valve reaches you like any other offline device.

It judges a room on whether the Evohome plugin has flagged it, never on how long since the room was heard from, and that distinction is the whole point. The heating controller pushes each room's temperature every few minutes, so the room looks freshly heard from at all times while the valve inside it has been silent for days. A valve that simply has not spoken yet is never called silent, and if the heating gateway itself fails and takes every room with it you get one message rather than twelve.

**v2.7.2** - **The GitHub record inside the bundle now uses the standard spelling.** The plugin bundle carries a small record of where its source lives on GitHub. Ours spelt the two field names its own way, while the plugins Indigo Domotics and the community publish spell them `GithubUser` and `GithubRepo`. It now matches them. Nothing else changed.

**v2.7.1** - **A device that ignores the new check is asked three times, then left alone.** Two loft repeater endpoints answer a status request with "does not support status request command" - as a logged error rather than a refusal the plugin can catch, and both claim to support it, so neither the exception nor the capability flag helps. Left as it was, that would have been two errors every few hours for ever, in a log the error watch reads and sends notifications about. The plugin now notices that a request achieved nothing, counts three of them, and stops asking. A node that ever does answer starts again from zero.


**v2.7.0** - **A mains Z-Wave device that has quietly died is finally noticed.** Three of them had been off the network for 91, 231 and 629 days without a single word from this plugin. Silence was never going to find them, and the check was right not to try: a light or a repeater that nobody has commanded is legitimately quiet for months, and measurement on 9 September put the healthy and the dead completely interleaved, from three months of silence to two years. No threshold separates those.

A ping separates them perfectly. So silence no longer accuses a mains node, it schedules a knock on the door: once one has been quiet for the configured time the plugin sends it a status request, and Indigo's own error state - which the check has always trusted, and which nothing had ever caused to be set on an idle node - gives the verdict on the next scan. One knock per node per period, so the traffic is a handful of frames a day.

The mains threshold setting, retired in May because it could not be made to work, is what controls the quiet time now. Battery devices are left alone: a sleeping node cannot answer a ping, so a failure would mean nothing.


**v2.6.0** - **ESPHome devices are watched now.** They never were, so a failure of anything on that bridge went unnoticed indefinitely - which is exactly what happened on 8 September, when a freezer monitor was off the network all evening and nothing anywhere said so. They are judged on the bridge's own connection flag rather than on silence, because an ESPHome sensor only publishes when a reading changes and a steady load can be quiet for a long time while being perfectly well.

Adding them needed one thing more than a line in the watch list. The away tolerance - how long a device may be out of contact before it is reported - has always been measured from the last successful communication, and for ESPHome that figure is not what it appears to be: the bridge writes "disconnected" from inside its own retry loop, and Indigo treats any such write as fresh contact. A node unreachable for hours therefore looks like it spoke seconds ago, and a tolerance measured from it would never run out, so the device could never be reported at all. Measured on 8 September: a monitor dropped at 21:06 and ninety seconds later still claimed contact thirty seconds old, while its own record of when it was last heard sat correctly frozen three minutes earlier. That record is the clock now, for ESPHome only - the other protocols are untouched.



**v2.5.2** - **The settings dialog was stretched wider than its own window, so the help text beside each setting was cut off mid-sentence.** The short help that can be attached to a setting is drawn on a single line and never wraps, so the longest one decides how wide every row is — and the window cannot be widened past a fixed maximum. All five long ones have moved into ordinary description paragraphs, which do wrap. Two new checks fail the build if any help text or setting label grows long enough to do it again. No setting or behaviour changed.
**v2.5.1** — **Tuned the watchdog for DahuaEvents.** Its cameras only speak when something
happens — a detection, or a change in the stream itself — so a quiet night with nobody about
can go well past an hour without a word, even with every stream open and healthy. The watchdog
had no tuned threshold for it and fell back to the generic sixty minutes, so three quiet
overnight hours cost three restarts and a "needs manual attention" page for cameras that
answered within a tenth of a second when checked by hand. The threshold is now four hours,
which clears the longest quiet spell seen so far with room to spare. A genuine fault still
shows up well inside a minute, so nothing is going unwatched — only the silent-and-healthy
case was being read wrong.

**v2.5.0** — **A plugin that only ever talks outwards is no longer judged on how long it has been quiet.** Some devices have no way of answering back. The RF transmitter that drives the living-room fire sends commands and hears nothing, so the only thing the clock measures is how long since *we* last spoke to *it* — which on a night nobody touched the fire read as a seventy-minute fault. The watchdog restarted a perfectly healthy plugin three times, ran out of its daily allowance, and woke the house at two minutes to midnight and again at twenty to four. Setting `stale_minutes` to nothing at all now means exactly that: watch this plugin for crashes, but never for silence. Humax Aura had the same problem and had been quietly papered over with a tolerance of a full day, which only ever delayed the same wrong answer — it is stated properly now. Crash detection still applies to both, so nothing stops being watched. Eight tests drive the real assessment, including the overnight case that caused this and a crashed transmit-only plugin still being caught.

**v2.4.0** — **A device can now be switched off on purpose without going invisible.** Some things are meant to be off. A washing-machine plug gets turned off at the wall between washes, so for most of the week it is out of contact and there is nothing wrong at all. Until now the only way to stop that filling your phone with alerts was to put the device on the exclusion list, and an exclusion never says anything — which means a plug that is off on purpose and a plug that has died look exactly alike. That is not a worry about something that might happen. On the 9th of August a tumble-dryer plug had been dead for five days, taking the appliance monitoring with it, and nothing had said a word, because it sat on the very same list as the two plugs that are off on purpose. Looking properly at that list the same afternoon turned up a second one, a temperature sensor last heard from 124 days earlier, still showing the reading it had gone quiet on. So there is a new setting, `offline_hours`, alongside the existing quiet-device setting in the same file. It says how long a device may be out of contact before you hear about it. Set a fortnight on the washing machine and it can sit switched off all week in peace, while a plug that never comes back is still reported — which is the one thing an exclusion can never do for you. Two details worth knowing. The clock runs from the last time the device actually spoke, not from when the plugin noticed it was missing, because the plugin's own memory resets whenever it restarts and a dead device could otherwise be handed a fresh grace period for ever and never be reported at all. And a device that has never once communicated is reported straight away however long you set the tolerance, because there is no starting point to measure from and a device that has never spoken is a pairing problem rather than a plug at a wall. The "Show Quiet Devices" menu item lists the tolerances alongside the quiet devices, and tells you if one of them points at a device you have since deleted. Tests: 86 to 101.
**v2.3.2** — **Added the missing support link.** Every Indigo plugin is meant to carry a web address inside its bundle — it is what the "About" item in the Plugins menu opens. This one had the entry but left it blank, so that menu item went nowhere. It now points at this repository. Nothing else changed.
**v2.3.1** — a device's alert is now cleared when it stops being scannable, so the
outstanding list can no longer collect entries that nothing is able to clear: one for a
device that was deleted, and one for a device excluded by hand-editing `exclusions.json`
after it had already alerted.

**v2.3.0** — **Quiet devices**: a per-device staleness threshold for sensors that are
silent by design, in `quiet_devices.json`, reloaded every scan so it can be tuned without
a restart. A hard fault still alerts either way. Also: an alert that could not be
delivered no longer latches, so a Pushover outage is retried instead of swallowed;
`watchdog_plugins.json` is reconciled once against the defaults that seeded it, so
thresholds tuned in later releases finally reach installs that already had the file;
config values are coerced safely, so a cleared field can no longer stop the plugin
loading and a saved dialog can no longer flip the watchdog back into dry-run; and the
plugin gets its first test suite.

**v2.2** — removed a watchdog override for a plugin that no longer exists.

**v2.1** — tightened the EcoFlow Cloud wedge threshold from 720 to 60 minutes, now that
it polls actively rather than waiting on a passive subscription.

**v2.0** — added the plugin watchdog: auto-discovers comms plugins and restarts any that
crash or wedge. Born from a Zigbee2MQTT bridge that kept a dead MQTT socket after a
network blip and went quietly silent.

**v1.1** — exclusion file and management menu items.

**v1.0** — initial release: device-level offline scan with consolidated Pushover alerts.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
