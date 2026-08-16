# DaVinci Resolve AI Bridge

Resolve AI Bridge is an open-source local MCP bridge that lets AI coding assistants (Antigravity, Claude, Cursor, Windsurf, Codex, VS Code) inspect and edit projects open in DaVinci Resolve (Free and Studio).

---

## Quick Setup

### 1. Run the installer

macOS:
```bash
python3 install.py
```
*(Or double-click `install-macos.command`)*

Windows PowerShell:
```powershell
py install.py
```
*(Or double-click `install-windows.bat`)*

The installer sets up the local runtime environment, installs dependencies, and automatically configures detected AI tools (Claude Desktop, Cursor, Windsurf, VS Code, Claude Code, Codex, and Antigravity).

### 2. Open DaVinci Resolve

Open DaVinci Resolve and your project.

- **Direct attach (default)**: The bridge connects automatically through Resolve's native scripting interface.
- **Fallback launcher**: If your build requires the internal console, choose **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge** in Resolve.

### 3. Add to your AI client (if not auto-configured)

If you are adding the MCP server manually to an AI client (such as Antigravity or Cursor), use this portable configuration:

```json
{
  "mcpServers": {
    "resolve-ai-bridge": {
      "command": "sh",
      "args": [
        "-c",
        "exec \"$HOME/.resolve-ai-bridge/.venv/bin/python\" \"$HOME/.resolve-ai-bridge/bridge/server.py\""
      ]
    }
  }
}
```

Or using the installed global binary:

```json
{
  "mcpServers": {
    "resolve-ai-bridge": {
      "command": "resolve-ai-bridge"
    }
  }
}
```

### 4. Verify

With Resolve open, run:

```bash
python3 tools/doctor.py
```

Then ask your AI:
> "Call resolve_status and tell me what project is currently open."

---

## Available Tools

- **`resolve_status`**: Check bridge connection, Resolve version, active project, and timeline.
- **`timeline_overview`**: Inspect tracks, clips, stable item IDs (`V1.1`, `V2.1`), timecode, and markers.
- **`project_info`**: Get project frame rate, resolution, and timeline counts.
- **`list_timelines`** / **`open_timeline`** / **`create_timeline`**: Manage timelines.
- **`list_media`** / **`import_media`** / **`append_media`**: Search and import media pool items.
- **`add_image`**: Place still images/overlays with custom duration and track index.
- **`set_clip_transform`**: Adjust pan, tilt, zoom, rotation, opacity, and retiming properties.
- **`split_clip`**: Razor cut clips at specific frame numbers, timecodes, or playhead.
- **`animate_zoom`**: Apply keyframed zoom in/out Fusion compositions across clip ranges.
- **`insert_title`**: Add text titles to the timeline.
- **`add_marker`** / **`delete_marker`**: Place and remove timeline markers.
- **`set_clip_property`** / **`set_clip_color`** / **`set_clip_enabled`**: Clip inspection and toggles.
- **`render_current_timeline`**: Start timeline export with named presets.

---

## Free vs Studio Version

Blackmagic Design's scripting APIs provide a common superset for both the Free and Studio versions of DaVinci Resolve. No feature in this bridge requires Studio-only tools. If external scripting is disabled in Resolve Preferences, the bridge falls back to the internal Console worker and all tools behave identically.

---

## Troubleshooting

Run the diagnostic tool before editing files:

```bash
python3 tools/doctor.py
```

- **Bridge reported offline**: Ensure DaVinci Resolve is open with a project. Check **Preferences > System > General > External scripting using** is set to **Local**. If needed, click **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge**.
- **Missing Scripts Menu**: Fully quit and reopen DaVinci Resolve so it rescans the script directories.
- Detailed troubleshooting guides are available in [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md).

---

## License

MIT. See [`LICENSE`](./LICENSE).
