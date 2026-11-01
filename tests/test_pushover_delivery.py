#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_pushover_delivery.py
# Description: 2.14.0. The Pushover plugin's send action logs a refused message and
#              returns nothing, so this plugin cannot know a message was delivered.
#              Covers the two backstops: a stopped Pushover plugin counts as a failed
#              send, and a once-a-day reminder lists every device still offline.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

from datetime import datetime, timedelta

from conftest import FakeDevice

Z2M = "com.clives.indigoplugin.z2mbridge"


def dead(dev_id=1, name="Dead Sensor"):
    # battery= so it is reported in one scan, without a direct read first.
    return FakeDevice(dev_id, name, Z2M, battery=50,
                      states={"availability": "online"}, hours_since_comm=100)


def reminders(pushover):
    return [p for _, p in pushover.sent if "still offline" in p["msgTitle"]]


# --------------------------------------------------------------------------
# Pushover enabled but not running
# --------------------------------------------------------------------------

def test_a_stopped_pushover_plugin_is_a_failed_send(plugin_mod, plugin, pushover):
    pushover.running = False
    plugin_mod.indigo.devices[1] = dead()
    plugin._run_scan()
    assert pushover.sent == []
    assert 1 not in plugin.alerted, "must not latch: nothing was handed to anyone"
    assert 1 in plugin._undelivered


def test_the_alert_goes_out_once_pushover_is_running_again(plugin_mod, plugin, pushover):
    pushover.running = False
    plugin_mod.indigo.devices[1] = dead()
    plugin._run_scan()
    pushover.running = True
    plugin._run_scan()
    assert len(pushover.sent) == 1 and 1 in plugin.alerted


# --------------------------------------------------------------------------
# Daily reminder
# --------------------------------------------------------------------------

DAY  = datetime(2026, 11, 1)
NINE = DAY.replace(hour=9, minute=5)


def latched(plugin_mod, plugin, hours_ago=20, dev_id=1, name="Dead Sensor", now=NINE):
    plugin_mod.indigo.devices[dev_id] = dead(dev_id, name)
    plugin.alerted[dev_id] = now - timedelta(hours=hours_ago)


def test_reminder_lists_devices_still_offline(plugin_mod, plugin, pushover):
    latched(plugin_mod, plugin)
    plugin._maybe_send_daily_reminder(NINE)
    got = reminders(pushover)
    assert len(got) == 1
    assert "Dead Sensor" in got[0]["msgBody"] and "20h" in got[0]["msgBody"]


def test_reminder_is_sent_once_a_day(plugin_mod, plugin, pushover):
    latched(plugin_mod, plugin)
    for minutes in (0, 10, 20, 600):
        plugin._maybe_send_daily_reminder(NINE + timedelta(minutes=minutes))
    assert len(reminders(pushover)) == 1
    plugin._maybe_send_daily_reminder(NINE + timedelta(days=1))
    assert len(reminders(pushover)) == 2


def test_no_reminder_before_the_hour(plugin_mod, plugin, pushover):
    latched(plugin_mod, plugin)
    plugin._maybe_send_daily_reminder(DAY.replace(hour=8, minute=59))
    assert reminders(pushover) == []


def test_no_reminder_when_nothing_is_offline(plugin_mod, plugin, pushover):
    plugin._maybe_send_daily_reminder(NINE)
    assert pushover.sent == []


def test_no_reminder_when_switched_off(plugin_mod, plugin, pushover):
    plugin.daily_reminder = False
    latched(plugin_mod, plugin)
    plugin._maybe_send_daily_reminder(NINE)
    assert pushover.sent == []


def test_a_just_reported_device_is_left_out(plugin_mod, plugin, pushover):
    latched(plugin_mod, plugin, hours_ago=0.2)
    plugin._maybe_send_daily_reminder(NINE)
    assert reminders(pushover) == []


def test_a_failed_reminder_is_retried(plugin_mod, plugin, pushover):
    latched(plugin_mod, plugin)
    pushover.raises = True
    plugin._maybe_send_daily_reminder(NINE)
    pushover.raises = False
    plugin._maybe_send_daily_reminder(NINE + timedelta(minutes=10))
    assert len(reminders(pushover)) == 1


def test_a_restart_does_not_send_it_twice(plugin_mod, plugin, pushover, prefs):
    """The day is kept in pluginPrefs, which survive a plugin restart."""
    latched(plugin_mod, plugin)
    plugin._maybe_send_daily_reminder(NINE)
    again = plugin_mod.Plugin(plugin.pluginId, "Device Health Monitor", "2.14.0",
                              plugin.pluginPrefs)
    again._maybe_send_daily_reminder(NINE + timedelta(minutes=30))
    assert len(reminders(pushover)) == 1


def test_reminder_hour_is_clamped(plugin):
    plugin._apply_prefs({"dailyReminderHour": "99"})
    assert plugin.daily_reminder_hour == 23
    plugin._apply_prefs({"dailyReminderHour": "rubbish"})
    assert plugin.daily_reminder_hour == 9


def test_the_scan_sends_the_reminder(plugin_mod, plugin, pushover, monkeypatch):
    """Wired into _run_scan, not only callable on its own."""
    plugin_mod.indigo.devices[1] = dead()
    plugin.alerted[1] = datetime.now() - timedelta(hours=30)
    plugin.daily_reminder_hour = 0
    plugin._run_scan()
    assert len(reminders(pushover)) == 1
