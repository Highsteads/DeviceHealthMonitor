#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_ramses_valves.py
# Description: An Evohome zone is judged on the error state RAMSES_ESP sets, never on
#              how long since the zone device was heard from.
# Author:      CliveS & Claude Opus 5
# Date:        12-09-2026
# Version:     1.0
#
# The load-bearing case is test_a_zone_whose_gateway_is_chatty_but_whose_valve_is_silent.
# A zone device is a thermostat the gateway keeps up to date, so its comm clock stays
# fresh while the radiator valve in that room has said nothing for days. Judged on
# silence, every valve in the house reads healthy for ever — which is the failure this
# whole check exists to prevent, arriving by the back door.

from conftest import FakeDevice

RAMSES = "uk.co.clives.ramses.esp"
Z2M    = "com.clives.indigoplugin.z2mbridge"


def zone(dev_id=1, name="En Suite Radiator", error="", hours_since_comm=0.01,
         status="answering"):
    """One Evohome zone device as RAMSES_ESP publishes it."""
    return FakeDevice(dev_id, name, RAMSES, error_state=error,
                      hours_since_comm=hours_since_comm,
                      states={"trvStatus": status, "trvBatteryWarn": "unknown",
                              "trvBattery": -1, "temperatureInput1": 20.4})


# ---------------------------------------------------------------------------
class TestTheProtocolIsWatchedAtAll:
    """It was not, and that is why this file exists.

    RAMSES_ESP shipped per-valve liveness on 12-09-2026 and nothing read the error
    state it sets. The one WARNING it logs is recorded by Log_Error_Watch and
    deliberately never pushed, so a dead valve reached nobody.
    """

    def test_ramses_is_in_the_monitored_protocols(self, plugin_mod):
        assert plugin_mod.MONITORED_PLUGINS.get(RAMSES) == "ramses"

    def test_a_zone_device_is_not_skipped_as_unmonitored(self, plugin, plugin_mod):
        offline, reason = plugin._check_device_health(zone(error="valve silent"))
        assert offline is not None, "the protocol is not being dispatched"
        assert offline is True
        assert "valve silent" in reason


# ---------------------------------------------------------------------------
class TestJudgedOnTheErrorStateNeverOnSilence:

    def test_a_silent_valve_is_reported(self, plugin):
        offline, reason = plugin._check_device_health(
            zone(error="valve silent", status="silent"))
        assert offline is True
        assert "valve silent" in reason

    def test_an_answering_valve_is_not(self, plugin):
        offline, _ = plugin._check_device_health(zone())
        assert offline is False

    def test_a_valve_not_heard_from_yet_is_not_accused(self, plugin):
        """RAMSES_ESP writes no error while the answer is unknown, and neither do we.

        Its own restart grace means a reload cannot raise a fault about its own
        downtime, and this check inherits that for free by reading the same flag.
        """
        offline, _ = plugin._check_device_health(zone(status="unknown"))
        assert offline is False

    def test_a_zone_whose_gateway_is_chatty_but_whose_valve_is_silent(self, plugin):
        """The reason this is not judged on comm age.

        The controller pushes temperature and setpoint every few minutes, so the
        zone device's clock is always fresh. Only the error state knows about the
        valve.
        """
        offline, _ = plugin._check_device_health(
            zone(error="valve silent", status="silent", hours_since_comm=0.001))
        assert offline is True, "a fresh comm clock must not excuse a silent valve"

    def test_a_long_quiet_zone_with_no_error_is_left_alone(self, plugin):
        """The mirror case: silence on its own is never evidence here."""
        offline, _ = plugin._check_device_health(zone(hours_since_comm=500))
        assert offline is False, "silence alone must not report a working valve"


# ---------------------------------------------------------------------------
class TestItReachesThePhone:
    """End to end through the real scan, because classification is only half of it."""

    def test_a_silent_valve_produces_a_pushover_naming_the_room(self, plugin_mod,
                                                                plugin, pushover):
        plugin_mod.indigo.devices[1] = zone(1, "En Suite Radiator",
                                            error="valve silent", status="silent")
        plugin._run_scan()
        assert len(pushover.sent) == 1
        body = str(pushover.sent[0])
        assert "En Suite Radiator" in body
        assert "valve silent" in body

    def test_a_healthy_zone_produces_nothing(self, plugin_mod, plugin, pushover):
        plugin_mod.indigo.devices[1] = zone(1, "Bathroom Radiator")
        plugin._run_scan()
        assert pushover.sent == []

    def test_the_whole_house_going_quiet_is_one_message_not_twelve(self, plugin_mod,
                                                                   plugin, pushover):
        """A dead gateway takes every zone with it, and twelve pushes is a swipe-away."""
        for i in range(1, 13):
            plugin_mod.indigo.devices[i] = zone(i, f"Zone {i} Radiator",
                                                error="valve silent", status="silent")
        plugin._run_scan()
        assert len(pushover.sent) == 1
        assert "Zone 1 Radiator" in str(pushover.sent[0])
        assert "Zone 12 Radiator" in str(pushover.sent[0])

    def test_a_recovered_valve_clears_its_latch(self, plugin_mod, plugin, pushover):
        plugin_mod.indigo.devices[1] = zone(1, "En Suite Radiator",
                                            error="valve silent", status="silent")
        plugin._run_scan()
        assert 1 in plugin.alerted
        plugin_mod.indigo.devices[1] = zone(1, "En Suite Radiator")
        plugin._run_scan()
        assert 1 not in plugin.alerted, "a valve that came back must be able to alert again"

    def test_it_does_not_disturb_the_other_protocols(self, plugin_mod, plugin, pushover):
        """A zone alongside a genuinely dead z2m sensor: both reported, one message."""
        plugin_mod.indigo.devices[1] = zone(1, "En Suite Radiator",
                                            error="valve silent", status="silent")
        plugin_mod.indigo.devices[2] = FakeDevice(
            2, "Dead Sensor", Z2M, states={"availability": "online"},
            hours_since_comm=100)
        plugin._run_scan()
        assert len(pushover.sent) == 1
        body = str(pushover.sent[0])
        assert "En Suite Radiator" in body and "Dead Sensor" in body
