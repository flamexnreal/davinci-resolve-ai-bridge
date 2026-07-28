# Release Notes

## v1.1.0 — Zero-paste setup, images on the timeline

Version 1.0 worked, but two things tripped people up: you had to hand-edit `YOUR_NAME` into the Console line, and you had to repaste that line every single time you opened DaVinci Resolve. Both are gone.

### Nothing to edit

The Console line is now one portable command that is identical on every computer and every operating system:

```python
import os;exec(open(os.path.expanduser("~/.resolve-ai-bridge/ResolveConsole.py"),encoding="utf-8").read())
```

Python expands `~` inside Resolve's own interpreter, so there is no user name to substitute and no personal path in anything you copy.

### Nothing to repaste

The bridge now picks its own route into Resolve:

- **Direct attach (default).** The MCP server talks to the running Resolve through Blackmagic's native scripting library. Open Resolve and your AI is connected. To turn the bridge off, disconnect the MCP server in your AI client.
- **One-click launcher (fallback).** The installer adds **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge**, plus **Bridge Status** and **Stop AI Bridge**. Restart Resolve once after installing so it picks up the new menu.
- **Console line (last resort).** Still there, still works, now with nothing to edit.

`resolve_status` and `tools/doctor.py` both report which route is live and why, so an offline bridge produces an actionable message instead of a shrug.

### Images and overlays

An AI client can now put a picture on your timeline and place it:

- `add_image` imports a still and places it with a real duration on a chosen track, creating the track when needed. Appending a still as ordinary footage produced a one-frame clip; this does not.
- `set_clip_transform` and `get_clip_transform` move, scale, rotate, crop, fade, and blend any timeline item, in pixels or as a percentage of frame size.
- `add_track` and `set_track_name` create and label the overlay tracks images need.

Example prompt:

> Put /Users/me/Desktop/logo.png on video track 2 for 4 seconds at the playhead, scaled to 40 percent and tucked into the bottom right corner. Then show me the timeline to confirm it.

### Also new

- `insert_title` inserts a title at the playhead and reports honestly whether its text could be set through the API.
- `open_page` switches Resolve to a page so you can see what changed.
- `list_render_presets` removes the guesswork before queueing a render.
- `timeline_overview` now reports track enabled state and the timeline frame rate; `list_media` reports frame counts and resolution.
- Every operation now lives in one shared module, so both transports execute exactly the same code.
- The installer verifies whether a direct attach works on your machine and tells you the result, and the doctor round-trips a real request over whichever transport is live.

### Compatibility

- Works with **free DaVinci Resolve**. Blackmagic's scripting documentation states the scripting APIs are a common superset for the free and Studio versions, and no tool here depends on a Studio-only or paid AI feature.
- If a build or preference refuses a direct attach, the bridge silently falls back to the Console worker and every tool behaves identically.
- Loading Resolve's native module is probed in a disposable subprocess first, so an incompatible Python can never take down the MCP server.

### Upgrading from 1.0.0

1. Download this release and run `python3 install.py` (`py install.py` on Windows). Your existing token is preserved, so your AI client's MCP entry keeps working.
2. Restart DaVinci Resolve once so the Workspace > Scripts menu appears.
3. Run `python3 tools/doctor.py` with Resolve open.

No breaking changes to the MCP tool names from 1.0.0. Six tools were added.
