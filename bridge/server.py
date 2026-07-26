"""MCP server for Resolve AI Bridge.

This process never imports DaVinci Resolve. It communicates with the internal
Console agent through authenticated JSON files. Do not print to stdout because
MCP uses stdout for JSON-RPC.
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from bridge import client


mcp = FastMCP(
    "Resolve AI Bridge",
    instructions=(
        "Inspect before editing. Call resolve_status, then timeline_overview. "
        "Use timeline item ids such as V1.2. Verify after each change. "
        "Never delete clips or start a render without explicit user approval."
    ),
)


def _result(operation: str, params: Optional[dict[str, Any]] = None, timeout: float = 30.0) -> str:
    try:
        payload = client.call(operation, params or {}, timeout=timeout)
        return json.dumps({"ok": True, "result": payload}, ensure_ascii=True, indent=2)
    except client.BridgeError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True, indent=2)
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": "Unexpected bridge error: %s" % exc},
            ensure_ascii=True,
            indent=2,
        )


@mcp.tool()
def resolve_status() -> str:
    """Check the local agent, Resolve version, open project, timeline, and token id. Always call this first."""
    return _result("status")


@mcp.tool()
def project_info() -> str:
    """Return the current project's name, timeline, frame rate, resolution, and timeline count."""
    return _result("project_info")


@mcp.tool()
def list_timelines() -> str:
    """List every timeline in the open project and identify the current one."""
    return _result("list_timelines")


@mcp.tool()
def open_timeline(name: Optional[str] = None, index: Optional[int] = None) -> str:
    """Open a timeline by exact name or one-based index from list_timelines."""
    return _result("open_timeline", {"name": name, "index": index})


@mcp.tool()
def timeline_overview(max_items: int = 500) -> str:
    """Inspect tracks, clips, stable item ids, frame ranges, playhead timecode, and markers. Call before and after edits."""
    return _result("timeline_overview", {"max_items": max_items})


@mcp.tool()
def list_media(limit: int = 1000) -> str:
    """List media pool items recursively with unique ids, bin paths, file paths, and durations."""
    return _result("list_media", {"limit": limit})


@mcp.tool()
def import_media(paths: list[str]) -> str:
    """Import existing local media files by absolute path. This does not place them on the timeline."""
    return _result("import_media", {"paths": paths}, timeout=90.0)


@mcp.tool()
def append_media(
    media_ids: Optional[list[str]] = None,
    paths: Optional[list[str]] = None,
    track_index: Optional[int] = None,
    record_frame: Optional[int] = None,
) -> str:
    """Append media pool ids or local files. Omit placement to append at the timeline end; otherwise use an absolute record frame."""
    return _result(
        "append_media",
        {
            "media_ids": media_ids or [],
            "paths": paths or [],
            "track_index": track_index,
            "record_frame": record_frame,
        },
        timeout=90.0,
    )


@mcp.tool()
def create_timeline(name: str) -> str:
    """Create and open a new empty timeline with an exact name."""
    return _result("create_timeline", {"name": name})


@mcp.tool()
def set_playhead(timecode: str) -> str:
    """Move the current timeline playhead. Use HH:MM:SS:FF matching the timeline frame rate."""
    return _result("set_playhead", {"timecode": timecode})


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
    """Set a documented Resolve timeline item property. Use an id from timeline_overview and verify the result."""
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
            {"ok": False, "error": "Deletion requires explicit user approval. Ask first, then retry with user_approved=true."},
            indent=2,
        )
    return _result("delete_clips", {"item_ids": item_ids, "ripple": ripple})


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
            {"ok": False, "error": "Starting a render requires explicit user approval. Ask first, then retry with user_approved=true."},
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

1. Call `resolve_status`. Stop if no project or timeline is open.
2. Call `timeline_overview` and refer to clips by ids such as `V1.2`, not by an ambiguous name.
3. Explain the edit plan and assumptions before changing anything.
4. Make one small change at a time and inspect again after each change.
5. Ask before deleting clips, using ripple delete, or starting a render.
6. Timeline item frames are absolute Resolve timeline frames unless a tool explicitly says relative.
7. Prefer Remotion for complex motion design. Render a clip, import it, then ask where to append it.
8. Resolve's public scripting API cannot perform every interactive Edit-page action. If a tool is absent, explain the limitation instead of pretending it worked.
"""


@mcp.prompt(name="edit_video")
def edit_video_prompt(goal: str) -> str:
    """Create a cautious, verifiable Resolve editing workflow for a user goal."""
    return (
        "Goal: %s\n\n"
        "First call resolve_status and timeline_overview. Summarize the current timeline, then propose a short plan. "
        "Wait if the goal is ambiguous. Apply small edits, verify each result, and request approval before deletion or rendering."
        % goal
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")