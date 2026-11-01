#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_last_seen.py
# Description: 2.14.2. parse_last_seen reads every lastSeen shape z2m and ESPHome can
#              write, and a value it still cannot read is warned about once per device
#              instead of silently switching off the device's silence check.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

from datetime import datetime, timedelta, timezone

import pytest

from conftest import FakeDevice

Z2M     = "com.clives.indigoplugin.z2mbridge"
LOCAL   = datetime(2026, 9, 18, 4, 22, 0)


@pytest.mark.parametrize("raw", [
    "2026-09-18T04:22:00",            # the two formats read before 2.14.2
    "2026-09-18 04:22:00",
    "2026-09-18T04:22:00.000",        # fractions of a second
    "2026-09-18 04:22:00.123456",
])
def test_plain_local_text(plugin_mod, raw):
    got = plugin_mod.parse_last_seen(raw)
    assert got.replace(microsecond=0) == LOCAL


def test_a_zoned_value_becomes_local_time(plugin_mod):
    """z2m's ISO_8601 option writes UTC with a 'Z'; ages are measured in local time."""
    utc = datetime(2026, 9, 18, 3, 22, 0, tzinfo=timezone.utc)
    want = utc.astimezone().replace(tzinfo=None)
    assert plugin_mod.parse_last_seen("2026-09-18T03:22:00.000Z") == want
    assert plugin_mod.parse_last_seen("2026-09-18T04:22:00+01:00") == want


@pytest.mark.parametrize("raw", [1789700520, 1789700520000, "1789700520000", 1789700520.5])
def test_epoch_seconds_or_milliseconds(plugin_mod, raw):
    got = plugin_mod.parse_last_seen(raw)
    assert abs((got - datetime.fromtimestamp(1789700520)).total_seconds()) < 1


@pytest.mark.parametrize("raw", [None, "", "yesterday", True, 0, "1999-01-01T00:00:00", "3000-01-01"])
def test_unreadable_or_absurd_is_none(plugin_mod, raw):
    assert plugin_mod.parse_last_seen(raw) is None


def z2m_dev(last_seen, dev_id=1, name="Hall Sensor"):
    dev = FakeDevice(dev_id, name, Z2M, battery=50, states={"availability": "online"},
                     hours_since_comm=0.1)
    dev.states["lastSeen"] = last_seen
    return dev


def test_a_milliseconds_value_now_drives_the_silence_check(plugin_mod, indigo_mod, plugin, pushover):
    """The fault: this shape gave no clock, so a device silent 30 h was never reported."""
    stamp = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    indigo_mod.devices[1] = z2m_dev(stamp)
    plugin._run_scan()
    assert 1 in plugin.alerted


def warnings(indigo_mod):
    return [m for m, _ in indigo_mod.server.lines if "cannot read its lastSeen" in m]


def test_an_unreadable_value_is_warned_about_once(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = z2m_dev("last Tuesday")
    for _ in range(3):
        plugin._run_scan()
    got = warnings(indigo_mod)
    assert len(got) == 1 and "Hall Sensor" in got[0] and "last Tuesday" in got[0]


def test_the_warning_comes_back_if_it_recurs(plugin_mod, indigo_mod, plugin, pushover):
    indigo_mod.devices[1] = z2m_dev("last Tuesday")
    plugin._run_scan()
    indigo_mod.devices[1].states["lastSeen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plugin._run_scan()
    indigo_mod.devices[1].states["lastSeen"] = "garbage"
    plugin._run_scan()
    assert len(warnings(indigo_mod)) == 2


def test_no_warning_when_there_is_no_lastSeen_yet(plugin_mod, indigo_mod, plugin, pushover):
    dev = z2m_dev("")
    indigo_mod.devices[1] = dev
    plugin._run_scan()
    del dev.states["lastSeen"]
    plugin._run_scan()
    assert warnings(indigo_mod) == []
