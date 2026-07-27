#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_alert_latch.py
# Description: A device is marked "already alerted" only once the alert has
#              actually been DELIVERED. Latching before the send meant a Pushover
#              outage swallowed the alert for good.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

from conftest import FakeDevice

Z2M = "com.clives.indigoplugin.z2mbridge"


def offline_device(dev_id=1, name="Dead Sensor", hours=100):
    return FakeDevice(dev_id, name, Z2M,
                      states={"availability": "online"}, hours_since_comm=hours)


def healthy_device(dev_id=1, name="Dead Sensor"):
    return FakeDevice(dev_id, name, Z2M,
                      states={"availability": "online"}, hours_since_comm=1)


def test_a_delivered_alert_latches_the_device(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    assert len(pushover.sent) == 1
    assert 1 in plugin.alerted
    assert plugin._undelivered == set()


def test_a_latched_device_is_not_alerted_again(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    plugin._run_scan()
    assert len(pushover.sent) == 1


def test_an_undelivered_alert_does_NOT_latch(plugin_mod, plugin, pushover):
    """The bug this release fixes: the device used to be latched ten lines before
    the send was attempted, so an outage was logged and then never notified."""
    pushover.raises = True
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    assert plugin.alerted == {}
    assert plugin._undelivered == {1}


def test_the_alert_is_retried_and_delivered_once_pushover_recovers(plugin_mod, plugin, pushover):
    pushover.raises = True
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    assert pushover.sent == []

    pushover.raises = False
    plugin._run_scan()
    assert len(pushover.sent) == 1
    assert 1 in plugin.alerted
    assert plugin._undelivered == set()


def test_no_pushover_plugin_at_all_is_treated_as_undelivered(plugin_mod, plugin):
    """No `pushover` fixture here, so getPlugin raises — the same as an outage."""
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    assert plugin.alerted == {}
    assert plugin._undelivered == {1}


def test_a_sustained_outage_stops_repeating_the_per_device_line(plugin_mod, plugin, pushover):
    pushover.raises = True
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    plugin._run_scan()
    plugin._run_scan()
    offline_lines = [m for m in plugin_mod.indigo.server.messages_at(30)
                     if "[OFFLINE] Dead Sensor" in m]
    assert len(offline_lines) == 1


def test_recovery_after_a_failed_alert_leaves_no_phantom_recovered_line(plugin_mod, plugin, pushover):
    """It recovered before anyone was told, so there is no alert to report
    recovery from — and nothing must be left behind in the persisted state."""
    pushover.raises = True
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()

    plugin_mod.indigo.devices[1] = healthy_device()
    plugin._run_scan()

    all_lines = [m for m, _ in plugin_mod.indigo.server.lines]
    assert not any("[RECOVERED]" in m for m in all_lines)
    assert plugin._undelivered == set()
    assert plugin.alerted == {}


def test_a_delivered_alert_then_recovery_does_report_recovered(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    plugin_mod.indigo.devices[1] = healthy_device()
    plugin._run_scan()

    all_lines = [m for m, _ in plugin_mod.indigo.server.lines]
    assert any("[RECOVERED] Dead Sensor" in m for m in all_lines)
    assert plugin.alerted == {}


def test_alert_pushover_returns_the_delivery_verdict(plugin_mod, plugin, pushover):
    assert plugin._alert_pushover([("A", "reason")]) is True
    pushover.raises = True
    assert plugin._alert_pushover([("A", "reason")]) is False


def test_a_failed_delivery_is_reported_as_an_error(plugin_mod, plugin, pushover):
    pushover.raises = True
    plugin._alert_pushover([("A", "reason")])
    errors = plugin_mod.indigo.server.messages_at(40)   # logging.ERROR
    assert any("NOT DELIVERED" in m for m in errors)


def test_excluded_and_disabled_devices_are_never_scanned(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = offline_device(1, "Excluded One")
    plugin_mod.indigo.devices[2] = offline_device(2, "Disabled One")
    plugin_mod.indigo.devices[2].enabled = False
    plugin.excluded_names = {"excluded one"}
    plugin._run_scan()
    assert pushover.sent == []
    assert plugin.alerted == {}


def test_a_deleted_device_stops_counting_as_an_outstanding_alert(plugin_mod, plugin, pushover):
    """The scan only iterates devices that exist, so a deleted one could never be
    cleared and sat in alerted_json for good."""
    plugin_mod.indigo.devices[1] = offline_device()
    plugin._run_scan()
    assert 1 in plugin.alerted

    del plugin_mod.indigo.devices[1]
    plugin._run_scan()
    assert plugin.alerted == {}
    assert plugin._undelivered == set()


def test_a_quiet_device_never_reaches_the_alert_path(plugin_mod, plugin, pushover):
    """End to end: the exemption and the latch working together."""
    plugin_mod.indigo.devices[1] = offline_device(1, "Bathroom Cupboard", hours=56)
    plugin.quiet_by_id = {1: 240.0}
    plugin._run_scan()
    assert pushover.sent == []
    assert plugin.alerted == {}
