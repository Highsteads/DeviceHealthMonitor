#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_plugin_info.py
# Description: Show Plugin Info lists every kind of device the plugin watches. Until
#              2.11.0 the list was typed out by hand and missed ESPHome and RAMSES ESP.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0


def test_every_watched_plugin_has_a_label(plugin_mod):
    assert set(plugin_mod.MONITORED_LABELS) == set(plugin_mod.MONITORED_PLUGINS)


def test_the_label_names_all_seven(plugin_mod):
    label = plugin_mod.monitored_protocols_label()
    for name in ("Z2M", "ShellyDirect", "ShellyGen1", "Z-Wave", "Ecowitt",
                 "ESPHome", "RAMSES ESP"):
        assert name in label


def test_show_plugin_info_uses_it(plugin_mod, plugin, monkeypatch):
    seen = {}

    def fake_banner(plugin_id, name, version, extras=None):
        seen["extras"] = dict(extras or [])

    monkeypatch.setattr(plugin_mod, "log_startup_banner", fake_banner)
    plugin.showPluginInfo()
    assert "ESPHome" in seen["extras"]["Protocols:"]
    assert "RAMSES ESP" in seen["extras"]["Protocols:"]
