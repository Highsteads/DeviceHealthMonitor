#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_menus_and_callbacks.py
# Description: Every <CallbackMethod> named in the bundle's XML exists on Plugin, and
#              every menu item runs against the fake Indigo without raising. A
#              misspelt callback only shows up when someone picks the menu item.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

import glob
import os
import xml.etree.ElementTree as ET

import pytest

from conftest import FakeDevice, SERVER_PLUGIN

XML_FILES  = sorted(glob.glob(os.path.join(SERVER_PLUGIN, "*.xml")))
MENU_XML   = os.path.join(SERVER_PLUGIN, "MenuItems.xml")
Z2M        = "com.clives.indigoplugin.z2mbridge"


def _callbacks():
    """(file, method name) for every CallbackMethod and every method= attribute."""
    found = []
    for path in XML_FILES:
        root = ET.parse(path).getroot()
        for el in root.iter("CallbackMethod"):
            if (el.text or "").strip():
                found.append((os.path.basename(path), el.text.strip()))
        for el in root.iter():
            for attr in ("method", "validationMethod"):
                if el.get(attr):
                    found.append((os.path.basename(path), el.get(attr)))
    return found


def _menu_ids():
    root = ET.parse(MENU_XML).getroot()
    return [(m.get("id"), m.findtext("CallbackMethod").strip())
            for m in root.iter("MenuItem")
            if m.get("isSeparator") != "true"]


def test_there_are_callbacks_to_check():
    # A glob that matched nothing would make the next test pass vacuously.
    assert _callbacks(), "no callbacks found in the XML — the check is not checking"


def test_every_xml_callback_exists_on_plugin(plugin_mod):
    missing = [(f, name) for f, name in _callbacks()
               if not callable(getattr(plugin_mod.Plugin, name, None))]
    assert not missing, f"named in XML but not defined in plugin.py: {missing}"


def test_menu_item_ids_are_unique():
    ids = [m.get("id") for m in ET.parse(MENU_XML).getroot().iter("MenuItem")]
    assert len(ids) == len(set(ids)), f"duplicate MenuItem ids: {ids}"


@pytest.mark.parametrize("menu_id, method", _menu_ids())
def test_every_menu_item_runs(plugin_mod, plugin, pushover, menu_id, method):
    """Runs each menu callback once with a latched device present, so the
    'show' and 'clear' menus have something to walk over."""
    # plugin_utils.log_startup_banner reads these two. Values as ApplianceMonitor's
    # fake uses them; set here rather than in the shared conftest.
    plugin_mod.indigo.server.version    = "2025.2.0"
    plugin_mod.indigo.server.apiVersion = "3.8"
    plugin_mod.indigo.devices[1] = FakeDevice(
        1, "Dead Sensor", Z2M, battery=50,
        states={"availability": "online"}, hours_since_comm=100)
    plugin._run_scan()
    assert 1 in plugin.alerted
    getattr(plugin, method)({}, menu_id)          # must not raise
