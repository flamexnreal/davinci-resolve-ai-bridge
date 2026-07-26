# Editing Recipes

These prompts are written to encourage inspection and verification.

## Safe First Test

```text
Call resolve_status and timeline_overview. Do not change clips. Add a blue marker at the current playhead named Bridge test, then inspect again and report the marker frame.
```

## Import a Rendered Motion Graphic

```text
Inspect the project and current timeline. Import /absolute/path/to/out/video.mp4 into the current Media Pool. Confirm its media id, then ask me which video track and record frame to use before appending it.
```

## Organize With Clip Colors

```text
Inspect the timeline and list every clip id with its current color. Propose a simple color system for interviews, b-roll, graphics, and audio. Wait for approval, apply one category at a time, then verify.
```

## Disable Without Deleting

```text
Inspect the timeline and find the clip I describe. If its name is ambiguous, show me the matching ids. Disable the selected clip without deleting it, then verify its enabled state.
```

## Queue a Render

```text
Inspect the project and current timeline. Explain which existing Resolve render preset you plan to use and the output directory. Wait for approval. Add the render job but do not start rendering unless I separately approve it.
```

## Better Editing Brief

```text
Target: 30-second 16:9 product introduction
Audience: first-time customers
Pacing: calm, confident, no rapid montage
Must keep: all spoken lines and the final logo shot
May change: clip order, disabled takes, markers, clip colors
Do not: delete source clips or start a render

First inspect the timeline. Summarize the existing story, propose an edit plan, and list anything the current MCP tools cannot perform reliably. Wait for approval before editing.
```