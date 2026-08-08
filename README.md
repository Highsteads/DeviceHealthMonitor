# Device Health Monitor

An Indigo home automation plugin that (1) continuously monitors all physical devices for offline or stale status and sends consolidated Pushover alerts, and (2) auto-discovers comms plugins and restarts any that crash or wedge — a plugin watchdog (v2.0).

## What It Monitors

| Protocol | Source Plugin | Health Check |
|---|---|---|
| Zigbee (via Z2M) | Zigbee2MQTTBridge | `lastSuccessfulComm` freshness (availability can sit stale at "online") |
| Shelly Gen2/3/4 | ShellyDirect | `deviceOnline` state (True/False) |
| Shelly Gen1 | ShellyGen1 | `deviceOnline` state (True/False) |
| Z-Wave | Indigo native | Indigo's `errorState` for mains, `lastSuccessfulComm` threshold for battery |
| Ecowitt | Ecowitt plugin | `lastChanged` timestamp vs threshold (proxy) |

Everything else is ignored by the *device-level* scan above (HomeKit bridges, virtual devices, timers, etc.). The **plugin watchdog** (below) is a separate layer that does watch comms plugins such as SigenEnergyManager, EcoFlow and RAMSES — at the plugin level rather than per device.

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
