#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_ecowitt_feed.py
# Description: Ecowitt devices are judged on the feed, not on lastChanged.
#              Ecowitt rewrites lastUpdateAgeSec on its gateway every 60 s and
#              deviceOnline=False on a stale sensor, so lastChanged stays fresh
#              on a dead gateway for ever. These tests use Ecowitt's real state
#              shapes (Ecowitt plugin 2.5.x Devices.xml and check_stale_devices).
# Author:      CliveS & Claude Opus 5.5
# Date:        05-10-2026
# Version:     1.0

from datetime import datetime, timedelta

from conftest import FakeDevice

ECOWITT = "com.clives.indigoplugin.ecowitt"
STAMP   = "%Y-%m-%d %H:%M:%S"


def stamp(hours_ago):
    return (datetime.now() - timedelta(hours=hours_ago)).strftime(STAMP)


def gateway(online=True, status="Live", age_sec=0, last_update_hours=0.0, changed=1 / 60):
    """The Main Gateway as Ecowitt leaves it. lastChanged one minute old by
    default, because the 60 s age write keeps it that way however dead the feed."""
    return FakeDevice(1, "Ecowitt Main Gateway", ECOWITT, states={
        "deviceOnline":     online,
        "connectionStatus": status,
        "lastUpdateAgeSec": age_sec,
        "lastUpdate":       stamp(last_update_hours),
    }, hours_since_changed=changed)


def sensor(online=True, last_update_hours=0.0, changed=1 / 60):
    return FakeDevice(2, "Ecowitt Outdoor Sensor", ECOWITT, states={
        "deviceOnline": online,
        "lastUpdate":   stamp(last_update_hours),
    }, hours_since_changed=changed)


# --------------------------------------------------------- the fault (MON-03)

def test_dead_gateway_with_fresh_lastchanged_is_offline(plugin):
    dev = gateway(online=False, status="Offline", age_sec=48 * 3600, last_update_hours=48)
    offline, reason = plugin._check_ecowitt(dev)
    assert offline is True
    assert "48" in reason


def test_dead_gateway_reported_when_online_arrives_as_a_string(plugin):
    """The v2 API and some readers hand custom states back as strings."""
    dev = gateway(online="False", status="Offline", age_sec=48 * 3600, last_update_hours=48)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is True


def test_stale_sensor_with_fresh_lastchanged_is_offline(plugin):
    dev = sensor(online=False, last_update_hours=48)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is True


def test_age_resets_on_ecowitt_restart_but_lastupdate_does_not(plugin):
    """After an Ecowitt restart lastUpdateAgeSec counts from the start, while
    the stored lastUpdate still shows the real last reading. The older wins."""
    dev = gateway(online=True, status="Live", age_sec=60, last_update_hours=48)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is True


def test_hung_ecowitt_still_saying_online_is_reported_on_feed_age(plugin):
    """If Ecowitt itself stops, nothing rewrites deviceOnline, so its verdict
    stays True. The receive time keeps ageing and decides."""
    dev = sensor(online=True, last_update_hours=48)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is True


def test_verdict_offline_with_no_reading_ever_is_offline(plugin):
    dev = FakeDevice(3, "Ecowitt Rain Sensor", ECOWITT,
                     states={"deviceOnline": False, "lastUpdate": ""},
                     hours_since_changed=1 / 60)
    offline, reason = plugin._check_ecowitt(dev)
    assert offline is True
    assert "offline" in reason.lower()


# --------------------------------------------------------------- healthy

def test_healthy_gateway_is_not_offline(plugin):
    offline, _ = plugin._check_ecowitt(gateway())
    assert offline is False


def test_healthy_sensor_is_not_offline(plugin):
    offline, _ = plugin._check_ecowitt(sensor())
    assert offline is False


def test_short_blip_inside_threshold_is_not_reported(plugin):
    """Ecowitt calls a sensor offline after 5 minutes; this plugin has no
    debounce, so the configured threshold still decides when to page."""
    dev = sensor(online=False, last_update_hours=0.2)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is False


def test_future_gateway_stamp_does_not_count_as_age(plugin):
    """A gateway clock running ahead gives a negative age, never a huge one."""
    dev = gateway(age_sec=30, last_update_hours=-0.5)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is False


# -------------------------------------------- older Ecowitt: no feed states

def test_missing_feed_states_fall_back_to_lastchanged_stale(plugin):
    dev = FakeDevice(4, "Old Ecowitt", ECOWITT, states={}, hours_since_changed=48)
    offline, reason = plugin._check_ecowitt(dev)
    assert offline is True
    assert "lastChanged" in reason


def test_missing_feed_states_fall_back_to_lastchanged_fresh(plugin):
    dev = FakeDevice(4, "Old Ecowitt", ECOWITT, states={}, hours_since_changed=1)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is False


def test_missing_everything_is_not_healthy(plugin):
    """An ABSENT state never counts as a pass."""
    dev = FakeDevice(4, "Old Ecowitt", ECOWITT, states={}, hours_since_changed=None)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is True


# ----------------------------------------------- quiet-device behaviour kept

def test_never_switches_the_check_off_even_with_a_dead_feed(plugin_mod, plugin):
    plugin.quiet_by_id = {1: None}
    dev = gateway(online=False, status="Offline", age_sec=48 * 3600, last_update_hours=48)
    offline, _ = plugin._check_ecowitt(dev)
    assert offline is False


def test_quiet_window_applies_to_feed_age(plugin_mod, plugin):
    plugin.quiet_by_id = {2: 72.0}
    offline, reason = plugin._check_ecowitt(sensor(online=False, last_update_hours=48))
    assert offline is False
    offline, reason = plugin._check_ecowitt(sensor(online=False, last_update_hours=80))
    assert offline is True
    assert "quiet device" in reason


# ------------------------------------------------- pure helper edge cases

def test_feed_age_takes_the_older_of_the_two_clocks(plugin_mod):
    now = datetime(2026, 10, 5, 12, 0, 0)
    states = {"lastUpdateAgeSec": 7200, "lastUpdate": "2026-10-05 11:00:00"}
    assert plugin_mod.ecowitt_feed_age_hours(states, now) == 2.0


def test_feed_age_ignores_junk(plugin_mod):
    now = datetime(2026, 10, 5, 12, 0, 0)
    assert plugin_mod.ecowitt_feed_age_hours({"lastUpdateAgeSec": "abc", "lastUpdate": "never"}, now) is None
    assert plugin_mod.ecowitt_feed_age_hours({"lastUpdateAgeSec": None, "lastUpdate": None}, now) is None


def test_verdict_reads_both_states(plugin_mod):
    assert plugin_mod.ecowitt_verdict({}) is None
    assert plugin_mod.ecowitt_verdict({"deviceOnline": True}) is False
    assert plugin_mod.ecowitt_verdict({"deviceOnline": "False"}) is True
    assert plugin_mod.ecowitt_verdict({"deviceOnline": True, "connectionStatus": "Offline"}) is True
    assert plugin_mod.ecowitt_verdict({"connectionStatus": "Live"}) is False
    assert plugin_mod.ecowitt_verdict({"connectionStatus": "Stale"}) is False


def test_future_stamp_alone_reads_as_no_age_not_negative(plugin_mod):
    now = datetime(2026, 10, 5, 12, 0, 0)
    assert plugin_mod.ecowitt_feed_age_hours({"lastUpdate": "2026-10-05 12:30:00"}, now) == 0.0
