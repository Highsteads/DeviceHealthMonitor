#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_watchdog_migration.py
# Description: The watchdog config file OVERLAYS the code and was only written
#              when absent, so later threshold changes never reached an existing
#              install. These pin the one-shot reconciliation that undoes that
#              without discarding real user edits.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import json
import os

ECOFLOW = "com.clives.indigoplugin.ecoflowcloud"
Z2M     = "com.clives.indigoplugin.z2mbridge"
MQTTX   = "com.clives.indigoplugin.mqttexplorerbridge"

# The file as it actually sat on disk since 29-May-2026.
V1_FILE = {
    "_comment": "Device Health Monitor — plugin watchdog policy (auto-discovering).",
    "overrides": {
        ECOFLOW: {"stale_minutes": 720, "cooldown_minutes": 30, "max_per_day": 3, "enabled": True},
        Z2M:     {"stale_minutes": 5,   "cooldown_minutes": 15, "max_per_day": 6, "enabled": True},
        MQTTX:   {"stale_minutes": 10,  "cooldown_minutes": 20, "max_per_day": 4, "enabled": True},
    },
    "exclude": ["com.perceptiveautomation.indigoplugin.zwave", "com.indigodomo.email"],
    "include": [],
    "discovered_default": {"stale_minutes": 60.0, "cooldown_minutes": 30,
                           "max_per_day": 3, "enabled": True},
}


def test_an_untouched_seed_is_dropped_so_current_code_wins(plugin_mod):
    migrated, dropped, kept = plugin_mod.migrate_watchdog_config(
        V1_FILE, plugin_mod.WATCHDOG_V1_BASELINE)
    assert ECOFLOW in dropped
    assert ECOFLOW not in migrated["overrides"]


def test_a_genuinely_edited_policy_is_kept(plugin_mod):
    data = json.loads(json.dumps(V1_FILE))
    data["overrides"][Z2M]["stale_minutes"] = 3          # user tightened it
    migrated, dropped, kept = plugin_mod.migrate_watchdog_config(
        data, plugin_mod.WATCHDOG_V1_BASELINE)
    assert Z2M in kept
    assert migrated["overrides"][Z2M]["stale_minutes"] == 3


def test_an_entry_for_a_removed_plugin_is_dropped(plugin_mod):
    migrated, dropped, _ = plugin_mod.migrate_watchdog_config(
        V1_FILE, plugin_mod.WATCHDOG_V1_BASELINE)
    assert MQTTX in dropped
    assert MQTTX not in migrated["overrides"]


def test_a_plugin_we_never_seeded_is_kept(plugin_mod):
    data = json.loads(json.dumps(V1_FILE))
    data["overrides"]["com.someone.else"] = {"stale_minutes": 42}
    migrated, _, kept = plugin_mod.migrate_watchdog_config(
        data, plugin_mod.WATCHDOG_V1_BASELINE)
    assert "com.someone.else" in kept
    assert migrated["overrides"]["com.someone.else"] == {"stale_minutes": 42}


def test_the_hand_curated_exclude_and_include_survive_verbatim(plugin_mod):
    migrated, _, _ = plugin_mod.migrate_watchdog_config(
        V1_FILE, plugin_mod.WATCHDOG_V1_BASELINE)
    assert migrated["exclude"] == V1_FILE["exclude"]
    assert migrated["include"] == V1_FILE["include"]
    assert migrated["discovered_default"] == V1_FILE["discovered_default"]
    assert migrated["_comment"] == V1_FILE["_comment"]


def test_migration_stamps_the_schema(plugin_mod):
    migrated, _, _ = plugin_mod.migrate_watchdog_config(
        V1_FILE, plugin_mod.WATCHDOG_V1_BASELINE)
    assert migrated["schema"] == plugin_mod.WATCHDOG_SCHEMA


def test_migration_does_not_mutate_the_input(plugin_mod):
    data = json.loads(json.dumps(V1_FILE))
    plugin_mod.migrate_watchdog_config(data, plugin_mod.WATCHDOG_V1_BASELINE)
    assert data == V1_FILE


def test_an_int_float_difference_does_not_look_like_an_edit(plugin_mod):
    """JSON round-tripping can turn 720 into 720.0. That is not a user edit."""
    data = json.loads(json.dumps(V1_FILE))
    data["overrides"][ECOFLOW]["stale_minutes"] = 720.0
    _, dropped, _ = plugin_mod.migrate_watchdog_config(
        data, plugin_mod.WATCHDOG_V1_BASELINE)
    assert ECOFLOW in dropped


# ------------------------------------------------------- the file round-trip

def write_watchdog(plugin_mod, doc):
    os.makedirs(os.path.dirname(plugin_mod.WATCHDOG_CONFIG_FILE), exist_ok=True)
    with open(plugin_mod.WATCHDOG_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f)


def read_watchdog(plugin_mod):
    with open(plugin_mod.WATCHDOG_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_loading_a_v1_file_migrates_it_and_backs_it_up(plugin_mod, plugin):
    write_watchdog(plugin_mod, V1_FILE)
    plugin._load_watchdog_config()

    on_disk = read_watchdog(plugin_mod)
    assert on_disk["schema"] == plugin_mod.WATCHDOG_SCHEMA
    assert ECOFLOW not in on_disk["overrides"]
    assert os.path.exists(f"{plugin_mod.WATCHDOG_CONFIG_FILE}.bak-v1")

    # And the resolved policy now uses the current code default, not the stale 720.
    assert plugin.watchdog_overrides[ECOFLOW]["stale_minutes"] == \
        plugin_mod.WATCHDOG_OVERRIDES[ECOFLOW]["stale_minutes"]


def test_a_second_load_is_a_no_op(plugin_mod, plugin):
    write_watchdog(plugin_mod, V1_FILE)
    plugin._load_watchdog_config()
    first = read_watchdog(plugin_mod)
    mtime = os.path.getmtime(plugin_mod.WATCHDOG_CONFIG_FILE)

    plugin._load_watchdog_config()
    assert read_watchdog(plugin_mod) == first
    assert os.path.getmtime(plugin_mod.WATCHDOG_CONFIG_FILE) == mtime


def test_a_fresh_file_is_written_with_the_schema_so_it_never_migrates(plugin_mod, plugin):
    """__init__ already seeded it; it must carry the marker."""
    assert read_watchdog(plugin_mod)["schema"] == plugin_mod.WATCHDOG_SCHEMA


def test_the_hard_excludes_survive_migration(plugin_mod, plugin):
    write_watchdog(plugin_mod, V1_FILE)
    plugin._load_watchdog_config()
    assert plugin_mod.CLAUDEBRIDGE_ID in plugin.watchdog_exclude
    assert plugin.pluginId in plugin.watchdog_exclude
