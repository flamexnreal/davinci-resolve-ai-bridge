"""Resolve AI Bridge agent.

Paste the installer-provided exec line into DaVinci Resolve's Python 3 Console.
The script captures Resolve's injected API object, starts a daemon worker, and
returns control to the Console immediately.
"""

import builtins
import hashlib
import hmac
import json
import os
import secrets
import shlex
import subprocess
import threading
import time
import traceback
import uuid
from pathlib import Path


AGENT_VERSION = "1.0.0"
PROTOCOL_VERSION = 1
RUNTIME_KEY = "__resolve_ai_bridge_runtime__"
HOME = Path(os.environ.get("RESOLVE_AI_BRIDGE_HOME", Path.home() / ".resolve-ai-bridge")).expanduser()
INBOX = HOME / "inbox"
OUTBOX = HOME / "outbox"
LOGS = HOME / "logs"
TOKEN_FILE = HOME / "token.txt"
HEARTBEAT_FILE = HOME / "agent.json"


def _ensure_dirs():
    for path in (HOME, INBOX, OUTBOX, LOGS):
        path.mkdir(parents=True, exist_ok=True)


def _atomic_json(path, data):
    path = Path(path)
    temp = path.with_name(".%s.%s.tmp" % (path.name, uuid.uuid4().hex))
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, indent=2)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(str(temp), str(path))


def _read_json(path):
    last_error = None
    for _ in range(4):
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError) as exc:
            last_error = exc
            time.sleep(0.03)
    raise last_error


def _load_token():
    if TOKEN_FILE.exists():
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = "rab_" + secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(value + "\n", encoding="utf-8")
    try:
        os.chmod(str(TOKEN_FILE), 0o600)
    except OSError:
        pass
    return value


def _injected(name):
    value = globals().get(name)
    if value is not None:
        return value
    return getattr(builtins, name, None)


def _get_resolve():
    candidate = _injected("resolve")
    if candidate is not None and hasattr(candidate, "GetProjectManager"):
        return candidate

    for name in ("app", "fusion", "fu"):
        host = _injected(name)
        if host is None:
            continue
        try:
            candidate = host.GetResolve()
            if candidate is not None and hasattr(candidate, "GetProjectManager"):
                return candidate
        except Exception:
            pass

    bmd = _injected("bmd")
    if bmd is not None:
        try:
            candidate = bmd.scriptapp("Resolve")
            if candidate is not None and hasattr(candidate, "GetProjectManager"):
                return candidate
        except Exception:
            pass

    raise RuntimeError(
        "Resolve API was not found. Open Workspace > Console, select Py3, and run this file inside Resolve."
    )


def _call(obj, method, default=None, *args):
    try:
        fn = getattr(obj, method, None)
        return fn(*args) if callable(fn) else default
    except Exception:
        return default


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return str(value)


class ResolveRuntime:
    def __init__(self, resolve):
        _ensure_dirs()
        self.resolve = resolve
        self.token = _load_token()
        self.token_id = hashlib.sha256(self.token.encode("utf-8")).hexdigest()[:12]
        self.stop_event = threading.Event()
        self.thread = None
        self.started_at = time.time()
        self.last_heartbeat = 0.0
        self.log_path = LOGS / "agent.log"

    def log(self, message):
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write("[%s] %s\n" % (stamp, message))
        except Exception:
            pass

    def alive(self):
        return self.thread is not None and self.thread.is_alive() and not self.stop_event.is_set()

    def start(self):
        if self.alive():
            self.banner()
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name="ResolveAIBridge", daemon=True)
        self.thread.start()
        self.banner()

    def stop(self):
        self.stop_event.set()
        self.log("Stop requested from Resolve Console")
        print("Resolve AI Bridge stopping. The heartbeat will expire shortly.")

    def banner(self):
        venv_python = HOME / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        server = HOME / "bridge" / "server.py"
        entry = {
            "command": str(venv_python),
            "args": [str(server)],
            "env": {"RESOLVE_AI_BRIDGE_TOKEN": self.token},
        }
        config = {"mcpServers": {"resolve-ai-bridge": entry}}
        print("\n" + "=" * 68)
        print("RESOLVE AI BRIDGE READY")
        print("Token: %s" % self.token)
        print("Token ID: %s" % self.token_id)
        print("\nGENERIC MCP SERVER ENTRY:")
        print(json.dumps(entry, indent=2))
        print("\nFULL MCP CONFIG (for Antigravity, Cursor, and JSON clients):")
        print(json.dumps(config, indent=2))
        claude_entry_file = HOME / "claude-server-entry.json"
        if os.name == "nt":
            claude_line = (
                '$entry = Get-Content -Raw "%s"; '
                "claude mcp add-json resolve-ai-bridge $entry --scope user"
            ) % claude_entry_file
        else:
            claude_line = (
                'claude mcp add-json resolve-ai-bridge "$(cat %s)" --scope user'
                % shlex.quote(str(claude_entry_file))
            )
        print("\nCLAUDE CODE COMMAND:")
        print(claude_line)
        if os.name == "nt":
            launch = subprocess.list2cmdline([str(venv_python), str(server)])
        else:
            launch = "%s %s" % (shlex.quote(str(venv_python)), shlex.quote(str(server)))
        print("\nCODEX CLI COMMAND:")
        print(
            "codex mcp add resolve-ai-bridge --env RESOLVE_AI_BRIDGE_TOKEN=%s -- %s"
            % (self.token, launch)
        )
        print("\nStop later with: __resolve_ai_bridge_runtime__.stop()")
        print("=" * 68 + "\n")

    def _project(self):
        manager = self.resolve.GetProjectManager()
        if manager is None:
            raise RuntimeError("Resolve did not return a Project Manager.")
        project = manager.GetCurrentProject()
        if project is None:
            raise RuntimeError("No project is open in Resolve.")
        return project

    def _timeline(self):
        timeline = self._project().GetCurrentTimeline()
        if timeline is None:
            raise RuntimeError("No timeline is open. Open a timeline, then try again.")
        return timeline

    def _media_pool(self):
        pool = self._project().GetMediaPool()
        if pool is None:
            raise RuntimeError("Resolve did not return a Media Pool.")
        return pool

    def _item_summary(self, item, track_type, track_index, item_index):
        prefix = "V" if track_type == "video" else "A" if track_type == "audio" else "S"
        unique_id = _call(item, "GetUniqueId", None)
        media_item = _call(item, "GetMediaPoolItem", None)
        media_id = _call(media_item, "GetUniqueId", None) if media_item is not None else None
        return {
            "id": "%s%d.%d" % (prefix, track_index, item_index),
            "unique_id": unique_id,
            "name": _call(item, "GetName", ""),
            "track_type": track_type,
            "track_index": track_index,
            "start": _call(item, "GetStart", None),
            "end": _call(item, "GetEnd", None),
            "duration": _call(item, "GetDuration", None),
            "enabled": _call(item, "GetClipEnabled", None),
            "color": _call(item, "GetClipColor", ""),
            "media_pool_id": media_id,
        }

    def _timeline_items(self):
        timeline = self._timeline()
        results = []
        for track_type in ("video", "audio", "subtitle"):
            count = int(_call(timeline, "GetTrackCount", 0, track_type) or 0)
            for track_index in range(1, count + 1):
                items = _call(timeline, "GetItemListInTrack", [], track_type, track_index) or []
                for item_index, item in enumerate(items, 1):
                    results.append((item, self._item_summary(item, track_type, track_index, item_index)))
        return results

    def _find_timeline_items(self, identifiers):
        wanted = [str(item) for item in identifiers]
        all_items = self._timeline_items()
        found = []
        missing = []
        for identifier in wanted:
            matches = []
            for item, info in all_items:
                if identifier in (str(info.get("id")), str(info.get("unique_id")), str(info.get("name"))):
                    matches.append((item, info))
            if not matches:
                missing.append(identifier)
            elif len(matches) > 1 and all(match[1].get("id") != identifier and str(match[1].get("unique_id")) != identifier for match in matches):
                raise RuntimeError("Clip name '%s' is ambiguous. Use an id such as V1.2 from timeline_overview." % identifier)
            else:
                exact = next((match for match in matches if match[1].get("id") == identifier or str(match[1].get("unique_id")) == identifier), matches[0])
                found.append(exact)
        if missing:
            raise RuntimeError("Timeline item not found: %s. Call timeline_overview for valid ids." % ", ".join(missing))
        return found

    def _walk_media(self, folder, prefix="", limit=2000):
        output = []
        folder_name = _call(folder, "GetName", "Media Pool")
        location = (prefix + "/" + folder_name).strip("/")
        for clip in (_call(folder, "GetClipList", []) or []):
            props = _call(clip, "GetClipProperty", {}) or {}
            output.append({
                "id": _call(clip, "GetUniqueId", None),
                "name": _call(clip, "GetName", props.get("Clip Name", "")),
                "bin": location,
                "file_path": props.get("File Path"),
                "duration": props.get("Duration"),
                "type": props.get("Type"),
            })
            if len(output) >= limit:
                return output
        for child in (_call(folder, "GetSubFolderList", []) or []):
            remaining = max(0, limit - len(output))
            if not remaining:
                break
            output.extend(self._walk_media(child, location, remaining))
        return output

    def _find_media_items(self, identifiers):
        pool = self._media_pool()
        root = pool.GetRootFolder()
        wanted = [str(value) for value in identifiers]
        found = []

        def visit(folder):
            for clip in (_call(folder, "GetClipList", []) or []):
                clip_id = str(_call(clip, "GetUniqueId", ""))
                name = str(_call(clip, "GetName", ""))
                if clip_id in wanted or name in wanted:
                    found.append(clip)
            for child in (_call(folder, "GetSubFolderList", []) or []):
                visit(child)

        visit(root)
        if len(found) < len(wanted):
            raise RuntimeError("One or more media items were not found. Call list_media and use unique ids.")
        return found

    def _project_rate(self):
        project = self._project()
        raw = _call(project, "GetSetting", "24", "timelineFrameRate") or "24"
        try:
            return float(str(raw).replace(" DF", "").strip())
        except ValueError:
            return 24.0

    def _tc_frames(self, value, fps):
        parts = str(value).replace(";", ":").split(":")
        if len(parts) != 4:
            return 0
        hours, minutes, seconds, frames = [int(part) for part in parts]
        rounded = max(1, int(round(fps)))
        return ((hours * 3600 + minutes * 60 + seconds) * rounded) + frames

    def _current_marker_frame(self, timeline):
        current = _call(timeline, "GetCurrentTimecode", "00:00:00:00")
        start = _call(timeline, "GetStartTimecode", "00:00:00:00")
        fps = self._project_rate()
        return max(0, self._tc_frames(current, fps) - self._tc_frames(start, fps))

    def _op_status(self, _params):
        manager = self.resolve.GetProjectManager()
        project = manager.GetCurrentProject() if manager else None
        timeline = project.GetCurrentTimeline() if project else None
        return {
            "online": True,
            "agent_version": AGENT_VERSION,
            "protocol": PROTOCOL_VERSION,
            "resolve_version": _call(self.resolve, "GetVersionString", None),
            "product": _call(self.resolve, "GetProductName", "DaVinci Resolve"),
            "project": _call(project, "GetName", None) if project else None,
            "timeline": _call(timeline, "GetName", None) if timeline else None,
            "token_id": self.token_id,
        }

    def _op_project_info(self, _params):
        project = self._project()
        timeline = project.GetCurrentTimeline()
        return {
            "name": project.GetName(),
            "timeline": _call(timeline, "GetName", None) if timeline else None,
            "timeline_count": _call(project, "GetTimelineCount", 0),
            "frame_rate": _call(project, "GetSetting", None, "timelineFrameRate"),
            "resolution_width": _call(project, "GetSetting", None, "timelineResolutionWidth"),
            "resolution_height": _call(project, "GetSetting", None, "timelineResolutionHeight"),
        }

    def _op_list_timelines(self, _params):
        project = self._project()
        current = project.GetCurrentTimeline()
        timelines = []
        for index in range(1, int(project.GetTimelineCount() or 0) + 1):
            item = project.GetTimelineByIndex(index)
            timelines.append({
                "index": index,
                "name": _call(item, "GetName", ""),
                "current": item == current,
                "start_frame": _call(item, "GetStartFrame", None),
                "end_frame": _call(item, "GetEndFrame", None),
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
            raise RuntimeError("Timeline not found. Call list_timelines for valid names and indexes.")
        if not project.SetCurrentTimeline(selected):
            raise RuntimeError("Resolve refused to open the requested timeline.")
        return {"opened": selected.GetName()}

    def _op_timeline_overview(self, params):
        timeline = self._timeline()
        max_items = max(1, min(int(params.get("max_items", 500)), 2000))
        tracks = []
        clips = []
        for track_type in ("video", "audio", "subtitle"):
            count = int(_call(timeline, "GetTrackCount", 0, track_type) or 0)
            for track_index in range(1, count + 1):
                name = _call(timeline, "GetTrackName", "", track_type, track_index)
                items = _call(timeline, "GetItemListInTrack", [], track_type, track_index) or []
                tracks.append({"type": track_type, "index": track_index, "name": name, "items": len(items)})
                for item_index, item in enumerate(items, 1):
                    if len(clips) < max_items:
                        clips.append(self._item_summary(item, track_type, track_index, item_index))
        return {
            "name": timeline.GetName(),
            "start_frame": _call(timeline, "GetStartFrame", None),
            "end_frame": _call(timeline, "GetEndFrame", None),
            "current_timecode": _call(timeline, "GetCurrentTimecode", None),
            "tracks": tracks,
            "clips": clips,
            "clips_truncated": sum(track["items"] for track in tracks) > len(clips),
            "markers": _plain(_call(timeline, "GetMarkers", {}) or {}),
        }

    def _op_list_media(self, params):
        limit = max(1, min(int(params.get("limit", 1000)), 5000))
        root = self._media_pool().GetRootFolder()
        items = self._walk_media(root, "", limit)
        return {"items": items, "count": len(items), "limited_to": limit}

    def _op_import_media(self, params):
        paths = [str(Path(value).expanduser().resolve()) for value in params.get("paths", [])]
        if not paths:
            raise RuntimeError("paths must contain at least one absolute media file path.")
        missing = [path for path in paths if not Path(path).exists()]
        if missing:
            raise RuntimeError("Media file not found: %s" % ", ".join(missing))
        imported = self._media_pool().ImportMedia(paths) or []
        return {
            "imported": [{"id": _call(item, "GetUniqueId", None), "name": _call(item, "GetName", "")} for item in imported],
            "requested": len(paths),
            "imported_count": len(imported),
        }

    def _op_append_media(self, params):
        media_ids = params.get("media_ids") or []
        paths = params.get("paths") or []
        items = None
        if paths:
            absolute_paths = [str(Path(value).expanduser().resolve()) for value in paths]
            missing = [path for path in absolute_paths if not Path(path).exists()]
            if missing:
                raise RuntimeError("Media file not found: %s" % ", ".join(missing))
            items = list(self._media_pool().ImportMedia(absolute_paths) or [])
            if not items:
                raise RuntimeError("Resolve did not import any of the requested media files.")
        if items is None and not media_ids:
            raise RuntimeError("Provide media_ids from list_media or absolute paths to import and append.")
        if items is None:
            items = self._find_media_items(media_ids)
        track_index = params.get("track_index")
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
                props = _call(item, "GetClipProperty", {}) or {}
                frames = props.get("Frames")
                if frames:
                    try:
                        clip_info.update({"startFrame": 0, "endFrame": max(0, int(frames) - 1)})
                    except (TypeError, ValueError):
                        pass
                payload.append(clip_info)
        created = self._media_pool().AppendToTimeline(payload) or []
        return {"appended_count": len(created), "requested": len(items)}

    def _op_create_timeline(self, params):
        name = str(params.get("name", "")).strip()
        if not name:
            raise RuntimeError("name is required.")
        timeline = self._media_pool().CreateEmptyTimeline(name)
        if timeline is None:
            raise RuntimeError("Resolve could not create the timeline. The name may already exist.")
        self._project().SetCurrentTimeline(timeline)
        return {"created": timeline.GetName()}

    def _op_set_playhead(self, params):
        timecode = str(params.get("timecode", "")).strip()
        if not timecode:
            raise RuntimeError("timecode is required in HH:MM:SS:FF format.")
        ok = self._timeline().SetCurrentTimecode(timecode)
        if not ok:
            raise RuntimeError("Resolve rejected the timecode. Use the timeline's frame rate and HH:MM:SS:FF format.")
        return {"timecode": timecode}

    def _op_add_marker(self, params):
        timeline = self._timeline()
        frame = params.get("frame")
        if frame is None:
            frame = self._current_marker_frame(timeline)
        color = str(params.get("color", "Blue"))
        name = str(params.get("name", "AI marker"))
        note = str(params.get("note", ""))
        duration = max(1, int(params.get("duration", 1)))
        custom_data = str(params.get("custom_data", "resolve-ai-bridge"))
        ok = timeline.AddMarker(int(frame), color, name, note, duration, custom_data)
        if not ok:
            raise RuntimeError("Resolve could not add the marker. Check the frame and marker color.")
        return {"frame": int(frame), "color": color, "name": name}

    def _op_delete_marker(self, params):
        frame = int(params.get("frame"))
        ok = self._timeline().DeleteMarkerAtFrame(frame)
        if not ok:
            raise RuntimeError("No marker was deleted at frame %d." % frame)
        return {"deleted_frame": frame}

    def _op_set_clip_property(self, params):
        targets = self._find_timeline_items([params.get("item_id")])
        item, info = targets[0]
        name = str(params.get("property_name", "")).strip()
        if not name:
            raise RuntimeError("property_name is required.")
        value = params.get("value")
        ok = item.SetProperty(name, value)
        if not ok:
            available = _plain(_call(item, "GetProperty", {}) or {})
            raise RuntimeError("Resolve rejected property '%s'. Available values: %s" % (name, json.dumps(available)))
        return {"item": info["id"], "property": name, "value": value}

    def _op_set_clip_enabled(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        enabled = bool(params.get("enabled", True))
        ok = item.SetClipEnabled(enabled)
        if not ok:
            raise RuntimeError("Resolve could not change the clip enabled state.")
        return {"item": info["id"], "enabled": enabled}

    def _op_set_clip_color(self, params):
        item, info = self._find_timeline_items([params.get("item_id")])[0]
        color = str(params.get("color", "")).strip()
        if color:
            ok = item.SetClipColor(color)
        else:
            ok = item.ClearClipColor()
        if not ok:
            raise RuntimeError("Resolve rejected the clip color. Use a standard Resolve color name or an empty value to clear it.")
        return {"item": info["id"], "color": color or None}

    def _op_delete_clips(self, params):
        ids = params.get("item_ids") or []
        if not ids:
            raise RuntimeError("item_ids is required. Call timeline_overview for valid ids.")
        targets = self._find_timeline_items(ids)
        ripple = bool(params.get("ripple", False))
        ok = self._timeline().DeleteClips([item for item, _ in targets], ripple)
        if not ok:
            raise RuntimeError("Resolve refused to delete the selected clips.")
        return {"deleted": [info["id"] for _, info in targets], "ripple": ripple}

    def _op_save_project(self, _params):
        ok = self.resolve.GetProjectManager().SaveProject()
        if not ok:
            raise RuntimeError("Resolve could not save the current project.")
        return {"saved": True, "project": self._project().GetName()}

    def _op_render_current_timeline(self, params):
        project = self._project()
        raw_output_dir = str(params.get("output_dir", "")).strip()
        if not raw_output_dir:
            raise RuntimeError("output_dir is required.")
        output_dir = str(Path(raw_output_dir).expanduser().resolve())
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        preset = str(params.get("preset", "")).strip()
        if preset and not project.LoadRenderPreset(preset):
            raise RuntimeError("Render preset '%s' was not found in Resolve." % preset)
        settings = {"TargetDir": output_dir}
        if params.get("name"):
            settings["CustomName"] = str(params["name"])
        if not project.SetRenderSettings(settings):
            raise RuntimeError("Resolve rejected the render settings.")
        job_id = project.AddRenderJob()
        if not job_id:
            raise RuntimeError("Resolve could not add a render job.")
        started = False
        if bool(params.get("start", False)):
            started = bool(project.StartRendering(job_id))
        return {"job_id": job_id, "started": started, "output_dir": output_dir, "preset": preset or None}

    def dispatch(self, operation, params):
        handlers = {
            "status": self._op_status,
            "project_info": self._op_project_info,
            "list_timelines": self._op_list_timelines,
            "open_timeline": self._op_open_timeline,
            "timeline_overview": self._op_timeline_overview,
            "list_media": self._op_list_media,
            "import_media": self._op_import_media,
            "append_media": self._op_append_media,
            "create_timeline": self._op_create_timeline,
            "set_playhead": self._op_set_playhead,
            "add_marker": self._op_add_marker,
            "delete_marker": self._op_delete_marker,
            "set_clip_property": self._op_set_clip_property,
            "set_clip_enabled": self._op_set_clip_enabled,
            "set_clip_color": self._op_set_clip_color,
            "delete_clips": self._op_delete_clips,
            "save_project": self._op_save_project,
            "render_current_timeline": self._op_render_current_timeline,
        }
        handler = handlers.get(operation)
        if handler is None:
            raise RuntimeError("Unknown operation '%s'. Available: %s" % (operation, ", ".join(sorted(handlers))))
        return _plain(handler(params or {}))

    def _heartbeat(self):
        status = self._op_status({})
        status.update({
            "pid": os.getpid(),
            "time": time.time(),
            "started_at": self.started_at,
            "thread_alive": True,
        })
        _atomic_json(HEARTBEAT_FILE, status)
        self.last_heartbeat = time.time()

    def _process(self, path):
        request_id = path.stem
        started = time.time()
        response = {"id": request_id, "ok": False}
        try:
            request = _read_json(path)
            if str(request.get("id", "")) != request_id:
                raise RuntimeError("Request id does not match its queue filename.")
            supplied = str(request.get("token", ""))
            if not hmac.compare_digest(supplied, self.token):
                raise RuntimeError("Bridge token mismatch. Re-copy the MCP config printed in the Resolve Console.")
            response["result"] = self.dispatch(str(request.get("op", "")), request.get("params") or {})
            response["ok"] = True
        except Exception as exc:
            response["error"] = str(exc)
            response["traceback"] = traceback.format_exc(limit=8)
            self.log("Request %s failed: %s" % (request_id, exc))
        response["took_ms"] = int((time.time() - started) * 1000)
        _atomic_json(OUTBOX / (request_id + ".json"), response)
        try:
            path.unlink()
        except OSError:
            pass

    def _loop(self):
        self.log("Agent %s started with token id %s" % (AGENT_VERSION, self.token_id))
        try:
            self._heartbeat()
            while not self.stop_event.wait(0.08):
                now = time.time()
                if now - self.last_heartbeat >= 2.0:
                    try:
                        self._heartbeat()
                    except Exception as exc:
                        self.log("Heartbeat failed: %s" % exc)
                for path in sorted(INBOX.glob("*.json"))[:8]:
                    try:
                        self._process(path)
                    except Exception as exc:
                        self.log("Could not process %s: %s" % (path.name, exc))
        finally:
            try:
                HEARTBEAT_FILE.unlink()
            except OSError:
                pass
            self.log("Agent stopped")


def _start_bridge():
    _ensure_dirs()
    existing = getattr(builtins, RUNTIME_KEY, None)
    if existing is not None and getattr(existing, "alive", lambda: False)():
        existing.banner()
        return existing
    runtime = ResolveRuntime(_get_resolve())
    setattr(builtins, RUNTIME_KEY, runtime)
    globals()[RUNTIME_KEY] = runtime
    runtime.start()
    return runtime


try:
    _start_bridge()
except Exception as error:
    print("\nRESOLVE AI BRIDGE DID NOT START")
    print(str(error))
    print("See ~/.resolve-ai-bridge/logs/agent.log after resolving the issue.\n")