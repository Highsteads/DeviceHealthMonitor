#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Device Health Monitor — scans all physical devices for offline/stale
#              status and sends consolidated Pushover alerts, AND auto-discovers
#              comms plugins, restarting any that crash or wedge.
# Author:      CliveS & Claude Opus 4.8
# Date:        19-06-2026
# Version:     2.2
#
# v2.2 (19-06-2026): removed the WATCHDOG_OVERRIDES entry for MQTTExplorerBridge —
# that plugin has been uninstalled and deleted, so the tuned threshold referenced
# a plugin that no longer exists (harmless dead entry; removed for tidiness).
#
# v2.1 (19-06-2026): tightened the EcoFlow Cloud wedged threshold 720->60 min.
# EcoFlow Cloud v1.8+ now actively polls each device every ~10s (River 3 / Delta 3
# don't stream passively), so lastSuccessfulComm stays fresh and a 60-min gap is a
# genuine wedge rather than normal idle — the old 720-min value was a workaround for
# the passive-subscribe bug that v1.8 fixed.
#
# v2.0 (29-05-2026): Added the Plugin Watchdog layer. The device-level scan
# (unchanged) alerts on individual offline/stale devices; the new watchdog works
# at the PLUGIN level and RESTARTS a plugin that is either crashed (enabled but
# not running) or wedged (its newest device comm is older than a threshold — the
# failure mode that left "Jane Lamp" dead on 29-05-2026 when z2mbridge kept a dead
# MQTT socket after a network blip). The watchdog AUTO-DISCOVERS any plugin that
# owns comms devices; a code denylist keeps native/virtual/derived/bridge plugins
# out, tuned thresholds are applied where the cadence is known and a generous
# default elsewhere. Guards: per-plugin cooldown + daily cap, post-restart grace,
# dry-run mode (default ON), Pushover on every action, ClaudeBridge hard-excluded
# in code (restarting it would drop the MCP channel). The z2m device-level check
# now uses lastSuccessfulComm freshness rather than the availability state, which
# can sit stale at "online" through a bridge wedge. log() upgraded to ms precision.
#
# v1.1 (29-04-2026): Device-level offline/stale scan with Pushover alerts and a
# live-editable exclusions file.

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
# Device-level health checks: which plugins we know how to check, and how.
# (This is the per-DEVICE offline scan — distinct from the plugin watchdog,
# which auto-discovers and restarts whole plugins.)
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
PLUGIN_VERSION = "2.2"

EXCLUSIONS_FILE = os.path.expanduser(
    "~/Documents/Indigo/DeviceHealthMonitor/exclusions.json"
)

# ---------------------------------------------------------------------------
# Plugin Watchdog — auto-discover and restart crashed or wedged comms plugins.
# ---------------------------------------------------------------------------
# Restarting the MCP bridge would sever the very channel Claude uses (and has a
# known reflector dead-zone on self-restart), so it is excluded in code and cannot
# be re-included. This plugin never restarts itself.
CLAUDEBRIDGE_ID = "com.clives.indigoplugin.claudebridge"

# Don't re-judge a plugin for this many minutes after WE restart it (let it come
# back up and re-establish before assessing running state / staleness again).
POST_RESTART_GRACE_MIN = 5

# The watchdog AUTO-DISCOVERS plugins to watch: any plugin that owns at least one
# enabled, configured device maintaining lastSuccessfulComm is a candidate, unless
# excluded. Crashed-detection (enabled but not running) applies to every candidate;
# staleness-detection uses a tuned threshold if we have one, else a generous
# discovered default so a newly-seen plugin is never nuisance-restarted.

# Tuned per-plugin thresholds (applied to discovered plugins whose cadence we know).
#   stale_minutes / cooldown_minutes / max_per_day / enabled
WATCHDOG_OVERRIDES = {
    "com.clives.indigoplugin.z2mbridge":                {"stale_minutes": 5,   "cooldown_minutes": 15, "max_per_day": 6, "enabled": True},
    "com.clives.indigoplugin.tasmotabridge":            {"stale_minutes": 8,   "cooldown_minutes": 15, "max_per_day": 6, "enabled": True},
    "com.clives.indigoplugin.esphomebridge":            {"stale_minutes": 10,  "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    "com.clives.indigoplugin.sigenergy-energy-manager": {"stale_minutes": 10,  "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    # EcoFlow Cloud v1.8+ actively polls each device every ~10s (River 3 / Delta 3 don't
    # stream passively), so lastSuccessfulComm stays fresh — a 60-min gap now means a
    # genuine wedge (dead MQTT + failed reconnect), not normal idle. Tightened 720->60.
    "com.clives.indigoplugin.ecoflowcloud":             {"stale_minutes": 60,  "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "com.clives.indigoplugin.ecowitt":                  {"stale_minutes": 20,  "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    # RAMSES TRVs report infrequently (esp. summer, heating off) — lenient threshold.
    "uk.co.clives.ramses.esp":                          {"stale_minutes": 180, "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "com.clives.indigoplugin.shellydirect":             {"stale_minutes": 15,  "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    # ShellyGen1 is known HTTP-flaky — long threshold + low cap so we don't thrash it.
    "com.clives.indigoplugin.shellyg1":                 {"stale_minutes": 30,  "cooldown_minutes": 60, "max_per_day": 2, "enabled": True},
    # Humax Aura (TV) only comms when in use — staleness is not a wedge signal, so this is
    # effectively crashed-only (24h threshold) to avoid nuisance restarts when the TV is off.
    "com.clives.indigoplugin.humaxaura":                {"stale_minutes": 1440, "cooldown_minutes": 60, "max_per_day": 2, "enabled": True},
}

# Never auto-restart these. ClaudeBridge (MCP channel) and this plugin are added in
# code and cannot be re-included. The rest are native / virtual / derived / bridge /
# notification plugins where a restart is wrong, meaningless, or too disruptive to
# automate. Un-exclude one via "include" in the config file if you do want it watched.
WATCHDOG_DENYLIST = {
    "com.perceptiveautomation.indigoplugin.zwave",             # native — restart re-inits the whole Z-Wave mesh
    "com.perceptiveautomation.indigoplugin.devicecollection",  # virtual devices
    "com.perceptiveautomation.indigoplugin.timersandpesters",  # timers / pesters
    "com.GlennNZ.indigoplugin.HomeKitLink-Siri",               # HomeKit bridges
    "com.indigodomo.email",                                    # SMTP, no polling
    "com.howartp.clockdisplay",                                # clock display
    "com.howartp.lockmanager",                                 # derived lock logic
    "com.drjason.temp-adapter",                                # derived temperature
    "com.clives.indigoplugin.deviceactivitymonitor",           # derived activity / presence
    "com.clives.indigoplugin.appliancemonitor",                # derived appliance state
    "com.clives.universal-zwave-sensor",                       # derived from Z-Wave
    "io.thechad.indigoplugin.pushover",                        # notifications
}

# Policy for auto-discovered plugins with no tuned override (generous so a newly-seen
# plugin is never nuisance-restarted before you tune it). stale_minutes is overridden
# by the "Auto-discovered default stale threshold" preference.
DISCOVERED_DEFAULT = {"stale_minutes": 60, "cooldown_minutes": 30, "max_per_day": 3, "enabled": True}

WATCHDOG_CONFIG_FILE = os.path.expanduser(
    "~/Documents/Indigo/DeviceHealthMonitor/watchdog_plugins.json"
)


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=level)


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug               = pluginPrefs.get("showDebugInfo", False)
        self.scan_interval_sec   = int(pluginPrefs.get("scanIntervalMinutes", 10)) * 60
        self.zwave_battery_hours = float(pluginPrefs.get("zwave_battery_hours", 24))
        self.zwave_mains_hours   = float(pluginPrefs.get("zwave_mains_hours", 6))
        self.ecowitt_hours       = float(pluginPrefs.get("ecowitt_hours", 24))
        self.z2m_stale_hours     = float(pluginPrefs.get("z2m_stale_hours", 12))

        # device_id -> datetime first alerted
        self.alerted: dict[int, datetime] = {}
        self._restore_alerted()

        # Exclusion list (set of lowercase device names) for the device-level scan
        self.excluded_names: set[str] = set()
        self._load_exclusions()

        # Plugin watchdog (auto-discovering)
        self.watchdog_enabled          = bool(pluginPrefs.get("watchdogEnabled", True))
        self.watchdog_dry_run          = bool(pluginPrefs.get("watchdogDryRun", True))
        self.watchdog_discovered_stale = float(pluginPrefs.get("watchdogDefaultStaleMin", 60))
        # pluginId -> {"last_restart": iso|None, "restarts_today": int, "day": str, "cap_alerted": bool}
        self.restart_state: dict = {}
        self._restore_watchdog_state()
        # Resolved config (seeded from code, overlaid by the editable JSON file)
        self.watchdog_overrides: dict          = {}
        self.watchdog_exclude: set             = set()
        self.watchdog_discovered_default: dict = {}
        self._load_watchdog_config()

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self):
        log(f"{PLUGIN_NAME} v{PLUGIN_VERSION} started — {len(MONITORED_PLUGINS)} device protocols, "
            f"watchdog {'ON' if self.watchdog_enabled else 'OFF'} "
            f"({'dry-run' if self.watchdog_dry_run else 'LIVE'}, auto-discover, "
            f"{len(self.watchdog_exclude)} excluded), {len(self.excluded_names)} device exclusion(s)")

    def shutdown(self):
        self._persist_alerted()
        self._persist_watchdog_state()
        log(f"{PLUGIN_NAME} shutting down")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.debug                     = valuesDict.get("showDebugInfo", False)
            self.scan_interval_sec         = int(valuesDict.get("scanIntervalMinutes", 10)) * 60
            self.zwave_battery_hours       = float(valuesDict.get("zwave_battery_hours", 24))
            self.zwave_mains_hours         = float(valuesDict.get("zwave_mains_hours", 6))
            self.ecowitt_hours             = float(valuesDict.get("ecowitt_hours", 24))
            self.z2m_stale_hours           = float(valuesDict.get("z2m_stale_hours", 12))
            self.watchdog_enabled          = bool(valuesDict.get("watchdogEnabled", True))
            self.watchdog_dry_run          = bool(valuesDict.get("watchdogDryRun", True))
            self.watchdog_discovered_stale = float(valuesDict.get("watchdogDefaultStaleMin", 60))
            self._load_watchdog_config()
            log("Preferences updated")

    # ------------------------------------------------------------------
    # Main scan + watchdog loop
    # ------------------------------------------------------------------

    def runConcurrentThread(self):
        self.sleep(30)  # brief delay to let Indigo finish loading devices
        while True:
            try:
                self._load_exclusions()       # reload each cycle — edits take effect without restart
                self._run_scan()
                self._load_watchdog_config()  # reload each cycle too
                self._run_plugin_watchdog()
            except Exception as e:
                log(f"Cycle error: {e}", level="ERROR")
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
    # Per-protocol device health checks
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
        # Trust comm freshness over the availability state: availability can sit
        # stale at "online" after a bridge MQTT wedge (the Jane Lamp case,
        # 29-05-2026), so check lastSuccessfulComm first, then fall back to the
        # availability flag for devices z2m has actively marked offline.
        last = dev.lastSuccessfulComm
        if last is not None:
            hours = self._hours_since(last)
            if hours > self.z2m_stale_hours:
                return True, f"no comm for {hours:.1f}h (threshold {self.z2m_stale_hours}h)"
        avail = dev.states.get("availability", "online")
        if avail == "offline":
            return True, "availability=offline"
        return False, ""

    def _check_shelly(self, dev):
        # deviceOnline may be bool or string depending on device type
        raw    = dev.states.get("deviceOnline", True)
        online = raw if isinstance(raw, bool) else str(raw).lower() not in ("false", "0", "no")
        return not online, "deviceOnline=False"

    def _check_zwave(self, dev):
        # Indigo's own errorState is the reliable signal — it is set when the
        # controller can't reach the node (failed poll / dead node). lastSuccessfulComm
        # is NOT a health signal for mains Z-Wave devices that aren't actively polled:
        # it only tracks "time since last used", so an idle-but-alive light or repeater
        # reads stale for days. Confirmed 29-05-2026 — 11 of 20 mains nodes were >6h
        # stale with errorState clear (En Suite floor heating, Loft repeater, everyday
        # lights), every one perfectly healthy.
        if dev.errorState:
            return True, f"errorState={dev.errorState!r}"
        # Battery Z-Wave devices DO report on a wake cadence, so prolonged silence is
        # meaningful (flat battery / fallen off the mesh).
        if dev.batteryLevel is not None:
            last = dev.lastSuccessfulComm
            if last is None:
                return True, "battery device never communicated (lastSuccessfulComm=None)"
            hours = self._hours_since(last)
            return hours > self.zwave_battery_hours, \
                f"battery device: last comm {hours:.1f}h ago (threshold {self.zwave_battery_hours}h)"
        # Mains device with no error — healthy (stale comm is normal for un-polled nodes).
        return False, ""

    def _check_ecowitt(self, dev):
        last = dev.lastChanged
        if last is None:
            return True, "lastChanged=None"
        hours = self._hours_since(last)
        return hours > self.ecowitt_hours, f"lastChanged {hours:.1f}h ago (threshold {self.ecowitt_hours}h)"

    # ------------------------------------------------------------------
    # Exclusion file (device-level scan)
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
    # Pushover
    # ------------------------------------------------------------------

    def _send_pushover(self, title, body, priority="0", sound="vibrate"):
        """Send a single Pushover message. Returns True on success."""
        try:
            plugin = indigo.server.getPlugin(PUSHOVER_PLUGIN_ID)
            if not plugin.isEnabled():
                raise RuntimeError("Pushover plugin not enabled")
            plugin.executeAction("send", props={
                "msgTitle":    title,
                "msgBody":     body,
                "msgPriority": str(priority),
                "msgSound":    sound,
            })
            return True
        except Exception as e:
            log(f"Pushover failed ({e}) — {title}: {body}", level="WARNING")
            return False

    def _alert_pushover(self, offline_list):
        body  = "\n".join(f"- {name} ({reason})" for name, reason in offline_list)
        title = f"Device Health: {len(offline_list)} offline"
        if self._send_pushover(title, body, priority="0"):
            log(f"Pushover alert sent: {len(offline_list)} device(s) offline")
        else:
            for name, reason in offline_list:
                log(f"[OFFLINE] {name}: {reason}", level="WARNING")

    # ==================================================================
    # Plugin Watchdog (auto-discovering)
    # ==================================================================

    def _load_watchdog_config(self):
        """Resolve the watchdog policy: code defaults overlaid by an editable JSON
        file (created on first run). Holds tuned per-plugin overrides, an exclude
        list, optional includes (to un-exclude a denylisted plugin) and the default
        policy for auto-discovered plugins. ClaudeBridge and this plugin are always
        excluded in code and cannot be re-included."""
        overrides = {pid: dict(pol) for pid, pol in WATCHDOG_OVERRIDES.items()}
        exclude   = set(WATCHDOG_DENYLIST)
        default   = dict(DISCOVERED_DEFAULT)
        default["stale_minutes"] = self.watchdog_discovered_stale
        try:
            if os.path.exists(WATCHDOG_CONFIG_FILE):
                with open(WATCHDOG_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pid, pol in (data.get("overrides") or {}).items():
                    if isinstance(pol, dict):
                        overrides.setdefault(pid, {})
                        overrides[pid].update(pol)
                for pid in (data.get("exclude") or []):
                    exclude.add(pid)
                for pid in (data.get("include") or []):
                    exclude.discard(pid)
                if isinstance(data.get("discovered_default"), dict):
                    default.update(data["discovered_default"])
            else:
                self._write_watchdog_config(overrides, sorted(exclude), default)
        except Exception as e:
            log(f"Watchdog: failed to load config ({e}) — using built-in defaults", level="WARNING")
        # Hard excludes — never restartable, cannot be re-included.
        exclude.add(CLAUDEBRIDGE_ID)
        exclude.add(self.pluginId)
        self.watchdog_overrides          = overrides
        self.watchdog_exclude            = exclude
        self.watchdog_discovered_default = default

    def _write_watchdog_config(self, overrides, exclude_list, default):
        try:
            os.makedirs(os.path.dirname(WATCHDOG_CONFIG_FILE), exist_ok=True)
            doc = {
                "_comment":  "Device Health Monitor — plugin watchdog policy (auto-discovering).",
                "_comment2": "The watchdog auto-discovers any plugin that owns comms devices. "
                             "'overrides' tunes per-plugin thresholds (stale_minutes / cooldown_minutes / "
                             "max_per_day / enabled). 'exclude' lists plugin ids never to restart. "
                             "'include' un-excludes a code-denylisted plugin. 'discovered_default' is the "
                             "policy for discovered plugins with no override.",
                "_comment3": f"{CLAUDEBRIDGE_ID} and {self.pluginId} are ALWAYS excluded in code.",
                "overrides":          overrides,
                "exclude":            exclude_list,
                "include":            [],
                "discovered_default": default,
            }
            with open(WATCHDOG_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=4)
            log(f"Watchdog: wrote default config to {WATCHDOG_CONFIG_FILE}")
        except Exception as e:
            log(f"Watchdog: failed to write config file: {e}", level="ERROR")

    def _discover_candidates(self, plugin_devices):
        """Return {pid: policy} for every device-owning comms plugin to watch.
        A plugin qualifies if it owns >=1 enabled+configured device that maintains
        lastSuccessfulComm and it is not excluded. Policy = tuned override if known,
        else the generous discovered default."""
        candidates = {}
        for pid, devs in plugin_devices.items():
            if pid in self.watchdog_exclude:
                continue
            if not any(d.lastSuccessfulComm is not None for d in devs):
                continue  # no comm timestamps => virtual/derived, not staleness-checkable
            policy = dict(self.watchdog_discovered_default)
            if pid in self.watchdog_overrides:
                policy.update(self.watchdog_overrides[pid])
            if not policy.get("enabled", True):
                continue
            candidates[pid] = policy
        return candidates

    def _run_plugin_watchdog(self):
        if not self.watchdog_enabled:
            return
        now = datetime.now()
        self._roll_restart_day(now)

        plugin_devices: dict = {}
        for dev in indigo.devices:
            if dev.enabled and dev.configured:
                plugin_devices.setdefault(dev.pluginId, []).append(dev)

        candidates = self._discover_candidates(plugin_devices)
        for pid, policy in candidates.items():
            if pid in (CLAUDEBRIDGE_ID, self.pluginId):   # defensive
                continue
            try:
                verdict, reason = self._assess_plugin_health(pid, policy, plugin_devices.get(pid, []), now)
                if verdict in ("crashed", "wedged"):
                    self._maybe_restart_plugin(pid, policy, verdict, reason, now)
                elif self.debug:
                    log(f"Watchdog: {self._plugin_label(pid)} {verdict} ({reason})")
            except Exception as e:
                log(f"Watchdog: error assessing {pid}: {e}", level="ERROR")

        self._persist_watchdog_state()

    def _assess_plugin_health(self, pid, policy, devs, now):
        """Return (verdict, reason); verdict in ok / crashed / wedged / unavailable."""
        try:
            wrapper = indigo.server.getPlugin(pid)
        except Exception as e:
            return "unavailable", f"getPlugin failed: {e}"
        if not wrapper.isInstalled():
            return "unavailable", "not installed"
        if not wrapper.isEnabled():
            return "unavailable", "disabled by user"

        # Give a plugin we just restarted time to come back before re-judging it.
        last = self._last_restart_dt(pid)
        if last and (now - last).total_seconds() < POST_RESTART_GRACE_MIN * 60:
            return "ok", "post-restart grace"

        if not wrapper.isRunning():
            return "crashed", "enabled but not running"

        comms = [d.lastSuccessfulComm for d in devs if d.lastSuccessfulComm is not None]
        if not comms:
            return "ok", "no comm timestamps to assess"
        newest  = max(comms)
        age_min = (now - newest).total_seconds() / 60.0
        stale   = float(policy.get("stale_minutes", self.watchdog_discovered_stale))
        if age_min > stale:
            return "wedged", (f"newest of {len(devs)} device(s) last comm "
                              f"{age_min:.0f}m ago (threshold {stale:.0f}m)")
        return "ok", f"newest comm {age_min:.0f}m ago"

    def _maybe_restart_plugin(self, pid, policy, verdict, reason, now):
        label        = self._plugin_label(pid)
        rec          = self._restart_record(pid, now)
        cooldown_min = float(policy.get("cooldown_minutes", 30))
        max_per_day  = int(policy.get("max_per_day", 3))
        last         = self._last_restart_dt(pid)

        if last and (now - last).total_seconds() < cooldown_min * 60:
            if self.debug:
                mins = (now - last).total_seconds() / 60.0
                log(f"Watchdog: {label} {verdict} but restarted {mins:.0f}m ago "
                    f"(cooldown {cooldown_min:.0f}m) — skipping")
            return

        if rec["restarts_today"] >= max_per_day:
            if not rec.get("cap_alerted"):
                rec["cap_alerted"] = True
                msg = (f"{label} still {verdict} after {rec['restarts_today']} restart(s) today "
                       f"(daily cap {max_per_day}). Needs manual attention. {reason}")
                log(msg, level="ERROR")
                self._send_pushover(f"Watchdog: {label} needs attention", msg, priority="1")
            return

        if self.watchdog_dry_run:
            log(f"[DRY RUN] Watchdog WOULD restart {label} — {verdict}: {reason}", level="WARNING")
            self._send_pushover(f"[DRY RUN] Watchdog: {label}",
                                f"Would restart ({verdict}): {reason}", priority="0")
            return

        log(f"Watchdog restarting {label} — {verdict}: {reason}", level="WARNING")
        try:
            try:
                indigo.server.getPlugin(pid).restart(waitUntilDone=False)
            except TypeError:
                indigo.server.getPlugin(pid).restart()
        except Exception as e:
            log(f"Watchdog: restart of {label} FAILED: {e}", level="ERROR")
            self._send_pushover(f"Watchdog: {label} restart FAILED", str(e), priority="1")
            return

        rec["last_restart"]   = now.isoformat()
        rec["restarts_today"] = rec["restarts_today"] + 1
        rec["cap_alerted"]    = False
        log(f"Watchdog: {label} restart issued (#{rec['restarts_today']} today)")
        self._send_pushover(f"Watchdog restarted {label}",
                            f"{verdict}: {reason}\nRestart #{rec['restarts_today']} today.", priority="0")

    # ── watchdog state helpers ────────────────────────────────────────────────

    def _restart_record(self, pid, now):
        rec   = self.restart_state.get(pid)
        today = now.strftime("%Y-%m-%d")
        if rec is None:
            rec = {"last_restart": None, "restarts_today": 0, "day": today, "cap_alerted": False}
            self.restart_state[pid] = rec
        return rec

    def _roll_restart_day(self, now):
        today = now.strftime("%Y-%m-%d")
        for rec in self.restart_state.values():
            if rec.get("day") != today:
                rec["day"]            = today
                rec["restarts_today"] = 0
                rec["cap_alerted"]    = False

    def _last_restart_dt(self, pid):
        rec = self.restart_state.get(pid)
        if not rec or not rec.get("last_restart"):
            return None
        try:
            return datetime.fromisoformat(rec["last_restart"])
        except Exception:
            return None

    def _plugin_label(self, pid):
        try:
            name = indigo.server.getPlugin(pid).pluginDisplayName
            if name:
                return name
        except Exception:
            pass
        return pid

    def _persist_watchdog_state(self):
        try:
            self.pluginPrefs["watchdog_state_json"] = json.dumps(self.restart_state)
            indigo.server.savePluginPrefs()
        except Exception as e:
            log(f"Watchdog: failed to persist restart state: {e}", level="ERROR")

    def _restore_watchdog_state(self):
        try:
            raw = self.pluginPrefs.get("watchdog_state_json", "{}")
            self.restart_state = json.loads(raw) or {}
        except Exception as e:
            log(f"Watchdog: could not restore restart state: {e}", level="WARNING")
            self.restart_state = {}

    # ------------------------------------------------------------------
    # Alert state persistence (device-level scan)
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

    # ── watchdog menus ─────────────────────────────────────────────────────────

    def menuRunWatchdogNow(self, valuesDict=None, typeId=None):
        log("Manual watchdog check triggered")
        self._load_watchdog_config()
        self._run_plugin_watchdog()
        return True

    def menuShowWatchdogStatus(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion)
        self._load_watchdog_config()
        now = datetime.now()
        self._roll_restart_day(now)

        plugin_devices: dict = {}
        for dev in indigo.devices:
            if dev.enabled and dev.configured:
                plugin_devices.setdefault(dev.pluginId, []).append(dev)
        candidates = self._discover_candidates(plugin_devices)

        mode  = "DRY RUN" if self.watchdog_dry_run else "LIVE"
        state = "enabled" if self.watchdog_enabled else "DISABLED"
        log(f"--- Plugin Watchdog ({state}, {mode}, auto-discover) — {len(candidates)} plugin(s) watched ---")
        for pid in sorted(candidates):
            policy          = candidates[pid]
            devs            = plugin_devices.get(pid, [])
            verdict, reason = self._assess_plugin_health(pid, policy, devs, now)
            src             = "tuned" if pid in self.watchdog_overrides else "auto"
            rec             = self.restart_state.get(pid, {})
            extra           = ""
            if rec.get("last_restart"):
                extra = f" | last restart {rec['last_restart']}, {rec.get('restarts_today', 0)} today"
            lvl = "WARNING" if verdict in ("crashed", "wedged") else "INFO"
            log(f"  {self._plugin_label(pid)}: {verdict} [{src} {policy.get('stale_minutes')}m] "
                f"({reason}){extra}", level=lvl)
        log(f"--- {len(self.watchdog_exclude)} excluded | config: {WATCHDOG_CONFIG_FILE} ---")
        return True

    def menuResetRestartCounters(self, valuesDict=None, typeId=None):
        self.restart_state = {}
        self._persist_watchdog_state()
        log("Watchdog: restart counters and cooldowns cleared.")
        return True

    def menuToggleDryRun(self, valuesDict=None, typeId=None):
        self.watchdog_dry_run = not self.watchdog_dry_run
        self.pluginPrefs["watchdogDryRun"] = self.watchdog_dry_run
        indigo.server.savePluginPrefs()
        log(f"Watchdog dry-run -> {'ON (no real restarts)' if self.watchdog_dry_run else 'OFF (LIVE restarts)'}",
            level="WARNING")
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
                ("Watchdog:",      f"{'ON' if self.watchdog_enabled else 'OFF'} "
                                   f"({'dry-run' if self.watchdog_dry_run else 'LIVE'}, auto-discover)"),
                ("Watchdog tuned:", f"{len(self.watchdog_overrides)} plugin(s)"),
                ("Watchdog excluded:", f"{len(self.watchdog_exclude)} plugin(s)"),
                ("Watchdog config:",  WATCHDOG_CONFIG_FILE),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion} | "
                              f"{len(self.alerted)} outstanding alert(s) | "
                              f"{len(self.excluded_names)} excluded | "
                              f"watchdog {'ON' if self.watchdog_enabled else 'OFF'}")
