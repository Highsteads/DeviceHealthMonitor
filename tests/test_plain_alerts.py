#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_plain_alerts.py
# Description: 2.15.0. What reaches the phone is plain English: no raw state text,
#              the device named in the title, a flapping device said so once and
#              then left alone (over a rolling week, with a drop that lasts three
#              hours always sent), and a reminder that gives when the
#              device was LAST HEARD FROM and does not follow the first alert
#              within the hour.
# Author:      CliveS & Claude Fable 5.2
# Date:        10-11-2026
# Version:     1.0

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pytest

from conftest import SERVER_PLUGIN, FakeDevice

Z2M     = "com.clives.indigoplugin.z2mbridge"
SHELLY  = "com.clives.indigoplugin.shellydirect"
ZWAVE   = "com.perceptiveautomation.indigoplugin.zwave"
ESPHOME = "com.clives.indigoplugin.esphomebridge"
RAMSES  = "uk.co.clives.ramses.esp"
ECOWITT = "com.clives.indigoplugin.ecowitt"

# Text that only ever belongs in the Event Log.
RAW_MARKERS = ("errorState", "deviceOnline", "availability", "threshold", "lastChanged",
               "connected=", "lastSuccessfulComm", "=", "|", "(", ")", "grace", "- ")


def shelly(dev_id=1, name="Twigs Plug", online=False):
    return FakeDevice(dev_id, name, SHELLY, states={"deviceOnline": online},
                      hours_since_comm=0.01)


def sent(pushover):
    return [props for _, props in pushover.sent]


def assert_plain(text):
    for marker in RAW_MARKERS:
        assert marker not in text, f"{marker!r} reached the phone: {text!r}"
    assert text.isascii(), text
    for line in text.split("\n"):
        assert line.endswith("."), f"not a sentence: {line!r}"


# --------------------------------------------------------------------------
# Words
# --------------------------------------------------------------------------

@pytest.mark.parametrize("hours, want", [
    (0.005, "less than a minute"),
    (1 / 60, "a minute"),
    (37 / 60, "37 minutes"),
    (1.0, "about an hour"),
    (1.5, "over an hour"),
    (2.4, "over two hours"),
    (2.5, "over two hours"),
    (60, "over two days"),
    (11.8, "nearly twelve hours"),
    (20, "about 20 hours"),
    (57, "over two days"),
    (69.5, "nearly three days"),
    (24 * 30, "about 30 days"),
])
def test_a_length_of_time_in_words(plugin_mod, hours, want):
    assert plugin_mod.span_words(hours) == want


@pytest.mark.parametrize("hour, minute, want", [
    (16, 0, "4pm"), (11, 41, "11:41am"), (0, 5, "12:05am"), (12, 0, "12pm"), (9, 9, "9:09am"),
])
def test_a_time_of_day_as_a_person_says_it(plugin_mod, hour, minute, want):
    assert plugin_mod.clock_words(datetime(2026, 11, 7, hour, minute)) == want


def test_a_moment_in_words(plugin_mod):
    now = datetime(2026, 11, 10, 9, 9)          # a Tuesday
    w   = plugin_mod.when_words
    assert w(datetime(2026, 11, 10, 8, 48), now) == "8:48am today"
    assert w(datetime(2026, 11, 9, 16, 0), now) == "4pm yesterday"
    assert w(datetime(2026, 11, 7, 11, 41), now) == "11:41am on Saturday"
    assert w(datetime(2026, 10, 2, 11, 41), now) == "11:41am on 2 October"


def test_a_long_body_keeps_whole_lines(plugin_mod):
    lines = [f"Device number {i} has stopped answering." for i in range(60)]
    body  = plugin_mod.cap_body(lines)
    assert len(body) <= 1024
    kept = body.split("\n")
    assert kept[:-1] == lines[:len(kept) - 1], "a kept line was altered"
    assert re.fullmatch(r"\S+ more are listed in the Indigo Event Log\.", kept[-1])
    assert plugin_mod.cap_body(lines[:3]) == "\n".join(lines[:3])


# --------------------------------------------------------------------------
# The new-offline alert
# --------------------------------------------------------------------------

def test_one_device_is_named_in_the_title(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = shelly()
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert msg["msgTitle"] == "Twigs Plug has stopped answering"
    assert msg["msgBody"] == "Twigs Plug has stopped answering."


def test_the_raw_reason_stays_in_the_event_log(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = shelly()
    plugin._run_scan()
    lines = [m for m, _ in plugin_mod.indigo.server.lines]
    assert any("[OFFLINE] Twigs Plug: deviceOnline=False" in m for m in lines)


def test_several_devices_are_counted_in_words(plugin_mod, plugin, pushover):
    for i, name in enumerate(("Twigs Plug", "NAS Plug", "Air Purifier Plug"), start=1):
        plugin_mod.indigo.devices[i] = shelly(i, name)
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert msg["msgTitle"] == "Three devices are offline"
    assert msg["msgBody"].count("\n") == 2
    assert_plain(msg["msgBody"])


CASES = [
    FakeDevice(1, "Twigs Plug", SHELLY, states={"deviceOnline": False}, hours_since_comm=0.01),
    FakeDevice(2, "Old Relay", "com.clives.indigoplugin.shellyg1", error_state="unreachable",
               hours_since_comm=1),
    FakeDevice(3, "Other Relay", "com.clives.indigoplugin.shellyg1", error_state="wrong device",
               hours_since_comm=1),
    FakeDevice(4, "Loft Repeater", ZWAVE, error_state="no ack", hours_since_comm=50),
    FakeDevice(5, "Door Sensor", ZWAVE, battery=80, hours_since_comm=30),
    FakeDevice(6, "New Sensor", ZWAVE, battery=80),
    FakeDevice(7, "Freezer Monitor", ESPHOME, states={"connected": False}, hours_since_comm=0.01),
    FakeDevice(8, "Dining Room", RAMSES, error_state="valve silent", hours_since_comm=0.01),
    FakeDevice(9, "Window Sensor", Z2M, battery=50, states={"availability": "online"},
               hours_since_comm=100),
    FakeDevice(10, "Lamp", Z2M, battery=50, states={"availability": "offline"},
               hours_since_comm=2),
    FakeDevice(11, "Rain Gauge", ECOWITT, hours_since_changed=30),
    FakeDevice(12, "Odd Relay", "com.clives.indigoplugin.shellyg1", error_state="brownout",
               hours_since_comm=1),
]


@pytest.mark.parametrize("dev", CASES, ids=lambda d: d.name)
def test_every_reason_reaches_the_phone_as_a_sentence(plugin_mod, plugin, pushover, dev):
    if dev.pluginId not in plugin_mod.MONITORED_PLUGINS:
        pytest.fail(f"fixture uses an unwatched plugin id {dev.pluginId}")
    plugin_mod.indigo.devices[dev.id] = dev
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert msg["msgTitle"].startswith(dev.name + " ")
    assert msg["msgBody"].startswith(dev.name + " ")
    assert_plain(msg["msgTitle"] + ".")
    if dev.name == "Odd Relay":
        # An error text the table does not know is quoted, never dropped.
        assert '"brownout"' in msg["msgBody"]
    assert_plain(msg["msgBody"].replace('"brownout"', "brownout"))


def test_a_reason_from_older_code_still_makes_a_sentence(plugin_mod, plugin, pushover):
    assert plugin._alert_pushover([("Shed Plug", "some=raw text")]) is True
    (msg,) = sent(pushover)
    assert msg["msgBody"] == "Shed Plug has stopped answering."


def test_last_heard_is_said_where_it_is_known(plugin_mod, plugin):
    now   = datetime(2026, 11, 10, 9, 9)
    title, body = plugin._alert_text(
        [("Loft Repeater", plugin_mod.error_reason("zwave", "no ack"),
          datetime(2026, 11, 9, 16, 0), 0)], now)
    assert body == ("Loft Repeater is not answering the Z-Wave controller. "
                    "It was last heard from at 4pm yesterday.")


# --------------------------------------------------------------------------
# Flap damping, every protocol
# --------------------------------------------------------------------------

def flap_pair(kind):
    if kind == "shelly":
        return shelly(), shelly(online=True)
    if kind == "zwave":
        return (FakeDevice(1, "Twigs Plug", ZWAVE, error_state="no ack", hours_since_comm=1),
                FakeDevice(1, "Twigs Plug", ZWAVE, hours_since_comm=0.01))
    if kind == "esphome":
        return (FakeDevice(1, "Twigs Plug", ESPHOME, states={"connected": False}),
                FakeDevice(1, "Twigs Plug", ESPHOME, states={"connected": True}))
    return (FakeDevice(1, "Twigs Plug", Z2M, battery=50, states={"availability": "online"},
                       hours_since_comm=100),
            FakeDevice(1, "Twigs Plug", Z2M, battery=50, states={"availability": "online"},
                       hours_since_comm=0.01))


def drop_and_recover(plugin_mod, plugin, down, up, recover=True):
    plugin_mod.indigo.devices[1] = down
    plugin._run_scan()
    if recover:
        plugin_mod.indigo.devices[1] = up
        plugin._run_scan()


@pytest.fixture
def clock(plugin_mod, monkeypatch):
    """A movable 'now' for the plugin. Only for devices whose check is not an
    age (the Shelly here): a FakeDevice's comm time is fixed when it is built."""
    real = datetime

    class Clock(datetime):
        offset = timedelta(0)

        @classmethod
        def now(cls, tz=None):
            return real.now() + cls.offset

        @classmethod
        def forward(cls, **kw):
            cls.offset += timedelta(**kw)

    monkeypatch.setattr(plugin_mod, "datetime", Clock)
    return Clock


@pytest.mark.parametrize("kind", ["shelly", "zwave", "esphome", "z2m"])
def test_a_flapping_device_is_said_once_then_left_alone(plugin_mod, plugin, pushover, kind):
    down, up = flap_pair(kind)
    for _ in range(3):
        drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 3, "the first three drops are ordinary alerts"
    assert all("keeps" not in m["msgTitle"] for m in sent(pushover))

    drop_and_recover(plugin_mod, plugin, down, up)
    fourth = sent(pushover)[3]
    assert fourth["msgTitle"] == "Twigs Plug keeps dropping out"
    assert fourth["msgBody"] == (
        "Twigs Plug has dropped out four times in the last week. It came back each time "
        "before, so its later drops will not be sent until it has gone two days without "
        "one. You will be told if it stays offline for three hours.")
    assert_plain(fourth["msgBody"])

    for _ in range(4):
        drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 4, "later drops must not page"
    flapping = [m for m in plugin_mod.indigo.server.messages_at(30) if "[FLAPPING] Twigs Plug" in m]
    assert len(flapping) == 4, "each unpaged drop is still in the log"


def test_one_drop_a_day_is_still_flapping(plugin_mod, plugin, pushover, clock):
    """The measured pattern (27-10 to 10-11-2026): once or twice a day, for days.
    A tally that reset at midnight never reached its limit and sent 70 of 76."""
    down, up = flap_pair("shelly")
    for _ in range(6):
        drop_and_recover(plugin_mod, plugin, down, up)
        clock.forward(hours=24)
    titles = [m["msgTitle"] for m in sent(pushover)]
    assert titles == ["Twigs Plug has stopped answering"] * 3 + ["Twigs Plug keeps dropping out"]


def test_drops_older_than_a_week_do_not_count(plugin_mod, plugin, pushover, clock):
    down, up = flap_pair("shelly")
    for _ in range(3):
        drop_and_recover(plugin_mod, plugin, down, up)
    clock.forward(days=7, minutes=5)
    drop_and_recover(plugin_mod, plugin, down, up)
    assert [m["msgTitle"] for m in sent(pushover)] == ["Twigs Plug has stopped answering"] * 4
    assert len(plugin._drops[1]) == 1


def test_a_held_back_drop_that_lasts_is_sent(plugin_mod, plugin, pushover, clock):
    """Flaps four times, then dies for good: that must reach the phone today."""
    down, up = flap_pair("shelly")
    for _ in range(4):
        drop_and_recover(plugin_mod, plugin, down, up)
    drop_and_recover(plugin_mod, plugin, down, up, recover=False)     # fifth: stays off
    assert len(sent(pushover)) == 4
    assert 1 in plugin.alerted and 1 in plugin._muted
    latched = plugin.alerted[1]

    clock.forward(hours=2, minutes=50)
    plugin._run_scan()
    assert len(sent(pushover)) == 4, "not yet three hours"

    clock.forward(minutes=20)
    plugin._run_scan()
    fifth = sent(pushover)[4]
    assert fifth["msgTitle"] == "Twigs Plug has stayed offline"
    assert fifth["msgBody"].startswith("Twigs Plug dropped out at ")
    assert fifth["msgBody"].endswith(" and this time it has not come back.")
    assert_plain(fifth["msgBody"])
    assert plugin.alerted[1] == latched and 1 not in plugin._muted

    clock.forward(hours=5)
    plugin._run_scan()
    assert len(sent(pushover)) == 5, "said once"


def test_a_held_back_drop_survives_a_restart(plugin_mod, plugin, pushover, clock):
    """A restart must not turn 'not sent yet' into 'never sent'."""
    down, up = flap_pair("shelly")
    for _ in range(4):
        drop_and_recover(plugin_mod, plugin, down, up)
    drop_and_recover(plugin_mod, plugin, down, up, recover=False)
    again = plugin_mod.Plugin(plugin.pluginId, "Device Health Monitor", "2.15.0",
                              plugin.pluginPrefs)
    assert again._muted == plugin._muted and 1 in again._muted
    assert again._drops == plugin._drops and again._flap_noticed == plugin._flap_noticed
    clock.forward(hours=3, minutes=5)
    again._run_scan()
    assert sent(pushover)[4]["msgTitle"] == "Twigs Plug has stayed offline"


def test_a_stayed_offline_message_that_fails_is_tried_again(plugin_mod, plugin, pushover, clock):
    down, up = flap_pair("shelly")
    for _ in range(4):
        drop_and_recover(plugin_mod, plugin, down, up)
    drop_and_recover(plugin_mod, plugin, down, up, recover=False)
    clock.forward(hours=4)
    pushover.raises = True
    plugin._run_scan()
    assert 1 in plugin._muted, "not delivered, so still owed"
    pushover.raises = False
    plugin._run_scan()
    assert sent(pushover)[-1]["msgTitle"] == "Twigs Plug has stayed offline"
    assert 1 not in plugin._muted


def test_a_held_back_drop_that_recovers_says_nothing(plugin_mod, plugin, pushover, clock):
    down, up = flap_pair("shelly")
    for _ in range(5):
        drop_and_recover(plugin_mod, plugin, down, up)
    assert plugin._muted == {} and plugin.alerted == {}
    clock.forward(hours=4)
    plugin._run_scan()
    assert len(sent(pushover)) == 4


def test_two_quiet_days_end_the_silence(plugin_mod, plugin, pushover, clock):
    down, up = flap_pair("shelly")
    for _ in range(5):
        drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 4
    clock.forward(hours=47)
    drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 4, "47 hours is not yet two days"
    clock.forward(hours=49)
    drop_and_recover(plugin_mod, plugin, down, up)
    last = sent(pushover)[4]
    assert last["msgTitle"] == "Twigs Plug keeps dropping out"
    assert "seven times in the last week" in last["msgBody"]
    drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 5, "and the quiet starts over"


def test_the_weeks_count_survives_a_restart(plugin_mod, plugin, pushover):
    down, up = flap_pair("shelly")
    for _ in range(3):
        drop_and_recover(plugin_mod, plugin, down, up)
    again = plugin_mod.Plugin(plugin.pluginId, "Device Health Monitor", "2.15.0",
                              plugin.pluginPrefs)
    drop_and_recover(plugin_mod, again, down, up)
    assert sent(pushover)[3]["msgTitle"] == "Twigs Plug keeps dropping out"


def test_a_flap_notice_that_fails_is_not_counted_as_said(plugin_mod, plugin, pushover):
    down, up = flap_pair("shelly")
    for _ in range(3):
        drop_and_recover(plugin_mod, plugin, down, up)
    pushover.raises = True
    plugin_mod.indigo.devices[1] = down
    for _ in range(3):
        plugin._run_scan()
    assert 1 not in plugin._flap_noticed and 1 not in plugin.alerted
    pushover.raises = False
    plugin._run_scan()
    assert sent(pushover)[-1]["msgTitle"] == "Twigs Plug keeps dropping out"
    assert "four times" in sent(pushover)[-1]["msgBody"], "retries are not drops"


def test_the_flap_limit_can_be_switched_off(plugin_mod, plugin, pushover):
    plugin._apply_prefs({"flapLimitPerWeek": "0"})
    down, up = flap_pair("shelly")
    for _ in range(6):
        drop_and_recover(plugin_mod, plugin, down, up)
    assert len(sent(pushover)) == 6
    assert all(m["msgTitle"] == "Twigs Plug has stopped answering" for m in sent(pushover))


def test_an_undelivered_alert_is_one_drop_not_many(plugin_mod, plugin, pushover):
    """Retries of one outage must not run the tally up and mute a real alert."""
    pushover.raises = True
    plugin_mod.indigo.devices[1] = shelly()
    for _ in range(8):
        plugin._run_scan()
    pushover.raises = False
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert msg["msgTitle"] == "Twigs Plug has stopped answering"
    assert len(plugin._drops[1]) == 1


@pytest.mark.parametrize("raw, want", [("", 3), ("rubbish", 3), (None, 3), ("5", 5), ("-2", 0)])
def test_the_flap_limit_setting_is_guarded(plugin, raw, want):
    plugin._apply_prefs({"flapLimitPerWeek": raw})
    assert plugin.flap_limit == want


# --------------------------------------------------------------------------
# The daily reminder
# --------------------------------------------------------------------------

NOW = datetime(2026, 11, 10, 9, 9)              # Tuesday


def reminders(pushover):
    return [m for m in sent(pushover) if "still offline" in m["msgTitle"]]


def test_the_reminder_says_when_the_device_was_last_heard_from(plugin_mod, plugin, pushover):
    """The window sensor of 07-11-2026: last report 11:41 Saturday, latched 12:41 Sunday."""
    plugin_mod.indigo.devices[1] = FakeDevice(1, "Living Room Left Window Contact Sensor", Z2M)
    plugin.alerted[1]    = datetime(2026, 11, 8, 12, 41)
    plugin.last_heard[1] = datetime(2026, 11, 7, 11, 41)
    plugin._maybe_send_daily_reminder(NOW)
    (msg,) = reminders(pushover)
    assert msg["msgTitle"] == "Living Room Left Window Contact Sensor is still offline"
    assert msg["msgBody"] == ("Living Room Left Window Contact Sensor has not been heard from "
                              "since 11:41am on Saturday, nearly three days ago.")


def test_the_reminder_is_honest_where_no_clock_exists(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[1] = shelly(1, "HP Printer Power Plug")
    plugin.alerted[1] = datetime(2026, 11, 7, 8, 48)
    plugin._maybe_send_daily_reminder(NOW)
    (msg,) = reminders(pushover)
    assert msg["msgBody"] == ("HP Printer Power Plug was found offline at 8:48am on Saturday, "
                              "about three days ago, and has not come back.")
    assert_plain(msg["msgBody"])


def test_several_still_offline_are_counted_in_words(plugin_mod, plugin, pushover):
    for i in (1, 2):
        plugin_mod.indigo.devices[i] = shelly(i, f"Plug {i}")
        plugin.alerted[i] = NOW - timedelta(hours=30 + i)
    plugin._maybe_send_daily_reminder(NOW)
    (msg,) = reminders(pushover)
    assert msg["msgTitle"] == "Two devices are still offline"
    assert_plain(msg["msgBody"])


def test_no_reminder_an_hour_after_the_first_alert(plugin_mod, plugin, pushover):
    """07-11-2026: alerted 08:48, 'still offline' 09:48."""
    plugin_mod.indigo.devices[1] = shelly()
    plugin.alerted[1] = NOW - timedelta(hours=1, minutes=1)
    plugin._maybe_send_daily_reminder(NOW)
    assert reminders(pushover) == []
    plugin.alerted[1] = NOW - timedelta(hours=11, minutes=50)
    plugin._maybe_send_daily_reminder(NOW)
    assert reminders(pushover) == []
    plugin.alerted[1] = NOW - timedelta(hours=12, minutes=10)
    plugin._maybe_send_daily_reminder(NOW)
    assert len(reminders(pushover)) == 1


@pytest.mark.parametrize("raw, want", [("", 12), ("rubbish", 12), (None, 12), ("2.5", 2.5),
                                       ("-4", 0), ("inf", 12), ("1e999", 12), ("nan", 12)])
def test_the_reminder_age_setting_is_guarded(plugin, raw, want):
    plugin._apply_prefs({"reminderMinAgeHours": raw})
    assert plugin.reminder_min_age_hours == want


def test_an_endless_reminder_age_is_said_in_the_log(plugin_mod, plugin):
    plugin._apply_prefs({"reminderMinAgeHours": "inf"})
    assert any("reminderMinAgeHours" in m for m in plugin_mod.indigo.server.messages_at(30))


def test_a_mains_zwave_node_has_no_last_heard(plugin_mod, plugin, pushover):
    """Its lastSuccessfulComm is when it was last USED: healthy mains nodes read
    thousands of hours stale, so 'last heard from 3 October' would be false."""
    plugin_mod.indigo.devices[4] = FakeDevice(4, "Loft Repeater", ZWAVE, error_state="no ack",
                                              hours_since_comm=3000)
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert msg["msgBody"] == "Loft Repeater is not answering the Z-Wave controller."
    assert 4 in plugin.alerted and 4 not in plugin.last_heard
    plugin._apply_prefs({"reminderMinAgeHours": "0"})
    plugin._maybe_send_daily_reminder(datetime.now().replace(hour=23, minute=59))
    (again,) = reminders(pushover)
    assert "heard" not in again["msgBody"] and "was found offline at" in again["msgBody"]


def test_a_battery_zwave_node_keeps_its_last_heard(plugin_mod, plugin, pushover):
    plugin_mod.indigo.devices[5] = FakeDevice(5, "Door Sensor", ZWAVE, battery=80,
                                              hours_since_comm=30)
    plugin._run_scan()
    assert 5 in plugin.alerted and 5 in plugin.last_heard


def test_the_scan_stores_last_heard_with_the_latch(plugin_mod, plugin, pushover, prefs):
    plugin_mod.indigo.devices[1] = FakeDevice(1, "Window Sensor", Z2M, battery=50,
                                              states={"availability": "online"},
                                              hours_since_comm=100)
    plugin._run_scan()
    assert 1 in plugin.alerted
    age = (datetime.now() - plugin.last_heard[1]).total_seconds() / 3600.0
    assert 99.9 < age < 100.1
    again = plugin_mod.Plugin(plugin.pluginId, "Device Health Monitor", "2.15.0", prefs)
    assert again.last_heard == plugin.last_heard, "it must survive a restart"


def test_no_last_heard_for_a_shelly(plugin_mod, plugin, pushover):
    """Its comm time is refreshed by the plugin's own offline write, so it is not used."""
    plugin_mod.indigo.devices[1] = shelly()
    plugin._run_scan()
    assert 1 in plugin.alerted and 1 not in plugin.last_heard


def test_last_heard_goes_when_the_latch_goes(plugin_mod, plugin, pushover):
    dead = FakeDevice(1, "Window Sensor", Z2M, battery=50, states={"availability": "online"},
                      hours_since_comm=100)
    plugin_mod.indigo.devices[1] = dead
    plugin._run_scan()
    plugin_mod.indigo.devices[1] = FakeDevice(1, "Window Sensor", Z2M, battery=50,
                                              states={"availability": "online"},
                                              hours_since_comm=0.01)
    plugin._run_scan()
    assert plugin.alerted == {} and plugin.last_heard == {}


# --------------------------------------------------------------------------
# The Configure dialog carries the two new settings
# --------------------------------------------------------------------------

def test_the_new_settings_are_in_the_configure_dialog():
    root = ET.parse(os.path.join(SERVER_PLUGIN, "PluginConfig.xml")).getroot()
    fields = {f.get("id"): f for f in root.iter("Field")}
    assert fields["reminderMinAgeHours"].get("defaultValue") == "12"
    assert fields["flapLimitPerWeek"].get("defaultValue") == "3"
    assert "flapLimitPerDay" not in fields


def test_a_long_alert_is_cut_on_a_whole_line(plugin_mod, plugin, pushover):
    for i in range(1, 61):
        plugin_mod.indigo.devices[i] = shelly(i, f"Plug number {i}")
    plugin._run_scan()
    (msg,) = sent(pushover)
    assert len(msg["msgBody"]) <= 1024
    assert msg["msgBody"].endswith("more are listed in the Indigo Event Log.")
    assert msg["msgTitle"] == "60 devices are offline"
