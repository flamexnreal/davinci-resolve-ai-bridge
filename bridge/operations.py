"""Resolve operation implementations shared by every transport.

This module is imported in two very different places:

* inside DaVinci Resolve, by ``ResolveConsole.py`` running in the Py3 Console
  or from the Workspace > Scripts menu
* outside DaVinci Resolve, by ``bridge/direct.py`` when the MCP server attaches
  to Resolve itself

Because of that it must stay dependent on the standard library only. Never
import ``mcp``, ``fusionscript``, or anything from ``bridge.server`` here.
"""

import json
import os
import time
from pathlib import Path


AGENT_VERSION = "1.1.0"
PROTOCOL_VERSION = 2

IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp",
    ".exr", ".dpx", ".tga", ".psd", ".heic", ".heif", ".jp2", ".cin",
}

# Names accepted by set_clip_transform for "composite_mode", mapped to the
# integer constants documented in Resolve's scripting README.
COMPOSITE_MODES = {
    "normal": 0, "add": 1, "subtract": 2, "diff": 3, "difference": 3,
    "multiply": 4, "screen": 5, "overlay": 6, "hardlight": 7, "hard_light": 7,
    "softlight": 8, "soft_light": 8, "darken": 9, "lighten": 10,
    "color_dodge": 11, "colordodge": 11, "color_burn": 12, "colorburn": 12,
    "exclusion": 13, "hue": 14, "saturate": 15, "colorize": 16,
    "luma_mask": 17, "divide": 18, "linear_dodge": 19, "linear_burn": 20,
    "linear_light": 21, "vivid_light": 22, "pin_light": 23, "hard_mix": 24,
    "lighter_color": 25, "darker_color": 26, "foreground": 27, "alpha": 28,
    "inverted_alpha": 29, "lum": 30, "inverted_lum": 31,
}

# Scalar transform keys exposed by set_clip_transform, mapped to the Resolve
# property key. Values are passed through float().
TRANSFORM_FLOATS = {
    "pan": "Pan",
    "tilt": "Tilt",
    "zoom_x": "ZoomX",
    "zoom_y": "ZoomY",
    "rotation": "RotationAngle",
    "anchor_x": "AnchorPointX",
    "anchor_y": "AnchorPointY",
    "pitch": "Pitch",
    "yaw": "Yaw",
    "crop_left": "CropLeft",
    "crop_right": "CropRight",
    "crop_top": "CropTop",
    "crop_bottom": "CropBottom",
    "crop_softness": "CropSoftness",
    "opacity": "Opacity",
    "distortion": "Distortion",
}

TRANSFORM_BOOLS = {
    "flip_x": "FlipX",
    "flip_y": "FlipY",
    "zoom_gang": "ZoomGang",
    "crop_retain": "CropRetain",
}

READABLE_TRANSFORM_KEYS = (
    "Pan", "Tilt", "ZoomX", "ZoomY", "ZoomGang", "RotationAngle",
    "AnchorPointX", "AnchorPointY", "Pitch", "Yaw", "FlipX", "FlipY",
    "CropLeft", "CropRight", "CropTop", "CropBottom", "CropSoftness",
    "CropRetain", "CompositeMode", "Opacity", "Distortion",
)

PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")


class OperationError(RuntimeError):
    """A Resolve operation failed for a reason the user or model can act on."""


def call(obj, method, default=None, *args):
    """Call an optional Resolve API method without raising."""
    try:
        function = getattr(obj, method, None)
        return function(*args) if callable(function) else default
    except Exception:
        return default


def plain(value):
    """Convert Resolve's native objects into JSON-safe values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return str(value)


def _absolute(value):
    return str(Path(str(value)).expanduser().resolve())


class ResolveOperations:
    """Every bridge operation, implemented against a live Resolve object.

    ``provider`` is a zero-argument callable that returns the Resolve API
    object. It is called on every operation so a transport that can lose its
    connection (direct attach) is able to reconnect transparently.
    """

    def __init__(self, provider, token_id=None, transport="unknown"):
        self._provider = provider
        self.token_id = token_id
        self.transport = transport

    # ------------------------------------------------------------------ core

    @property
    def resolve(self):
        instance = self._provider()
        if instance is None:
            raise OperationError(
                "DaVinci Resolve is not reachable. Open Resolve with a project, then try again."
            )
        return instance

    def _project(self):
        manager = self.resolve.GetProjectManager()
        if manager is None:
            raise OperationError("Resolve did not return a Project Manager.")
        project = manager.GetCurrentProject()
        if project is None:
            raise OperationError("No project is open in Resolve. Open a project and try again.")
        return project

    def _timeline(self):
        timeline = self._project().GetCurrentTimeline()
        if timeline is None:
            raise OperationError("No timeline is open. Open or create a timeline, then try again.")
        return timeline

    def _media_pool(self):
        pool = self._project().GetMediaPool()
        if pool is None:
            raise OperationError("Resolve did not return a Media Pool.")
        return pool

    def _project_rate(self):
        raw = call(self._project(), "GetSetting", "24", "timelineFrameRate") or "24"
        try:
            return float(str(raw).replace(" DF", "").strip())
        except ValueError:
            return 24.0

    def _project_resolution(self):
        project = self._project()
        try:
            width = int(call(project, "GetSetting", 1920, "timelineResolutionWidth") or 1920)
            height = int(call(project, "GetSetting", 1080, "timelineResolutionHeight") or 1080)
        except (TypeError, ValueError):
            width, height = 1920, 1080
        return width, height

    def _tc_frames(self, value, fps):
        parts = str(value).replace(";", ":").split(":")
        if len(parts) != 4:
            return 0
        try:
            hours, minutes, seconds, frames = [int(part) for part in parts]
        except ValueError:
            return 0
        rounded = max(1, int(round(fps)))
        return ((hours * 3600 + minutes * 60 + seconds) * rounded) + frames

    def _current_marker_frame(self, timeline):
        current = call(timeline, "GetCurrentTimecode", "00:00:00:00")
        start = call(timeline, "GetStartTimecode", "00:00:00:00")
        fps = self._project_rate()
        return max(0, self._tc_frames(current, fps) - self._tc_frames(start, fps))

    # -------------------------------------------------------------- lookups

    def _item_summary(self, item, track_type, track_index, item_index):
        prefix = "V" if track_type == "video" else "A" if track_type == "audio" else "S"
        media_item = call(item, "GetMediaPoolItem", None)
        media_id = call(media_item, "GetUniqueId", None) if media_item is not None else None
        return {
            "id": "%s%d.%d" % (prefix, track_index, item_index),
            "unique_id": call(item, "GetUniqueId", None),
            "name": call(item, "GetName", ""),
            "track_type": track_type,
            "track_index": track_index,
            "start": call(item, "GetStart", None),
            "end": call(item, "GetEnd", None),
            "duration": call(item, "GetDuration", None),
            "enabled": call(item, "GetClipEnabled", None),
            "color": call(item, "GetClipColor", ""),
            "media_pool_id": media_id,
        }

    def _timeline_items(self):
        timeline = self._timeline()
        results = []
        for track_type in ("video", "audio", "subtitle"):
            count = int(call(timeline, "GetTrackCount", 0, track_type) or 0)
            for track_index in range(1, count + 1):
                items = call(timeline, "GetItemListInTrack", [], track_type, track_index) or []
                for item_index, item in enumerate(items, 1):
                    results.append(
                        (item, self._item_summary(item, track_type, track_index, item_index))
                    )
        return results

    def _find_timeline_items(self, identifiers):
        wanted = [str(item) for item in identifiers]
        all_items = self._timeline_items()
        found = []
        missing = []
        for identifier in wanted:
            matches = [
                (item, info)
                for item, info in all_items
                if identifier in (str(info.get("id")), str(info.get("unique_id")), str(info.get("name")))
            ]
            if not matches:
                missing.append(identifier)
                continue
            exact = next(
                (
                    match
                    for match in matches
                    if match[1].get("id") == identifier or str(match[1].get("unique_id")) == identifier
                ),
                None,
            )
            if exact is None and len(matches) > 1:
                raise OperationError(
                    "Clip name '%s' is ambiguous. Use an id such as V1.2 from timeline_overview."
                    % identifier
                )
            found.append(exact or matches[0])
        if missing:
            raise OperationError(
                "Timeline item not found: %s. Call timeline_overview for valid ids."
                % ", ".join(missing)
            )
        return found

    def _walk_media(self, folder, prefix="", limit=2000):
        output = []
        folder_name = call(folder, "GetName", "Media Pool")
        location = (prefix + "/" + folder_name).strip("/")
        for clip in call(folder, "GetClipList", []) or []:
            props = call(clip, "GetClipProperty", {}) or {}
            output.append({
                "id": call(clip, "GetUniqueId", None),
                "name": call(clip, "GetName", props.get("Clip Name", "")),
                "bin": location,
                "file_path": props.get("File Path"),
                "duration": props.get("Duration"),
                "frames": props.get("Frames"),
                "resolution": props.get("Resolution"),
                "type": props.get("Type"),
            })
            if len(output) >= limit:
                return output
        for child in call(folder, "GetSubFolderList", []) or []:
            remaining = max(0, limit - len(output))
            if not remaining:
                break
            output.extend(self._walk_media(child, location, remaining))
        return output

    def _find_media_items(self, identifiers):
        wanted = [str(value) for value in identifiers]
        found = []

        def visit(folder):
            for clip in call(folder, "GetClipList", []) or []:
                if str(call(clip, "GetUniqueId", "")) in wanted or str(call(clip, "GetName", "")) in wanted:
                    found.append(clip)
            for child in call(folder, "GetSubFolderList", []) or []:
                visit(child)

        visit(self._media_pool().GetRootFolder())
        if len(found) < len(wanted):
            raise OperationError(
                "One or more media items were not found. Call list_media and use unique ids."
            )
        return found

    def _ensure_video_track(self, timeline, track_index, allow_create=True):
        """Make sure video track ``track_index`` exists, adding tracks if allowed."""
        if track_index is None:
            return None
        wanted = int(track_index)
        if wanted < 1:
            raise OperationError("track_index must be 1 or greater.")
        count = int(call(timeline, "GetTrackCount", 0, "video") or 0)
        if wanted <= count:
            return wanted
        if not allow_create:
            raise OperationError(
                "Video track V%d does not exist. The timeline has %d video track(s)."
                % (wanted, count)
            )
        for _ in range(wanted - count):
            if not call(timeline, "AddTrack", False, "video"):
                raise OperationError(
                    "Resolve refused to add a video track. The timeline has %d video track(s)."
                    % int(call(timeline, "GetTrackCount", 0, "video") or 0)
                )
        return wanted

    def _apply_transform(self, item, params):
        """Apply the transform subset of ``params`` to one timeline item."""
        applied = {}
        rejected = {}
        width, height = self._project_resolution()

        requests = []
        if params.get("pan_percent") is not None:
            requests.append(("Pan", float(params["pan_percent"]) / 100.0 * width))
        if params.get("tilt_percent") is not None:
            requests.append(("Tilt", float(params["tilt_percent"]) / 100.0 * height))
        zoom = params.get("zoom")
        if zoom is not None:
            requests.append(("ZoomX", float(zoom)))
            requests.append(("ZoomY", float(zoom)))
        for name, key in TRANSFORM_FLOATS.items():
            if params.get(name) is not None:
                requests.append((key, float(params[name])))
        for name, key in TRANSFORM_BOOLS.items():
            if params.get(name) is not None:
                requests.append((key, bool(params[name])))
        mode = params.get("composite_mode")
        if mode is not None:
            if isinstance(mode, str):
                resolved = COMPOSITE_MODES.get(mode.strip().lower().replace(" ", "_"))
                if resolved is None:
                    raise OperationError(
                        "Unknown composite_mode '%s'. Valid names: %s"
                        % (mode, ", ".join(sorted(COMPOSITE_MODES)))
                    )
                requests.append(("CompositeMode", resolved))
            else:
                requests.append(("CompositeMode", int(mode)))

        for key, value in requests:
            if call(item, "SetProperty", False, key, value):
                applied[key] = value
            else:
                rejected[key] = value
        return applied, rejected

    def _read_transform(self, item):
        values = {}
        snapshot = call(item, "GetProperty", None)
        if isinstance(snapshot, dict):
            for key in READABLE_TRANSFORM_KEYS:
                if key in snapshot:
                    values[key] = plain(snapshot[key])
            if values:
                return values
        for key in READABLE_TRANSFORM_KEYS:
            value = call(item, "GetProperty", None, key)
            if value is not None:
                values[key] = plain(value)
        return values

    def _newest_item_on_track(self, timeline, track_index):
        items = call(timeline, "GetItemListInTrack", [], "video", track_index) or []
        if not items:
            return None, None
        index = len(items)
        return items[-1], self._item_summary(items[-1], "video", track_index, index)

    # ----------------------------------------------------------- operations

    def _op_status(self, _params):
        instance = self._provider()
        manager = instance.GetProjectManager() if instance is not None else None
        project = manager.GetCurrentProject() if manager else None
        timeline = project.GetCurrentTimeline() if project else None
        return {
            "online": instance is not None,
            "transport": self.transport,
            "agent_version": AGENT_VERSION,
            "protocol": PROTOCOL_VERSION,
            "resolve_version": call(instance, "GetVersionString", None),
            "product": call(instance, "GetProductName", None),
            "page": call(instance, "GetCurrentPage", None),
            "project": call(project, "GetName", None) if project else None,
            "timeline": call(timeline, "GetName", None) if timeline else None,
            "token_id": self.token_id,
        }

    def _op_project_info(self, _params):
        project = self._project()
        timeline = project.GetCurrentTimeline()
        return {
            "name": project.GetName(),
            "timeline": call(timeline, "GetName", None) if timeline else None,
            "timeline_count": call(project, "GetTimelineCount", 0),
            "frame_rate": call(project, "GetSetting", None, "timelineFrameRate"),
            "resolution_width": call(project, "GetSetting", None, "timelineResolutionWidth"),
            "resolution_height": call(project, "GetSetting", None, "timelineResolutionHeight"),
        }

    def _op_list_timelines(self, _params):
        project = self._project()
        current = project.GetCurrentTimeline()
        timelines = []
        for index in range(1, int(project.GetTimelineCount() or 0) + 1):
            item = project.GetTimelineByIndex(index)
            timelines.append({
                "index": index,
                "name": call(item, "GetName", ""),
                "current": item == current,
                "start_frame": call(item, "GetStartFrame", None),
                "end_frame": call(item, "GetEndFrame", None),
            })
        return {"timelines": timelines}

    def _op_open_timeline(self, params):
        project = self._project()
        name = params.get("name")
        index = params.get("index")
        selected = None
        for item_index in range(1, int(project.GetTimelineCount() or 0) + 1):
            item = project.GetTimelineByIndex(item_index)
            if (index is not None and int(index) == item_index) or (name and item.GetName() == name):
                selected = item
                break
        if selected is None:
            raise OperationError("Timeline not found. Call list_timelines for valid names and indexes.")
        if not project.SetCurrentTimeline(selected):
            raise OperationError("Resolve refused to open the requested timeline.")
        return {"opened": selected.GetName()}

    def _op_timeline_overview(self, params):
        timeline = self._timeline()
        max_items = max(1, min(int(params.get("max_items", 500) or 500), 2000))
        tracks = []
        clips = []
        for track_type in ("video", "audio", "subtitle"):
            count = int(call(timeline, "GetTrackCount", 0, track_type) or 0)
            for track_index in range(1, count + 1):
                items = call(timeline, "GetItemListInTrack", [], track_type, track_index) or []
                tracks.append({
                    "type": track_type,
                    "index": track_index,
                    "name": call(timeline, "GetTrackName", "", track_type, track_index),
                    "enabled": call(timeline, "GetIsTrackEnabled", None, track_type, track_index),
                    "items": len(items),
                })
                for item_index, item in enumerate(items, 1):
                    if len(clips) < max_items:
                        clips.append(self._item_summary(item, track_type, track_index, item_index))
        return {
            "name": timeline.GetName(),
            "start_frame": call(timeline, "GetStartFrame", None),
            "end_frame": call(timeline, "GetEndFrame", None),
            "current_timecode": call(timeline, "GetCurrentTimecode", None),
            "frame_rate": self._project_rate(),
            "tracks": tracks,
            "clips": clips,
            "clips_truncated": sum(track["items"] for track in tracks) > len(clips),
            "markers": plain(call(timeline, "GetMarkers", {}) or {}),
        }

    def _op_list_media(self, params):
        limit = max(1, min(int(params.get("limit", 1000) or 1000), 5000))
        items = self._walk_media(self._media_pool().GetRootFolder(), "", limit)
        return {"items": items, "count": len(items), "limited_to": limit}

    def _op_import_media(self, params):
        paths = [_absolute(value) for value in params.get("paths", [])]
        if not paths:
            raise OperationError("paths must contain at least one absolute media file path.")
        missing = [path for path in paths if not Path(path).exists()]
        if missing:
            raise OperationError("Media file not found: %s" % ", ".join(missing))
        imported = self._media_pool().ImportMedia(paths) or []
        if not imported:
            raise OperationError(
                "Resolve imported none of the requested files. Confirm the format is supported "
                "and that a project is open."
            )
        return {
            "imported": [
                {
                    "id": call(item, "GetUniqueId", None),
                    "name": call(item, "GetName", ""),
                    "frames": (call(item, "GetClipProperty", {}) or {}).get("Frames"),
                }
                for item in imported
            ],
            "requested": len(paths),
            "imported_count": len(imported),
        }

    def _op_append_media(self, params):
        media_ids = params.get("media_ids") or []
        paths = params.get("paths") or []
        items = None
        if paths:
            absolute = [_absolute(value) for value in paths]
            missing = [path for path in absolute if not Path(path).exists()]
            if missing:
                raise OperationError("Media file not found: %s" % ", ".join(missing))
            items = list(self._media_pool().ImportMedia(absolute) or [])
            if not items:
                raise OperationError("Resolve did not import any of the requested media files.")
        if items is None and not media_ids:
            raise OperationError(
                "Provide media_ids from list_media or absolute paths to import and append."
            )
        if items is None:
            items = self._find_media_items(media_ids)

        timeline = self._timeline()
        track_index = params.get("track_index")
        if track_index is not None:
            track_index = self._ensure_video_track(
                timeline, track_index, bool(params.get("create_track", True))
            )
        record_frame = params.get("record_frame")

        payload = items
        if track_index is not None or record_frame is not None:
            payload = []
            for item in items:
                clip_info = {"mediaPoolItem": item}
                if track_index is not None:
                    clip_info["trackIndex"] = int(track_index)
                if record_frame is not None:
                    clip_info["recordFrame"] = int(record_frame)
                frames = (call(item, "GetClipProperty", {}) or {}).get("Frames")
                try:
                    total = int(frames)
                except (TypeError, ValueError):
                    total = 0
                if total > 1:
                    clip_info.update({"startFrame": 0, "endFrame": total - 1})
                payload.append(clip_info)

        created = self._media_pool().AppendToTimeline(payload) or []
        if not created:
            raise OperationError(
                "Resolve appended nothing. A still image needs add_image, and an explicit "
                "record_frame must land on empty space on that track."
            )
        return {
            "appended_count": len(created),
            "requested": len(items),
            "track_index": track_index,
            "record_frame": record_frame,
        }

    def _op_add_image(self, params):
        """Import one still image and place it on the timeline with a real duration."""
        raw_path = str(params.get("path", "")).strip()
        if not raw_path:
            raise OperationError("path is required and must be an absolute image file path.")
        path = _absolute(raw_path)
        if not Path(path).exists():
            raise OperationError("Image file not found: %s" % path)
        suffix = Path(path).suffix.lower()

        timeline = self._timeline()
        fps = self._project_rate()
        duration_frames = params.get("duration_frames")
        if duration_frames is None:
            seconds = params.get("duration_seconds")
            seconds = 5.0 if seconds is None else float(seconds)
            duration_frames = int(round(seconds * fps))
        duration_frames = max(1, int(duration_frames))

        track_index = self._ensure_video_track(
            timeline,
            params.get("track_index") or 1,
            bool(params.get("create_track", True)),
        )
        record_frame = params.get("record_frame")
        if record_frame is None and params.get("at_playhead"):
            record_frame = (
                int(call(timeline, "GetStartFrame", 0) or 0) + self._current_marker_frame(timeline)
            )

        pool = self._media_pool()
        existing = None
        for candidate in self._walk_media(pool.GetRootFolder(), "", 5000):
            if candidate.get("file_path") and _absolute(candidate["file_path"]) == path:
                existing = candidate.get("id")
                break
        if existing:
            media_item = self._find_media_items([existing])[0]
            reused = True
        else:
            imported = pool.ImportMedia([path]) or []
            if not imported:
                raise OperationError(
                    "Resolve could not import %s. Confirm the file is a supported image format." % path
                )
            media_item = imported[0]
            reused = False

        available = (call(media_item, "GetClipProperty", {}) or {}).get("Frames")
        try:
            available_frames = int(available)
        except (TypeError, ValueError):
            available_frames = 0

        clip_info = {
            "mediaPoolItem": media_item,
            "startFrame": 0,
            "endFrame": duration_frames - 1,
            "trackIndex": int(track_index),
        }
        if record_frame is not None:
            clip_info["recordFrame"] = int(record_frame)

        created = pool.AppendToTimeline([clip_info]) or []
        fallback_used = False
        if not created and available_frames > 1:
            # Some builds refuse an endFrame beyond the still's reported length.
            clip_info["endFrame"] = min(duration_frames, available_frames) - 1
            created = pool.AppendToTimeline([clip_info]) or []
            fallback_used = bool(created)
        if not created:
            clip_info.pop("startFrame", None)
            clip_info.pop("endFrame", None)
            created = pool.AppendToTimeline([clip_info]) or []
            fallback_used = bool(created)
        if not created:
            raise OperationError(
                "Resolve placed nothing on V%d. If record_frame was given, that space may already "
                "be occupied. Try another record_frame, another track_index, or omit both to append "
                "at the end of the track." % track_index
            )

        item = created[0]
        actual = call(item, "GetDuration", None)
        applied, rejected = self._apply_transform(item, params)
        _, info = self._newest_item_on_track(timeline, track_index)

        result = {
            "item": (info or {}).get("id"),
            "name": call(item, "GetName", ""),
            "media_pool_id": call(media_item, "GetUniqueId", None),
            "reused_existing_media": reused,
            "is_recognised_image_format": suffix in IMAGE_SUFFIXES,
            "track_index": track_index,
            "record_frame": record_frame,
            "start": call(item, "GetStart", None),
            "requested_duration_frames": duration_frames,
            "actual_duration_frames": actual,
            "frame_rate": fps,
            "transform_applied": applied,
        }
        if rejected:
            result["transform_rejected"] = rejected
        notes = []
        if fallback_used:
            notes.append(
                "Resolve would not honour the exact requested length, so a shorter or default "
                "still duration was used."
            )
        try:
            if actual is not None and int(actual) != duration_frames:
                notes.append(
                    "Requested %d frames, Resolve created %d. Raise Preferences > Editing > "
                    "Standard still duration if longer stills are needed."
                    % (duration_frames, int(actual))
                )
        except (TypeError, ValueError):
            pass
        if notes:
            result["notes"] = notes
        return result

    def _op_set_clip_transform(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        applied, rejected = self._apply_transform(item, params)
        if not applied and not rejected:
            raise OperationError(
                "No transform values were supplied. Pass at least one of pan, tilt, pan_percent, "
                "tilt_percent, zoom, zoom_x, zoom_y, rotation, opacity, composite_mode, flip_x, "
                "flip_y, or a crop value."
            )
        result = {"item": info["id"], "applied": applied, "current": self._read_transform(item)}
        if rejected:
            result["rejected"] = rejected
            result["note"] = (
                "Resolve rejected the listed keys. Confirm they are supported on this clip type "
                "and Resolve version."
            )
        return result

    def _op_get_clip_transform(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        width, height = self._project_resolution()
        return {
            "item": info["id"],
            "timeline_resolution": {"width": width, "height": height},
            "transform": self._read_transform(item),
        }

    def _op_add_track(self, params):
        timeline = self._timeline()
        track_type = str(params.get("track_type", "video")).strip().lower()
        if track_type not in ("video", "audio", "subtitle"):
            raise OperationError("track_type must be video, audio, or subtitle.")
        count = max(1, min(int(params.get("count", 1) or 1), 8))
        added = 0
        for _ in range(count):
            if call(timeline, "AddTrack", False, track_type):
                added += 1
            else:
                break
        if not added:
            raise OperationError("Resolve refused to add a %s track." % track_type)
        return {
            "track_type": track_type,
            "added": added,
            "total": call(timeline, "GetTrackCount", 0, track_type),
        }

    def _op_set_track_name(self, params):
        timeline = self._timeline()
        track_type = str(params.get("track_type", "video")).strip().lower()
        index = int(params.get("track_index", 1))
        name = str(params.get("name", "")).strip()
        if not name:
            raise OperationError("name is required.")
        if not call(timeline, "SetTrackName", False, track_type, index, name):
            raise OperationError("Resolve refused to rename %s track %d." % (track_type, index))
        return {"track_type": track_type, "track_index": index, "name": name}

    def _op_insert_title(self, params):
        """Insert a title at the playhead. Text setting is best effort."""
        timeline = self._timeline()
        title = str(params.get("title_name", "") or "Text+").strip()
        item = None
        used = None
        for method in ("InsertFusionTitleIntoTimeline", "InsertTitleIntoTimeline"):
            function = getattr(timeline, method, None)
            if not callable(function):
                continue
            try:
                candidate = function(title)
            except Exception:
                candidate = None
            if candidate:
                item, used = candidate, method
                break
        if item is None:
            raise OperationError(
                "Resolve did not insert a title named '%s'. Use the exact name shown in the Edit "
                "page Titles list, for example 'Text+' or 'Text'. This depends on the Resolve "
                "version and installed title templates." % title
            )

        text = params.get("text")
        text_set = None
        if text is not None:
            text_set = self._set_title_text(item, str(text))
        applied, rejected = self._apply_transform(item, params)
        result = {
            "inserted": call(item, "GetName", title),
            "method": used,
            "start": call(item, "GetStart", None),
            "duration": call(item, "GetDuration", None),
            "text_set": text_set,
            "transform_applied": applied,
        }
        if rejected:
            result["transform_rejected"] = rejected
        if text is not None and not text_set:
            result["note"] = (
                "The title was inserted but its text could not be set through the scripting API. "
                "Type the text in the Inspector, or render the text with Remotion instead."
            )
        return result

    def _set_title_text(self, item, text):
        count = call(item, "GetFusionCompCount", 0) or 0
        for index in range(1, int(count) + 1):
            comp = call(item, "GetFusionCompByIndex", None, index)
            if comp is None:
                continue
            tools = call(comp, "GetToolList", None, False) or {}
            candidates = tools.values() if isinstance(tools, dict) else list(tools)
            for tool in candidates:
                for attribute in ("StyledText", "Text"):
                    try:
                        target = getattr(tool, attribute, None)
                        if target is None:
                            continue
                        setattr(tool, attribute, text)
                        return True
                    except Exception:
                        continue
        return False

    def _op_create_timeline(self, params):
        name = str(params.get("name", "")).strip()
        if not name:
            raise OperationError("name is required.")
        timeline = self._media_pool().CreateEmptyTimeline(name)
        if timeline is None:
            raise OperationError(
                "Resolve could not create the timeline. The name may already be in use."
            )
        self._project().SetCurrentTimeline(timeline)
        return {"created": timeline.GetName()}

    def _op_set_playhead(self, params):
        timecode = str(params.get("timecode", "")).strip()
        if not timecode:
            raise OperationError("timecode is required in HH:MM:SS:FF format.")
        if not self._timeline().SetCurrentTimecode(timecode):
            raise OperationError(
                "Resolve rejected the timecode. Use the timeline's frame rate and HH:MM:SS:FF."
            )
        return {"timecode": timecode}

    def _op_open_page(self, params):
        page = str(params.get("page", "")).strip().lower()
        if page not in PAGES:
            raise OperationError("page must be one of: %s" % ", ".join(PAGES))
        self.resolve.OpenPage(page)
        return {"page": call(self.resolve, "GetCurrentPage", page)}

    def _op_add_marker(self, params):
        timeline = self._timeline()
        frame = params.get("frame")
        if frame is None:
            frame = self._current_marker_frame(timeline)
        color = str(params.get("color", "Blue"))
        name = str(params.get("name", "AI marker"))
        note = str(params.get("note", ""))
        duration = max(1, int(params.get("duration", 1) or 1))
        custom_data = str(params.get("custom_data", "resolve-ai-bridge"))
        if not timeline.AddMarker(int(frame), color, name, note, duration, custom_data):
            raise OperationError(
                "Resolve could not add the marker. A marker may already exist at frame %d, or the "
                "colour name may be invalid." % int(frame)
            )
        return {"frame": int(frame), "color": color, "name": name}

    def _op_delete_marker(self, params):
        frame = int(params.get("frame"))
        if not self._timeline().DeleteMarkerAtFrame(frame):
            raise OperationError("No marker was deleted at frame %d." % frame)
        return {"deleted_frame": frame}

    def _op_set_clip_property(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        name = str(params.get("property_name", "")).strip()
        if not name:
            raise OperationError("property_name is required.")
        value = params.get("value")
        if not item.SetProperty(name, value):
            available = plain(call(item, "GetProperty", {}) or {})
            raise OperationError(
                "Resolve rejected property '%s'. Current values: %s" % (name, json.dumps(available))
            )
        return {"item": info["id"], "property": name, "value": value}

    def _op_set_clip_enabled(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        enabled = bool(params.get("enabled", True))
        if not item.SetClipEnabled(enabled):
            raise OperationError("Resolve could not change the clip enabled state.")
        return {"item": info["id"], "enabled": enabled}

    def _op_set_clip_color(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        color = str(params.get("color", "")).strip()
        ok = item.SetClipColor(color) if color else item.ClearClipColor()
        if not ok:
            raise OperationError(
                "Resolve rejected the clip color. Use a standard Resolve color name, or an empty "
                "value to clear it."
            )
        return {"item": info["id"], "color": color or None}

    def _op_delete_clips(self, params):
        ids = params.get("item_ids") or []
        if not ids:
            raise OperationError("item_ids is required. Call timeline_overview for valid ids.")
        targets = self._find_timeline_items(ids)
        ripple = bool(params.get("ripple", False))
        if not self._timeline().DeleteClips([item for item, _ in targets], ripple):
            raise OperationError("Resolve refused to delete the selected clips.")
        return {"deleted": [info["id"] for _, info in targets], "ripple": ripple}

    def _op_save_project(self, _params):
        if not self.resolve.GetProjectManager().SaveProject():
            raise OperationError("Resolve could not save the current project.")
        return {"saved": True, "project": self._project().GetName()}

    def _op_list_render_presets(self, _params):
        project = self._project()
        return {
            "presets": plain(call(project, "GetRenderPresetList", []) or []),
            "formats": plain(call(project, "GetRenderFormats", {}) or {}),
        }

    def _op_render_current_timeline(self, params):
        project = self._project()
        raw_output_dir = str(params.get("output_dir", "")).strip()
        if not raw_output_dir:
            raise OperationError("output_dir is required.")
        output_dir = _absolute(raw_output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        preset = str(params.get("preset", "")).strip()
        if preset and not project.LoadRenderPreset(preset):
            raise OperationError(
                "Render preset '%s' was not found. Call list_render_presets for valid names."
                % preset
            )
        settings = {"TargetDir": output_dir}
        if params.get("name"):
            settings["CustomName"] = str(params["name"])
        if not project.SetRenderSettings(settings):
            raise OperationError("Resolve rejected the render settings.")
        job_id = project.AddRenderJob()
        if not job_id:
            raise OperationError("Resolve could not add a render job.")
        started = bool(project.StartRendering(job_id)) if params.get("start") else False
        return {
            "job_id": job_id,
            "started": started,
            "output_dir": output_dir,
            "preset": preset or None,
        }

    # ------------------------------------------------------------- dispatch

    def handlers(self):
        return {
            "status": self._op_status,
            "project_info": self._op_project_info,
            "list_timelines": self._op_list_timelines,
            "open_timeline": self._op_open_timeline,
            "timeline_overview": self._op_timeline_overview,
            "list_media": self._op_list_media,
            "import_media": self._op_import_media,
            "append_media": self._op_append_media,
            "add_image": self._op_add_image,
            "insert_title": self._op_insert_title,
            "set_clip_transform": self._op_set_clip_transform,
            "get_clip_transform": self._op_get_clip_transform,
            "add_track": self._op_add_track,
            "set_track_name": self._op_set_track_name,
            "create_timeline": self._op_create_timeline,
            "set_playhead": self._op_set_playhead,
            "open_page": self._op_open_page,
            "add_marker": self._op_add_marker,
            "delete_marker": self._op_delete_marker,
            "set_clip_property": self._op_set_clip_property,
            "set_clip_enabled": self._op_set_clip_enabled,
            "set_clip_color": self._op_set_clip_color,
            "delete_clips": self._op_delete_clips,
            "save_project": self._op_save_project,
            "list_render_presets": self._op_list_render_presets,
            "render_current_timeline": self._op_render_current_timeline,
        }

    def dispatch(self, operation, params=None):
        handlers = self.handlers()
        handler = handlers.get(str(operation))
        if handler is None:
            raise OperationError(
                "Unknown operation '%s'. Available: %s" % (operation, ", ".join(sorted(handlers)))
            )
        return plain(handler(params or {}))

    def heartbeat_payload(self, extra=None):
        payload = self._op_status({})
        payload.update({"pid": os.getpid(), "time": time.time()})
        if extra:
            payload.update(extra)
        return plain(payload)
