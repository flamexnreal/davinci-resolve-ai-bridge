# DaVinci Resolve AI Bridge

Resolve AI Bridge is an MIT-licensed local MCP bridge that lets a compatible AI client inspect and control the project currently open in DaVinci Resolve.

**Zero-Configuration Multi-Harness Integration:**
- **Auto-Configuring Installer**: Automatically discovers and registers with Claude Desktop, Cursor, Antigravity, Windsurf, VS Code (Cline/Roo), Codex, and Claude Code.
- **Zero-Token Local Authentication**: Authentication between the MCP server and DaVinci Resolve is automatically and transparently secured via a private local file token (`~/.resolve-ai-bridge/token.txt`). No manual token typing or copying.
- **Portable Zero-Edit Snippet**: Dynamic `$HOME` expansion and global CLI launcher `resolve-ai-bridge` so you never have to replace usernames or home paths.
- **Timeline Clip Editing**: Timeline editing tools (`split_clip`, `animate_zoom`, `set_clip_transform`), image placement, and full track management.

## How it connects

The bridge picks whichever route works, automatically.

| Route | What you do | How it works |
| --- | --- | --- |
| **Direct attach** (default) | Open Resolve | The MCP process talks to the running Resolve through Blackmagic's native scripting library. Nothing runs inside Resolve. |
| **Console launcher helper** | **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge** | Displays the activation command directly in DaVinci Resolve's Console so you can copy and paste it into the Py3 tab. |

`resolve_status` and `tools/doctor.py` both report which route is live.

To turn the bridge off, disconnect or disable the `resolve-ai-bridge` MCP server in your AI client. If a Console worker is running, also use **Stop AI Bridge** in the same menu, or quit Resolve.

There is no hosted bridge account and no network listener. Your AI provider may still process prompts according to its own privacy policy.

## Does it work on free DaVinci Resolve?

Yes. Blackmagic's own scripting README states that "the DaVinci Resolve scripting APIs cover a common superset of functions for both the Free and Studio versions of the application." No tool in this project depends on a Studio-only or paid AI feature. The Console worker route runs inside Resolve's own Console, which the free version has always allowed.

If a particular build or preference refuses a direct attach, the bridge falls back to the Console worker and every tool behaves identically.

## Requirements

- DaVinci Resolve, free or Studio, with the internal Python 3 Console available
- Python 3.10 or newer on the computer
- An MCP-compatible client such as Antigravity, Claude Code, Codex, or Cursor
- Internet access during installation so pip can install the Python MCP package
- Node.js current LTS, heavily recommended for Remotion motion graphics

The bridge itself does not require Node.js.

## Quick Setup

### 1. Download the complete repository

On GitHub select **Code**, then **Download ZIP**, and extract it. Do not copy only `install.py`; it needs the `agent`, `bridge`, and `skills` folders beside it.

You may rename the downloaded folder. The installer copies runtime files to a fixed location.

### 2. Run the installer

macOS:

```bash
python3 install.py
```

Windows PowerShell:

```powershell
py install.py
```

The installer:

- Copies the runtime to `~/.resolve-ai-bridge`
- Preserves or creates a private `rab_...` token
- Creates `~/.resolve-ai-bridge/.venv` and installs the official Python MCP dependency
- Writes a filled MCP configuration plus exact Claude Code and Codex commands
- Installs **Workspace > Scripts > Resolve AI Bridge** menu entries into Resolve
- Installs the included Resolve editing skill for Claude Code and Codex
- Checks whether a direct attach works on this computer and tells you the result

It does not rewrite an AI client's existing MCP settings.

**Restart DaVinci Resolve once after installing.** Resolve only scans for new Workspace > Scripts entries while it starts up.

### 3. Add the MCP server to your AI client

**The installer auto-configures Claude Desktop, Claude Code, and Codex automatically.**

For other clients (such as Antigravity or Cursor), you can use the **zero-edit portable configuration** below — no username or home folder editing is required:

#### Option A: Portable Zero-Edit Snippet (Works on any Mac/Linux machine without editing)

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

#### Option B: Global CLI Launcher

The installer places a global launcher at `~/.local/bin/resolve-ai-bridge`:

```json
{
  "mcpServers": {
    "resolve-ai-bridge": {
      "command": "resolve-ai-bridge"
    }
  }
}
```

#### Option C: Explicit Absolute Paths

The installer also outputs your machine's exact paths directly into the terminal and saves them to `~/.resolve-ai-bridge/mcp-config.json`.

### 4. Open Resolve

Open Resolve and your project. In most cases that is the entire step.

If your AI reports the bridge as offline, run the Console launcher helper:

**Workspace > Scripts > Resolve AI Bridge > Start AI Bridge**

This prints the exact script to copy and paste into **Workspace > Console** (with the **Py3** tab selected).

Or paste this line directly into **Workspace > Console** with the **Py3** tab selected:

```python
import os;exec(open(os.path.expanduser("~/.resolve-ai-bridge/ResolveConsole.py"),encoding="utf-8").read())
```

The same line is saved at `~/.resolve-ai-bridge/console-command.txt`. A Console paste runs on a daemon thread, so the Console stays usable. The menu launcher uses a non-daemon worker because Resolve can close a one-shot menu-script context when the launcher returns. Stop it with:

```python
__resolve_ai_bridge_runtime__.stop()
```

### 5. Verify before editing

With Resolve open, run:

```bash
python3 tools/doctor.py
```

On Windows:

```powershell
py tools/doctor.py
```

Then ask your AI:

```text
Call resolve_status and tell me the open project, timeline, and which transport you are using. Do not edit anything.
```

For a safe first write:

```text
Inspect the timeline. Add a blue marker at the current playhead named Bridge test, then inspect again to verify it.
```

## Images and Overlays

An AI client can put a still onto your timeline directly. Give it an absolute path:

```text
Put /Users/me/Desktop/logo.png on video track 2 for 4 seconds at the playhead, scaled to 40 percent and tucked into the bottom right corner. Then show me the timeline to confirm it.
```

`add_image` exists because appending a still like ordinary footage produces a one-frame clip: Resolve reports a still's length differently from a video clip. The tool asks for a duration in seconds, creates the video track it needs, places the still, and reports `actual_duration_frames` so nobody has to trust that the requested length was honoured. When Resolve caps the length, raise **Preferences > Editing > Standard still duration**.

`set_clip_transform` then moves, scales, rotates, crops, fades, or blends any timeline item by id. Positions can be given in pixels (`pan`, `tilt`) or as a percentage of frame size (`pan_percent`, `tilt_percent`). It also scales each axis (`zoom_x`, `zoom_y`) and sets `scaling`, `resize_filter`, `retime_process`, and `motion_estimation`. Pass `item_id="playhead"` to act on the clip under the playhead without looking up its id first.

### Editing clips already on the timeline

`animate_zoom` gives a clip a scale that changes over time. Because Resolve cannot keyframe Edit-page sizing through scripting, it builds a Fusion composition on the clip with a keyframed Transform node from `start_zoom` to `end_zoom`. The reply's `keyframes_created` and `trace` say exactly what Resolve did; on a build that will not keyframe from scripting it falls back to a static zoom and reports that.

`split_clip` cuts a clip in two at a frame, a timecode, or the playhead. Resolve's scripting API exposes no razor, split, or trim, so the cut is synthesised: the clip's source range and transform are read, the clip is removed, and two adjacent pieces are re-appended and re-transformed. If both halves cannot be placed the original is restored. Color grades and Fusion compositions on the original are not copied onto the halves — the reply states this.

Generated images work the same way: have the AI write the file to disk, then pass the absolute path. For animated typography and designed motion, render it with Remotion and import the video instead.

## Token Behavior

The token is functional, not decorative. It protects the Console queue.

- The installer writes it to `~/.resolve-ai-bridge/token.txt` with restricted permissions where supported.
- The MCP process receives the same token through its environment.
- Every queued job includes the token, and the worker compares it before executing an operation.
- A mismatched request is rejected.

It is not an internet login. Do not commit it, post it, or paste it into a public issue.

Rotate it if exposed:

```bash
python3 install.py --rotate-token
```

Then restart the Resolve worker and replace the old MCP entry in your AI client.

## MCP Tools

26 focused tools, so a model can choose them reliably.

| Tool | Purpose |
| --- | --- |
| `resolve_status` | Report the live transport, Resolve version, project, timeline, and token id |
| `project_info` | Read project frame rate and resolution |
| `list_timelines` | List all timelines |
| `open_timeline` | Select a timeline by name or index |
| `create_timeline` | Create an empty timeline |
| `timeline_overview` | Inspect tracks, markers, clips, and stable ids |
| `list_media` | Walk Media Pool bins |
| `list_render_presets` | List render presets and formats available in the project |
| `import_media` | Import absolute local file paths |
| `append_media` | Append media ids or imported paths |
| `add_image` | Import a still and place it with a real duration, track, and position |
| `insert_title` | Insert a title at the playhead, best effort |
| `add_track` | Add video, audio, or subtitle tracks |
| `set_track_name` | Rename a track |
| `set_clip_transform` | Position, scale (both axes), rotate, crop, fade, blend, or set scaling/resize/retime mode. Accepts `item_id="playhead"` |
| `get_clip_transform` | Read an item's current transform values |
| `animate_zoom` | Animate a clip's scale over time via a keyframed Fusion composition |
| `split_clip` | Cut a clip in two at a frame, timecode, or the playhead |
| `set_playhead` | Move to a timecode |
| `open_page` | Switch Resolve to a page so the user can see a change |
| `add_marker` | Add a timeline marker |
| `delete_marker` | Delete a marker at a relative frame |
| `set_clip_property` | Change any supported timeline item property |
| `set_clip_enabled` | Enable or disable one item |
| `set_clip_color` | Set or clear a Resolve clip color |
| `delete_clips` | Delete selected items after approval |
| `save_project` | Save the open project |
| `render_current_timeline` | Queue or start a render after approval |

The server also provides the `resolve://guide` resource and an `edit_video` prompt.

## Getting Better AI Edits

The included `resolve-ai-editing` skill uses an inspect, plan, edit, verify workflow. The installer copies it to Claude Code and Codex skill folders and keeps a reference copy at:

```text
~/.resolve-ai-bridge/skills/resolve-ai-editing/SKILL.md
```

Start complicated requests with:

```text
First inspect the open project and timeline. Summarize what is there, state a short edit plan, and list assumptions. Work in small steps and verify after each change. Ask before deleting clips or starting a render.
```

Good prompts include target platform and aspect ratio, desired duration, audience and story goal, reference style, what must not change, and whether deletion and rendering are allowed.

Skills improve API usage and planning. They do not make subjective editing quality automatic. Review the timeline and use project backups.

## Remotion Setup, Heavily Recommended

[Remotion](https://www.remotion.dev/) creates video with React. It is useful for motion graphics, animated type, explainers, and designed scenes that are awkward through Resolve's scripting API.

Remotion does not control Resolve. The practical workflow is:

1. Build and preview a designed clip with a coding agent and Remotion.
2. Render the clip to a local media file.
3. Import that file through Resolve AI Bridge.
4. Ask where it should be placed before appending it.

### Install Node.js

Install the current LTS release from [nodejs.org](https://nodejs.org/), open a new terminal, and verify:

```bash
node --version
npm --version
```

### Install the official Remotion skill and create a project

```bash
npx -y skills@latest add remotion-dev/skills -g -y
npx create-video@latest --yes --blank my-video
cd my-video
npm install
npx remotion skills add
npm run dev
```

Render the approved composition:

```bash
npx remotion render <CompositionId> out/video.mp4
```

Then give the absolute output path to your Resolve AI:

```text
Import /absolute/path/to/my-video/out/video.mp4. Inspect the current timeline and ask me where to place it before appending it.
```

See `docs/REMOTION.md` for a detailed workflow and prompt checklist.

## Architecture

```text
AI client
  |  MCP over stdio
  v
~/.resolve-ai-bridge/bridge/server.py
  |
  +-- direct attach ----------------------------> DaVinci Resolve
  |     bridge/direct.py loads fusionscript          (default route)
  |
  +-- authenticated queue
        ~/.resolve-ai-bridge/inbox and outbox
          |
          v
        ResolveConsole.py daemon thread inside Resolve
          |
          v
        Current Resolve project and timeline

Both routes execute the same code in bridge/operations.py.
```

## Known Boundaries

- Resolve's public scripting API does not expose every action from the Edit page.
- Transition creation and arbitrary timeline repositioning are not offered because they cannot be implemented reliably with the documented API surface.
- There is no razor/split/trim in Resolve scripting. `split_clip` synthesises a cut by rebuilding the clip as two pieces; it does not copy color grades or Fusion comps onto the halves.
- Edit-page sizing cannot be keyframed through scripting. `animate_zoom` builds the animation in a Fusion composition and reports `keyframes_created`; on builds that refuse scripted keyframes it applies a static zoom instead.
- `insert_title` depends on the Resolve version and installed templates. Setting a title's text through scripting does not work on every build, and the tool reports `text_set` honestly rather than claiming success.
- Still duration can be capped by Resolve's own preference. `add_image` reports the real result.
- Direct attach depends on the Resolve build, the **External scripting using** preference, and whether Resolve's native module loads in your Python. The bridge probes it in a disposable subprocess first so a bad load can never take down the MCP server, and falls back to the Console worker.
- Render presets must already exist in Resolve.
- Complex Fusion automation is intentionally not included. Use Remotion for designed motion.
- The bridge works on the currently open local project. It is not a remote collaboration server.

## Verification Status

- The React instructions application is built with Vite as part of repository verification.
- `tools/doctor.py` compiles every Python source in memory before checking the installation, then round-trips a real `status` request over whichever transport is live.
- A real Resolve session is still required to verify each editing operation on a specific Resolve build.
- The 1.2.0 editing tools (`split_clip`, `animate_zoom`, and the extended `set_clip_transform` modes) were written against Blackmagic's scripting README but were not run against a live Resolve for this release. Confirm them on your build with `timeline_overview` and the doctor round-trip.

Do not interpret a successful web build as proof that a particular Resolve API operation works on every Resolve version.

## Repository Layout

```text
README.md                      complete written reference
RELEASE_NOTES.md               what changed in this version
install.py                     cross-platform installer
install-macos.command          macOS double-click wrapper
install-windows.bat            Windows double-click wrapper
requirements.txt               Python MCP dependency

agent/ResolveConsole.py        internal Resolve Console worker
agent/menu/                    Workspace > Scripts one-click launchers
bridge/operations.py           every Resolve operation, shared by both transports
bridge/direct.py               direct attach to a running Resolve
bridge/client.py               authenticated file queue
bridge/transport.py            picks direct attach or the Console queue
bridge/server.py               MCP tools over stdio
tools/doctor.py                syntax, install, transport, and round-trip checks
skills/resolve-ai-editing/     included Agent Skill
docs/                          troubleshooting, recipes, and Remotion guide
```

## Development

Python syntax and local installation checks:

```bash
python3 tools/doctor.py
```

Force a transport while testing:

```bash
RESOLVE_AI_BRIDGE_MODE=console python3 tools/doctor.py
RESOLVE_AI_BRIDGE_MODE=direct python3 tools/doctor.py
```

Important contributor rules are in `AGENTS.md`.

## Need Help From Your Provider?

After following the steps above, paste this into Antigravity, Claude Code, Codex, Cursor, or another local coding agent:

```text
Read README.md in this project. Run tools/doctor.py, inspect ~/.resolve-ai-bridge/mcp-config.json, and configure your own MCP settings for resolve-ai-bridge. Preserve my existing MCP servers. Test with resolve_status only and explain any error in simple steps.
```

## License

MIT. See [`LICENSE`](./LICENSE).
