"""MCP server for Resolve AI Bridge.

Talks to DaVinci Resolve over whichever transport is available: a direct attach
that needs nothing started inside Resolve, or the authenticated Console queue.
See ``bridge/transport.py``.

Never print to stdout from this process. MCP uses stdout for JSON-RPC.
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from bridge import client, transport
from bridge.operations import AGENT_VERSION


mcp = FastMCP(
    "Resolve AI Bridge",
    instructions=(
        "Inspect before editing. Call resolve_status, then timeline_overview. "
        "Refer to timeline items by ids such as V1.2. Verify after each change. "
        "Use add_image for stills and set_clip_transform to position them. "
        "Never delete clips or start a render without explicit user approval."
    ),
)

try:  # Report our own version in the MCP handshake instead of the SDK's.
    mcp._mcp_server.version = AGENT_VERSION
except Exception:  # A future SDK may rename this; the handshake still works.
    pass


def _result(operation: str, params: Optional[dict[str, Any]] = None, timeout: float = 30.0) -> str:
    try:
        payload, used = transport.call(operation, params or {}, timeout=timeout)
        return json.dumps({"ok": True, "transport": used, "result": payload}, ensure_ascii=True, indent=2)
    except client.BridgeOffline as exc:
        return json.dumps(
            {"ok": False, "error": str(exc), "help": transport.offline_help()},
            ensure_ascii=True,
            indent=2,
        )
    except client.BridgeError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True, indent=2)
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)},
            ensure_ascii=True,
            indent=2,
        )


# --------------------------------------------------------------- inspection


@mcp.tool()
def resolve_status() -> str:
    """Check how the bridge is connected, plus the Resolve version, open project, and timeline. Always call this first."""
    report = {"bridge_version": AGENT_VERSION, "connection": transport.describe()}
    try:
        payload, used = transport.call("status", {}, timeout=15.0)
        report.update({"ok": True, "transport": used, "result": payload})
    except Exception as exc:
        report.update({"ok": False, "error": str(exc), "help": transport.offline_help()})
    return json.dumps(report, ensure_ascii=True, indent=2)


@mcp.tool()
def project_info() -> str:
    """Return the current project's name, timeline, frame rate, resolution, and timeline count."""
    return _result("project_info")


@mcp.tool()
def list_timelines() -> str:
    """List every timeline in the open project and identify the current one."""
    return _result("list_timelines")


@mcp.tool()
def timeline_overview(max_items: int = 500) -> str:
    """Inspect tracks, clips, stable item ids, frame ranges, playhead timecode, and markers. Call before and after edits."""
    return _result("timeline_overview", {"max_items": max_items})


@mcp.tool()
def list_media(limit: int = 1000) -> str:
    """List media pool items recursively with unique ids, bin paths, file paths, frame counts, and durations."""
    return _result("list_media", {"limit": limit})


@mcp.tool()
def list_render_presets() -> str:
    """List the render presets and formats available in this project, for use with render_current_timeline."""
    return _result("list_render_presets")


# ---------------------------------------------------------------- navigation


@mcp.tool()
def open_timeline(name: Optional[str] = None, index: Optional[int] = None) -> str:
    """Open a timeline by exact name or one-based index from list_timelines."""
    return _result("open_timeline", {"name": name, "index": index})


@mcp.tool()
def create_timeline(name: str) -> str:
    """Create and open a new empty timeline with an exact name."""
    return _result("create_timeline", {"name": name})


@mcp.tool()
def set_playhead(timecode: str) -> str:
    """Move the current timeline playhead. Use HH:MM:SS:FF matching the timeline frame rate."""
    return _result("set_playhead", {"timecode": timecode})


@mcp.tool()
def open_page(page: str) -> str:
    """Switch the Resolve window to a page so the user can see a change: media, cut, edit, fusion, color, fairlight, or deliver."""
    return _result("open_page", {"page": page})


# --------------------------------------------------------------------- media


@mcp.tool()
def import_media(paths: list[str]) -> str:
    """Import existing local media files by absolute path into the Media Pool. This does not place them on the timeline."""
    return _result("import_media", {"paths": paths}, timeout=90.0)


@mcp.tool()
def append_media(
    media_ids: Optional[list[str]] = None,
    paths: Optional[list[str]] = None,
    track_index: Optional[int] = None,
    record_frame: Optional[int] = None,
    create_track: bool = True,
) -> str:
    """Append video or audio to the timeline from media pool ids or absolute file paths.

    Omit track_index and record_frame to append at the end of the timeline. For still
    images use add_image instead, which controls how long the still lasts.
    """
    return _result(
        "append_media",
        {
            "media_ids": media_ids or [],
            "paths": paths or [],
            "track_index": track_index,
            "record_frame": record_frame,
            "create_track": create_track,
        },
        timeout=90.0,
    )


@mcp.tool()
def add_image(
    path: str,
    duration_seconds: float = 5.0,
    duration_frames: Optional[int] = None,
    track_index: int = 1,
    record_frame: Optional[int] = None,
    at_playhead: bool = False,
    create_track: bool = True,
    pan_percent: Optional[float] = None,
    tilt_percent: Optional[float] = None,
    zoom: Optional[float] = None,
    rotation: Optional[float] = None,
    opacity: Optional[float] = None,
) -> str:
    """Put an image on the timeline: import the still, place it with a real duration, and optionally position it.

    This is the tool for logos, screenshots, overlays, title cards, and any generated
    picture. Use track_index=2 or higher to lay the image over existing footage; the
    track is created automatically when missing. Set at_playhead=True to place it at
    the current playhead instead of the end of the track.

    pan_percent and tilt_percent move the image as a percentage of frame width and
    height from centre. zoom is a scale multiplier where 1.0 is the original size.
    opacity runs from 0 to 100. Verify with timeline_overview afterwards, and read the
    returned actual_duration_frames: Resolve can shorten a still.
    """
    return _result(
        "add_image",
        {
            "path": path,
            "duration_seconds": duration_seconds,
            "duration_frames": duration_frames,
            "track_index": track_index,
            "record_frame": record_frame,
            "at_playhead": at_playhead,
            "create_track": create_track,
            "pan_percent": pan_percent,
            "tilt_percent": tilt_percent,
            "zoom": zoom,
            "rotation": rotation,
            "opacity": opacity,
        },
        timeout=90.0,
    )


# ------------------------------------------------------------ timeline edits


@mcp.tool()
def add_track(track_type: str = "video", count: int = 1) -> str:
    """Add one or more empty tracks. track_type is video, audio, or subtitle."""
    return _result("add_track", {"track_type": track_type, "count": count})


@mcp.tool()
def set_track_name(track_index: int, name: str, track_type: str = "video") -> str:
    """Rename one track, for example labelling V2 as Overlays."""
    return _result(
        "set_track_name", {"track_index": track_index, "name": name, "track_type": track_type}
    )


@mcp.tool()
def set_clip_transform(
    item_id: str,
    pan: Optional[float] = None,
    tilt: Optional[float] = None,
    pan_percent: Optional[float] = None,
    tilt_percent: Optional[float] = None,
    zoom: Optional[float] = None,
    zoom_x: Optional[float] = None,
    zoom_y: Optional[float] = None,
    rotation: Optional[float] = None,
    anchor_x: Optional[float] = None,
    anchor_y: Optional[float] = None,
    opacity: Optional[float] = None,
    composite_mode: Optional[str] = None,
    flip_x: Optional[bool] = None,
    flip_y: Optional[bool] = None,
    crop_left: Optional[float] = None,
    crop_right: Optional[float] = None,
    crop_top: Optional[float] = None,
    crop_bottom: Optional[float] = None,
) -> str:
    """Position, scale, rotate, fade, crop, or blend one timeline item.

    Use an id such as V2.1 from timeline_overview. pan and tilt are in pixels from
    centre; pan_percent and tilt_percent are the same move as a percentage of the
    timeline width and height. zoom sets both axes at once, where 1.0 is original
    size. opacity runs from 0 to 100. composite_mode accepts names such as normal,
    screen, multiply, add, overlay, or alpha.
    """
    return _result(
        "set_clip_transform",
        {
            "item_id": item_id,
            "pan": pan,
            "tilt": tilt,
            "pan_percent": pan_percent,
            "tilt_percent": tilt_percent,
            "zoom": zoom,
            "zoom_x": zoom_x,
            "zoom_y": zoom_y,
            "rotation": rotation,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "opacity": opacity,
            "composite_mode": composite_mode,
            "flip_x": flip_x,
            "flip_y": flip_y,
            "crop_left": crop_left,
            "crop_right": crop_right,
            "crop_top": crop_top,
            "crop_bottom": crop_bottom,
        },
    )


@mcp.tool()
def get_clip_transform(item_id: str) -> str:
    """Read the current position, scale, rotation, crop, opacity, and blend mode of one timeline item."""
    return _result("get_clip_transform", {"item_id": item_id})


@mcp.tool()
def insert_title(
    title_name: str = "Text+",
    text: Optional[str] = None,
    opacity: Optional[float] = None,
) -> str:
    """Insert a title at the playhead on the current video track, best effort.

    Available title names depend on the Resolve version and installed templates;
    Text+ and Text are the common ones. Setting the text through scripting is not
    supported on every build, so check text_set in the result and tell the user to
    type it in the Inspector if it is false. For designed animated typography,
    Remotion produces a better result.
    """
    return _result("insert_title", {"title_name": title_name, "text": text, "opacity": opacity})


@mcp.tool()
def add_marker(
    name: str,
    note: str = "",
    color: str = "Blue",
    frame: Optional[int] = None,
    duration: int = 1,
) -> str:
    """Add a timeline marker. Omit frame to use the current playhead; frame values are relative to timeline start."""
    return _result(
        "add_marker",
        {"name": name, "note": note, "color": color, "frame": frame, "duration": duration},
    )


@mcp.tool()
def delete_marker(frame: int) -> str:
    """Delete the timeline marker at a frame relative to timeline start."""
    return _result("delete_marker", {"frame": frame})


@mcp.tool()
def set_clip_property(item_id: str, property_name: str, value: Any) -> str:
    """Set any documented Resolve timeline item property directly. Prefer set_clip_transform for common changes."""
    return _result(
        "set_clip_property",
        {"item_id": item_id, "property_name": property_name, "value": value},
    )


@mcp.tool()
def set_clip_enabled(item_id: str, enabled: bool) -> str:
    """Enable or disable one timeline item without deleting it."""
    return _result("set_clip_enabled", {"item_id": item_id, "enabled": enabled})


@mcp.tool()
def set_clip_color(item_id: str, color: str = "") -> str:
    """Set a standard Resolve clip color, or pass an empty string to clear it."""
    return _result("set_clip_color", {"item_id": item_id, "color": color})


@mcp.tool()
def delete_clips(item_ids: list[str], ripple: bool = False, user_approved: bool = False) -> str:
    """Delete timeline items. Refuses unless the user explicitly approved this destructive action in the current conversation."""
    if not user_approved:
        return json.dumps(
            {
                "ok": False,
                "error": "Deletion requires explicit user approval. Ask first, then retry with user_approved=true.",
            },
            indent=2,
        )
    return _result("delete_clips", {"item_ids": item_ids, "ripple": ripple})


# ------------------------------------------------------------------ delivery


@mcp.tool()
def save_project() -> str:
    """Save the current Resolve project."""
    return _result("save_project")


@mcp.tool()
def render_current_timeline(
    output_dir: str,
    name: str = "",
    preset: str = "",
    start: bool = False,
    user_approved: bool = False,
) -> str:
    """Add a render job for the current timeline. Starting the render requires explicit user approval."""
    if start and not user_approved:
        return json.dumps(
            {
                "ok": False,
                "error": "Starting a render requires explicit user approval. Ask first, then retry with user_approved=true.",
            },
            indent=2,
        )
    return _result(
        "render_current_timeline",
        {"output_dir": output_dir, "name": name, "preset": preset, "start": start},
        timeout=180.0,
    )


@mcp.resource("resolve://guide")
def editing_guide() -> str:
    """Workflow and safety guide for editing with Resolve AI Bridge."""
    return """# Resolve AI Bridge editing guide

1. Call `resolve_status`. It reports which transport is live. Stop if no project or
   timeline is open, and pass the `help` text on to the user rather than guessing.
2. Call `timeline_overview` and refer to clips by ids such as `V1.2`, never by an
   ambiguous name.
3. Explain the edit plan and assumptions before changing anything.
4. Make one small change at a time and inspect again after each change.
5. Ask before deleting clips, using ripple delete, or starting a render.
6. Images: use `add_image`. Put overlays on `track_index` 2 or higher so footage on V1
   stays visible, then position with `set_clip_transform` or the pan/tilt/zoom
   arguments of `add_image`. Always check `actual_duration_frames` in the result,
   because Resolve can shorten a still to its default length.
7. `insert_title` is best effort. If `text_set` is false, say so and ask the user to
   type the text in the Inspector.
8. Timeline item frames are absolute Resolve timeline frames unless a tool says
   otherwise. Marker frames are relative to the timeline start.
9. Prefer Remotion for designed motion graphics and animated typography. Render a
   clip, import it, then ask where to place it.
10. Resolve's public scripting API cannot perform every interactive Edit page action.
    If a tool is absent, explain the limitation instead of pretending it worked.
"""


@mcp.prompt(name="edit_video")
def edit_video_prompt(goal: str) -> str:
    """Create a cautious, verifiable Resolve editing workflow for a user goal."""
    return (
        "Goal: %s\n\n"
        "First call resolve_status and timeline_overview. Summarize the current timeline, then "
        "propose a short plan. Wait if the goal is ambiguous. Apply small edits, verify each "
        "result with a fresh timeline_overview, and request approval before deletion or rendering."
        % goal
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
