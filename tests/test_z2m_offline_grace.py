#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_z2m_offline_grace.py
# Description: The zigbee2mqtt offline flag flaps, so it gets a grace period
#              measured on the device's own lastSeen clock. Covers the grace,
#              the flapping report that stops the grace being a silent mute, and
#              the clock swap that made the staleness threshold work at all.
# Author:      CliveS & Claude Opus 5
# Date:        18-09-2026
# Version:     2.0
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


def verdict(plugin, dev, scans=2):
    """The verdict after `scans` consecutive scans with the device still silent.

    A mains device is ASKED before it is accused (v2.10.0), so one scan can only
    ever hold. Anything testing "this gets reported" has to drive the second scan
    — which is the behaviour, not a test artefact: a real dead device is paged ten
    minutes later than it used to be, and a device that answers is never paged.
    """
    out = (None, None)
    for _ in range(scans):
        out = plugin._check_z2m(dev)
    return out


# ------------------------------------------------------- the grace itself

def test_a_flag_on_a_device_seen_moments_ago_is_held_back(plugin):
    """The Clive Lamp case: flagged offline at 22:54, had reported at 23:20."""
    assert plugin._check_z2m(offline_dev(seen_hours=0.1)) == (False, "")


def test_a_flag_on_a_device_silent_past_the_grace_is_reported(plugin):
    """The Back Door Light case: genuinely quiet for 109 minutes."""
    offline, reason = verdict(plugin, offline_dev(seen_hours=109 / 60))
    assert offline is True
    assert "availability=offline" in reason
    assert "109 min" in reason
    assert "grace 30 min" in reason
    assert "ignored 2 direct reads" in reason


def test_the_grace_boundary_is_the_configured_number_of_minutes(plugin):
    """29 minutes held, 31 reported. The two dropout populations measured on
    18-09-2026 sit either side of 30: 20 minutes and under were false, 39 and
    over were real."""
    assert verdict(plugin, offline_dev(seen_hours=29 / 60))[0] is False
    assert verdict(plugin, offline_dev(2, seen_hours=31 / 60))[0] is True


def test_the_grace_is_configurable(plugin_mod, prefs):
    prefs["z2mOfflineGraceMinutes"] = "5"
    p = plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                          "Device Health Monitor", "2.9.0", prefs)
    assert p.z2m_offline_grace_min == 5.0
    assert verdict(p, offline_dev(seen_hours=10 / 60))[0] is True


def test_zero_disables_the_grace_and_pages_on_the_raw_flag(plugin_mod, prefs):
    prefs["z2mOfflineGraceMinutes"] = "0"
    p = plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                          "Device Health Monitor", "2.9.0", prefs)
    offline, reason = verdict(p, offline_dev(seen_hours=0.01))
    assert offline is True
    assert reason.startswith("availability=offline")


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
    offline, reason = verdict(plugin, dev)
    assert offline is True
    assert "no lastSeen" in reason


def test_an_unparseable_lastSeen_is_reported_rather_than_guessed(plugin):
    dev = FakeDevice(1, "Odd Clock", Z2M,
                     states={"availability": "offline", "lastSeen": "yesterday"},
                     hours_since_comm=0.05)
    offline, reason = verdict(plugin, dev)
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
    offline, reason = verdict(plugin, dev)
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
    assert verdict(plugin, dev)[0] is True


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
    for _ in range(plugin.FLAP_REPORT_THRESHOLD * 2 + 2):
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
    plugin._run_scan()          # asks it
    plugin._run_scan()          # no answer, so now it is paged
    assert len(pushover.sent) == 1
    assert "Back Door Light" in str(pushover.sent[0])
    assert 1 in plugin.alerted


# ------------------------------------------- asking before accusing (v2.10.0)

def mains_offline(dev_id=1, name="Back Door Light", seen_hours=2):
    return offline_dev(dev_id, name, seen_hours=seen_hours)


def battery_offline(dev_id=9, name="Dining Room Temperature and Humidity Sensor",
                    seen_hours=67.2):
    return FakeDevice(dev_id, name, Z2M, battery=49,
                      states={"availability": "offline"},
                      hours_since_comm=0.08, hours_since_seen=seen_hours)


def test_a_mains_device_is_asked_before_it_is_accused(plugin, indigo_mod):
    dev = mains_offline()
    assert plugin._check_z2m(dev) == (None, None)
    assert indigo_mod.device.status_requests == [1]


def test_it_is_accused_once_it_has_ignored_two_reads(plugin, indigo_mod):
    dev = mains_offline()
    plugin._check_z2m(dev)
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "ignored 2 direct reads" in reason
    assert indigo_mod.device.status_requests == [1, 1]


def test_a_device_that_spoke_since_we_asked_starts_again_from_one(plugin):
    """The whole point: Clive Lamp was paged at 07:12 and dimming at 07:13.

    Strikes count reads that went NOWHERE, so a device that has spoken since we
    asked starts again from one — otherwise a device answering every single time
    would still be accused in the end.

    THE DEVICE IS KEPT PAST THE GRACE ON PURPOSE. Moving lastSeen to a few seconds
    ago makes the grace hold it before the probe logic is ever reached, so the test
    passes whatever the strike counter does — which is exactly how an earlier
    version of this test survived a mutation that removed the reset.
    """
    dev = mains_offline(seen_hours=90 / 60)
    assert plugin._check_z2m(dev) == (None, None)
    assert plugin._z2m_probes[1]["strikes"] == 1
    dev.states["lastSeen"] = _stamp_minutes_ago(40)     # answered, still past grace
    assert plugin._check_z2m(dev) == (None, None)
    assert plugin._z2m_probes[1]["strikes"] == 1


def test_a_device_that_keeps_answering_is_never_accused(plugin):
    """Ten rounds, answering each time, always past the grace."""
    dev = mains_offline(seen_hours=90 / 60)
    for minutes in range(40, 50):
        assert plugin._check_z2m(dev) == (None, None)
        dev.states["lastSeen"] = _stamp_minutes_ago(minutes)
    # Never ACCUSED — the verdict is "no opinion, asking again", which is not the
    # same as a clean bill and must not be asserted as one.
    assert plugin._check_z2m(dev) == (None, None)


def test_a_battery_device_is_never_probed_and_is_reported_at_once(plugin, indigo_mod):
    """A sleeping device cannot answer a read, so the probe proves nothing either
    way. Measured 19-09-2026: two healthy battery sensors and two genuinely dead
    devices ALL failed to move lastSeen when asked. Silence is all there is here,
    which is what z2m's 25-hour passive timeout is for."""
    offline, reason = plugin._check_z2m(battery_offline())
    assert offline is True
    assert "direct reads" not in reason
    assert indigo_mod.device.status_requests == []


def test_a_healthy_device_clears_its_probe_record(plugin):
    dev = mains_offline()
    plugin._check_z2m(dev)
    assert 1 in plugin._z2m_probes
    dev.states["availability"] = "online"
    dev.states["lastSeen"] = _stamp_minutes_ago(1)
    plugin._check_z2m(dev)
    assert 1 not in plugin._z2m_probes


def test_a_probe_that_will_not_send_is_the_answer_not_an_error(plugin, indigo_mod):
    """A statusRequest Indigo refuses is a device that cannot be reached, so it
    counts as a failed read rather than taking the health check down."""
    indigo_mod.device.raise_on_status = RuntimeError("no such device")
    dev = mains_offline()
    assert plugin._check_z2m(dev) == (None, None)
    assert plugin._check_z2m(dev)[0] is True


def test_the_stale_leg_is_probed_too(plugin, indigo_mod):
    """A mains device unseen for 13 hours gets the same courtesy as one z2m has
    flagged — the rule is one sentence, applied wherever the verdict is made."""
    dev = FakeDevice(1, "Quiet Mains Light", Z2M, states={"availability": "online"},
                     hours_since_comm=0.05, hours_since_seen=13)
    assert plugin._check_z2m(dev) == (None, None)
    assert indigo_mod.device.status_requests == [1]
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "not seen for 13" in reason and "ignored 2 direct reads" in reason


def _stamp_minutes_ago(minutes):
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------- a hold is not a recovery (v2.10.1)

def test_a_hold_is_no_verdict_rather_than_a_clean_bill(plugin):
    """(None, None), never (False, ""). _run_scan skips a None entirely, so a
    latched device is neither un-latched nor re-reported while we wait."""
    assert plugin._check_z2m(mains_offline()) == (None, None)


def test_a_latched_device_is_not_announced_recovered_while_being_asked(
        plugin, plugin_mod, pushover):
    """Live-hit on the first scan after installing 2.10.0: `[RECOVERED]
    0xf84477fffe0a931d` for a node that had been silent 230 hours. A hold read as
    health, so the latch cleared and the next scan reported it as new — a spurious
    recovery and a spurious alert for a device that never moved."""
    dev = mains_offline(seen_hours=230)
    plugin_mod.indigo.devices[1] = dev
    plugin.alerted[1] = __import__("datetime").datetime.now()   # as restored at startup
    plugin._run_scan()
    assert 1 in plugin.alerted, "the latch must survive a scan that only asked"
    assert pushover.sent == []
    assert not [m for m in plugin_mod.indigo.server.lines if "RECOVERED" in m[0]]


def test_it_still_reports_recovered_when_the_device_really_comes_back(
        plugin, plugin_mod, pushover):
    """The other half — a hold must not become a latch that nothing can clear."""
    dev = mains_offline(seen_hours=230)
    plugin_mod.indigo.devices[1] = dev
    plugin.alerted[1] = __import__("datetime").datetime.now()
    plugin._run_scan()                                  # asked, held
    dev.states["availability"] = "online"
    dev.states["lastSeen"] = _stamp_minutes_ago(1)      # genuinely back
    plugin._run_scan()
    assert 1 not in plugin.alerted
    assert [m for m in plugin_mod.indigo.server.lines if "RECOVERED" in m[0]]


# ------------------- which devices a read cannot reach (v2.10.2)

def test_a_device_z2m_calls_battery_is_not_probed_even_with_no_battery_reading(
        plugin, indigo_mod):
    """The Shelly BLU RC Button, live on 19-09-2026. It half-joined on 09-09, its
    interview failed six times, and it has never reported a battery level — so
    `batteryLevel` is None while z2m calls it EndDevice / Battery. It was being
    probed and reported as having "ignored 2 direct reads", which is a claim the
    probe cannot support about a device that was asleep."""
    dev = FakeDevice(1, "0xf84477fffe0a931d", Z2M,
                     states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=230,
                     global_props={"power_source": "Battery",
                                   "friendly_name": "0xf84477fffe0a931d"})
    assert getattr(dev, "batteryLevel", None) is None, "the whole point of the case"
    offline, reason = plugin._check_z2m(dev)
    assert offline is True
    assert "direct reads" not in reason
    assert indigo_mod.device.status_requests == []


def test_a_mains_device_with_no_power_source_prop_is_still_probed(plugin, indigo_mod):
    """The union must not swallow the ordinary case."""
    dev = FakeDevice(1, "Back Door Light", Z2M, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=2,
                     global_props={"power_source": "Mains (single phase)"})
    assert plugin._check_z2m(dev) == (None, None)
    assert indigo_mod.device.status_requests == [1]


def test_the_power_source_test_is_case_and_space_tolerant(plugin, indigo_mod):
    dev = FakeDevice(1, "Odd Props", Z2M, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=230,
                     global_props={"power_source": "  battery  "})
    assert plugin._check_z2m(dev)[0] is True
    assert indigo_mod.device.status_requests == []


def test_a_device_with_no_props_at_all_is_still_probed(plugin, indigo_mod):
    """No props to read is not a reason to stop checking a device."""
    dev = FakeDevice(1, "Bare", Z2M, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=2)
    dev.globalProps = {}
    assert plugin._check_z2m(dev) == (None, None)
    assert indigo_mod.device.status_requests == [1]


def test_a_battery_reading_still_counts_on_its_own(plugin, indigo_mod):
    """The original signal keeps working where z2m says nothing."""
    dev = FakeDevice(1, "Sleepy", Z2M, battery=49, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=67)
    assert plugin._check_z2m(dev)[0] is True
    assert indigo_mod.device.status_requests == []


def test_a_device_object_with_no_globalProps_attribute_is_still_probed(plugin, indigo_mod):
    """The except branch, which the empty-dict case above cannot reach — a dict
    answers .get() without raising. A device object that has no globalProps at all
    must fall back to probing rather than take the health check down."""
    dev = FakeDevice(1, "No Props At All", Z2M, states={"availability": "offline"},
                     hours_since_comm=0.05, hours_since_seen=2)
    del dev.globalProps
    assert plugin._check_z2m(dev) == (None, None)
    assert indigo_mod.device.status_requests == [1]
