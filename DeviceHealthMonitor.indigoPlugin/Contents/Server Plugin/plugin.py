#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Device Health Monitor — scans all physical devices for offline/stale status
#              and sends consolidated Pushover alerts.
# Author:      CliveS & Claude Sonnet 4.6
# Date:        29-04-2026
# Version:     1.1

import json
import os
import os as _os
import sys as _sys
from datetime import datetime

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
PLUGIN_VERSION = "1.1"

EXCLUSIONS_FILE = os.path.expanduser(
    "~/Documents/Indigo/DeviceHealthMonitor/exclusions.json"
)


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", level=level)


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug               = pluginPrefs.get("showDebugInfo", False)
        self.scan_interval_sec   = int(pluginPrefs.get("scanIntervalMinutes", 10)) * 60
        self.zwave_battery_hours = float(pluginPrefs.get("zwave_battery_hours", 24))
        self.zwave_mains_hours   = float(pluginPrefs.get("zwave_mains_hours", 6))
        self.ecowitt_hours       = float(pluginPrefs.get("ecowitt_hours", 24))

        # device_id -> datetime first alerted
        self.alerted: dict[int, datetime] = {}
        self._restore_alerted()

        # Exclusion list (set of lowercase device names)
        self.excluded_names: set[str] = set()
        self._load_exclusions()

        if log_startup_banner:
            log_startup_banner(pluginId, pluginDisplayName, pluginVersion, extras=[
                ("Scan interval:", f"{pluginPrefs.get('scanIntervalMinutes', 10)} min"),
                ("Z-Wave battery:", f"{self.zwave_battery_hours}h threshold"),
                ("Z-Wave mains:",   f"{self.zwave_mains_hours}h threshold"),
                ("Exclusions:",     f"{len(self.excluded_names)} device(s) excluded"),
                ("Protocols:",      "Z2M (availability), Shelly (deviceOnline), Z-Wave (lastSuccessfulComm), Ecowitt (lastChanged)"),
            ])
        else:
            indigo.server.log(f"{pluginDisplayName} v{pluginVersion} starting")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self):
        log(f"{PLUGIN_NAME} v{PLUGIN_VERSION} started — monitoring {len(MONITORED_PLUGINS)} protocols, "
            f"{len(self.excluded_names)} exclusion(s)")

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
            self._load_exclusions()  # reload each cycle — edits take effect without restart
            self._run_scan()
            self.sleep(self.scan_interval_sec)

    def _run_scan(self):
        now           = datetime.now()
        newly_offline = []
        recovered     = []

        for dev in indigo.devices:
            if not dev.enabled:
                continue
            if dev.name.lower() in self.excluded_names:
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
        raw    = dev.states.get("deviceOnline", True)
        online = raw if isinstance(raw, bool) else str(raw).lower() not in ("false", "0", "no")
        return not online, "deviceOnline=False"

    def _check_zwave(self, dev):
        last = dev.lastSuccessfulComm
        if last is None:
            return True, "lastSuccessfulComm=None (never communicated)"
        hours      = self._hours_since(last)
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
    # Exclusion file
    # ------------------------------------------------------------------

    def _load_exclusions(self):
        try:
            if not os.path.exists(EXCLUSIONS_FILE):
                self.excluded_names = set()
                return
            with open(EXCLUSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            names = data.get("excluded_names", [])
            self.excluded_names = {n.lower() for n in names}
            if self.debug:
                log(f"Loaded {len(self.excluded_names)} exclusion(s) from file")
        except Exception as e:
            log(f"Failed to load exclusions file: {e}", level="ERROR")
            self.excluded_names = set()

    def _save_exclusions(self, names: list[str]):
        try:
            os.makedirs(os.path.dirname(EXCLUSIONS_FILE), exist_ok=True)
            existing = []
            if os.path.exists(EXCLUSIONS_FILE):
                with open(EXCLUSIONS_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing = existing_data.get("excluded_names", [])
            merged = sorted(set(existing) | set(names))
            data = {
                "_comment":  "Device Health Monitor exclusion list.",
                "_comment2": "Add device names to 'excluded_names' to permanently skip a device.",
                "_comment3": "Use the plugin menu 'Add Offline Devices to Exclusions' to bulk-add current alerts.",
                "excluded_names": merged,
            }
            with open(EXCLUSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._load_exclusions()
            log(f"Exclusions file updated — {len(merged)} device(s) excluded total")
        except Exception as e:
            log(f"Failed to save exclusions: {e}", level="ERROR")

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
            log(f"  {name} -- offline for {duration:.1f}h (since {first_seen.strftime('%H:%M %d-%b')})",
                level="WARNING")
        log("---")
        return True

    def menuAddOfflineToExclusions(self, valuesDict=None, typeId=None):
        if not self.alerted:
            log("No offline devices to add to exclusions")
            return True

        names = []
        for dev_id in list(self.alerted.keys()):
            try:
                names.append(indigo.devices[dev_id].name)
            except Exception:
                pass

        if names:
            self._save_exclusions(names)
            # Clear alerted state for newly excluded devices so they don't linger
            for dev_id in list(self.alerted.keys()):
                try:
                    if indigo.devices[dev_id].name in names:
                        del self.alerted[dev_id]
                except Exception:
                    del self.alerted[dev_id]
            self._persist_alerted()
            log(f"Added {len(names)} device(s) to exclusions — they will not be monitored in future scans")
            for n in names:
                log(f"  Excluded: {n}")
        return True

    def menuShowExclusions(self, valuesDict=None, typeId=None):
        if not self.excluded_names:
            log(f"No exclusions defined. Edit {EXCLUSIONS_FILE} to add device names.")
            return True
        log(f"--- Excluded devices ({len(self.excluded_names)}) --- file: {EXCLUSIONS_FILE}")
        for name in sorted(self.excluded_names):
            log(f"  {name}")
        log("---")
        return True

    def menuClearAlertState(self, valuesDict=None, typeId=None):
        count = len(self.alerted)
        self.alerted = {}
        self._persist_alerted()
        log(f"Alert state cleared ({count} device(s) reset). Next scan starts fresh.")
        return True

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=[
                ("Scan interval:", f"{self.pluginPrefs.get('scanIntervalMinutes', 10)} min"),
                ("Z-Wave battery:", f"{self.zwave_battery_hours}h threshold"),
                ("Z-Wave mains:",   f"{self.zwave_mains_hours}h threshold"),
                ("Outstanding alerts:", str(len(self.alerted))),
                ("Exclusions:",    f"{len(self.excluded_names)} device(s)"),
                ("Exclusions file:", EXCLUSIONS_FILE),
                ("Protocols:",     "Z2M, ShellyDirect, ShellyGen1, Z-Wave, Ecowitt"),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion} | "
                              f"{len(self.alerted)} outstanding alert(s) | "
                              f"{len(self.excluded_names)} excluded")
