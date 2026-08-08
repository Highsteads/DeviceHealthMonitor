#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Device Health Monitor — scans all physical devices for offline/stale
#              status and sends consolidated Pushover alerts, AND auto-discovers
#              comms plugins, restarting any that crash or wedge.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     2.3.2
#
# v2.3.2 (08-08-2026): REQUIRED Info.plist KEY. `CFBundleURLTypes` was PRESENT but
# EMPTY, so the plugin shipped without the support URL that becomes its
# "About" menu item — one of the SIX keys the official Developer's Guide lists as
# required. An empty array satisfies "key exists" while giving users nowhere to go,
# which is why an earlier sweep that only looked for a MISSING key passed it. Found
# by an estate check auditing the VALUE rather than the key's presence.
# No plugin logic changed.
#
# v2.3.1 (27-07-2026): a latched alert is now cleared when its device stops being
# scannable, so the outstanding-alert list can no longer accumulate entries that
# nothing is able to clear. Two routes, both found while verifying v2.3.0 live:
# * The device was DELETED. The scan only iterates devices that exist, so its
#   latch was unreachable. Four had built up, the oldest from 12-06-2026.
# * The device was EXCLUDED by hand-editing exclusions.json. The skip sits above
#   the recovery branch, so an existing latch could never clear. Both Z2M bridge
#   devices had been listed as outstanding since 12-06-2026. (The "Add Offline
#   Devices to Exclusions" menu item already cleared them; a hand-edit did not.)
# Live: 12 outstanding alerts fell to 5, all five genuinely offline.
#
# v2.3.0 (27-07-2026): QUIET DEVICES — a per-device staleness threshold, plus
# three fixes and this plugin's first test suite.
#
# * Some sensors are silent BY DESIGN. A cupboard presence sensor that reports
#   only when the door opens went 56 hours without a word, perfectly healthy,
#   and the 12-hour z2m default called it offline 17 times — once at 01:36. A
#   health monitor that cries wolf gets swiped away without being read, and then
#   a real outage looks exactly the same. Nothing in the plugin could reach an
#   individual device: WATCHDOG_OVERRIDES and WATCHDOG_DENYLIST are per-PLUGIN
#   and belong to the watchdog, and exclusions.json is all-or-nothing.
#   quiet_devices.json now gives a device its own threshold — by id or by name,
#   in hours, or "never". Deliberately a longer threshold rather than an
#   exclusion, so a flat battery still surfaces eventually. It is reloaded every
#   scan cycle, so a threshold can be tuned without a restart, and it never
#   suppresses a HARD fault: errorState, availability=offline and
#   deviceOnline=False all still alert. Ships EMPTY with a worked example —
#   seeding real device ids would paint in one person's install.
# * An alert that could not be DELIVERED no longer latches. _run_scan marked the
#   device "already alerted" ten lines before the Pushover was attempted, so an
#   outage was logged and then never notified, for good. Delivery now returns a
#   bool and the latch only happens on success. Same bug class as
#   WaterLeakMonitor v1.8.
# * watchdog_plugins.json no longer shadows the code. The file OVERLAYS the
#   built-in policy and was only ever written when absent, so the v2.1 EcoFlow
#   720->60 tightening and the v2.2 entry removal had never taken effect on any
#   install that already had the file. A schema marker plus a frozen v1 baseline
#   reconciles it once: an on-disk policy identical to the seed it came from is
#   dropped so current code wins, anything genuinely edited is kept, and the old
#   file is copied to .bak-v1 first.
# * Config coercion is guarded throughout. Every float()/int() was bare, so a
#   cleared numeric field would have stopped the plugin loading. The checkboxes
#   now use as_bool: Indigo re-serialises a saved checkbox as the STRING
#   "false", and bool("false") is True — one save of the Configure dialog would
#   have switched watchdog dry-run back ON and quietly disabled every real
#   restart. Both pref blocks now share one _apply_prefs, which is how they
#   would have drifted.
# * First test suite for this plugin.
#
# v2.2.2 (21-07-2026): shared plugin_utils.py refreshed to v1.3 — the
# estate-wide propagation of the four Appliance Monitor deep-review fixes.
# * install_timestamp_filter() is idempotent — a second call used to stack a
#   second filter, so every log line came out with two timestamps.
# * `import indigo` is soft, so the module imports outside the Indigo host and
#   can be exercised by offline tests.
# * A malformed log call keeps its arguments in the log instead of dropping
#   them, so a %-placeholder mismatch is visible.
# * New shared as_bool() — a pref re-serialised as the string "false" is
#   truthy, which is exactly the wrong answer.
# This bundle was still on plugin_utils v1.1 and had no timestamp filter at
# all — it now has the whole v1.3 surface.
#
# v2.2.1 (21-07-2026): LOG-LEVEL FIX. indigo.server.log(level=...) wants a Python
# logging INT — a STRING is silently ignored and the line logs as plain Info.
# The log() helper passed its level name straight through, so every WARNING and
# ERROR raised through it had been appearing as an ordinary Info line. Added
# _lvl() to map the name to a real level. Estate-wide sweep (38 files).
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
import shutil
import sys as _sys
from datetime import datetime

import indigo  # noqa — provided by Indigo runtime

_sys.path.insert(0, _os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None
try:
    from plugin_utils import as_bool
except ImportError:
    def as_bool(value, default=False):
        """Fallback for a bundled plugin_utils older than v1.3.

        Per-key import so a missing as_bool cannot also cost us the banner.
        """
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in ("true", "1", "yes", "on")

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
PLUGIN_VERSION = "2.3.1"

EXCLUSIONS_FILE = os.path.expanduser(
    "~/Documents/Indigo/DeviceHealthMonitor/exclusions.json"
)

# ---------------------------------------------------------------------------
# Quiet devices — per-device staleness thresholds.
# ---------------------------------------------------------------------------
# Some sensors are silent BY DESIGN. A cupboard presence sensor that only reports
# when the door opens goes days without a word and is perfectly healthy; against
# the 12-hour z2m default it was reported offline 17 times, once at 01:36. A health
# monitor that cries wolf gets swiped away without reading, and then a real outage
# looks exactly the same.
#
# Deliberately a longer THRESHOLD rather than an exclusion: a flat battery must
# still surface eventually. exclusions.json remains the way to ignore a device
# outright.
#
# Its own file, NOT a key inside exclusions.json: _save_exclusions rebuilds that
# document from a literal dict and writes it over the file, so anything colocated
# there is destroyed by the next "Add All Offline Devices to Exclusions" click.
QUIET_DEVICES_FILE = os.path.expanduser(
    "~/Documents/Indigo/DeviceHealthMonitor/quiet_devices.json"
)

# Ships EMPTY with a worked example. Seeding real device ids would paint in one
# person's install and mean nothing on anybody else's.
QUIET_DEVICES_EXAMPLE = [
    {"id": 123456789, "name": "Bathroom Cupboard Presence Sensor", "hours": 240,
     "note": "Example only — delete this and add your own. Reports just twice a "
             "week, so 10 days of silence is normal; a flat battery still alerts."},
]

_QUIET_BAD = object()   # distinct from None, which legitimately means "never"


def _quiet_hours(raw):
    """Coerce a quiet entry's 'hours': a non-negative number, or None for "never"."""
    if isinstance(raw, str) and raw.strip().lower() == "never":
        return None
    try:
        hours = float(raw)
    except (TypeError, ValueError):
        return _QUIET_BAD
    return hours if hours >= 0 else _QUIET_BAD


def parse_quiet_devices(data):
    """Parse the quiet-devices document into two lookup maps.

    Returns (by_id, by_name, problems). A value is float hours, or None meaning
    "never alert on silence".

    Never raises. One malformed entry is reported in `problems` and skipped while
    the rest of the list still loads — a single bad hand-edit must not silently
    disable the exemption for every other device.

    TWO SEPARATE MAPS, deliberately. JSON object keys are always strings, so a map
    keyed by device would leave "1035480788" ambiguous between an id and a name.
    Keying ints and lowercased strings apart makes the collision impossible: a
    device NAMED "1035480788" can only ever match through by_name.
    """
    by_id, by_name, problems = {}, {}, []
    for entry in (data.get("quiet_devices") or []):
        if not isinstance(entry, dict):
            problems.append(f"{entry!r} is not an object")
            continue
        label = entry.get("name") or entry.get("id")
        hours = _quiet_hours(entry.get("hours"))
        if hours is _QUIET_BAD:
            problems.append(f"{label!r}: bad 'hours' value {entry.get('hours')!r}")
            continue
        if entry.get("id") not in (None, ""):
            try:
                by_id[int(entry["id"])] = hours
            except (TypeError, ValueError):
                problems.append(f"{label!r}: bad 'id' value {entry['id']!r}")
            continue
        name = str(entry.get("name") or "").strip().lower()
        if name:
            by_name[name] = hours
        else:
            problems.append(f"{entry!r} has neither 'id' nor 'name'")
    return by_id, by_name, problems


def resolve_quiet_hours(dev_id, dev_name, default_hours, by_id, by_name):
    """Staleness threshold for one device: its quiet override, else the default.

    Id wins over name — naming a device by id is the more specific statement, and
    a name can be edited in the Indigo UI at any time.

    Returns (hours, overridden). hours is None when the device is set to "never",
    meaning never alert on silence. One source of truth for both the threshold and
    whether it was overridden, so the log text cannot drift from the decision.
    """
    if dev_id in by_id:
        return by_id[dev_id], True
    key = str(dev_name or "").strip().lower()
    if key in by_name:
        return by_name[key], True
    return default_hours, False

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

# The config file OVERLAYS the code and was only ever written when absent, so any
# threshold tuned in a later release never reached an install that already had the
# file. On this install that shadowed BOTH the v2.1 EcoFlow 720->60 tightening and
# the v2.2 entry removal — neither had ever been in effect. The schema marker plus
# the frozen v1 baseline below let us undo that once, without discarding real edits.
WATCHDOG_SCHEMA = 2

# The v2.0 overrides that seeded every pre-schema file. An on-disk policy identical
# to its entry here was never touched by anyone, so the current code default wins.
# DO NOT update this to track WATCHDOG_OVERRIDES — it is a historical record of what
# was written, and rewriting it would make real user edits look like untouched seeds.
WATCHDOG_V1_BASELINE = {
    "com.clives.indigoplugin.z2mbridge":                {"stale_minutes": 5,    "cooldown_minutes": 15, "max_per_day": 6, "enabled": True},
    "com.clives.indigoplugin.tasmotabridge":            {"stale_minutes": 8,    "cooldown_minutes": 15, "max_per_day": 6, "enabled": True},
    "com.clives.indigoplugin.esphomebridge":            {"stale_minutes": 10,   "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    "com.clives.indigoplugin.sigenergy-energy-manager": {"stale_minutes": 10,   "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    "com.clives.indigoplugin.mqttexplorerbridge":       {"stale_minutes": 10,   "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    "com.clives.indigoplugin.ecoflowcloud":             {"stale_minutes": 720,  "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "com.clives.indigoplugin.ecowitt":                  {"stale_minutes": 20,   "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "uk.co.clives.ramses.esp":                          {"stale_minutes": 180,  "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "com.clives.indigoplugin.shellydirect":             {"stale_minutes": 15,   "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
    "com.clives.indigoplugin.shellyg1":                 {"stale_minutes": 30,   "cooldown_minutes": 60, "max_per_day": 2, "enabled": True},
    "com.clives.indigoplugin.humaxaura":                {"stale_minutes": 1440, "cooldown_minutes": 60, "max_per_day": 2, "enabled": True},
}


def migrate_watchdog_config(data, v1_baseline):
    """Reconcile a pre-schema watchdog config against the baseline that seeded it.

    An on-disk policy EQUAL to its v1 baseline is an untouched default, so it is
    dropped and the current code default takes over. Anything that differs is a
    real edit and is kept, as is any plugin id we never shipped a default for.
    'exclude' and 'include' are preserved verbatim — that list is hand-curated.

    The one cost is that an edit which happens to match the old baseline exactly is
    reverted, which is harmless: that is precisely the case where the code default
    moving is the answer you wanted.

    Pure — plain dicts in, plain dicts out, so the riskiest change in this release
    is testable without breaking a live file.

    Returns (migrated_data, dropped_ids, kept_ids).
    """
    overrides    = dict(data.get("overrides") or {})
    dropped, kept = [], []
    for pid in sorted(overrides):
        baseline = v1_baseline.get(pid)
        if baseline is not None and overrides[pid] == baseline:
            dropped.append(pid)
        else:
            kept.append(pid)
    migrated = dict(data)
    migrated["overrides"] = {pid: overrides[pid] for pid in kept}
    migrated["schema"]    = WATCHDOG_SCHEMA
    return migrated, dropped, kept


import logging


_LOG_LEVELS = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR":   logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _lvl(level):
    """Map a level NAME to a Python logging int.

    indigo.server.log(level=...) wants an int. A STRING is silently ignored
    and the line logs as plain Info, which hid every WARNING and ERROR raised
    through log() until this was corrected (21-07-2026).
    """
    if isinstance(level, int):
        return level
    return _LOG_LEVELS.get(str(level).upper(), logging.INFO)


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=_lvl(level))


def _as_float(value, fallback):
    """Coerce a config value to float, returning fallback on blank/None/non-numeric.

    Indigo re-serialises every textfield as a STRING once a dialog has been saved,
    and a cleared field comes back as "". A bare float("") raises ValueError in
    __init__, which stops the plugin loading altogether. The fallback is coerced
    too, so a string default can never leak unconverted into arithmetic.
    """
    try:
        if value not in (None, ""):
            return float(value)
    except (TypeError, ValueError):
        pass
    try:
        return float(fallback)
    except (TypeError, ValueError):
        return fallback


def _as_int(value, fallback):
    """Coerce a config value to int, returning fallback on blank/None/non-numeric.
    The fallback is coerced too so a string default can't leak into arithmetic."""
    try:
        if value not in (None, ""):
            return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return int(fallback)
    except (TypeError, ValueError):
        return fallback


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self._apply_prefs(pluginPrefs)

        # device_id -> datetime first alerted
        self.alerted: dict[int, datetime] = {}
        self._restore_alerted()
        # Device ids whose alert we could not deliver — so a Pushover outage keeps
        # retrying instead of latching the device as "already alerted" (see _run_scan).
        self._undelivered: set[int] = set()

        # Exclusion list (set of lowercase device names) for the device-level scan
        self.excluded_names: set[str] = set()
        self._load_exclusions()

        # Quiet devices — per-device staleness overrides for sensors that are
        # silent BY DESIGN (a cupboard door opened twice a week).
        self.quiet_by_id: dict[int, float | None]   = {}
        self.quiet_by_name: dict[str, float | None] = {}
        self._load_quiet_devices()

        # pluginId -> {"last_restart": iso|None, "restarts_today": int, "day": str, "cap_alerted": bool}
        self.restart_state: dict = {}
        self._restore_watchdog_state()
        # Resolved config (seeded from code, overlaid by the editable JSON file)
        self.watchdog_overrides: dict          = {}
        self.watchdog_exclude: set             = set()
        self.watchdog_discovered_default: dict = {}
        self._load_watchdog_config()

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

    def _apply_prefs(self, values):
        """Read every preference into its attribute, guarded.

        One home for the lot, called from both __init__ and closedPrefsConfigUi —
        they used to carry the same nine lines twice, which is how a pref gets
        added to one and forgotten in the other.
        """
        self.debug                     = as_bool(values.get("showDebugInfo", False))
        self.scan_interval_sec         = _as_int(values.get("scanIntervalMinutes", 10), 10) * 60
        self.zwave_battery_hours       = _as_float(values.get("zwave_battery_hours", 24), 24)
        self.zwave_mains_hours         = _as_float(values.get("zwave_mains_hours", 6), 6)
        self.ecowitt_hours             = _as_float(values.get("ecowitt_hours", 24), 24)
        self.z2m_stale_hours           = _as_float(values.get("z2m_stale_hours", 12), 12)
        # Plugin watchdog (auto-discovering).
        # as_bool, not bool: Indigo re-serialises a saved checkbox as the STRING
        # "false", and bool("false") is True — which would silently switch dry-run
        # back ON and quietly disable every real restart.
        self.watchdog_enabled          = as_bool(values.get("watchdogEnabled", True), True)
        self.watchdog_dry_run          = as_bool(values.get("watchdogDryRun", True), True)
        self.watchdog_discovered_stale = _as_float(values.get("watchdogDefaultStaleMin", 60), 60)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self):
        log(f"{PLUGIN_NAME} v{PLUGIN_VERSION} started — {len(MONITORED_PLUGINS)} device protocols, "
            f"watchdog {'ON' if self.watchdog_enabled else 'OFF'} "
            f"({'dry-run' if self.watchdog_dry_run else 'LIVE'}, auto-discover, "
            f"{len(self.watchdog_exclude)} excluded), {len(self.excluded_names)} device exclusion(s), "
            f"{len(self.quiet_by_id) + len(self.quiet_by_name)} quiet device(s)")

    def shutdown(self):
        self._persist_alerted()
        self._persist_watchdog_state()
        log(f"{PLUGIN_NAME} shutting down")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self._apply_prefs(valuesDict)
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
                self._load_quiet_devices()    # same, so a quiet threshold can be tuned live
                self._run_scan()
                self._load_watchdog_config()  # reload each cycle too
                self._run_plugin_watchdog()
            except Exception as e:
                log(f"Cycle error: {e}", level="ERROR")
            self.sleep(self.scan_interval_sec)

    def _run_scan(self):
        now       = datetime.now()
        pending   = []   # [(dev_id, name, reason)] offline and not yet notified
        recovered = []

        for dev in indigo.devices:
            if not dev.enabled:
                continue
            if dev.name.lower() in self.excluded_names:
                # Excluding a device by hand-editing the file used to leave any
                # existing latch stuck for good — the skip happens before the
                # recovery branch below, so it could never be cleared. Two Z2M
                # bridge devices had been listed as outstanding since 12-Jun-2026.
                # (The "Add Offline Devices to Exclusions" menu already did this.)
                if self.alerted.pop(dev.id, None) is not None:
                    log(f"Cleared alert for now-excluded device {dev.name}")
                self._undelivered.discard(dev.id)
                continue

            is_offline, reason = self._check_device_health(dev)
            if is_offline is None:
                continue  # device type not monitored

            if is_offline:
                if dev.id in self.alerted:
                    continue                      # already notified for this outage
                # Log in full the first time. On a sustained delivery outage the
                # device stays in _undelivered and we stop repeating the line every
                # scan interval — _send_pushover's own WARNING is the heartbeat.
                if dev.id not in self._undelivered:
                    log(f"[OFFLINE] {dev.name}: {reason}", level="WARNING")
                pending.append((dev.id, dev.name, reason))
            else:
                # Clear an undelivered entry silently: it recovered before we ever
                # managed to tell anyone, so there is no alert to report recovery from.
                self._undelivered.discard(dev.id)
                if dev.id in self.alerted:
                    del self.alerted[dev.id]
                    recovered.append(dev.name)
                    log(f"[RECOVERED] {dev.name}")

        # A deleted device is never seen by the loop above, so its latch could
        # never be cleared and it sat in alerted_json for good — two devices
        # deleted on 27-Jul-2026 were still listed as outstanding alerts.
        for dev_id in [i for i in self.alerted if i not in indigo.devices]:
            del self.alerted[dev_id]
            self._undelivered.discard(dev_id)
            log(f"Cleared alert for deleted device {dev_id}")

        if pending:
            # Latch ONLY on a delivered alert. Latching inside the loop meant a
            # Pushover outage marked the device "already alerted", so the outage was
            # logged and never notified — the WaterLeakMonitor v1.8 bug class.
            if self._alert_pushover([(name, reason) for _, name, reason in pending]):
                for dev_id, _, _ in pending:
                    self.alerted[dev_id] = now
                    self._undelivered.discard(dev_id)
            else:
                for dev_id, _, _ in pending:
                    self._undelivered.add(dev_id)

        self._persist_alerted()

        if self.debug:
            log(f"Scan complete — {len(pending)} new offline, {len(recovered)} recovered, "
                f"{len(self.alerted)} total outstanding, {len(self._undelivered)} undelivered")

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
            thresh, quiet = self._threshold_for(dev, self.z2m_stale_hours)
            hours = self._hours_since(last)
            if thresh is not None and hours > thresh:
                note = " — quiet device" if quiet else ""
                return True, f"no comm for {hours:.1f}h (threshold {thresh:g}h{note})"
        # A quiet device is exempt from SILENCE, never from a fault the stack has
        # actively reported. z2m marking it offline is exactly that.
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
            thresh, quiet = self._threshold_for(dev, self.zwave_battery_hours)
            if last is None:
                # "Never communicated" IS an inference from silence, so a device set
                # to "never" must not trip it. With a finite threshold it still does:
                # a node that has never once reported is a genuine pairing fault.
                if thresh is None:
                    return False, ""
                return True, "battery device never communicated (lastSuccessfulComm=None)"
            if thresh is None:
                return False, ""
            hours = self._hours_since(last)
            note  = " — quiet device" if quiet else ""
            return hours > thresh, \
                f"battery device: last comm {hours:.1f}h ago (threshold {thresh:g}h{note})"
        # Mains device with no error — healthy (stale comm is normal for un-polled nodes).
        return False, ""

    def _check_ecowitt(self, dev):
        # NB this judges lastChanged, not lastSuccessfulComm — so it trips on an
        # UNCHANGED VALUE rather than on silence. A quiet override here therefore
        # relaxes a slightly different failure mode than on the other two paths.
        last = dev.lastChanged
        if last is None:
            return True, "lastChanged=None"
        thresh, quiet = self._threshold_for(dev, self.ecowitt_hours)
        if thresh is None:
            return False, ""
        hours = self._hours_since(last)
        note  = " — quiet device" if quiet else ""
        return hours > thresh, f"lastChanged {hours:.1f}h ago (threshold {thresh:g}h{note})"

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
    # Quiet devices (per-device staleness thresholds)
    # ------------------------------------------------------------------

    def _threshold_for(self, dev, default_hours):
        """(threshold_hours, overridden) for this device. None hours = never."""
        return resolve_quiet_hours(dev.id, dev.name, default_hours,
                                   self.quiet_by_id, self.quiet_by_name)

    def _load_quiet_devices(self):
        try:
            if not os.path.exists(QUIET_DEVICES_FILE):
                self.quiet_by_id, self.quiet_by_name = {}, {}
                self._write_quiet_devices()
                return
            with open(QUIET_DEVICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            by_id, by_name, problems = parse_quiet_devices(data)
            self.quiet_by_id, self.quiet_by_name = by_id, by_name
            for problem in problems:
                log(f"Quiet devices: skipped a bad entry — {problem}", level="WARNING")
            if self.debug:
                log(f"Loaded {len(by_id) + len(by_name)} quiet device(s) from file")
        except Exception as e:
            # Fail OPEN: with no overrides every device is judged on the normal
            # thresholds, so a broken file costs noise, never a missed outage.
            log(f"Failed to load quiet devices file: {e}", level="ERROR")
            self.quiet_by_id, self.quiet_by_name = {}, {}

    def _write_quiet_devices(self):
        """Seed the file once, when it is absent. Never rewritten afterwards —
        there is no code-side list to reconcile against, so a rewrite could only
        lose the user's own entries."""
        try:
            os.makedirs(os.path.dirname(QUIET_DEVICES_FILE), exist_ok=True)
            doc = {
                "_comment":  "Device Health Monitor — devices that are silent BY DESIGN.",
                "_comment2": "Each entry takes 'id' (preferred) or 'name', plus 'hours'. "
                             "'hours' replaces the protocol default staleness threshold for "
                             "that device only, and may be higher OR lower than the default. "
                             "Use \"never\" to never alert on silence at all.",
                "_comment3": "A HARD FAULT still alerts either way — errorState, "
                             "availability=offline, deviceOnline=False. To ignore a device "
                             "completely instead, list it in exclusions.json.",
                "_comment4": "Reloaded every scan cycle, so edits take effect without a "
                             "plugin restart. 'Show Quiet Devices' lists what is in force.",
                "_example":  QUIET_DEVICES_EXAMPLE,
                "quiet_devices": [],
            }
            with open(QUIET_DEVICES_FILE, "w", encoding="utf-8") as f:
                # ensure_ascii=False: this file exists to be hand-edited, and a
                # wall of — escapes in the guidance text helps nobody.
                json.dump(doc, f, indent=4, ensure_ascii=False)
            log(f"Quiet devices: wrote starter file to {QUIET_DEVICES_FILE}")
        except Exception as e:
            log(f"Quiet devices: failed to write starter file: {e}", level="ERROR")

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
        """Send one consolidated alert. Returns True only if it was DELIVERED.

        The caller latches on that bool, so this must never report success it
        did not achieve.
        """
        body  = "\n".join(f"- {name} ({reason})" for name, reason in offline_list)
        title = f"Device Health: {len(offline_list)} offline"
        if self._send_pushover(title, body, priority="0"):
            log(f"Pushover alert sent: {len(offline_list)} device(s) offline")
            return True
        log(f"NOT DELIVERED — {len(offline_list)} device(s) offline, retrying next scan",
            level="ERROR")
        return False

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
                if _as_int(data.get("schema", 0), 0) < WATCHDOG_SCHEMA:
                    data = self._migrate_watchdog_file(data)
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

    def _migrate_watchdog_file(self, data):
        """One-shot reconciliation of a pre-schema config file: back it up, rewrite it.

        Runs only while the file carries no (or an older) schema marker, so it never
        churns the file on the 10-minute reload — which would otherwise fight anyone
        editing it in a text editor.
        """
        migrated, dropped, kept = migrate_watchdog_config(data, WATCHDOG_V1_BASELINE)
        migrated.setdefault(
            "_comment4",
            "'overrides' now holds only YOUR edits — anything absent uses the plugin's "
            "current built-in default. 'Show Watchdog Status' lists the policy actually "
            "in force for every watched plugin.",
        )
        try:
            backup = f"{WATCHDOG_CONFIG_FILE}.bak-v1"
            if not os.path.exists(backup):
                shutil.copy2(WATCHDOG_CONFIG_FILE, backup)
            with open(WATCHDOG_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(migrated, f, indent=4)
            log(f"Watchdog: config migrated to schema {WATCHDOG_SCHEMA} — dropped {len(dropped)} "
                f"untouched default(s), kept {len(kept)} edit(s). Backup: {backup}")
            if dropped:
                log(f"Watchdog: current code defaults now apply to {', '.join(dropped)}")
        except Exception as e:
            # The reconciliation itself already succeeded in memory, so the right
            # policy applies this session even if we cannot persist it.
            log(f"Watchdog: could not rewrite config after migration ({e}) — "
                f"migrated policy applies for this session only", level="WARNING")
        return migrated

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
                # Stamp the schema on a fresh file so it is never put through the
                # one-shot v1 reconciliation on its next load.
                "schema":             WATCHDOG_SCHEMA,
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
    def _hours_since(dt, now=None):
        """Hours between dt and now. `now` is injectable so the threshold checks
        can be tested deterministically rather than against the wall clock."""
        return ((now or datetime.now()) - dt).total_seconds() / 3600.0

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

    @staticmethod
    def _quiet_label(hours):
        return "never alerts on silence" if hours is None else f"allowed {hours:g}h of silence"

    def menuShowQuietDevices(self, valuesDict=None, typeId=None):
        self._load_quiet_devices()
        total = len(self.quiet_by_id) + len(self.quiet_by_name)
        if not total:
            log(f"No quiet devices defined. Edit {QUIET_DEVICES_FILE} to give a device "
                f"that is silent by design a longer threshold of its own.")
            return True
        log(f"--- Quiet devices ({total}) --- file: {QUIET_DEVICES_FILE}")
        for dev_id, hours in sorted(self.quiet_by_id.items()):
            try:
                name = indigo.devices[dev_id].name
            except Exception:
                name = f"[no device with id {dev_id}]"
            log(f"  {name} — {self._quiet_label(hours)} (matched by id {dev_id})")
        for name, hours in sorted(self.quiet_by_name.items()):
            log(f"  {name} — {self._quiet_label(hours)} (matched by name)")
        log("--- a hard fault still alerts: errorState, availability=offline, deviceOnline=False ---")
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
                ("Quiet devices:", f"{len(self.quiet_by_id) + len(self.quiet_by_name)} device(s)"),
                ("Quiet file:",    QUIET_DEVICES_FILE),
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
