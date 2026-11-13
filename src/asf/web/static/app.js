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

// Read-only viewer. Every string from the server is untrusted: it is only ever put on the page with textContent.
const state = { cursor: 0, includeInternal: false, source: null, handoffsShown: new Set(), colours: new Map() };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function renderParticipants(participants) {
  const column = document.getElementById("participants");
  column.replaceChildren();
  for (const p of participants) {
    state.colours.set(p.key, p.colour);
    const avatar = el("div", "avatar", p.avatar);
    avatar.style.background = p.colour;
    const info = el("div");
    info.append(el("div", "name", p.key));
    const meta = [p.role, p.model_tier, p.current_task && "task " + p.current_task].filter(Boolean).join(" · ");
    info.append(el("div", "meta", meta));
    if (p.last_result) info.append(el("div", "meta", p.last_result));
    const row = el("div", "participant");
    row.append(avatar, info);
    column.append(row);
  }
}

function renderItem(item) {
  const card = el("div", "card" + (item.internal ? " internal" : ""));
  card.style.borderLeftColor = state.colours.get(item.participant) || "#94a3b8";
  card.append(el("div", "who", item.participant), el("div", "what", item.summary), el("div", "kind", "#" + item.seq + " " + item.kind));
  if (item.detail_ref) {
    const button = el("button", null, "details");
    button.type = "button";
    button.addEventListener("click", () => showDetail(item.detail_ref));
    card.append(button);
  }
  return card;
}

function renderPage(page) {
  document.getElementById("run-title").textContent = "Run " + page.run_id;
  document.getElementById("run-status").textContent = page.status;
  renderParticipants(page.participants);
  const thread = document.getElementById("thread");
  const handoffs = new Map(page.handoffs.map((h) => [h.sent_seq, h]));
  for (const item of page.items) {
    thread.append(renderItem(item));
    const h = handoffs.get(item.seq);
    if (h && !state.handoffsShown.has(h.sent_seq)) {
      state.handoffsShown.add(h.sent_seq);
      thread.append(el("div", "handoff", h.from_participant + " → " + h.to_participant + (h.received_seq === null ? " (not yet received)" : "")));
    }
  }
  state.cursor = Math.max(state.cursor, page.next_seq);
  if (page.items.length) thread.scrollTop = thread.scrollHeight;
}

async function getJson(url) {
  const response = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || response.statusText);
  return body;
}

async function replay() {
  for (;;) {
    const page = await getJson("/api/runs/current/events?after=" + state.cursor + "&limit=200" + (state.includeInternal ? "&internal=1" : ""));
    renderPage(page);
    if (!page.more) return;
  }
}

function follow() {
  if (state.source) state.source.close();
  const url = "/api/runs/current/stream?after=" + state.cursor + (state.includeInternal ? "&internal=1" : "");
  state.source = new EventSource(url);
  const status = document.getElementById("connection");
  state.source.addEventListener("page", (event) => {
    status.textContent = "live";
    renderPage(JSON.parse(event.data));
  });
  state.source.addEventListener("error", () => {
    status.textContent = "reconnecting…";
  });
}

async function showDetail(ref) {
  const drawer = document.getElementById("detail");
  document.getElementById("detail-title").textContent = ref;
  document.getElementById("detail-text").textContent = "loading…";
  drawer.hidden = false;
  try {
    const detail = await getJson("/api/details/" + encodeURIComponent(ref));
    document.getElementById("detail-text").textContent = detail.text + (detail.truncated ? "\n\n[truncated]" : "");
  } catch (err) {
    document.getElementById("detail-text").textContent = String(err.message || err);
  }
}

function main() {
  document.getElementById("detail-close").addEventListener("click", () => { document.getElementById("detail").hidden = true; });
  document.getElementById("show-internal").addEventListener("change", (event) => {
    state.includeInternal = event.target.checked;
    state.cursor = 0;
    state.handoffsShown.clear();
    document.getElementById("thread").replaceChildren();
    replay().then(follow).catch(showError);
  });
  replay().then(follow).catch(showError);
}

function showError(err) {
  document.getElementById("thread").replaceChildren(el("div", "card", String(err.message || err)));
}

main();
