#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_shelly_gen1.py
# Description: A Shelly is judged on Indigo's errorState as well as deviceOnline.
#              Shelly Gen 1 has no deviceOnline state and marks a dead Shelly with
#              errorState "unreachable", so until 2.11.0 it could never be reported.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

from conftest import FakeDevice

SHELLY_G1 = "com.clives.indigoplugin.shellyg1"
SHELLY    = "com.clives.indigoplugin.shellydirect"
Z2M       = "com.clives.indigoplugin.z2mbridge"


def gen1(dev_id=1, name="Garage Light", error=""):
    """A Shelly Gen 1 relay as ShellyGen1 publishes it: no deviceOnline state."""
    return FakeDevice(dev_id, name, SHELLY_G1, error_state=error,
                      hours_since_comm=0.01,
                      states={"onOffState": True, "power": 0.0})


class TestShellyGen1:

    def test_an_unreachable_gen1_device_is_reported(self, plugin):
        offline, reason = plugin._check_device_health(gen1(error="unreachable"))
        assert offline is True
        assert "unreachable" in reason

    def test_a_wrong_device_answering_is_reported(self, plugin):
        offline, reason = plugin._check_device_health(gen1(error="wrong device"))
        assert offline is True
        assert "wrong device" in reason

    def test_a_healthy_gen1_device_is_not(self, plugin):
        offline, _ = plugin._check_device_health(gen1())
        assert offline is False

    def test_it_reaches_the_phone(self, plugin_mod, plugin, pushover):
        plugin_mod.indigo.devices[1] = gen1(1, "Garage Light", error="unreachable")
        plugin._run_scan()
        assert len(pushover.sent) == 1
        assert "Garage Light" in str(pushover.sent[0])

    def test_a_recovered_gen1_device_clears_its_latch(self, plugin_mod, plugin, pushover):
        plugin_mod.indigo.devices[1] = gen1(1, "Garage Light", error="unreachable")
        plugin._run_scan()
        assert 1 in plugin.alerted
        plugin_mod.indigo.devices[1] = gen1(1, "Garage Light")
        plugin._run_scan()
        assert 1 not in plugin.alerted

    def test_an_away_tolerance_still_applies(self, plugin_mod, plugin):
        """A Shelly the user expects to be off sometimes is handled as before."""
        plugin.offline_tol_by_name = {"car charger": 48.0}
        offline, _ = plugin._check_device_health(
            gen1(1, "Car Charger", error="unreachable"))
        assert offline is False


class TestShellyDirectUnchanged:

    def test_device_online_false_is_still_reported(self, plugin):
        dev = FakeDevice(1, "Plug", SHELLY, hours_since_comm=0.01,
                         states={"deviceOnline": False})
        offline, reason = plugin._check_device_health(dev)
        assert offline is True
        assert reason == "deviceOnline=False"

    def test_an_online_plug_is_not(self, plugin):
        dev = FakeDevice(1, "Plug", SHELLY, hours_since_comm=0.01,
                         states={"deviceOnline": True})
        offline, _ = plugin._check_device_health(dev)
        assert offline is False


class TestNotGeneralised:

    def test_a_z2m_error_state_still_goes_through_the_grace(self, plugin):
        """z2mbridge sets errorState 'offline' from its availability flag. Reading it
        would skip the grace and the direct read and bring back the false alarms."""
        dev = FakeDevice(1, "Lamp", Z2M, error_state="offline",
                         hours_since_comm=0.05,
                         states={"availability": "offline"})
        offline, _ = plugin._check_device_health(dev)
        assert offline is False, "a z2m device just flagged must still get its grace"
