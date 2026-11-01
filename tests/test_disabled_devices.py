#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_disabled_devices.py
# Description: 2.14.1. A watched device that is disabled in Indigo is not checked, but
#              no longer drops out in silence: its latch is cleared, the change is
#              logged once each way, and the first scan lists the disabled devices.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

from conftest import FakeDevice

Z2M = "com.clives.indigoplugin.z2mbridge"


def dead(dev_id=1, name="Dead Sensor", enabled=True):
    # battery= so it is reported in one scan, without a direct read first.
    return FakeDevice(dev_id, name, Z2M, battery=50, enabled=enabled,
                      states={"availability": "online"}, hours_since_comm=100)


def lines(indigo_mod, text):
    return [m for m, _ in indigo_mod.server.lines if text in m]


def test_disabling_a_reported_device_clears_its_latch(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = dead()
    plugin._run_scan()
    assert 1 in plugin.alerted
    indigo_mod.devices[1].enabled = False
    plugin._run_scan()
    assert 1 not in plugin.alerted
    assert lines(indigo_mod, "Cleared alert for now-disabled device Dead Sensor")


def test_re_enabled_still_dead_is_reported_again(plugin_mod, indigo_mod, plugin, pushover):
    """The bug: the old latch outlived the disable, so this never alerted again."""
    indigo_mod.devices[1] = dead()
    plugin._run_scan()
    indigo_mod.devices[1].enabled = False
    plugin._run_scan()
    indigo_mod.devices[1].enabled = True
    plugin._run_scan()
    offline = [p for _, p in pushover.sent if "offline" in p["msgTitle"]]
    assert len(offline) == 2


def test_disabling_is_logged_once(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = dead()
    plugin._run_scan()
    indigo_mod.devices[1].enabled = False
    for _ in range(3):
        plugin._run_scan()
    assert len(lines(indigo_mod, "has been disabled in Indigo")) == 1


def test_re_enabling_is_logged(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = dead()
    plugin._run_scan()
    indigo_mod.devices[1].enabled = False
    plugin._run_scan()
    indigo_mod.devices[1].enabled = True
    plugin._run_scan()
    plugin._run_scan()
    assert len(lines(indigo_mod, "has been enabled again")) == 1


def test_first_scan_lists_disabled_devices_once(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = dead(1, "Garage Plug", enabled=False)
    indigo_mod.devices[2] = dead(2, "Attic Sensor", enabled=False)
    plugin._run_scan()
    plugin._run_scan()
    summary = lines(indigo_mod, "watched device(s) are disabled")
    assert len(summary) == 1
    assert "Attic Sensor, Garage Plug" in summary[0]
    # Already disabled at start: the summary covers it, no per-device warning too.
    assert lines(indigo_mod, "has been disabled in Indigo") == []


def test_unwatched_and_excluded_devices_are_not_mentioned(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = FakeDevice(1, "Virtual Switch", "com.example.virtual", enabled=False)
    indigo_mod.devices[2] = dead(2, "Ignored Plug", enabled=False)
    plugin.excluded_names = {"ignored plug"}
    plugin._load_exclusions = lambda: None
    plugin._run_scan()
    assert lines(indigo_mod, "disabled") == []


def test_a_disabled_device_is_not_alerted(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = dead(enabled=False)
    plugin._run_scan()
    assert pushover.sent == [] and plugin.alerted == {}
