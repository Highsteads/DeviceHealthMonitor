#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_watchdog_restart.py
# Description: The plugin watchdog's verdicts (_assess_plugin_health) and the LIVE
#              restart path of _maybe_restart_plugin: cooldown, daily cap, and what
#              happens when a restart or the Pushover about it fails. tests/README.md
#              listed this machinery as not covered.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

from datetime import datetime, timedelta

import pytest

from conftest import FakeDevice

PID    = "com.example.watched"
POLICY = {"stale_minutes": 10, "cooldown_minutes": 30, "max_per_day": 2, "enabled": True}
T0     = datetime(2026, 11, 1, 9, 0)


class FakeWatchedPlugin:
    """Only the PluginInfo methods plugin.py calls. isInstalled/isEnabled/isRunning/
    restart are taken from plugin.py's own use, not checked against Indigo here."""
    pluginDisplayName = "Watched Plugin"

    def __init__(self, installed=True, enabled=True, running=True, restart_raises=None):
        self.installed      = installed
        self.enabled        = enabled
        self.running        = running
        self.restart_raises = restart_raises
        self.restarts       = 0

    def isInstalled(self):
        return self.installed

    def isEnabled(self):
        return self.enabled

    def isRunning(self):
        return self.running

    def restart(self, waitUntilDone=True):
        if self.restart_raises is not None:
            raise self.restart_raises
        self.restarts += 1


def device_seen(minutes_ago, now=T0):
    dev = FakeDevice(1, "Dev", PID)
    dev.lastSuccessfulComm = now - timedelta(minutes=minutes_ago)
    return dev


def assess(indigo_mod, plugin, watched, devs, policy=POLICY, now=T0):
    indigo_mod.server.plugins[PID] = watched
    return plugin._assess_plugin_health(PID, policy, devs, now)


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------

def test_fresh_comm_is_ok(indigo_mod, plugin):
    verdict, _ = assess(indigo_mod, plugin, FakeWatchedPlugin(), [device_seen(2)])
    assert verdict == "ok"


def test_stale_comm_is_wedged(indigo_mod, plugin):
    verdict, reason = assess(indigo_mod, plugin, FakeWatchedPlugin(), [device_seen(25)])
    assert verdict == "wedged"
    assert "25m" in reason


def test_newest_device_decides(indigo_mod, plugin):
    """One live device is enough: the plugin is talking to something."""
    old, new = device_seen(500), device_seen(1)
    verdict, _ = assess(indigo_mod, plugin, FakeWatchedPlugin(), [old, new])
    assert verdict == "ok"


def test_not_running_is_crashed(indigo_mod, plugin):
    verdict, _ = assess(indigo_mod, plugin, FakeWatchedPlugin(running=False), [device_seen(1)])
    assert verdict == "crashed"


def test_disabled_by_user_is_left_alone(indigo_mod, plugin):
    verdict, _ = assess(indigo_mod, plugin, FakeWatchedPlugin(enabled=False, running=False),
                        [device_seen(500)])
    assert verdict == "unavailable"


def test_transmit_only_is_never_wedged(indigo_mod, plugin):
    policy = dict(POLICY, stale_minutes=None)
    verdict, _ = assess(indigo_mod, plugin, FakeWatchedPlugin(), [device_seen(10000)], policy)
    assert verdict == "ok"


def test_post_restart_grace(indigo_mod, plugin):
    plugin.restart_state[PID] = {"last_restart": (T0 - timedelta(minutes=2)).isoformat(),
                                 "restarts_today": 1, "day": "2026-11-01",
                                 "cap_alerted": False}
    verdict, reason = assess(indigo_mod, plugin, FakeWatchedPlugin(running=False),
                             [device_seen(500)])
    assert verdict == "ok" and "grace" in reason


def test_claudebridge_and_self_are_never_candidates(plugin_mod, plugin):
    devs = [device_seen(1)]
    plugin._load_watchdog_config()
    got = plugin._discover_candidates({plugin_mod.CLAUDEBRIDGE_ID: devs,
                                       plugin.pluginId: devs,
                                       PID: devs})
    assert set(got) == {PID}


# --------------------------------------------------------------------------
# Live restart path
# --------------------------------------------------------------------------

def live_check(plugin, when):
    plugin._roll_restart_day(when)
    plugin._maybe_restart_plugin(PID, POLICY, "wedged", "quiet", when)


def test_live_restart_is_issued_and_announced(indigo_mod, plugin, pushover):
    watched = FakeWatchedPlugin()
    indigo_mod.server.plugins[PID] = watched
    plugin.watchdog_dry_run = False
    live_check(plugin, T0)
    assert watched.restarts == 1
    assert plugin.restart_state[PID]["restarts_today"] == 1
    assert any("restarted" in p["msgTitle"] for _, p in pushover.sent)


@pytest.mark.xfail(strict=True, reason=(
    "BUG: a restart that raises records nothing (no last_restart, no count), so the "
    "cooldown and the daily cap never apply and a priority-1 'restart FAILED' Pushover "
    "goes out at every scan for as long as the fault lasts. plugin.py _maybe_restart_plugin."))
def test_a_failing_restart_does_not_page_at_every_scan(indigo_mod, plugin, pushover):
    indigo_mod.server.plugins[PID] = FakeWatchedPlugin(restart_raises=RuntimeError("boom"))
    plugin.watchdog_dry_run = False
    for i in range(12):                                  # two hours of 10-minute scans
        live_check(plugin, T0 + timedelta(minutes=10 * i))
    failed = [p for _, p in pushover.sent if "FAILED" in p["msgTitle"]]
    assert len(failed) <= POLICY["max_per_day"] + 1


@pytest.mark.xfail(strict=True, reason=(
    "BUG: the once-a-day 'needs attention' latch (cap_alerted) is set BEFORE the "
    "Pushover is sent and the send result is ignored, so if Pushover is down at that "
    "moment the only alert that a plugin is beyond automatic repair is lost for the "
    "rest of the day. plugin.py _maybe_restart_plugin."))
def test_needs_attention_alert_is_retried_if_pushover_failed(indigo_mod, plugin, pushover):
    indigo_mod.server.plugins[PID] = FakeWatchedPlugin()
    plugin.watchdog_dry_run = False
    live_check(plugin, T0)
    live_check(plugin, T0 + timedelta(minutes=40))       # cap of 2 now used
    pushover.raises = True
    live_check(plugin, T0 + timedelta(minutes=80))       # cap alert attempted, lost
    pushover.raises = False
    live_check(plugin, T0 + timedelta(minutes=90))
    assert any("needs attention" in p["msgTitle"] for _, p in pushover.sent)
