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

Not covered: the plugin watchdog's restart machinery (cooldowns, daily caps,
`_assess_plugin_health`) and the menu callbacks.
