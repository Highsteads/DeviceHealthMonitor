# Device Health Monitor

An Indigo home automation plugin that (1) continuously monitors all physical devices for offline or stale status and sends consolidated Pushover alerts, and (2) auto-discovers comms plugins and restarts any that crash or wedge — a plugin watchdog (v2.0).

## What It Monitors

| Protocol | Source Plugin | Health Check |
|---|---|---|
| Zigbee (via Z2M) | Zigbee2MQTTBridge | `lastSuccessfulComm` freshness (availability can sit stale at "online") |
| Shelly Gen2/3/4 | ShellyDirect | `deviceOnline` state (True/False) |
| Shelly Gen1 | ShellyGen1 | `deviceOnline` state (True/False) |
| Z-Wave | Indigo native | `lastSuccessfulComm` timestamp vs threshold |
| Ecowitt | Ecowitt plugin | `lastChanged` timestamp vs threshold (proxy) |

Everything else is ignored by the *device-level* scan above (HomeKit bridges, virtual devices, timers, etc.). The **plugin watchdog** (below) is a separate layer that does watch comms plugins such as SigenEnergyManager, EcoFlow and RAMSES — at the plugin level rather than per device.

## Features

- Runs a background scan on a configurable interval (5–30 min)
- Protocol-aware health checks — uses the right signal for each device type
- Battery vs mains thresholds for Z-Wave devices (default: 24h battery, 6h mains)
- **One-shot alerting**: alerts fire once per outage, not every scan cycle
- Consolidated Pushover notification (all new offline devices in one message)
- Alert state persists across plugin restarts
- "Scan Now" and "Show Offline Devices" menu items

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

Tune the policy live (no restart needed) in `~/Documents/Indigo/DeviceHealthMonitor/watchdog_plugins.json`. Menu items: Run Watchdog Check Now, Show Watchdog Status, Toggle Watchdog Dry-Run, Reset Watchdog Restart Counters.

## Installation

1. Go to the Releases page and download `DeviceHealthMonitor.indigoPlugin.zip`
2. Unzip — you will get `DeviceHealthMonitor.indigoPlugin`
3. Double-click `DeviceHealthMonitor.indigoPlugin` — Indigo will install it automatically

## Configuration

Open Plugin > Device Health Monitor > Configure:

- **Scan interval** — how often to scan (5/10/15/30 min, default 10)
- **Z-Wave battery threshold** — hours before alerting on a battery Z-Wave device (default 24)
- **Z-Wave mains threshold** — hours before alerting on a mains Z-Wave device (default 6)
- **Ecowitt threshold** — hours since last state change before alerting (default 24)
- **Debug logging** — verbose scan output

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

## Author

CliveS & Claude Opus 4.8
