#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    conftest.py
# Description: Test seam for Device Health Monitor. Installs a fake `indigo` module
#              into sys.modules BEFORE plugin.py is imported, so the plugin can be
#              exercised with no Indigo server and no hardware.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import logging
import os
import sys
import types
from datetime import datetime, timedelta

import pytest

REPO_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PLUGIN = os.path.join(
    REPO_ROOT, "DeviceHealthMonitor.indigoPlugin", "Contents", "Server Plugin"
)

def ago(hours):
    """A timestamp `hours` in the past, as of construction.

    The three threshold checks call _hours_since() with no injected clock, so a
    fake device has to be anchored to real time. The measured age therefore comes
    out a few milliseconds ABOVE the nominal figure — fine, because no test sits
    on a threshold boundary. _hours_since itself is tested with an injected clock.
    """
    return datetime.now() - timedelta(hours=hours)


# ==========================================================================
# Fake Indigo object model
#
# Only the surface plugin.py actually touches. A fake that drifts from the
# real API is worse than no fake at all.
# ==========================================================================

class FakeDevice:
    def __init__(self, dev_id, name, plugin_id, states=None, hours_since_comm=None,
                 hours_since_changed=None, battery=None, error_state="",
                 enabled=True, configured=True):
        self.id         = dev_id
        self.name       = name
        self.pluginId   = plugin_id
        self.states     = dict(states or {})
        self.enabled    = enabled
        self.configured = configured
        self.errorState = error_state
        self.batteryLevel       = battery
        self.lastSuccessfulComm = (None if hours_since_comm is None
                                   else ago(hours_since_comm))
        self.lastChanged        = (None if hours_since_changed is None
                                   else ago(hours_since_changed))


class FakeCollection(dict):
    """Stands in for indigo.devices.

    Real Indigo yields device OBJECTS when iterated, while a plain dict yields
    keys — plugin.py does `for dev in indigo.devices`, so without this override
    every scan test would silently walk a list of ints and check nothing.
    """

    def __iter__(self):
        return iter(list(self.values()))


class FakeServer:
    def __init__(self):
        self.lines   = []   # [(message, level)]
        self.plugins = {}
        self.saved_prefs = 0

    def log(self, message, type=None, level=None, isError=False):
        self.lines.append((message, level))

    def getPlugin(self, plugin_id):
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            raise KeyError(plugin_id)
        return plugin

    def savePluginPrefs(self):
        self.saved_prefs += 1

    def getInstallFolderPath(self):
        return "/tmp/fake-indigo"

    def messages_at(self, level):
        return [m for m, lvl in self.lines if lvl == level]


class FakePushoverPlugin:
    def __init__(self, enabled=True, raises=False):
        self._enabled = enabled
        self.raises   = raises
        self.sent     = []

    def isEnabled(self):
        return self._enabled

    def executeAction(self, action_id, props=None):
        if self.raises:
            raise RuntimeError("pushover exploded")
        self.sent.append((action_id, dict(props or {})))


class FakePluginBase:
    """Minimal stand-in for indigo.PluginBase."""

    class StopThread(Exception):
        pass

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        self.pluginId          = pluginId
        self.pluginDisplayName = pluginDisplayName
        self.pluginVersion     = pluginVersion
        self.pluginPrefs       = pluginPrefs
        self.logger            = logging.getLogger("devicehealthmonitor.test")
        self.logger.addHandler(logging.NullHandler())
        self.slept             = []

    def sleep(self, seconds):
        self.slept.append(seconds)


def _build_fake_indigo():
    ind = types.ModuleType("indigo")
    ind.PluginBase = FakePluginBase
    ind.Dict       = dict
    ind.List       = list
    ind.devices    = FakeCollection()
    ind.server     = FakeServer()
    return ind


# ==========================================================================
# Fixtures
# ==========================================================================

@pytest.fixture
def indigo_mod(monkeypatch):
    """A fresh fake indigo per test, with plugin.py re-imported against it."""
    ind = _build_fake_indigo()
    monkeypatch.setitem(sys.modules, "indigo", ind)
    if SERVER_PLUGIN not in sys.path:
        sys.path.insert(0, SERVER_PLUGIN)
    for mod in ("plugin", "plugin_utils"):
        sys.modules.pop(mod, None)
    return ind


@pytest.fixture
def plugin_mod(indigo_mod, tmp_path, monkeypatch):
    """plugin.py with every on-disk config path redirected into tmp_path.

    __init__ SEEDS both the quiet-devices and watchdog files when they are
    absent, so without this a test run would write into the real
    ~/Documents/Indigo folder.
    """
    import plugin
    monkeypatch.setattr(plugin, "EXCLUSIONS_FILE",
                        str(tmp_path / "exclusions.json"))
    monkeypatch.setattr(plugin, "QUIET_DEVICES_FILE",
                        str(tmp_path / "quiet_devices.json"))
    monkeypatch.setattr(plugin, "WATCHDOG_CONFIG_FILE",
                        str(tmp_path / "watchdog_plugins.json"))
    return plugin


@pytest.fixture
def prefs():
    return {}


@pytest.fixture
def plugin(plugin_mod, prefs):
    return plugin_mod.Plugin(
        "com.clives.indigoplugin.device-health-monitor",
        "Device Health Monitor",
        "2.3.0",
        prefs,
    )


@pytest.fixture
def pushover(indigo_mod, plugin_mod):
    """A working Pushover plugin registered under the id plugin.py looks up."""
    fake = FakePushoverPlugin()
    indigo_mod.server.plugins[plugin_mod.PUSHOVER_PLUGIN_ID] = fake
    return fake
