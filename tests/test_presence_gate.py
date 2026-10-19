#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_presence_gate.py
# Description: Presence gate. A device that travels with the household (a Shelly
#              Gen 1 in the car drops off the IoT network whenever the car is
#              driven) is not reported offline while a named presence device reads
#              away. Fails towards alerting: a missing, unknown or unreadable
#              presence reading alerts as it always did.
# Author:      CliveS & Claude Haiku 5.5
# Date:        19-10-2026
# Version:     1.0

from conftest import FakeDevice

SHELLY_G1 = "com.clives.indigoplugin.shellyg1"
UNIFI     = "com.clives.indigoplugin.unifihealth"   # any non-monitored plugin id will do

QASHQAI_ID = 7001
CLIVE_ID   = 1809194959
JANE_ID    = 420261884


def qashqai(error="unreachable"):
    """The car battery monitor as ShellyGen1 publishes it while off-network."""
    return FakeDevice(QASHQAI_ID, "Qashqai Battery Monitor", SHELLY_G1,
                      error_state=error, hours_since_comm=0.01,
                      states={"onOffState": True})


def presence(dev_id, name, value):
    """A presence device as the household reads it: its "presence" state."""
    return FakeDevice(dev_id, name, UNIFI, states={"presence": value},
                      hours_since_comm=0.01)


class TestPresenceGateVerdict:
    """presence_gate_away is the rule itself, with no Indigo in sight."""

    def test_both_home_alerts(self, plugin_mod):
        assert plugin_mod.presence_gate_away(["home", "home"]) is False

    def test_one_away_holds_back(self, plugin_mod):
        assert plugin_mod.presence_gate_away(["away", "home"]) is True
        assert plugin_mod.presence_gate_away(["home", "away"]) is True

    def test_both_away_holds_back(self, plugin_mod):
        assert plugin_mod.presence_gate_away(["away", "away"]) is True

    def test_a_missing_reading_alerts_even_beside_an_away(self, plugin_mod):
        assert plugin_mod.presence_gate_away(["away", None]) is False
        assert plugin_mod.presence_gate_away([None, "away"]) is False

    def test_an_unknown_value_alerts_even_beside_an_away(self, plugin_mod):
        assert plugin_mod.presence_gate_away(["away", "unknown"]) is False
        assert plugin_mod.presence_gate_away(["", "home"]) is False

    def test_a_non_string_reading_alerts(self, plugin_mod):
        assert plugin_mod.presence_gate_away([True, "away"]) is False

    def test_no_presence_devices_alerts(self, plugin_mod):
        assert plugin_mod.presence_gate_away([]) is False


class TestPresenceGateFile:
    """parse_presence_gated: a bad entry is reported and skipped, never guessed at."""

    def test_a_valid_entry_is_read(self, plugin_mod):
        by_id, problems = plugin_mod.parse_presence_gated(
            [{"id": QASHQAI_ID, "presence_ids": [CLIVE_ID, JANE_ID], "name": "Qashqai"}])
        assert by_id == {QASHQAI_ID: [CLIVE_ID, JANE_ID]}
        assert problems == []

    def test_a_missing_file_gates_nothing(self, plugin_mod):
        assert plugin_mod.parse_presence_gated(None) == ({}, [])

    def test_a_file_that_is_not_a_list_is_reported(self, plugin_mod):
        by_id, problems = plugin_mod.parse_presence_gated({"id": QASHQAI_ID})
        assert by_id == {}
        assert problems

    def test_an_entry_without_presence_ids_is_skipped(self, plugin_mod):
        by_id, problems = plugin_mod.parse_presence_gated([{"id": QASHQAI_ID}])
        assert by_id == {}
        assert len(problems) == 1

    def test_an_empty_presence_list_is_skipped(self, plugin_mod):
        by_id, problems = plugin_mod.parse_presence_gated(
            [{"id": QASHQAI_ID, "presence_ids": []}])
        assert by_id == {}
        assert len(problems) == 1

    def test_a_non_integer_id_is_skipped(self, plugin_mod):
        by_id, problems = plugin_mod.parse_presence_gated(
            [{"id": "not-a-number", "presence_ids": [CLIVE_ID]}])
        assert by_id == {}
        assert len(problems) == 1


class TestPresenceGateOnDevices:
    """The gate as _check_device_health and the scan see it."""

    def _gate(self, plugin):
        plugin.presence_gated_by_id = {QASHQAI_ID: [CLIVE_ID, JANE_ID]}

    def test_car_out_with_clive_is_not_offline(self, plugin_mod, plugin):
        """Fails before the change: the unreachable car monitor was reported."""
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "home")
        offline, reason = plugin._check_device_health(qashqai())
        assert offline is False
        assert reason == ""

    def test_car_out_with_jane_is_not_offline(self, plugin_mod, plugin):
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "home")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "away")
        offline, _ = plugin._check_device_health(qashqai())
        assert offline is False

    def test_both_home_is_still_offline(self, plugin_mod, plugin):
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "home")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "home")
        offline, reason = plugin._check_device_health(qashqai())
        assert offline is True
        assert "unreachable" in reason

    def test_a_presence_device_that_is_missing_alerts(self, plugin_mod, plugin):
        """Fail towards alerting: Jane's device not in Indigo at all."""
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        offline, _ = plugin._check_device_health(qashqai())
        assert offline is True

    def test_a_presence_state_that_is_unknown_alerts(self, plugin_mod, plugin):
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "")
        offline, _ = plugin._check_device_health(qashqai())
        assert offline is True

    def test_an_ungated_device_still_alerts_beside_an_away(self, plugin_mod, plugin):
        """Only the device named in the file is gated."""
        self._gate(plugin)
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "away")
        other = FakeDevice(8001, "Garage Light", SHELLY_G1, error_state="unreachable",
                           hours_since_comm=0.01, states={"onOffState": True})
        offline, _ = plugin._check_device_health(other)
        assert offline is True

    def test_no_file_means_no_gate(self, plugin_mod, plugin):
        plugin.presence_gated_by_id = {}
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        offline, _ = plugin._check_device_health(qashqai())
        assert offline is True

    def test_the_scan_sends_nothing_while_the_car_is_out(self, plugin_mod, plugin, pushover):
        self._gate(plugin)
        plugin_mod.indigo.devices[QASHQAI_ID] = qashqai()
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "away")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "home")
        plugin._run_scan()
        assert pushover.sent == []

    def test_the_scan_alerts_when_both_are_home(self, plugin_mod, plugin, pushover):
        self._gate(plugin)
        plugin_mod.indigo.devices[QASHQAI_ID] = qashqai()
        plugin_mod.indigo.devices[CLIVE_ID] = presence(CLIVE_ID, "Presence - Clive", "home")
        plugin_mod.indigo.devices[JANE_ID] = presence(JANE_ID, "Presence - Jane", "home")
        plugin._run_scan()
        assert len(pushover.sent) == 1
        assert "Qashqai Battery Monitor" in str(pushover.sent[0])
