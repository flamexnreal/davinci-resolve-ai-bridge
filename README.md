# DaVinci Resolve AI Bridge

[![npm version](https://img.shields.io/npm/v/davinci-resolve-ai-bridge-mcp.svg)](https://www.npmjs.com/package/davinci-resolve-ai-bridge-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Resolve AI Bridge is an open-source local Model Context Protocol (MCP) bridge that lets AI coding assistants (**Claude**, **Claude Code**, **Antigravity**, **Cursor**, **Windsurf**, **Codex**, **VS Code**) inspect and edit projects open in **DaVinci Resolve** (Free and Studio).

**Prerequisite:** Requires **Python 3.10 or newer** (download from [python.org/downloads](https://www.python.org/downloads/) if not already on your computer).

---

## ⚡ Quick Setup

### Option A: Run directly with npx (Recommended for Node / npm users)

```bash
npx davinci-resolve-ai-bridge-mcp
```

### Option B: One-Line Shell Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/flamexnreal/davinci-resolve-ai-bridge-mcp/main/install.sh | bash
```

**Windows PowerShell:**
```powershell
irm https://raw.githubusercontent.com/flamexnreal/davinci-resolve-ai-bridge-mcp/main/install.ps1 | iex
```

*(Alternatively, if you cloned the repository or downloaded the ZIP, double-click `install-macos.command` / `install-windows.bat` or run `python3 install.py`).*

The installer sets up the local isolated runtime environment, installs dependencies, and automatically configures detected AI tools (Claude Desktop, Cursor, Windsurf, VS Code, Claude Code, Codex, and Antigravity).

---

## 🎬 How It Works

1. **Open DaVinci Resolve** and open any project or timeline.
2. **Direct attach (default)**: The bridge connects automatically through Resolve's native scripting interface.
3. **Fallback launcher**: If your build requires the internal console, choose **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge** in Resolve.

---

## 🤖 MCP Client Configuration

If you are adding the MCP server manually to your AI client configuration:

### Claude Desktop (`claude_desktop_config.json`) / Cursor / Antigravity

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

### Claude Code CLI

```bash
claude mcp add resolve-ai-bridge -- resolve-ai-bridge
```

---

## 🛠️ Available MCP Tools

| Tool | Description |
| :--- | :--- |
| **`resolve_status`** | Check bridge connection, Resolve version, active project, and timeline. |
| **`timeline_overview`** | Inspect tracks, clips, stable item IDs (`V1.1`, `V2.1`), timecode, and markers. |
| **`timeline_frame`** | Capture a visual frame snapshot at the playhead or specified timecode. |
| **`project_info`** | Get project frame rate, resolution, and timeline counts. |
| **`list_timelines`** / **`open_timeline`** / **`create_timeline`** | Create, switch, and list timelines. |
| **`list_media`** / **`import_media`** / **`append_media`** | Search, import, and place media pool assets. |
| **`add_image`** | Place still images or graphics overlays with custom duration and track target. |
| **`set_clip_transform`** | Modify pan, tilt, zoom, rotation, opacity, and retiming properties. |
| **`split_clip`** | Razor cut clips at specific frame numbers, timecodes, or playhead position. |
| **`animate_zoom`** | Apply keyframed zoom in/out Fusion compositions across clip ranges. |
| **`insert_title`** | Add customizable text titles directly onto the timeline. |
| **`add_marker`** / **`delete_marker`** | Place and remove timeline markers with color tags. |
| **`set_clip_property`** / **`set_clip_color`** / **`set_clip_enabled`** | Inspect and toggle clip parameters. |
| **`render_current_timeline`** | Start background timeline export with named presets. |

---

## 🎨 Motion Graphics with Remotion

For programmatic motion graphics, lower thirds, animated titles, and video overlays, using [Remotion](https://www.remotion.dev/) (React-based video) alongside this bridge is recommended. AI coding agents can generate React components with precise timing, animations, typography, and layout, render them to video files, and place them directly onto your DaVinci Resolve timeline using `append_media` or `add_image`.

```bash
# 1. Create a motion graphics project
npx create-video@latest --yes --blank motion-graphics
cd motion-graphics
npm install

# 2. Add Remotion AI agent skills
npx -y skills@latest add remotion-dev/skills -g -y
```

See [`docs/REMOTION.md`](./docs/REMOTION.md) for full workflows and rendering instructions.

---

## ⚖️ Free vs Studio Version

Blackmagic Design's scripting APIs provide a common superset for both the Free and Studio versions of DaVinci Resolve. No feature in this bridge requires Studio-only tools. If external scripting is disabled in Resolve Preferences, the bridge falls back to the internal Console worker and all tools behave identically.

---

## 🔍 Verification & Troubleshooting

Run the diagnostic tool before editing files:

```bash
python3 tools/doctor.py
```

- **Bridge reported offline**: Ensure DaVinci Resolve is open with a project. Check **Preferences > System > General > External scripting using** is set to **Local**. If needed, click **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge**.
- **Missing Scripts Menu**: Fully quit and reopen DaVinci Resolve so it rescans the script directories.
- Detailed troubleshooting guides are available in [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md).

---

## 📄 License

MIT. See [`LICENSE`](./LICENSE).
