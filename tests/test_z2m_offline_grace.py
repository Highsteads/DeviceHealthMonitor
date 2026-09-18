#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_z2m_offline_grace.py
# Description: The zigbee2mqtt offline flag flaps, so it gets a grace period
#              measured on the device's own lastSeen clock. Covers the grace,
#              the flapping report that stops the grace being a silent mute, and
#              the clock swap that made the staleness threshold work at all.
# Author:      CliveS & Claude Opus 5
# Date:        18-09-2026
# Version:     1.0
#
# Why this file exists (measured 18-09-2026):
# * zigbee2mqtt pings a mains device about every ten minutes and, with its
#   availability.active.timeout at the ten-minute default, one lost packet
#   declared the device offline. 41 offline reports in seven days across four
#   devices, 13 on 18-09 alone, one Pushover each.
# * Three of those four had not been silent for more than 20 minutes ONCE in the
#   week. Back Door Light had genuinely gone quiet six times, up to 109 minutes.
#   So the flag needs a grace, and 30 minutes separates the two sets cleanly.
# * The Dining Room Temperature and Humidity Sensor had been silent 67.2 hours
#   with a lastSuccessfulComm reading 0.08 hours old, because z2mbridge keeps
#   writing availability to it and Indigo refreshes the comm time on any write.
#   The 12-hour staleness threshold could therefore never fire on any device.

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import FakeDevice  # noqa: E402

Z2M = "com.clives.indigoplugin.z2mbridge"


def offline_dev(dev_id=1, name="Back Door Light", seen_hours=0.1, comm_hours=0.05):
    """A z2m device z2m has flagged offline, seen `seen_hours` ago.

    comm_hours stays small on purpose: that is the real shape — the comm time is
    fresh because the availability write itself refreshed it.
    """
    return FakeDevice(dev_id, name, Z2M, states={"availability": "offline"},
                      hours_since_comm=comm_hours, hours_since_seen=seen_hours)


# ------------------------------------------------------- the grace itself

def test_a_flag_on_a_device_seen_moments_ago_is_held_back(plugin):
    """The Clive Lamp case: flagged offline at 22:54, had reported at 23:20."""
    assert plugin._check_z2m(offline_dev(seen_hours=0.1)) == (False, "")


def test_a_flag_on_a_device_silent_past_the_grace_is_reported(plugin):
    """The Back Door Light case: genuinely quiet for 109 minutes."""
    offline, reason = plugin._check_z2m(offline_dev(seen_hours=109 / 60))
    assert offline is True
    assert "availability=offline" in reason
    assert "109 min" in reason
    assert "grace 30 min" in reason


def test_the_grace_boundary_is_the_configured_number_of_minutes(plugin):
    """29 minutes held, 31 reported. The two dropout populations measured on
    18-09-2026 sit either side of 30: 20 minutes and under were false, 39 and
    over were real."""
    assert plugin._check_z2m(offline_dev(seen_hours=29 / 60))[0] is False
    assert plugin._check_z2m(offline_dev(seen_hours=31 / 60))[0] is True


def test_the_grace_is_configurable(plugin_mod, prefs):
    prefs["z2mOfflineGraceMinutes"] = "5"
    p = plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                          "Device Health Monitor", "2.9.0", prefs)
    assert p.z2m_offline_grace_min == 5.0
    assert p._check_z2m(offline_dev(seen_hours=10 / 60))[0] is True


def test_zero_disables_the_grace_and_pages_on_the_raw_flag(plugin_mod, prefs):
    prefs["z2mOfflineGraceMinutes"] = "0"
    p = plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                          "Device Health Monitor", "2.9.0", prefs)
    assert p._check_z2m(offline_dev(seen_hours=0.01)) == (True, "availability=offline")


@pytest.mark.parametrize("bad", ["", "   ", "soon", None, "-"])
def test_a_blank_or_daft_grace_falls_back_to_thirty_minutes(plugin_mod, prefs, bad):
    """A never-saved dialog and a cleared textfield must not crash startup, and
    must not silently disable the grace either."""
    prefs["z2mOfflineGraceMinutes"] = bad
    p = plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                          "Device Health Monitor", "2.9.0", prefs)
    assert p.z2m_offline_grace_min == 30.0


def test_a_device_with_no_lastSeen_at_all_is_reported_immediately(plugin):
    """No clock, no grace — the same call away_clock and the away tolerance make.
    A device that has never published a lastSeen is a pairing fault."""
    dev = FakeDevice(1, "Never Spoke", Z2M, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=None)
    dev.states.pop("lastSeen", None)
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "no lastSeen" in reason


def test_an_unparseable_lastSeen_is_reported_rather_than_guessed(plugin):
    dev = FakeDevice(1, "Odd Clock", Z2M,
                     states={"availability": "offline", "lastSeen": "yesterday"},
                     hours_since_comm=0.05)
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "no lastSeen" in reason


def test_an_online_device_is_still_fine(plugin):
    dev = FakeDevice(1, "Hall Lamp", Z2M, states={"availability": "online"},
                     hours_since_comm=0.05, hours_since_seen=0.1)
    assert plugin._check_z2m(dev) == (False, "")


# ------------------------------------------------- the clock that was wrong

def test_staleness_now_measures_lastSeen_not_the_comm_time(plugin):
    """The Dining Room sensor, to the hour: silent 67.2h, comm 0.08h.

    This is the case the old code could not see. It asserts on the SHAPE that
    occurs in the house, not on a fixture where both clocks agree.
    """
    dev = FakeDevice(1, "Dining Room Temperature and Humidity Sensor", Z2M,
                     states={"availability": "online"},
                     hours_since_comm=0.08, hours_since_seen=67.2)
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "not seen for 67" in reason
    assert "threshold 12h" in reason


def test_a_fresh_device_whose_comm_time_is_old_is_not_accused(plugin):
    """The mirror case, so the swap is a swap and not an extra condition."""
    dev = FakeDevice(1, "Chatty Sensor", Z2M, states={"availability": "online"},
                     hours_since_comm=99, hours_since_seen=0.2)
    assert plugin._check_z2m(dev) == (False, "")


def test_silence_is_reported_whatever_the_flag_says(plugin):
    """A bridge MQTT wedge leaves availability stuck at online — the Jane Lamp
    case of 29-05-2026. Silence still wins."""
    dev = FakeDevice(1, "Wedged", Z2M, states={"availability": "online"},
                     hours_since_comm=0.05, hours_since_seen=40)
    assert plugin._check_z2m(dev)[0] is True


# ------------------------------------------- the grace must not be a mute

def test_a_device_the_grace_holds_back_repeatedly_is_reported_as_flapping(plugin, indigo_mod):
    dev = offline_dev(name="Back Door Light")
    for _ in range(plugin.FLAP_REPORT_THRESHOLD):
        plugin._check_z2m(dev)
    warnings = indigo_mod.server.messages_at(30)          # logging.WARNING
    flapping = [m for m in warnings if "[FLAPPING]" in m]
    assert len(flapping) == 1
    assert "Back Door Light" in flapping[0]
    assert "4 times today" in flapping[0]


def test_the_flapping_report_is_said_once_not_every_scan(plugin, indigo_mod):
    dev = offline_dev()
    for _ in range(plugin.FLAP_REPORT_THRESHOLD * 5):
        plugin._check_z2m(dev)
    flapping = [m for m in indigo_mod.server.messages_at(30)          # logging.WARNING
                if "[FLAPPING]" in m]
    assert len(flapping) == 1


def test_a_single_held_back_flag_says_nothing(plugin, indigo_mod):
    plugin._check_z2m(offline_dev())
    assert not [m for m in indigo_mod.server.messages_at(30)          # logging.WARNING
                if "[FLAPPING]" in m]


def test_each_device_is_counted_separately(plugin, indigo_mod):
    a = offline_dev(1, "Back Door Light")
    b = offline_dev(2, "Jane Lamp")
    for _ in range(plugin.FLAP_REPORT_THRESHOLD):
        plugin._check_z2m(a)
    plugin._check_z2m(b)
    flapping = [m for m in indigo_mod.server.messages_at(30)          # logging.WARNING
                if "[FLAPPING]" in m]
    assert len(flapping) == 1
    assert "Back Door Light" in flapping[0]


def test_the_tally_resets_on_a_new_day(plugin, indigo_mod):
    """Otherwise one report covers a device for the rest of the install's life."""
    dev = offline_dev()
    for _ in range(plugin.FLAP_REPORT_THRESHOLD):
        plugin._check_z2m(dev)
    plugin._flap_day = "1970-01-01"          # as a date rollover leaves it
    for _ in range(plugin.FLAP_REPORT_THRESHOLD):
        plugin._check_z2m(dev)
    flapping = [m for m in indigo_mod.server.messages_at(30)          # logging.WARNING
                if "[FLAPPING]" in m]
    assert len(flapping) == 2


def test_a_reported_offline_device_is_not_counted_as_flapping(plugin, indigo_mod):
    """Flapping is what the grace HELD BACK. A device past the grace is paged as
    offline, and counting it here as well would say it twice."""
    dev = offline_dev(seen_hours=200 / 60)
    for _ in range(plugin.FLAP_REPORT_THRESHOLD * 2):
        plugin._check_z2m(dev)
    assert not [m for m in indigo_mod.server.messages_at(30)          # logging.WARNING
                if "[FLAPPING]" in m]


# ------------------------------------------------------------- end to end

def test_the_scan_does_not_page_for_a_device_inside_the_grace(plugin, plugin_mod, pushover):
    plugin_mod.indigo.devices[1] = offline_dev()
    plugin._run_scan()
    assert pushover.sent == []
    assert plugin.alerted == {}


def test_the_scan_does_page_for_a_device_past_the_grace(plugin, plugin_mod, pushover):
    plugin_mod.indigo.devices[1] = offline_dev(seen_hours=2)
    plugin._run_scan()
    assert len(pushover.sent) == 1
    assert "Back Door Light" in str(pushover.sent[0])
    assert 1 in plugin.alerted
