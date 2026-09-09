#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_offline_tolerance.py
# Description: Contract tests for the v2.4.0 per-device away tolerance.
#
#              The gap it fills: a plug switched off at the wall between uses is
#              away by design, so an exclusion was the only option — and an
#              exclusion never alerts, which is how a genuinely dead tumble-dryer
#              plug sat unnoticed for five days (09-08-2026). The quiet-devices
#              'hours' knob could not help: it relaxes SILENCE, while a Shelly
#              that is off reports deviceOnline=False, a hard fault that alerts
#              whatever the silence threshold says.
#
#              'offline_hours' says how long a device may be OUT OF CONTACT
#              before it is reported. The tests below pin the three properties
#              that make it trustworthy rather than merely quiet:
#                * it expires — two weeks away IS reported;
#                * the clock is lastSuccessfulComm, so a plugin restart cannot
#                  hand a dead device a fresh grace period for ever;
#                * a device that has never communicated is reported at once.
# Author:      CliveS & Claude Opus 5
# Date:        10-08-2026
# Version:     1.0

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


# ── the pure parser / resolver ───────────────────────────────────────────────

def test_entry_without_offline_hours_is_absent_from_both_maps(plugin_mod):
    """Silence about a device must leave the original behaviour untouched."""
    by_id, by_name, problems = plugin_mod.parse_offline_tolerance(
        {"quiet_devices": [{"id": 1, "name": "Quiet Sensor", "hours": 240}]})

    assert by_id == {} and by_name == {}
    assert problems == []


def test_offline_hours_parsed_by_id_and_by_name(plugin_mod):
    by_id, by_name, problems = plugin_mod.parse_offline_tolerance({"quiet_devices": [
        {"id": 42, "name": "Washer", "offline_hours": 336},
        {"name": "Dryer", "offline_hours": 168},
    ]})

    assert by_id == {42: 336.0}
    assert by_name == {"dryer": 168.0}
    assert problems == []


def test_named_entry_with_an_id_is_matched_by_id_only(plugin_mod):
    """Mirrors parse_quiet_devices: an id is the more specific statement.

    A device NAMED like a number must not be reachable through the id map.
    """
    by_id, by_name, _ = plugin_mod.parse_offline_tolerance(
        {"quiet_devices": [{"id": 42, "name": "Washer", "offline_hours": 336}]})

    assert 42 in by_id
    assert "washer" not in by_name


def test_never_means_tolerate_indefinitely(plugin_mod):
    by_id, _, problems = plugin_mod.parse_offline_tolerance(
        {"quiet_devices": [{"id": 7, "offline_hours": "never"}]})

    assert by_id == {7: None}
    assert problems == []


def test_one_bad_entry_is_reported_and_the_rest_still_load(plugin_mod):
    by_id, _, problems = plugin_mod.parse_offline_tolerance({"quiet_devices": [
        {"id": 1, "offline_hours": "a fortnight"},
        {"id": 2, "offline_hours": 336},
    ]})

    assert by_id == {2: 336.0}, "a bad hand-edit must not disable the others"
    assert len(problems) == 1 and "offline_hours" in problems[0]


def test_unconfigured_device_gets_no_tolerance(plugin_mod):
    hours, configured = plugin_mod.resolve_offline_tolerance(99, "Anything", {}, {})

    assert configured is False
    assert hours == 0.0, "no entry must mean: report it the moment it is away"


def test_id_wins_over_name(plugin_mod):
    hours, configured = plugin_mod.resolve_offline_tolerance(
        5, "Washer", {5: 336.0}, {"washer": 1.0})

    assert (hours, configured) == (336.0, True)


# ── one document through BOTH parsers ────────────────────────────────────────
# Added after a live restart at 09:45 on 10-08-2026 logged
#   "Quiet devices: skipped a bad entry — 'Washing Machine Monitor': bad 'hours'
#    value None"
# on a file that was entirely correct. Every test above passes each parser its own
# document, so nothing exercised the join, and 'hours' becoming optional was
# invisible to all of them. Testing each half is not testing the two together.

def test_offline_only_entry_is_not_reported_as_malformed(plugin_mod):
    """'hours' is optional now — an entry with only a tolerance is correct."""
    doc = {"quiet_devices": [
        {"id": 1220479210, "name": "Washing Machine Monitor", "offline_hours": 336},
    ]}
    q_id, q_name, q_problems = plugin_mod.parse_quiet_devices(doc)
    t_id, _, t_problems = plugin_mod.parse_offline_tolerance(doc)

    assert q_problems == [], "a tolerance-only entry must load without complaint"
    assert q_id == {} and q_name == {}, "and must not become a silence override"
    assert t_id == {1220479210: 336.0}
    assert t_problems == []


def test_entry_setting_neither_key_is_reported(plugin_mod):
    """It does nothing at all, so silence would be the wrong answer."""
    _, _, problems = plugin_mod.parse_quiet_devices(
        {"quiet_devices": [{"id": 5, "name": "Pointless", "note": "no threshold"}]})

    assert len(problems) == 1 and "neither" in problems[0]


def test_an_entry_may_set_both_knobs(plugin_mod):
    doc = {"quiet_devices": [
        {"id": 9, "name": "Both", "hours": 240, "offline_hours": 336},
    ]}
    q_id, _, q_problems = plugin_mod.parse_quiet_devices(doc)
    t_id, _, t_problems = plugin_mod.parse_offline_tolerance(doc)

    assert q_id == {9: 240.0} and t_id == {9: 336.0}
    assert q_problems == [] and t_problems == []


def test_never_still_loads_as_a_silence_override(plugin_mod):
    """The new absent-hours guard reads the RAW value, so "never" must survive it."""
    q_id, _, problems = plugin_mod.parse_quiet_devices(
        {"quiet_devices": [{"id": 3, "hours": "never"}]})

    assert q_id == {3: None}
    assert problems == []


def test_the_live_file_loads_without_problems(plugin_mod):
    """The real document, as it stands on disk, must produce no warnings.

    A unit test over a hand-written fixture cannot catch a file that has drifted
    from what the parser expects — which is precisely how the 09:45 warning got
    out. Skipped rather than failed when the file is absent, so the suite still
    runs on any other machine.
    """
    import json
    import os
    path = os.path.expanduser(
        "~/Documents/Indigo/DeviceHealthMonitor/quiet_devices.json")
    if not os.path.exists(path):
        pytest.skip("no live quiet_devices.json on this machine")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    _, _, q_problems = plugin_mod.parse_quiet_devices(doc)
    _, _, t_problems = plugin_mod.parse_offline_tolerance(doc)

    assert q_problems == [], f"live file reports quiet problems: {q_problems}"
    assert t_problems == [], f"live file reports tolerance problems: {t_problems}"


# ── the applied rule ─────────────────────────────────────────────────────────

class _Dev:
    def __init__(self, dev_id=1, name="Washing Machine Plug", away_hours=1.0):
        self.id   = dev_id
        self.name = name
        self.lastSuccessfulComm = (
            None if away_hours is None
            else datetime.now() - timedelta(hours=away_hours)
        )


@pytest.fixture
def host(plugin_mod):
    """A bare plugin instance carrying just the tolerance maps and the helper."""
    p = plugin_mod.Plugin.__new__(plugin_mod.Plugin)
    p.offline_tol_by_id   = {}
    p.offline_tol_by_name = {}
    return p


def test_no_tolerance_configured_reports_immediately(host):
    """The long-standing behaviour, unchanged for every device nobody configures."""
    offline, reason = host._apply_offline_tolerance(_Dev(away_hours=0.1),
                                                    "deviceOnline=False")

    assert offline is True
    assert reason == "deviceOnline=False"


def test_inside_the_tolerance_is_not_reported(host):
    host.offline_tol_by_id = {1: 336.0}
    offline, reason = host._apply_offline_tolerance(_Dev(away_hours=48),
                                                    "deviceOnline=False")

    assert offline is False
    assert reason == ""


def test_beyond_the_tolerance_is_reported_and_says_how_long(host):
    """The whole point: the grace period must EXPIRE, or this is an exclusion."""
    host.offline_tol_by_id = {1: 336.0}
    offline, reason = host._apply_offline_tolerance(_Dev(away_hours=400),
                                                    "deviceOnline=False")

    assert offline is True
    assert "away 400" in reason and "336" in reason


def test_clock_runs_from_last_comm_not_from_first_notice(host):
    """A restart must not hand a long-dead device a fresh grace period.

    Measuring from when WE first noticed would live in memory and reset on every
    plugin restart, so a device could sit inside a new window for ever and never
    be reported. lastSuccessfulComm cannot be reset by anything the plugin does.
    """
    host.offline_tol_by_id = {1: 24.0}
    fresh_process = _Dev(away_hours=120)   # noticed for the first time just now

    offline, reason = host._apply_offline_tolerance(fresh_process, "deviceOnline=False")

    assert offline is True, "the device has been away 120h, whatever this process saw"
    assert "away 120" in reason


def test_never_communicated_is_reported_however_long_the_tolerance(host):
    """No start point to measure from, and a pairing fault is not a plug at a wall."""
    host.offline_tol_by_id = {1: 336.0}
    offline, reason = host._apply_offline_tolerance(_Dev(away_hours=None),
                                                    "deviceOnline=False")

    assert offline is True
    assert "never communicated" in reason


def test_never_tolerance_suppresses_indefinitely(host):
    host.offline_tol_by_id = {1: None}
    offline, reason = host._apply_offline_tolerance(_Dev(away_hours=100000),
                                                    "deviceOnline=False")

    assert offline is False
    assert reason == ""


def test_tolerance_matches_by_name_when_no_id_given(host):
    host.offline_tol_by_name = {"washing machine plug": 336.0}
    offline, _ = host._apply_offline_tolerance(_Dev(dev_id=777, away_hours=48),
                                               "deviceOnline=False")

    assert offline is False


def test_a_configured_device_that_is_healthy_is_never_touched(host, plugin_mod):
    """_apply_offline_tolerance runs only on an offline verdict.

    Pinned because moving the call above that branch would make a healthy device
    depend on its own tolerance — the sort of rearrangement that reads harmless.
    """
    import inspect
    src = inspect.getsource(plugin_mod.Plugin._check_device_health)

    assert "if offline:" in src and "_apply_offline_tolerance" in src
    before, after = src.split("_apply_offline_tolerance", 1)
    assert "if offline:" in before, \
        "the tolerance must be applied only to an offline verdict"


# ── ESPHome: the away clock had to change, or the tolerance could never expire ──
# ESPHomeBridge was not watched at all until 09-09-2026. Adding it was not just a
# line in MONITORED_PLUGINS: it writes connected=False from inside its reconnect
# loop on EVERY failed attempt, and Indigo refreshes lastSuccessfulComm on any
# state write, so a node unreachable for hours reports a comm time of seconds
# ago. An away tolerance measured from that never expires — the device could
# never be reported, which is the very fault the change exists to fix.
# Measured 08-09-2026: dropped 21:06:27; at 21:08:02 lastSuccessfulComm was 30 s
# old while the node's own lastSeen stood frozen at 21:04:23.

ESPHOME = "com.clives.indigoplugin.esphomebridge"
SHELLY  = "com.clives.indigoplugin.shellydirect"


def test_esphome_away_is_measured_from_its_own_lastSeen(plugin_mod):
    comm = datetime(2026, 9, 8, 21, 7, 32)      # refreshed by the retry loop
    seen = datetime(2026, 9, 8, 21, 4, 23)      # the last real contact
    got = plugin_mod.Plugin.away_clock(ESPHOME, {"lastSeen": "2026-09-08T21:04:23"}, comm)
    assert got == seen, "the retry loop's comm time must not be the away clock"


def test_a_space_separated_timestamp_is_understood_too(plugin_mod):
    assert plugin_mod.Plugin.away_clock(
        ESPHOME, {"lastSeen": "2026-09-08 21:04:23"}, None) == datetime(2026, 9, 8, 21, 4, 23)


def test_every_other_protocol_keeps_lastSuccessfulComm(plugin_mod):
    """Scoped deliberately: z2m publishes a lastSeen too, and switching its
    clock unmeasured would change behaviour nobody asked about."""
    comm = datetime(2026, 9, 8, 21, 7, 32)
    assert plugin_mod.Plugin.away_clock(
        SHELLY, {"lastSeen": "2026-01-01T00:00:00"}, comm) == comm


def test_an_esphome_node_with_no_lastSeen_has_no_away_clock(plugin_mod):
    """None means "report it": falling back to the comm time would reinstate
    the tolerance that can never expire."""
    assert plugin_mod.Plugin.away_clock(ESPHOME, {}, datetime(2026, 9, 8, 21, 7)) is None


def test_an_unparseable_lastSeen_has_no_away_clock(plugin_mod):
    assert plugin_mod.Plugin.away_clock(
        ESPHOME, {"lastSeen": "yesterday"}, datetime(2026, 9, 8, 21, 7)) is None
    assert plugin_mod.Plugin.away_clock(
        ESPHOME, {"lastSeen": ""}, datetime(2026, 9, 8, 21, 7)) is None


# ── the check itself ─────────────────────────────────────────────────────────

class _EspDev:
    """Named apart from the _Dev already in this file: appending to a test
    module silently rebinds a helper for every test ABOVE it too, and this
    shadowing turned seven passing tolerance tests red."""
    def __init__(self, states, pid=ESPHOME):
        self.states, self.pluginId, self.id, self.name = states, pid, 1, "Freezer"


def test_a_connected_esphome_node_is_healthy(plugin_mod, plugin):
    assert plugin._check_esphome(_EspDev({"connected": True})) == (False, "")


def test_a_disconnected_esphome_node_is_offline(plugin_mod, plugin):
    offline, reason = plugin._check_esphome(_EspDev({"connected": False}))
    assert offline is True and "connected" in reason


def test_the_string_form_is_never_coerced(plugin_mod, plugin):
    """bool("Disconnected") is True — the value the check exists to catch."""
    for bad in ("false", "False", "no", "0", "offline", "Disconnected"):
        assert plugin._check_esphome(_EspDev({"connected": bad}))[0] is True, bad
    for good in ("true", "True", "online", "Connected"):
        assert plugin._check_esphome(_EspDev({"connected": good}))[0] is False, good


def test_a_node_that_says_nothing_is_assumed_well(plugin_mod, plugin):
    """Silence is not a fault here — an ESPHome sensor publishes on change, so
    a steady freezer load can be quiet for a long time and be perfectly well."""
    assert plugin._check_esphome(_EspDev({}))[0] is False


def test_esphome_is_in_the_watch_list(plugin_mod):
    assert plugin_mod.MONITORED_PLUGINS.get(ESPHOME) == "esphome"


# ── the wiring, not just the parts ───────────────────────────────────────────
# A mutation that listed esphome in MONITORED_PLUGINS and then never dispatched
# to _check_esphome survived the first sweep: every test above drives the check
# directly, so nothing exercised the path from the watch list to it. That is the
# one seam where "watched" and "actually checked" can come apart.

class _EspFullDev(_EspDev):
    def __init__(self, states, comm=None):
        super().__init__(states)
        self.lastSuccessfulComm = comm
        self.enabled = True


def test_a_disconnected_esphome_device_reaches_a_verdict(plugin_mod, plugin):
    offline, reason = plugin._check_device_health(_EspFullDev({"connected": False}))
    assert offline is True, "listed in MONITORED_PLUGINS but never dispatched"
    assert "connected" in reason


def test_a_connected_esphome_device_reaches_a_verdict(plugin_mod, plugin):
    offline, _ = plugin._check_device_health(_EspFullDev({"connected": True}))
    assert offline is False


def test_an_unwatched_plugin_still_returns_not_monitored(plugin_mod, plugin):
    dev = _EspFullDev({"connected": False})
    dev.pluginId = "com.example.somethingelse"
    assert plugin._check_device_health(dev) == (None, None)


def test_the_away_tolerance_reaches_an_esphome_device_through_the_dispatch(plugin_mod, plugin):
    """The freezer case end to end: away inside its tolerance is not reported,
    and the clock is lastSeen — the comm time here is deliberately fresh,
    because ESPHomeBridge's retry loop keeps refreshing it."""
    plugin.offline_tol_by_id = {1: 24.0}
    seen = datetime.now() - timedelta(hours=3)
    dev = _EspFullDev({"connected": False,
                       "lastSeen": seen.strftime("%Y-%m-%dT%H:%M:%S")},
                      comm=datetime.now())
    assert plugin._check_device_health(dev)[0] is False, "3h away, 24h tolerance"

    seen = datetime.now() - timedelta(hours=30)
    dev = _EspFullDev({"connected": False,
                       "lastSeen": seen.strftime("%Y-%m-%dT%H:%M:%S")},
                      comm=datetime.now())
    offline, reason = plugin._check_device_health(dev)
    assert offline is True, "30h away against a 24h tolerance must be reported"
    assert "away 30" in reason or "away 29" in reason, reason


# ── quiet mains Z-Wave nodes are POKED, never accused ────────────────────────
# Measured 09-09-2026, sorted by how long each had been quiet — healthy and dead
# interleave completely, so no silence threshold can separate them:
#     2191 h  En Suite Floor Heating Switch      HEALTHY (pings fine)
#     2192 h  En Suite Floor Heating Thermostat  DEAD
#     3196 h  Loft Repeater Dimmable Load        HEALTHY
#     4907 h  Garage Loft Repeater Smart Plug    HEALTHY
#     5545 h  HP Printer Power Plug              DEAD
#    15098 h  Bedroom 3 Repeater Smart Plug      DEAD
# A ping separates them perfectly, and it sets the errorState the check already
# trusts. Three devices had been dead 91, 231 and 629 days in total silence.

def test_a_node_quiet_past_the_threshold_is_probed(plugin_mod):
    assert plugin_mod.Plugin.zwave_probe_due(200.0, 6.0, None) is True


def test_a_node_inside_the_threshold_is_left_alone(plugin_mod):
    assert plugin_mod.Plugin.zwave_probe_due(5.9, 6.0, None) is False
    assert plugin_mod.Plugin.zwave_probe_due(6.0, 6.0, None) is False, "the bar is ABOVE it"


def test_a_recently_probed_node_is_not_probed_again(plugin_mod):
    """One probe per node per period — the point is to notice within hours,
    not to poll. The scan runs every ten minutes."""
    assert plugin_mod.Plugin.zwave_probe_due(5000.0, 6.0, 0.2) is False
    assert plugin_mod.Plugin.zwave_probe_due(5000.0, 6.0, 5.9) is False
    assert plugin_mod.Plugin.zwave_probe_due(5000.0, 6.0, 6.0) is True


def test_zero_or_none_turns_probing_off(plugin_mod):
    assert plugin_mod.Plugin.zwave_probe_due(5000.0, 0, None) is False
    assert plugin_mod.Plugin.zwave_probe_due(5000.0, None, None) is False


def test_unusable_numbers_never_probe(plugin_mod):
    assert plugin_mod.Plugin.zwave_probe_due("x", 6.0, None) is False
    assert plugin_mod.Plugin.zwave_probe_due(None, 6.0, None) is False
    assert plugin_mod.Plugin.zwave_probe_due(200.0, "x", None) is False


def test_an_unreadable_probe_time_probes_rather_than_never(plugin_mod):
    """Failing open: the cost of an extra frame is nothing, and the cost of
    never probing is a device dead for 629 days in silence."""
    assert plugin_mod.Plugin.zwave_probe_due(200.0, 6.0, "x") is True


# ── who gets probed ──────────────────────────────────────────────────────────

class _ZDev:
    def __init__(self, comm, err="", battery=None,
                 pid="com.perceptiveautomation.indigoplugin.zwave"):
        self.id, self.name, self.pluginId = 7, "Loft Repeater", pid
        self.lastSuccessfulComm, self.errorState = comm, err
        self.batteryLevel, self.states, self.enabled = battery, {}, True


def _host(plugin, hours=6.0):
    plugin.zwave_mains_hours = hours
    plugin._zwave_probed = {}
    return plugin


def test_a_quiet_mains_node_is_probed(plugin_mod, plugin):
    host = _host(plugin)
    assert host._probe_quiet_zwave(_ZDev(datetime.now() - timedelta(hours=200))) is True
    assert plugin_mod.indigo.device.status_requests == [7]


def test_a_node_already_in_error_is_not_probed(plugin_mod, plugin):
    """It is already condemned — a probe teaches nothing and adds traffic."""
    host = _host(plugin)
    assert host._probe_quiet_zwave(
        _ZDev(datetime.now() - timedelta(hours=200), err="no ack")) is False


def test_a_battery_node_is_never_probed(plugin_mod, plugin):
    """A sleeping node cannot answer a ping, so a failure would mean nothing."""
    host = _host(plugin)
    assert host._probe_quiet_zwave(
        _ZDev(datetime.now() - timedelta(hours=200), battery=80)) is False


def test_a_node_that_never_communicated_is_not_probed(plugin_mod, plugin):
    """No start point to measure from — that is a pairing fault, reported by
    its own rule rather than poked at."""
    host = _host(plugin)
    assert host._probe_quiet_zwave(_ZDev(None)) is False


def test_a_non_zwave_device_is_never_probed(plugin_mod, plugin):
    host = _host(plugin)
    assert host._probe_quiet_zwave(
        _ZDev(datetime.now() - timedelta(hours=200),
              pid="com.clives.indigoplugin.shellydirect")) is False


def test_the_probe_is_recorded_so_it_is_not_repeated(plugin_mod, plugin):
    host = _host(plugin)
    dev = _ZDev(datetime.now() - timedelta(hours=200))
    assert host._probe_quiet_zwave(dev) is True
    assert host._probe_quiet_zwave(dev) is False, "a 10-minute scan must not re-poke"
    assert plugin_mod.indigo.device.status_requests == [7]


def test_a_probe_that_raises_is_not_an_error_for_the_scan(plugin_mod, plugin):
    plugin_mod.indigo.device.raise_on_status = RuntimeError("controller busy")
    host = _host(plugin)
    assert host._probe_quiet_zwave(_ZDev(datetime.now() - timedelta(hours=200))) is False


# ── a node that ignores the probe is asked three times, then left ────────────
# Both Loft Repeater endpoints answered the very first probe round with
# `does not support status request command`, logged as a Z-Wave ERROR. It is
# LOGGED, not raised, so it cannot be caught, and supportsStatusRequest is True
# on both, so the capability flag cannot be trusted. Unchecked that is two
# permanent errors every period in a log Log_Error_Watch pages on — noise this
# plugin would have created for itself.

def test_a_probe_that_moved_the_comm_time_counts_as_answered(plugin_mod):
    t0, t1 = datetime(2026, 9, 9, 10), datetime(2026, 9, 9, 11)
    assert plugin_mod.Plugin.zwave_probe_strikes(2, t0, t1) == 0


def test_a_probe_that_changed_nothing_is_a_strike(plugin_mod):
    t0 = datetime(2026, 9, 9, 10)
    assert plugin_mod.Plugin.zwave_probe_strikes(0, t0, t0) == 1
    assert plugin_mod.Plugin.zwave_probe_strikes(2, t0, t0) == 3


def test_the_first_ever_probe_is_not_a_strike(plugin_mod):
    assert plugin_mod.Plugin.zwave_probe_strikes(0, None, datetime.now()) == 0
    # Both absent is the case that makes the `comm_at_probe is None` half of the
    # guard load-bearing: without it this returns a strike for a node that has
    # never been probed at all. A mutation sweep found nothing was testing it.
    assert plugin_mod.Plugin.zwave_probe_strikes(2, None, None) == 0


def test_an_unusable_strike_count_starts_again_at_one(plugin_mod):
    t0 = datetime(2026, 9, 9, 10)
    assert plugin_mod.Plugin.zwave_probe_strikes("x", t0, t0) == 1


def test_a_node_that_ignores_three_probes_is_not_probed_again(plugin_mod, plugin):
    host = _host(plugin)
    comm = datetime.now() - timedelta(hours=200)
    dev = _ZDev(comm)
    for expected in (True, False, False):
        # each round is a fresh period, and the device never replies
        host._zwave_probed[dev.id] = (
            host._zwave_probed[dev.id][0] - timedelta(hours=12),
            host._zwave_probed[dev.id][1],
            host._zwave_probed[dev.id][2]) if dev.id in host._zwave_probed else None
        if host._zwave_probed.get(dev.id) is None:
            host._zwave_probed.pop(dev.id, None)
        got = host._probe_quiet_zwave(dev)
        if expected:
            assert got is True
    assert len(plugin_mod.indigo.device.status_requests) == 3, \
        "asked three times"
    # a fourth period: it has ignored three, so it is left alone
    w, c, st = host._zwave_probed[dev.id]
    host._zwave_probed[dev.id] = (w - timedelta(hours=12), c, st)
    assert host._probe_quiet_zwave(dev) is False
    assert len(plugin_mod.indigo.device.status_requests) == 3, "and not a fourth time"


def test_a_node_that_starts_answering_is_probed_normally_again(plugin_mod, plugin):
    """Self-healing: a repeater that comes back must not stay written off."""
    host = _host(plugin)
    old_comm = datetime.now() - timedelta(hours=200)
    dev = _ZDev(old_comm)
    host._zwave_probed[dev.id] = (datetime.now() - timedelta(hours=12), old_comm, 3)
    assert host._probe_quiet_zwave(dev) is False, "written off while silent"
    dev.lastSuccessfulComm = datetime.now() - timedelta(hours=100)   # it spoke
    host._zwave_probed[dev.id] = (datetime.now() - timedelta(hours=12), old_comm, 3)
    assert host._probe_quiet_zwave(dev) is True, "it answered, so start again"


def test_a_device_that_says_it_cannot_be_asked_is_believed(plugin_mod, plugin):
    host = _host(plugin)
    dev = _ZDev(datetime.now() - timedelta(hours=200))
    dev.supportsStatusRequest = False
    assert host._probe_quiet_zwave(dev) is False
