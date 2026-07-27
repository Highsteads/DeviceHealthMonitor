#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_config_coercion.py
# Description: Indigo re-serialises every saved config value as a STRING, so a
#              cleared numeric field is "" and a cleared checkbox is "false".
#              Bare float() would stop the plugin loading; bool("false") is True.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import pytest


# ------------------------------------------------------------- the helpers

@pytest.mark.parametrize("value,expected", [
    ("", 12.0), (None, 12.0), ("abc", 12.0),
    ("24", 24.0), (24, 24.0), (24.5, 24.5),
    ("0", 0.0),                       # zero is a real value, not "missing"
])
def test_as_float(plugin_mod, value, expected):
    assert plugin_mod._as_float(value, 12) == expected


def test_as_float_coerces_its_fallback_too(plugin_mod):
    """A string default must never leak unconverted into arithmetic."""
    assert plugin_mod._as_float("", "12") == 12.0
    assert isinstance(plugin_mod._as_float("", "12"), float)


@pytest.mark.parametrize("value,expected", [
    ("", 10), (None, 10), ("abc", 10), ("30", 30), (30, 30), ("0", 0),
])
def test_as_int(plugin_mod, value, expected):
    assert plugin_mod._as_int(value, 10) == expected


@pytest.mark.parametrize("value,expected", [
    ("false", False), ("False", False), ("FALSE", False), ("0", False), ("no", False),
    ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
    (False, False), (True, True),
])
def test_as_bool_is_not_fooled_by_the_string_false(plugin_mod, value, expected):
    assert plugin_mod.as_bool(value) is expected


def test_as_bool_uses_the_default_for_blank(plugin_mod):
    assert plugin_mod.as_bool("", default=True) is True
    assert plugin_mod.as_bool(None, default=True) is True


# ------------------------------------------------------------ applied live

def test_blank_numeric_prefs_do_not_stop_the_plugin_loading(plugin_mod):
    """Every one of these used to be a bare float()/int(), so a cleared field
    raised ValueError in __init__ and the plugin never started."""
    blanked = {
        "scanIntervalMinutes":     "",
        "zwave_battery_hours":     "",
        "zwave_mains_hours":       "",
        "ecowitt_hours":           "",
        "z2m_stale_hours":         "",
        "watchdogDefaultStaleMin": "",
    }
    plugin = plugin_mod.Plugin("id", "Device Health Monitor", "2.3.0", blanked)
    assert plugin.scan_interval_sec   == 600
    assert plugin.zwave_battery_hours == 24.0
    assert plugin.ecowitt_hours       == 24.0
    assert plugin.z2m_stale_hours     == 12.0
    assert plugin.watchdog_discovered_stale == 60.0


def test_garbage_numeric_prefs_fall_back_to_the_defaults(plugin_mod):
    plugin = plugin_mod.Plugin("id", "Device Health Monitor", "2.3.0",
                               {"z2m_stale_hours": "twelve", "scanIntervalMinutes": "soon"})
    assert plugin.z2m_stale_hours   == 12.0
    assert plugin.scan_interval_sec == 600


def test_a_saved_dialog_does_not_switch_watchdog_dry_run_back_on(plugin_mod):
    """The trap this closes: Indigo stores a saved checkbox as the STRING
    "false", and bool("false") is True — so one save of the Configure dialog
    would have re-enabled dry-run and quietly disabled every real restart."""
    plugin = plugin_mod.Plugin("id", "Device Health Monitor", "2.3.0",
                               {"watchdogDryRun": "false", "showDebugInfo": "false"})
    assert plugin.watchdog_dry_run is False
    assert plugin.debug is False


def test_absent_watchdog_prefs_keep_their_safe_defaults(plugin_mod):
    plugin = plugin_mod.Plugin("id", "Device Health Monitor", "2.3.0", {})
    assert plugin.watchdog_enabled is True
    assert plugin.watchdog_dry_run is True      # dry-run defaults ON


def test_closedPrefsConfigUi_applies_the_same_guards(plugin_mod, plugin):
    plugin.closedPrefsConfigUi({"z2m_stale_hours": "", "watchdogDryRun": "false"}, False)
    assert plugin.z2m_stale_hours == 12.0
    assert plugin.watchdog_dry_run is False


def test_a_cancelled_dialog_changes_nothing(plugin_mod, plugin):
    plugin.z2m_stale_hours = 99.0
    plugin.closedPrefsConfigUi({"z2m_stale_hours": "1"}, True)
    assert plugin.z2m_stale_hours == 99.0
