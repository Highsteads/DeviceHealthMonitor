#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_watchdog_dry_run.py
# Description: Dry-run keeps to the same cooldown and daily limit as a real restart.
#              Until 2.11.0 those counted only real restarts, so a dry run sent a
#              Pushover at every check for as long as a plugin looked failed.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

from datetime import datetime, timedelta

PID    = "com.example.flaky"
POLICY = {"stale_minutes": 10, "cooldown_minutes": 30, "max_per_day": 2, "enabled": True}


class FakeWatchedPlugin:
    pluginDisplayName = "Flaky Plugin"

    def __init__(self):
        self.restarts = 0

    def restart(self, waitUntilDone=True):
        self.restarts += 1


def setup(indigo_mod, plugin, dry):
    watched = FakeWatchedPlugin()
    indigo_mod.server.plugins[PID] = watched
    plugin.watchdog_dry_run = dry
    return watched


def check(plugin, when):
    plugin._roll_restart_day(when)
    plugin._maybe_restart_plugin(PID, POLICY, "wedged", "quiet", when)


def test_dry_run_respects_the_cooldown(indigo_mod, plugin, pushover):
    watched = setup(indigo_mod, plugin, dry=True)
    t0 = datetime(2026, 9, 27, 9, 0)
    check(plugin, t0)
    check(plugin, t0 + timedelta(minutes=10))
    check(plugin, t0 + timedelta(minutes=20))
    assert len(pushover.sent) == 1, "a dry run must not push at every check"
    assert watched.restarts == 0


def test_dry_run_respects_the_daily_limit_and_says_so_once(indigo_mod, plugin, pushover):
    setup(indigo_mod, plugin, dry=True)
    t0 = datetime(2026, 9, 27, 9, 0)
    for i in range(8):
        check(plugin, t0 + timedelta(minutes=40 * i))
    titles = [props["msgTitle"] for _, props in pushover.sent]
    assert len([t for t in titles if "would need attention" in t]) == 1
    assert len([t for t in titles if "would need attention" not in t]) == 2   # max_per_day
    assert all(t.startswith("[DRY RUN]") for t in titles)


def test_the_dry_count_starts_again_the_next_day(indigo_mod, plugin, pushover):
    setup(indigo_mod, plugin, dry=True)
    t0 = datetime(2026, 9, 27, 9, 0)
    for i in range(4):
        check(plugin, t0 + timedelta(minutes=40 * i))
    before = len(pushover.sent)
    check(plugin, t0 + timedelta(days=1))
    assert len(pushover.sent) == before + 1


def test_dry_runs_do_not_use_up_live_restarts(indigo_mod, plugin, pushover):
    """Switching to LIVE starts from the real history, not the pretend one."""
    watched = setup(indigo_mod, plugin, dry=True)
    t0 = datetime(2026, 9, 27, 9, 0)
    for i in range(4):
        check(plugin, t0 + timedelta(minutes=40 * i))
    plugin.watchdog_dry_run = False
    check(plugin, t0 + timedelta(minutes=200))
    assert watched.restarts == 1


def test_live_behaviour_is_unchanged(indigo_mod, plugin, pushover):
    watched = setup(indigo_mod, plugin, dry=False)
    t0 = datetime(2026, 9, 27, 9, 0)
    check(plugin, t0)
    check(plugin, t0 + timedelta(minutes=10))      # cooldown
    check(plugin, t0 + timedelta(minutes=40))
    check(plugin, t0 + timedelta(minutes=80))      # over the cap of 2
    check(plugin, t0 + timedelta(minutes=120))
    assert watched.restarts == 2
    titles = [props["msgTitle"] for _, props in pushover.sent]
    assert len([t for t in titles if "needs attention" in t]) == 1
