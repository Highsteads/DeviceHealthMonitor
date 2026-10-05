# Device Health Monitor

**Tells your phone when a device in Indigo stops answering, and restarts a plugin that has stopped working.**

**Version:** 2.12.0 | **Author:** CliveS & Claude | **Needs:** Indigo 2022.1 or later and the Pushover plugin

**[Read the full guide](https://highsteads.github.io/DeviceHealthMonitor/)** — setting up, what everything means, and what to do when something goes wrong.

---

## What it does

This plugin keeps an eye on the devices in [Indigo](https://www.indigodomo.com) that talk to the house over a network or a radio, and sends a message to your phone through Pushover when one of them goes quiet. It has no devices of its own — you install it, check a few settings, and it works in the background.

- **Checks your devices every 10 minutes,** or every 5, 15 or 30, using the right test for each kind of device.
- **Sends one message for everything found offline** in a check, and tells you about each outage once, not at every check.
- **Asks a mains Zigbee light or Z-Wave node whether it is there** before calling it offline, because a light nobody has used for a while is quiet but perfectly healthy.
- **Lets a device be quiet or away on purpose.** A cupboard door sensor can be allowed days of silence, and a washing machine plug switched off at the wall can be allowed to be away for a fortnight, while one that never comes back is still reported.
- **Watches the plugins themselves** and can restart one that has crashed or stopped hearing from its devices. It starts in a trial mode where it only tells you what it would restart.

## What it watches

| Your devices | Through |
|---|---|
| Zigbee lights, plugs and sensors | Zigbee2MQTT Bridge |
| Shelly Plus, Pro, Gen 3 and Gen 4 | Shelly Direct |
| Shelly Gen 1 relays and plugs | Shelly Gen 1 |
| Z-Wave devices | Indigo's own Z-Wave |
| Ecowitt weather sensors | Ecowitt Weather Station |
| ESPHome devices | ESPHome Bridge |
| Evohome radiator valves | RAMSES ESP |

The plugin watchdog works with almost any plugin that runs devices.

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/DeviceHealthMonitor/releases/latest) and download `DeviceHealthMonitor.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `DeviceHealthMonitor.indigoPlugin`
3. Double-click `DeviceHealthMonitor.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Make sure the Pushover plugin is installed and sends messages to your phone.
2. Open **Plugins → Device Health Monitor → Configure**, look over the settings, and click **Save**. The ones it starts with suit most houses.
3. Choose **Plugins → Device Health Monitor → Scan Devices Now**. Anything already offline appears in the Event Log and in a Pushover message.
4. Give any device that is quiet or switched off on purpose its own allowance, as the guide explains.

The [full guide](https://highsteads.github.io/DeviceHealthMonitor/) goes through each step, explains every setting, and covers what to do if something does not work.

## What's new

**v2.12.0** — An Ecowitt gateway or sensor that stops sending is reported. The plugin judged Ecowitt devices on when a device last changed, and Ecowitt updates its gateway every minute even when no reading arrives, so a dead gateway was never reported.

**v2.11.0** — A Shelly Gen 1 device that stops answering is reported, the auto-discovered stale threshold setting works after the first run, and a dry run no longer sends a message at every check.

**v2.10.2** — A Zigbee device is treated as battery-powered if Zigbee2MQTT says it runs on a battery, so a sleeping device is no longer asked a question it cannot answer.

**v2.10.1** — While the plugin waits for a Zigbee device to answer, it no longer announces the device as recovered.

Every version is listed in the [version history](https://highsteads.github.io/DeviceHealthMonitor/changelog.html).

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
