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
