# Resolve AI Bridge Agent Instructions

Read `README.md` and `skills/resolve-ai-editing/SKILL.md` before changing the Python bridge or editing a Resolve project.

- Keep `agent/ResolveConsole.py` dependent only on the Python standard library and Resolve's injected objects.
- Never import Resolve from `bridge/` or `tools/`.
- Never write normal output to stdout from `bridge/`; stdio is reserved for MCP JSON-RPC.
- Preserve token validation on every queue request.
- Preserve the non-blocking Console start. Do not replace the daemon worker with a blocking loop.
- Use absolute installed paths in MCP configuration.
- Be honest about anything not tested against a real Resolve instance.
- Run the doctor check and web build after changes when the environment allows it.