---
title: When something goes wrong
nav_order: 9
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## No message reaches my phone

The Event Log shows **[OFFLINE]** lines, but nothing arrives.

- Look in the Event Log for a line starting **Pushover failed** or **NOT DELIVERED**. It gives the reason.
- Check the Pushover plugin is installed and enabled, and that it sends messages when you use it on its own.

The plugin keeps trying at every check until a message gets through, so once Pushover works again the waiting alert arrives by itself.

## A healthy device keeps being reported

- **A sensor that only reports when something happens**, such as a door or a cupboard sensor — give it a quiet device entry with a longer silence limit.
- **A device that is switched off on purpose**, such as a plug turned off at the wall — give it an away tolerance.
- **A device you never want to hear about** — add it to the left-out list.

The [Quiet, away and left-out devices](quiet-and-excluded.md) page explains all three.

## The log says a Zigbee device is FLAPPING

The plugin has held back an offline verdict on this device four or more times today, each time because the device had been heard from recently or was still being asked whether it was there. It is not sent to your phone, but a device that keeps being called offline has a radio link worth a look.

## A Z-Wave node has ignored three status requests

The log says a node **has ignored 3 status requests** and that the plugin will not ask again. Some Z-Wave nodes refuse status requests altogether, so the plugin stops asking rather than fill the log. If the node has in fact died, Indigo marks it in error the next time anything sends it a command, and the plugin reports it then. The plugin starts asking again as soon as the node next speaks.

## A dead mains Z-Wave node is never reported

Check **Mains device quiet time** in the settings is not 0. With it at 0, the plugin never asks a quiet mains node whether it is there, and a mains node is never reported for being quiet.

## The watchdog says it would restart a plugin

The message starts **[DRY RUN]**. The watchdog is in its trial mode and has not restarted anything.

- If the plugin really had stopped working, the watchdog was right, and you can untick **Dry-run** in the settings so it restarts plugins for real.
- If the plugin was fine and simply quiet, give it a longer time limit, or `null` for never, in `watchdog_plugins.json`, or add it to that file's **exclude** list. The [plugin watchdog](watchdog.md#changing-the-rules) page explains how.

## A plugin "needs attention"

The watchdog has restarted the plugin as many times as it is allowed today, and it is still failing, so it has stopped trying. Something is wrong that a restart does not fix — have a look at that plugin's own lines in the Event Log. Once it is sorted out, choose **Reset Watchdog Restart Counters** so the watchdog can restart it again if it needs to.

## Changing Auto-discovered default stale threshold has no effect

Once the watchdog's rules file exists, the figure in that file is used instead. Change `stale_minutes` under **discovered_default** in `watchdog_plugins.json`.

## The log says an entry in the quiet devices file was skipped

One entry in `quiet_devices.json` could not be understood. The log line names it and says what is wrong — a word where a number should be, or no ID or name. The other entries still work. Put that one right and it is picked up at the next check.

## Still stuck?

Choose **Plugins → Device Health Monitor → Show Plugin Info**, copy the lines it writes to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/DeviceHealthMonitor/issues).
