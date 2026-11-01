# Device Health Monitor tests

```bash
python3 -m pytest tests -q
```

No Indigo server, no hardware. `conftest.py` installs a fake `indigo` module into
`sys.modules` before `plugin.py` is imported — the plugin does a hard
`import indigo` at module level, so that has to happen first.

Two things about the fake are load-bearing:

- **`FakeCollection.__iter__` yields device objects, not keys.** Real Indigo does,
  and `plugin.py` relies on it (`for dev in indigo.devices`). A plain dict would
  yield ints and every scan test would quietly check nothing.
- **The `plugin_mod` fixture redirects all three config-file paths into `tmp_path`.**
  `__init__` seeds the quiet-devices and watchdog files when they are absent, so
  without that a test run would write into the real `~/Documents/Indigo` folder.

Devices are anchored to real time via `ago(hours)`, because the three threshold
checks call `_hours_since()` with no injected clock. Measured ages therefore land a
few milliseconds above the nominal figure, so no test sits on a boundary.
`_hours_since` itself is tested with an injected clock.

## What is covered

| File | Covers |
|---|---|
| `test_quiet_devices.py` | Parsing the quiet list, id-vs-name resolution, and the override landing on each of the three threshold paths — including that it never suppresses a reported fault |
| `test_alert_latch.py` | A device is latched as "alerted" only once the Pushover was actually delivered |
| `test_watchdog_migration.py` | The one-shot v1 config reconciliation: untouched seeds dropped, real edits kept |
| `test_config_coercion.py` | Blank and garbage config values, and `as_bool` not being fooled by the string `"false"` |

| `test_watchdog_restart.py` | Watchdog verdicts (ok / crashed / wedged / transmit-only / post-restart grace) and the live restart path. a failing restart keeps to the cooldown and cap, a "needs attention" alert is retried until delivered, and the start-up / wake grace (all 2.13.1) |
| `test_menus_and_callbacks.py` | Every callback named in the XML exists in plugin.py, and every menu item runs |
| `test_pushover_delivery.py` | A stopped Pushover plugin is a failed send, and the daily reminder of devices still offline (2.14.0) |
| `test_disabled_devices.py` | A disabled watched device has its latch cleared and is logged when disabled and re-enabled (2.14.1) |
| `test_changelog.py` | `docs/changelog.md` has an entry for the Info.plist version, at the top |
