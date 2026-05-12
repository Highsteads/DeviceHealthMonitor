# Device Health Monitor

An Indigo home automation plugin that continuously monitors all physical devices for offline or stale status, and sends consolidated Pushover alerts.

## What It Monitors

| Protocol | Source Plugin | Health Check |
|---|---|---|
| Zigbee (via Z2M) | Zigbee2MQTTBridge | `availability` state ("online"/"offline") |
| Shelly Gen2/3/4 | ShellyDirect | `deviceOnline` state (True/False) |
| Shelly Gen1 | ShellyGen1 | `deviceOnline` state (True/False) |
| Z-Wave | Indigo native | `lastSuccessfulComm` timestamp vs threshold |
| Ecowitt | Ecowitt plugin | `lastChanged` timestamp vs threshold (proxy) |

Everything else (HomeKit bridges, virtual devices, timers, SigenEnergyManager, EcoFlow, RAMSES heating, etc.) is silently ignored.

## Features

- Runs a background scan on a configurable interval (5–30 min)
- Protocol-aware health checks — uses the right signal for each device type
- Battery vs mains thresholds for Z-Wave devices (default: 24h battery, 6h mains)
- **One-shot alerting**: alerts fire once per outage, not every scan cycle
- Consolidated Pushover notification (all new offline devices in one message)
- Alert state persists across plugin restarts
- "Scan Now" and "Show Offline Devices" menu items

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

- Indigo 2025.1 or later
- Pushover plugin (io.thechad.indigoplugin.pushover) — for alerts
- One or more of: Zigbee2MQTTBridge, ShellyDirect, ShellyGen1, Z-Wave devices, Ecowitt plugin

## Author

CliveS & Claude Sonnet 4.6
