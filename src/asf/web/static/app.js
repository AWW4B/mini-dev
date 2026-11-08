/*
FILE: src/asf/web/static/app.js
ROLE: Viewer script: replays /events by seq cursor, then follows the SSE stream; renders every string with textContent only.
ARCH REF: M1; IF-18; D-14b
OWNS: Viewer front-end (no build step, no Node)
DOES NOT OWN: Data (served by server.py)
CONNECTS TO (external boundaries only):
  - called by src/asf/web/server.py: served as a static file
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Never use innerHTML, eval or inline event handlers; treat all event text as untrusted.
  6. No external CDNs; everything is served from 127.0.0.1.
  7. The page has no forms and issues only GET requests.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; write requests; third-party scripts
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
*/

"use strict";
// Stub: implement replay (GET /api/runs/{run}/events?after=seq) then EventSource(/api/runs/{run}/stream).
// Render text ONLY with textContent / createTextNode, never innerHTML.
function main() {
  throw new Error("not implemented");
}
