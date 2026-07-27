#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_quiet_devices.py
# Description: Contract tests for the per-device quiet threshold — parsing,
#              resolution, and how it lands on each of the three check paths.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import json

from conftest import FakeDevice

Z2M     = "com.clives.indigoplugin.z2mbridge"
ZWAVE   = "com.perceptiveautomation.indigoplugin.zwave"
ECOWITT = "com.clives.indigoplugin.ecowitt"


def write_quiet(plugin_mod, entries):
    with open(plugin_mod.QUIET_DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump({"quiet_devices": entries}, f)


# ---------------------------------------------------------------- parsing

def test_parses_id_and_name_entries_into_separate_maps(plugin_mod):
    by_id, by_name, problems = plugin_mod.parse_quiet_devices({"quiet_devices": [
        {"id": 42, "hours": 240},
        {"name": "Coat Cupboard", "hours": 336},
    ]})
    assert by_id == {42: 240.0}
    assert by_name == {"coat cupboard": 336.0}
    assert problems == []


def test_never_parses_to_none_not_a_number(plugin_mod):
    by_id, _, problems = plugin_mod.parse_quiet_devices({"quiet_devices": [
        {"id": 42, "hours": "never"},
    ]})
    assert by_id == {42: None}
    assert problems == []


def test_name_is_lowercased_so_matching_is_case_insensitive(plugin_mod):
    _, by_name, _ = plugin_mod.parse_quiet_devices({"quiet_devices": [
        {"name": "  Bathroom CUPBOARD Sensor  ", "hours": 240},
    ]})
    assert by_name == {"bathroom cupboard sensor": 240.0}


def test_one_bad_entry_is_skipped_and_the_rest_still_load(plugin_mod):
    """The whole point of collecting problems rather than raising: a single bad
    hand-edit must not silently disable the exemption for every other device."""
    by_id, by_name, problems = plugin_mod.parse_quiet_devices({"quiet_devices": [
        {"id": 1, "hours": 240},
        {"id": 2, "hours": "abc"},          # unparseable
        {"id": "not-a-number", "hours": 10},
        {"hours": 10},                       # neither id nor name
        "just a string",                     # not an object at all
        {"id": 3, "hours": -5},              # negative
        {"name": "Good One", "hours": 48},
    ]})
    assert by_id == {1: 240.0}
    assert by_name == {"good one": 48.0}
    assert len(problems) == 5


def test_missing_or_empty_document_yields_empty_maps(plugin_mod):
    for doc in ({}, {"quiet_devices": []}, {"quiet_devices": None}):
        assert plugin_mod.parse_quiet_devices(doc) == ({}, {}, [])


# ------------------------------------------------------------- resolution

def test_id_match_wins_over_name(plugin_mod):
    hours, overridden = plugin_mod.resolve_quiet_hours(
        7, "Hall Sensor", 12, {7: 240.0}, {"hall sensor": 999.0})
    assert (hours, overridden) == (240.0, True)


def test_a_device_named_like_an_id_does_not_pick_up_the_id_entry(plugin_mod):
    """The collision the two-map design exists to make impossible: device 999
    is NOT the device named "42", even though an id entry for 42 exists."""
    hours, overridden = plugin_mod.resolve_quiet_hours(
        999, "42", 12, {42: 240.0}, {})
    assert (hours, overridden) == (12, False)


def test_no_entry_returns_the_default_unchanged(plugin_mod):
    assert plugin_mod.resolve_quiet_hours(1, "Nothing", 12, {}, {}) == (12, False)


def test_a_quiet_threshold_may_be_TIGHTER_than_the_default(plugin_mod):
    hours, overridden = plugin_mod.resolve_quiet_hours(1, "x", 12, {1: 2.0}, {})
    assert (hours, overridden) == (2.0, True)


# --------------------------------------------------------- z2m check path

def test_quiet_z2m_device_is_not_offline_inside_its_window(plugin_mod, plugin):
    dev = FakeDevice(1035480788, "Bathroom Cupboard", Z2M,
                     states={"availability": "online"}, hours_since_comm=56)
    plugin.quiet_by_id = {1035480788: 240.0}
    assert plugin._check_z2m(dev) == (False, "")


def test_quiet_z2m_device_still_alerts_once_past_its_own_window(plugin_mod, plugin):
    dev = FakeDevice(1, "Cupboard", Z2M,
                     states={"availability": "online"}, hours_since_comm=241)
    plugin.quiet_by_id = {1: 240.0}
    offline, reason = plugin._check_z2m(dev)
    assert offline
    assert "threshold 240h" in reason and "quiet device" in reason


def test_quiet_z2m_device_below_its_window_names_the_overridden_threshold(plugin_mod, plugin):
    dev = FakeDevice(1, "Cupboard", Z2M,
                     states={"availability": "online"}, hours_since_comm=239)
    plugin.quiet_by_id = {1: 240.0}
    assert plugin._check_z2m(dev) == (False, "")


def test_a_normal_z2m_device_is_unaffected(plugin_mod, plugin):
    dev = FakeDevice(2, "Normal", Z2M,
                     states={"availability": "online"}, hours_since_comm=13)
    offline, reason = plugin._check_z2m(dev)
    assert offline
    assert "threshold 12h" in reason and "quiet device" not in reason


def test_never_means_silence_never_alerts(plugin_mod, plugin):
    dev = FakeDevice(1, "Cupboard", Z2M,
                     states={"availability": "online"}, hours_since_comm=5000)
    plugin.quiet_by_id = {1: None}
    assert plugin._check_z2m(dev) == (False, "")


def test_never_does_NOT_suppress_a_reported_fault(plugin_mod, plugin):
    """availability=offline is z2m actively reporting a fault, not us inferring
    one from silence. Quiet exempts silence only."""
    dev = FakeDevice(1, "Cupboard", Z2M,
                     states={"availability": "offline"}, hours_since_comm=5000)
    plugin.quiet_by_id = {1: None}
    assert plugin._check_z2m(dev) == (True, "availability=offline")


# ------------------------------------------------- Z-Wave battery path

def test_quiet_zwave_battery_device_is_not_offline_inside_its_window(plugin_mod, plugin):
    dev = FakeDevice(783402018, "Coat Cupboard", ZWAVE,
                     hours_since_comm=47, battery=100)
    plugin.quiet_by_id = {783402018: 336.0}
    offline, _ = plugin._check_zwave(dev)
    assert not offline


def test_quiet_zwave_battery_device_alerts_past_its_window(plugin_mod, plugin):
    dev = FakeDevice(1, "Coat Cupboard", ZWAVE, hours_since_comm=400, battery=100)
    plugin.quiet_by_id = {1: 336.0}
    offline, reason = plugin._check_zwave(dev)
    assert offline
    assert "threshold 336h" in reason and "quiet device" in reason


def test_never_communicated_still_alerts_on_a_finite_quiet_threshold(plugin_mod, plugin):
    """A node that has never once reported is a pairing fault, not quietness."""
    dev = FakeDevice(1, "Coat Cupboard", ZWAVE, hours_since_comm=None, battery=100)
    plugin.quiet_by_id = {1: 336.0}
    offline, reason = plugin._check_zwave(dev)
    assert offline and "never communicated" in reason


def test_never_communicated_is_silent_under_never(plugin_mod, plugin):
    dev = FakeDevice(1, "Coat Cupboard", ZWAVE, hours_since_comm=None, battery=100)
    plugin.quiet_by_id = {1: None}
    assert plugin._check_zwave(dev) == (False, "")


def test_quiet_does_not_suppress_zwave_errorState(plugin_mod, plugin):
    dev = FakeDevice(1, "Coat Cupboard", ZWAVE, hours_since_comm=1,
                     battery=100, error_state="no ack")
    plugin.quiet_by_id = {1: None}
    offline, reason = plugin._check_zwave(dev)
    assert offline and "errorState" in reason


# -------------------------------------------------------- Ecowitt path

def test_quiet_ecowitt_device_is_not_offline_inside_its_window(plugin_mod, plugin):
    dev = FakeDevice(1, "Multi-Channel", ECOWITT, hours_since_changed=56)
    plugin.quiet_by_id = {1: 240.0}
    offline, _ = plugin._check_ecowitt(dev)
    assert not offline


def test_quiet_ecowitt_device_alerts_past_its_window(plugin_mod, plugin):
    dev = FakeDevice(1, "Multi-Channel", ECOWITT, hours_since_changed=300)
    plugin.quiet_by_id = {1: 240.0}
    offline, reason = plugin._check_ecowitt(dev)
    assert offline and "threshold 240h" in reason


# ---------------------------------------------- shelly path is untouched

def test_quiet_does_not_suppress_a_shelly_deviceOnline_fault(plugin_mod, plugin):
    dev = FakeDevice(1, "Plug", "com.clives.indigoplugin.shellydirect",
                     states={"deviceOnline": False})
    plugin.quiet_by_id = {1: None}
    offline, _ = plugin._check_shelly(dev)
    assert offline


# --------------------------------------------------------- file loading

def test_load_seeds_an_empty_starter_file_when_absent(plugin_mod, plugin):
    """Ships EMPTY with a worked example — real device ids would be a paint-in."""
    with open(plugin_mod.QUIET_DEVICES_FILE, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["quiet_devices"] == []
    assert doc["_example"]                       # the shape is documented
    assert plugin.quiet_by_id == {} and plugin.quiet_by_name == {}


def test_load_reads_entries_and_reports_bad_ones(plugin_mod, plugin):
    write_quiet(plugin_mod, [{"id": 5, "hours": 100}, {"id": 6, "hours": "nope"}])
    plugin._load_quiet_devices()
    assert plugin.quiet_by_id == {5: 100.0}
    warnings = plugin_mod.indigo.server.messages_at(30)   # logging.WARNING
    assert any("skipped a bad entry" in m for m in warnings)


def test_load_fails_open_on_a_corrupt_file(plugin_mod, plugin):
    """No overrides means every device is judged normally — a broken file costs
    noise, never a missed outage."""
    with open(plugin_mod.QUIET_DEVICES_FILE, "w", encoding="utf-8") as f:
        f.write("{not json")
    plugin.quiet_by_id = {1: 240.0}
    plugin._load_quiet_devices()
    assert plugin.quiet_by_id == {} and plugin.quiet_by_name == {}


def test_hours_since_accepts_an_injected_clock(plugin_mod, plugin):
    from datetime import datetime, timedelta
    now = datetime(2026, 7, 27, 12, 0, 0)
    assert plugin._hours_since(now - timedelta(hours=6), now=now) == 6.0
