"""Direct attach transport: talk to DaVinci Resolve without a Console worker.

Resolve ships a native module (``fusionscript``) that lets a normal Python
process obtain the same API object the internal Console gets. When that works,
Resolve AI Bridge needs nothing pasted or clicked: open Resolve and the MCP
tools are live.

Blackmagic's own scripting README states that "the DaVinci Resolve scripting
APIs cover a common superset of functions for both the Free and Studio versions
of the application", so this path is not Studio-only. It can still be
unavailable, for example when:

* Resolve is not running
* Preferences > System > General > External scripting using is set to None
* the native module cannot be loaded by this exact Python build

Every failure is reported as a reason string and the bridge falls back to the
authenticated Console queue, which always works.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MODULE_NAME = "fusionscript"

MAC_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
MAC_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
WIN_LIB = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
LINUX_LIBS = (
    "/opt/resolve/libs/Fusion/fusionscript.so",
    "/home/resolve/libs/Fusion/fusionscript.so",
)

_cache = {"module": None, "resolve": None, "reason": None, "probed": None}


def library_candidates():
    """Absolute paths to try, most specific first."""
    candidates = []
    override = os.environ.get("RESOLVE_SCRIPT_LIB", "").strip()
    if override:
        candidates.append(override)
    if sys.platform.startswith("darwin"):
        candidates.append(MAC_LIB)
    elif sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
        candidates.append(WIN_LIB)
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        candidates.append(str(Path(program_files) / "Blackmagic Design" / "DaVinci Resolve" / "fusionscript.dll"))
    else:
        candidates.extend(LINUX_LIBS)
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _load_module():
    """Import the native Resolve scripting module, or raise ImportError."""
    try:  # Already available when running inside Resolve's own interpreter.
        import fusionscript  # type: ignore

        return fusionscript
    except ImportError:
        pass

    import importlib.machinery
    import importlib.util

    attempts = []
    for path in library_candidates():
        if not Path(path).exists():
            attempts.append("%s (not found)" % path)
            continue
        try:
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(Path(path).parent))
                except OSError:
                    pass
            loader = importlib.machinery.ExtensionFileLoader(MODULE_NAME, path)
            spec = importlib.util.spec_from_loader(MODULE_NAME, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
            return module
        except Exception as exc:
            attempts.append("%s (%s)" % (path, exc))
    raise ImportError(
        "Could not load Resolve's scripting library. Tried: %s" % "; ".join(attempts or ["no candidates"])
    )


def attach():
    """Return a live Resolve object, or None with ``last_reason()`` explaining why."""
    if _cache["resolve"] is not None:
        try:  # Confirm the cached handle still answers.
            if _cache["resolve"].GetProductName():
                return _cache["resolve"]
        except Exception:
            pass
        _cache["resolve"] = None

    if _cache["module"] is None:
        try:
            _cache["module"] = _load_module()
        except ImportError as exc:
            _cache["reason"] = str(exc)
            return None

    try:
        instance = _cache["module"].scriptapp("Resolve")
    except Exception as exc:
        _cache["reason"] = "Resolve's scripting library raised: %s" % exc
        return None

    if instance is None:
        _cache["reason"] = (
            "Resolve's scripting library loaded but Resolve did not answer. Open DaVinci Resolve, "
            "and check Preferences > System > General > External scripting using is not set to None."
        )
        return None

    _cache["resolve"] = instance
    _cache["reason"] = None
    return instance


def last_reason():
    return _cache["reason"]


def probe_in_process():
    """Attempt an attach and describe the outcome as JSON-safe data.

    ``loadable`` is the important field: it says the native module can be
    imported by this Python build without crashing it, which means in-process
    attaches are safe to retry even while Resolve is closed.
    """
    instance = attach()
    loadable = _cache["module"] is not None
    if instance is None:
        return {"ok": False, "loadable": loadable, "reason": last_reason() or "unknown"}
    try:
        return {
            "ok": True,
            "loadable": True,
            "product": instance.GetProductName(),
            "version": instance.GetVersionString(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "loadable": True,
            "reason": "Resolve answered but failed a basic call: %s" % exc,
        }


PROBE_SOURCE = (
    "import json,sys;"
    "sys.path.insert(0, %r);"
    "from bridge import direct;"
    "sys.stdout.write(json.dumps(direct.probe_in_process()))"
)


def probe(timeout=20.0, force=False):
    """Test direct attach in a short-lived subprocess before trusting it here.

    Loading a native module built for a different Python can abort the whole
    process. The MCP server must survive that, so the first attempt happens
    somewhere disposable.
    """
    if _cache["probed"] is not None and not force:
        return _cache["probed"]
    command = [sys.executable, "-c", PROBE_SOURCE % str(ROOT)]
    try:
        finished = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
    except subprocess.TimeoutExpired:
        outcome = {
            "ok": False,
            "loadable": False,
            "reason": "The direct attach probe timed out after %.0fs." % timeout,
        }
    except OSError as exc:
        outcome = {
            "ok": False,
            "loadable": False,
            "reason": "Could not start the direct attach probe: %s" % exc,
        }
    else:
        payload = (finished.stdout or "").strip()
        if finished.returncode != 0 and not payload:
            detail = (finished.stderr or "").strip().splitlines()
            outcome = {
                "ok": False,
                "loadable": False,
                "reason": "The direct attach probe exited with code %d. %s"
                % (finished.returncode, detail[-1] if detail else "No output."),
            }
        else:
            try:
                outcome = json.loads(payload)
            except ValueError:
                outcome = {
                    "ok": False,
                    "loadable": False,
                    "reason": "The direct attach probe returned unreadable output.",
                }
    _cache["probed"] = outcome
    return outcome


def reset():
    """Forget cached state so the next call re-probes and re-attaches."""
    _cache.update({"module": None, "resolve": None, "reason": None, "probed": None})
