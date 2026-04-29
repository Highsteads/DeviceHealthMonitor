#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Device Health Monitor — scans all physical devices for offline/stale status
#              and sends consolidated Pushover alerts.
# Author:      CliveS & Claude Sonnet 4.6
# Date:        29-04-2026
# Version:     1.0

import json
import os as _os
import sys as _sys
from datetime import datetime, timedelta

import indigo  # noqa — provided by Indigo runtime

_sys.path.insert(0, _os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None

# ---------------------------------------------------------------------------
# Which plugins we know how to health-check, and which method to use
# ---------------------------------------------------------------------------
MONITORED_PLUGINS = {
    "com.clives.indigoplugin.z2mbridge":               "z2m",
    "com.clives.indigoplugin.shellydirect":            "shelly",
    "com.clives.indigoplugin.shellyg1":                "shelly",
    "com.perceptiveautomation.indigoplugin.zwave":     "zwave",
    "com.clives.indigoplugin.ecowitt":                 "ecowitt",
}

PUSHOVER_PLUGIN_ID = "io.thechad.indigoplugin.pushover"

PLUGIN_ID      = "com.clives.indigoplugin.device-health-monitor"
PLUGIN_NAME    = "Device Health Monitor"
PLUGIN_VERSION = "1.0"


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", level=level)


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug              = pluginPrefs.get("showDebugInfo", False)
        self.scan_interval_sec  = int(pluginPrefs.get("scanIntervalMinutes", 10)) * 60
        self.zwave_battery_hours = float(pluginPrefs.get("zwave_battery_hours", 24))
        self.zwave_mains_hours   = float(pluginPrefs.get("zwave_mains_hours", 6))
        self.ecowitt_hours       = float(pluginPrefs.get("ecowitt_hours", 24))

        # device_id -> datetime first alerted
        self.alerted: dict[int, datetime] = {}
        self._restore_alerted()

        if log_startup_banner:
            log_startup_banner(pluginId, pluginDisplayName, pluginVersion, extras=[
                ("Scan interval:", f"{pluginPrefs.get('scanIntervalMinutes', 10)} min"),
                ("Z-Wave battery:", f"{self.zwave_battery_hours}h threshold"),
                ("Z-Wave mains:",   f"{self.zwave_mains_hours}h threshold"),
                ("Protocols:",      "Z2M (availability), Shelly (deviceOnline), Z-Wave (lastSuccessfulComm), Ecowitt (lastChanged)"),
            ])
        else:
            indigo.server.log(f"{pluginDisplayName} v{pluginVersion} starting")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self):
        log(f"{PLUGIN_NAME} v{PLUGIN_VERSION} started — monitoring {len(MONITORED_PLUGINS)} protocols")

    def shutdown(self):
        self._persist_alerted()
        log(f"{PLUGIN_NAME} shutting down")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.debug               = valuesDict.get("showDebugInfo", False)
            self.scan_interval_sec   = int(valuesDict.get("scanIntervalMinutes", 10)) * 60
            self.zwave_battery_hours = float(valuesDict.get("zwave_battery_hours", 24))
            self.zwave_mains_hours   = float(valuesDict.get("zwave_mains_hours", 6))
            self.ecowitt_hours       = float(valuesDict.get("ecowitt_hours", 24))
            log("Preferences updated")

    # ------------------------------------------------------------------
    # Main scan loop
    # ------------------------------------------------------------------

    def runConcurrentThread(self):
        self.sleep(30)  # brief delay to let Indigo finish loading devices
        while True:
            self._run_scan()
            self.sleep(self.scan_interval_sec)

    def _run_scan(self):
        now          = datetime.now()
        newly_offline = []
        recovered     = []

        for dev in indigo.devices:
            if not dev.enabled:
                continue

            is_offline, reason = self._check_device_health(dev)
            if is_offline is None:
                continue  # device type not monitored

            if is_offline:
                if dev.id not in self.alerted:
                    self.alerted[dev.id] = now
                    newly_offline.append((dev.name, reason))
                    log(f"[OFFLINE] {dev.name}: {reason}", level="WARNING")
            else:
                if dev.id in self.alerted:
                    del self.alerted[dev.id]
                    recovered.append(dev.name)
                    log(f"[RECOVERED] {dev.name}")

        if newly_offline:
            self._alert_pushover(newly_offline)

        self._persist_alerted()

        if self.debug:
            log(f"Scan complete — {len(newly_offline)} new offline, {len(recovered)} recovered, "
                f"{len(self.alerted)} total outstanding")

    # ------------------------------------------------------------------
    # Per-protocol health checks
    # ------------------------------------------------------------------

    def _check_device_health(self, dev):
        """Returns (is_offline: bool, reason: str) or (None, None) if not monitored."""
        protocol = MONITORED_PLUGINS.get(dev.pluginId)
        if protocol is None:
            return None, None

        try:
            if protocol == "z2m":
                return self._check_z2m(dev)
            if protocol == "shelly":
                return self._check_shelly(dev)
            if protocol == "zwave":
                return self._check_zwave(dev)
            if protocol == "ecowitt":
                return self._check_ecowitt(dev)
        except Exception as e:
            log(f"Error checking {dev.name}: {e}", level="ERROR")

        return None, None

    def _check_z2m(self, dev):
        avail = dev.states.get("availability", "online")
        return avail == "offline", "availability=offline"

    def _check_shelly(self, dev):
        # deviceOnline may be bool or string depending on device type
        raw = dev.states.get("deviceOnline", True)
        online = raw if isinstance(raw, bool) else str(raw).lower() not in ("false", "0", "no")
        return not online, "deviceOnline=False"

    def _check_zwave(self, dev):
        last = dev.lastSuccessfulComm
        if last is None:
            return True, "lastSuccessfulComm=None (never communicated)"
        hours = self._hours_since(last)
        is_battery = dev.batteryLevel is not None
        threshold  = self.zwave_battery_hours if is_battery else self.zwave_mains_hours
        kind       = "battery" if is_battery else "mains"
        return hours > threshold, f"last comm {hours:.1f}h ago ({kind}, threshold {threshold}h)"

    def _check_ecowitt(self, dev):
        last = dev.lastChanged
        if last is None:
            return True, "lastChanged=None"
        hours = self._hours_since(last)
        return hours > self.ecowitt_hours, f"lastChanged {hours:.1f}h ago (threshold {self.ecowitt_hours}h)"

    # ------------------------------------------------------------------
    # Alerting
    # ------------------------------------------------------------------

    def _alert_pushover(self, offline_list):
        try:
            plugin = indigo.server.getPlugin(PUSHOVER_PLUGIN_ID)
            if not plugin.isEnabled():
                raise RuntimeError("Pushover plugin not enabled")

            body  = "\n".join(f"- {name} ({reason})" for name, reason in offline_list)
            title = f"Device Health: {len(offline_list)} offline"
            props = {
                "msgTitle":    title,
                "msgBody":     body,
                "msgPriority": "0",
                "msgSound":    "vibrate",
            }
            plugin.executeAction("send", props=props)
            log(f"Pushover alert sent: {len(offline_list)} device(s) offline")
        except Exception as e:
            log(f"Pushover failed ({e}) — logging offline devices to event log", level="WARNING")
            for name, reason in offline_list:
                log(f"[OFFLINE] {name}: {reason}", level="WARNING")

    # ------------------------------------------------------------------
    # Alert state persistence
    # ------------------------------------------------------------------

    def _persist_alerted(self):
        try:
            data = {str(k): v.isoformat() for k, v in self.alerted.items()}
            self.pluginPrefs["alerted_json"] = json.dumps(data)
            indigo.server.savePluginPrefs()
        except Exception as e:
            log(f"Failed to persist alert state: {e}", level="ERROR")

    def _restore_alerted(self):
        try:
            raw  = self.pluginPrefs.get("alerted_json", "{}")
            data = json.loads(raw)
            self.alerted = {int(k): datetime.fromisoformat(v) for k, v in data.items()}
            if self.alerted:
                log(f"Restored {len(self.alerted)} outstanding alert(s) from previous session")
        except Exception as e:
            log(f"Could not restore alert state: {e}", level="WARNING")
            self.alerted = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hours_since(dt):
        return (datetime.now() - dt).total_seconds() / 3600.0

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def menuScanNow(self, valuesDict=None, typeId=None):
        log("Manual scan triggered")
        self._run_scan()
        return True

    def menuShowStaleDevices(self, valuesDict=None, typeId=None):
        if not self.alerted:
            log("No devices currently offline or stale")
            return True

        log(f"--- Currently offline/stale devices ({len(self.alerted)}) ---")
        for dev_id, first_seen in self.alerted.items():
            try:
                dev  = indigo.devices[dev_id]
                name = dev.name
            except Exception:
                name = f"[deleted device {dev_id}]"
            duration = self._hours_since(first_seen)
            log(f"  {name} — offline for {duration:.1f}h (since {first_seen.strftime('%H:%M %d-%b')})",
                level="WARNING")
        log("---")
        return True

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=[
                ("Scan interval:", f"{self.pluginPrefs.get('scanIntervalMinutes', 10)} min"),
                ("Z-Wave battery:", f"{self.zwave_battery_hours}h threshold"),
                ("Z-Wave mains:",   f"{self.zwave_mains_hours}h threshold"),
                ("Outstanding alerts:", str(len(self.alerted))),
                ("Protocols:",     "Z2M, ShellyDirect, ShellyGen1, Z-Wave, Ecowitt"),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion} | "
                              f"{len(self.alerted)} outstanding alert(s)")
