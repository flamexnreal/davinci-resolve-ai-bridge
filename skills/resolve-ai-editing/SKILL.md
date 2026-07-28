---
name: resolve-ai-editing
description: Plan, perform, and verify careful edits in an open DaVinci Resolve project through Resolve AI Bridge MCP tools.
---

# Resolve AI Editing

Use this skill whenever a request involves the open DaVinci Resolve project.

## Required Workflow

1. Call `resolve_status` before every editing session. It reports which transport is live.
2. Call `timeline_overview` before proposing an edit.
3. Summarize what is open and identify ambiguities.
4. State a short plan before changing the timeline.
5. Use ids such as `V1.2` from the latest overview. Do not target a clip by a repeated name.
6. Make one logical change per tool call.
7. Call `timeline_overview` again to verify the result.
8. Ask for explicit approval before deletion, ripple deletion, or starting a render.

## When The Bridge Is Offline

`resolve_status` returns a `help` string. Pass it on rather than guessing. The order that fixes it:

1. Open DaVinci Resolve with a project.
2. **Workspace > Scripts > Resolve AI Bridge > Start AI Bridge**.
3. Paste the line in `~/.resolve-ai-bridge/console-command.txt` into **Workspace > Console**, Py3 tab.

Never claim an edit succeeded while the bridge is offline.

## Images And Overlays

- Use `add_image` for any still. Do not use `append_media` for a picture; that produces a one-frame clip.
- Give a real `duration_seconds`. Read `actual_duration_frames` in the reply and report it if it differs from the request.
- Put overlays on `track_index` 2 or higher so footage on V1 stays visible. The track is created automatically.
- Position with `pan_percent`, `tilt_percent`, `zoom`, and `opacity`, or afterwards with `set_clip_transform`.
- `pan` and `tilt` are pixels from centre. The percent variants are relative to the timeline resolution, which `project_info` reports.
- After placing an image, call `timeline_overview` and confirm the new item id before making further changes.

## Titles

`insert_title` is best effort. Available names depend on the Resolve version and installed templates. Check `text_set` in the reply. When it is false, say the text must be typed in the Inspector, or offer to build the title in Remotion instead.

## Editing Quality

- Treat pacing, story, and audio clarity as editorial decisions, not random effects.
- Ask for a reference, target platform, duration, aspect ratio, and audience when they are missing.
- Prefer a small number of intentional changes over applying the same effect to every clip.
- Preserve source media. Disable a clip before deleting it when the goal is uncertain.
- Use markers to show a proposed edit when an operation is not safely reversible.
- Save only after the requested changes have been verified.

## Remotion Workflow

Use Remotion when the user asks for complex animated typography, explainers, product demonstrations, or designed motion scenes.

1. Confirm Node.js and the official `remotion-dev/skills` bundle are installed.
2. Build the composition in a separate Remotion project.
3. Preview it in Remotion Studio and get approval.
4. Render a local video file.
5. Use `import_media` with its absolute path.
6. Inspect the Resolve timeline and ask where to place it before calling `append_media`.

Remotion does not control Resolve. It produces media that the bridge can bring into Resolve.

## API Boundaries

The public Resolve scripting API does not expose every action from the Edit page. Do not claim that transitions, arbitrary clip repositioning, or advanced Fusion animation worked unless a returned result and a fresh timeline inspection confirm it. If a requested action has no MCP tool, explain the limitation and offer a safe alternative.

## Failure Behavior

- If `resolve_status` reports no connection, stop and give the start instructions above.
- If a tool returns an error, do not repeat it unchanged more than once.
- Read the error, inspect current state, and adjust the plan.
- Never report success based only on an attempted call.
