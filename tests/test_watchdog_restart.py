#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_watchdog_restart.py
# Description: The plugin watchdog's verdicts (_assess_plugin_health) and the LIVE
#              restart path of _maybe_restart_plugin: cooldown, daily cap, and what
#              happens when a restart or the Pushover about it fails, and the
#              start-up / wake grace added in 2.13.1.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.1

from datetime import datetime, timedelta

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


def test_a_failing_restart_does_not_page_at_every_scan(indigo_mod, plugin, pushover):
    """Fixed in 2.13.1: a failed attempt counts toward the cooldown and daily cap."""
    indigo_mod.server.plugins[PID] = FakeWatchedPlugin(restart_raises=RuntimeError("boom"))
    plugin.watchdog_dry_run = False
    for i in range(12):                                  # two hours of 10-minute scans
        live_check(plugin, T0 + timedelta(minutes=10 * i))
    titles = [p["msgTitle"] for _, p in pushover.sent]
    assert len([t for t in titles if "FAILED" in t]) == POLICY["max_per_day"]
    assert len([t for t in titles if "needs attention" in t]) == 1


def test_needs_attention_alert_is_retried_if_pushover_failed(indigo_mod, plugin, pushover):
    """Fixed in 2.13.1: the latch is set only once the Pushover is delivered."""
    indigo_mod.server.plugins[PID] = FakeWatchedPlugin()
    plugin.watchdog_dry_run = False
    live_check(plugin, T0)
    live_check(plugin, T0 + timedelta(minutes=40))       # cap of 2 now used
    pushover.raises = True
    live_check(plugin, T0 + timedelta(minutes=80))       # cap alert attempted, lost
    pushover.raises = False
    live_check(plugin, T0 + timedelta(minutes=90))
    live_check(plugin, T0 + timedelta(minutes=100))      # delivered: no repeat
    assert len([p for _, p in pushover.sent if "needs attention" in p["msgTitle"]]) == 1


def test_dry_run_attention_alert_is_also_retried(indigo_mod, plugin, pushover):
    indigo_mod.server.plugins[PID] = FakeWatchedPlugin()
    plugin.watchdog_dry_run = True
    live_check(plugin, T0)
    live_check(plugin, T0 + timedelta(minutes=40))
    pushover.raises = True
    live_check(plugin, T0 + timedelta(minutes=80))
    pushover.raises = False
    live_check(plugin, T0 + timedelta(minutes=90))
    assert any("would need attention" in p["msgTitle"] for _, p in pushover.sent)


# --------------------------------------------------------------------------
# Start-up / wake grace (2.13.1)
# --------------------------------------------------------------------------

class FrozenClock:
    """Pins plugin.datetime.now() so _run_plugin_watchdog can be walked through time."""

    def __init__(self, plugin_mod, monkeypatch, start):
        self.now = start
        real = plugin_mod.datetime
        clock = self

        class _DT(real):
            @classmethod
            def now(cls, tz=None):
                return clock.now
        monkeypatch.setattr(plugin_mod, "datetime", _DT)


def crashed_setup(plugin_mod, indigo_mod, plugin, monkeypatch):
    watched = FakeWatchedPlugin(running=False)
    indigo_mod.server.plugins[PID] = watched
    dev = FakeDevice(1, "Dev", PID)
    dev.configured = True
    dev.lastSuccessfulComm = T0
    indigo_mod.devices[1] = dev
    plugin.watchdog_enabled = True
    plugin.watchdog_dry_run = False
    plugin.watchdog_overrides[PID] = dict(POLICY)
    return watched, FrozenClock(plugin_mod, monkeypatch, T0)


def test_no_restart_in_the_first_minutes_after_start(plugin_mod, indigo_mod, plugin,
                                                     pushover, monkeypatch):
    watched, clock = crashed_setup(plugin_mod, indigo_mod, plugin, monkeypatch)
    plugin._run_plugin_watchdog()
    clock.now = T0 + timedelta(minutes=5)
    plugin._run_plugin_watchdog()
    assert watched.restarts == 0
    clock.now = T0 + timedelta(minutes=plugin_mod.WATCHDOG_STARTUP_GRACE_MIN + 1)
    plugin._run_plugin_watchdog()
    assert watched.restarts == 1, "after the grace a crashed plugin is restarted"


def test_a_long_gap_starts_a_new_grace(plugin_mod, indigo_mod, plugin,
                                       pushover, monkeypatch):
    watched, clock = crashed_setup(plugin_mod, indigo_mod, plugin, monkeypatch)
    plugin._run_plugin_watchdog()                                    # grace starts
    clock.now = T0 + timedelta(minutes=11)
    plugin._run_plugin_watchdog()                                    # restart #1
    assert watched.restarts == 1
    clock.now = T0 + timedelta(hours=3)                              # Mac slept
    plugin._run_plugin_watchdog()
    clock.now = T0 + timedelta(hours=3, minutes=5)
    plugin._run_plugin_watchdog()
    assert watched.restarts == 1, "no judging straight after a wake"
    clock.now = T0 + timedelta(hours=3, minutes=11)
    plugin._run_plugin_watchdog()
    assert watched.restarts == 2


def test_normal_cadence_does_not_restart_the_grace(plugin_mod, indigo_mod, plugin,
                                                   pushover, monkeypatch):
    _, clock = crashed_setup(plugin_mod, indigo_mod, plugin, monkeypatch)
    for i in range(6):                                               # 10-minute scans
        clock.now = T0 + timedelta(minutes=10 * i)
        plugin._run_plugin_watchdog()
    grace_logs = [m for m, _ in indigo_mod.server.lines if "holding off for" in m]
    assert len(grace_logs) == 1
