#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_changelog.py
# Description: docs/changelog.md (the published Version history page) has an entry
#              for the version in Info.plist, and that entry is the newest one.
#              test_version_consistency.py checks the README; nothing checked this page.
# Author:      CliveS & Claude Opus 5.5
# Date:        01-11-2026
# Version:     1.0

import glob
import os
import plistlib
import re

REPO      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(REPO, "docs", "changelog.md")
HEADING   = re.compile(r"^##\s+v?(\d+(?:\.\d+)+)\b", re.M)


def _plist_version():
    plists = glob.glob(os.path.join(REPO, "*.indigoPlugin", "Contents", "Info.plist"))
    assert len(plists) == 1, f"expected one Info.plist, found {plists}"
    with open(plists[0], "rb") as handle:
        return plistlib.load(handle)["PluginVersion"]


def _versions():
    with open(CHANGELOG, encoding="utf-8") as handle:
        return HEADING.findall(handle.read())


def test_changelog_exists_and_has_versions():
    assert os.path.isfile(CHANGELOG), "docs/changelog.md is missing"
    assert _versions(), "no '## x.y.z' headings found in docs/changelog.md"


def test_changelog_has_an_entry_for_this_version():
    want = _plist_version()
    assert want in _versions(), f"docs/changelog.md has no '## {want}' entry"


def test_this_version_is_the_newest_entry():
    want = _plist_version()
    assert _versions()[0] == want, (
        f"the first entry in docs/changelog.md is {_versions()[0]}, Info.plist says {want}")
