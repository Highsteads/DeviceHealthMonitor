#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_watchdog_rules_file.py
# Description: From 2.11.0 the watchdog rules file holds only the user's own edits.
#              Until then a NEW file was seeded with every built-in limit and the
#              discovered default, so later built-in changes never reached that
#              install and the "Auto-discovered default stale threshold" setting did
#              nothing after the first run. These pin the fix and the one-shot
#              reconciliation of files written by 2.3.0 to 2.10.2.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import json
import os

ECOFLOW = "com.clives.indigoplugin.ecoflowcloud"
Z2M     = "com.clives.indigoplugin.z2mbridge"
HUMAX   = "com.clives.indigoplugin.humaxaura"
EMAIL   = "com.indigodomo.email"
OTHER   = "com.someone.else"


def write_watchdog(plugin_mod, doc):
    os.makedirs(os.path.dirname(plugin_mod.WATCHDOG_CONFIG_FILE), exist_ok=True)
    with open(plugin_mod.WATCHDOG_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f)


def read_watchdog(plugin_mod):
    with open(plugin_mod.WATCHDOG_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def schema2_file(plugin_mod, stale=60.0):
    """A file exactly as 2.3.0 to 2.10.2 wrote it on first run."""
    return {
        "schema":    2,
        "overrides": {pid: dict(pol) for pid, pol in plugin_mod.WATCHDOG_OVERRIDES.items()},
        "exclude":   sorted(plugin_mod.WATCHDOG_DENYLIST),
        "include":   [],
        "discovered_default": {"stale_minutes": stale, "cooldown_minutes": 30,
                               "max_per_day": 3, "enabled": True},
    }


def make_plugin(plugin_mod, prefs):
    return plugin_mod.Plugin("com.clives.indigoplugin.device-health-monitor",
                             "Device Health Monitor", "2.11.0", prefs)


# ---------------------------------------------------------------- fresh file

class TestAFreshFileHoldsNoCopies:

    def test_the_new_file_has_empty_sections(self, plugin_mod, plugin):
        doc = read_watchdog(plugin_mod)
        assert doc["schema"] == plugin_mod.WATCHDOG_SCHEMA
        assert doc["overrides"] == {}
        assert doc["exclude"] == []
        assert doc["discovered_default"] == {}

    def test_the_built_ins_still_apply_with_an_empty_file(self, plugin_mod, plugin):
        assert plugin.watchdog_overrides[Z2M] == plugin_mod.WATCHDOG_OVERRIDES[Z2M]
        assert plugin_mod.WATCHDOG_DENYLIST <= plugin.watchdog_exclude

    def test_a_later_built_in_change_reaches_an_existing_file(self, plugin_mod, plugin,
                                                              monkeypatch):
        """The fault: a file froze the limits of the day it was written."""
        changed = dict(plugin_mod.WATCHDOG_OVERRIDES)
        changed[Z2M] = dict(changed[Z2M], stale_minutes=7)
        monkeypatch.setattr(plugin_mod, "WATCHDOG_OVERRIDES", changed)
        plugin._load_watchdog_config()
        assert plugin.watchdog_overrides[Z2M]["stale_minutes"] == 7


# ------------------------------------------------ the dialog's stale threshold

class TestTheDialogSettingWorks:

    def test_changing_it_after_the_file_exists_takes_effect(self, plugin_mod, plugin):
        assert os.path.exists(plugin_mod.WATCHDOG_CONFIG_FILE)
        plugin.closedPrefsConfigUi({"watchdogDefaultStaleMin": "15"}, False)
        assert plugin.watchdog_discovered_default["stale_minutes"] == 15

    def test_a_figure_typed_into_the_file_is_ignored_and_said_once(self, plugin_mod,
                                                                    plugin, indigo_mod):
        doc = read_watchdog(plugin_mod)
        doc["discovered_default"] = {"stale_minutes": 5}
        write_watchdog(plugin_mod, doc)
        plugin._load_watchdog_config()
        plugin._load_watchdog_config()
        assert plugin.watchdog_discovered_default["stale_minutes"] == 60
        warned = [m for m in indigo_mod.server.messages_at(30) if "not used" in m]
        assert len(warned) == 1

    def test_the_file_can_still_change_the_other_discovered_limits(self, plugin_mod,
                                                                    plugin):
        doc = read_watchdog(plugin_mod)
        doc["discovered_default"] = {"max_per_day": 1}
        write_watchdog(plugin_mod, doc)
        plugin._load_watchdog_config()
        assert plugin.watchdog_discovered_default["max_per_day"] == 1


# ------------------------------------------------ reconciling a schema-2 file

class TestPureV3Migration:

    def run(self, plugin_mod, data, dialog=60.0):
        return plugin_mod.migrate_watchdog_config_v3(
            data, plugin_mod.WATCHDOG_SHIPPED_OVERRIDES, plugin_mod.WATCHDOG_DENYLIST,
            plugin_mod.DISCOVERED_DEFAULT, dialog)

    def test_every_seeded_override_is_dropped(self, plugin_mod):
        migrated, report = self.run(plugin_mod, schema2_file(plugin_mod))
        assert migrated["overrides"] == {}
        assert ECOFLOW in report["dropped"]

    def test_an_older_shipped_value_counts_as_a_seed(self, plugin_mod):
        data = schema2_file(plugin_mod)
        data["overrides"][HUMAX]["stale_minutes"] = 1440      # the 2.3.0 value
        migrated, _ = self.run(plugin_mod, data)
        assert HUMAX not in migrated["overrides"]

    def test_an_edited_override_is_kept(self, plugin_mod):
        data = schema2_file(plugin_mod)
        data["overrides"][Z2M]["stale_minutes"] = 3
        data["overrides"][OTHER] = {"stale_minutes": 42}
        migrated, report = self.run(plugin_mod, data)
        assert migrated["overrides"][Z2M]["stale_minutes"] == 3
        assert migrated["overrides"][OTHER] == {"stale_minutes": 42}
        assert Z2M in report["kept"]

    def test_copies_of_the_never_restart_list_go_but_own_additions_stay(self, plugin_mod):
        data = schema2_file(plugin_mod)
        data["exclude"].append(OTHER)
        migrated, report = self.run(plugin_mod, data)
        assert migrated["exclude"] == [OTHER]
        assert EMAIL in report["dropped_excludes"]

    def test_the_discovered_default_loses_its_copies(self, plugin_mod):
        migrated, _ = self.run(plugin_mod, schema2_file(plugin_mod))
        assert migrated["discovered_default"] == {}

    def test_an_edited_discovered_limit_is_kept(self, plugin_mod):
        data = schema2_file(plugin_mod)
        data["discovered_default"]["max_per_day"] = 1
        migrated, _ = self.run(plugin_mod, data)
        assert migrated["discovered_default"] == {"max_per_day": 1}

    def test_a_hand_edited_file_stale_is_handed_to_the_dialog(self, plugin_mod):
        _, report = self.run(plugin_mod, schema2_file(plugin_mod, stale=45), dialog=60.0)
        assert report["adopt_stale"] == 45

    def test_a_moved_dialog_is_never_overwritten(self, plugin_mod):
        """The bug case: the dialog was changed and the file's copy outvoted it."""
        _, report = self.run(plugin_mod, schema2_file(plugin_mod, stale=60), dialog=15.0)
        assert report["adopt_stale"] is None

    def test_it_does_not_mutate_the_input(self, plugin_mod):
        data  = schema2_file(plugin_mod)
        again = json.loads(json.dumps(data))
        self.run(plugin_mod, data)
        assert data == again

    def test_it_stamps_the_schema(self, plugin_mod):
        migrated, _ = self.run(plugin_mod, schema2_file(plugin_mod))
        assert migrated["schema"] == plugin_mod.WATCHDOG_SCHEMA == 3


class TestLoadingASchema2File:

    def test_a_later_built_in_change_now_reaches_it(self, plugin_mod, tmp_path,
                                                    monkeypatch):
        write_watchdog(plugin_mod, schema2_file(plugin_mod))
        changed = dict(plugin_mod.WATCHDOG_OVERRIDES)
        changed[Z2M] = dict(changed[Z2M], stale_minutes=7)
        monkeypatch.setattr(plugin_mod, "WATCHDOG_OVERRIDES", changed)
        p = make_plugin(plugin_mod, {})
        assert p.watchdog_overrides[Z2M]["stale_minutes"] == 7
        assert read_watchdog(plugin_mod)["schema"] == plugin_mod.WATCHDOG_SCHEMA
        assert os.path.exists(f"{plugin_mod.WATCHDOG_CONFIG_FILE}.bak-v2")

    def test_the_bug_case_the_dialog_now_wins(self, plugin_mod):
        write_watchdog(plugin_mod, schema2_file(plugin_mod, stale=60))
        p = make_plugin(plugin_mod, {"watchdogDefaultStaleMin": "15"})
        assert p.watchdog_discovered_default["stale_minutes"] == 15

    def test_a_hand_edited_file_figure_moves_into_the_dialog(self, plugin_mod,
                                                             indigo_mod):
        write_watchdog(plugin_mod, schema2_file(plugin_mod, stale=45))
        prefs = {}
        p = make_plugin(plugin_mod, prefs)
        assert p.watchdog_discovered_default["stale_minutes"] == 45
        assert prefs["watchdogDefaultStaleMin"] == "45"
        assert indigo_mod.server.saved_prefs >= 1
        assert "stale_minutes" not in read_watchdog(plugin_mod)["discovered_default"]

    def test_both_moved_and_different_the_dialog_wins_with_a_warning(self, plugin_mod,
                                                                     indigo_mod):
        write_watchdog(plugin_mod, schema2_file(plugin_mod, stale=45))
        p = make_plugin(plugin_mod, {"watchdogDefaultStaleMin": "20"})
        assert p.watchdog_discovered_default["stale_minutes"] == 20
        assert any("dialog's figure applies" in m
                   for m in indigo_mod.server.messages_at(30))

    def test_a_second_load_is_a_no_op(self, plugin_mod):
        write_watchdog(plugin_mod, schema2_file(plugin_mod))
        p = make_plugin(plugin_mod, {})
        first = read_watchdog(plugin_mod)
        mtime = os.path.getmtime(plugin_mod.WATCHDOG_CONFIG_FILE)
        p._load_watchdog_config()
        assert read_watchdog(plugin_mod) == first
        assert os.path.getmtime(plugin_mod.WATCHDOG_CONFIG_FILE) == mtime

    def test_the_shipped_record_covers_every_built_in(self, plugin_mod):
        """Every current built-in must be recognised as a seed, or a 2.10.2 file
        would keep a frozen copy of it."""
        for pid, pol in plugin_mod.WATCHDOG_OVERRIDES.items():
            assert pol in plugin_mod.WATCHDOG_SHIPPED_OVERRIDES[pid], pid
