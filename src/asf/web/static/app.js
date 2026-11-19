/*
FILE: src/asf/web/static/app.js
ROLE: Viewer script: replays /events by seq cursor, then follows the SSE stream; renders agents talking to each other as a group conversation using textContent only.
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
// The run is shown as a group conversation between the agents: each message is an event, a hand-off is a message addressed to
// another agent with a delivery receipt, and tool calls are quiet activity lines under the agent that made them.
const SVG_NS = "http://www.w3.org/2000/svg";
// the server colours each role deterministically; they are mapped onto Apple's system colours here
const SYSTEM_COLOURS = {
  "#2563eb": "#007aff", "#16a34a": "#34c759", "#d97706": "#ff9500", "#9333ea": "#af52de",
  "#dc2626": "#ff3b30", "#0891b2": "#32ade6", "#be185d": "#ff2d55", "#65a30d": "#00c7be",
};
const ICONS = {
  "arrow-right": { paths: ["M5 12h14M13 6l6 6-6 6"] },
  "arrow-down": { paths: ["M12 5v14M6 13l6 6 6-6"] },
  reply: { paths: ["M9 14L4 9l5-5M4 9h10a6 6 0 016 6v2"] },
  terminal: { paths: ["M4 7l5 5-5 5M12 18h8"] },
  check: { circle: true, paths: ["M8 12.5l2.7 2.7L16 9.5"] },
  xmark: { circle: true, paths: ["M9.5 9.5l5 5M14.5 9.5l-5 5"] },
  alert: { paths: ["M12 4.5l9 15.5H3L12 4.5zM12 10v4.5M12 17.4v.1"] },
};
const QUIET_STATUSES = new Set(["DONE", "FAILED", "CANCELLED", "CANCELED", "ABORTED", "COMPLETED", "SUCCEEDED", "ERROR", "STOPPED", "PAUSED", "PENDING", "BLOCKED", "UNKNOWN"]);
const ACTIVITY_KINDS = new Set(["tool_called", "tool_result"]);

const state = {
  cursor: 0, includeInternal: false, source: null, live: false, count: 0,
  colours: new Map(), participants: new Map(), handoffs: new Map(), handoffByReceipt: new Map(),
  group: null, activeKey: null, typing: null, opener: null, unseen: 0,
};

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function icon(name) {
  const spec = ICONS[name];
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  if (spec.circle) {
    const ring = document.createElementNS(SVG_NS, "circle");
    ring.setAttribute("cx", "12"); ring.setAttribute("cy", "12"); ring.setAttribute("r", "9");
    svg.append(ring);
  }
  for (const d of spec.paths) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

// the tag on a bubble already says what the template prefix says ("Gate passed", "To reviewer"), so the prefix is dropped from the text
const PREFIXES = {
  handoff_sent: /^handed over to [^:]+:\s*/i,
  handoff_received: /^received the hand-off:?\s*/i,
  gate_result: /^gate (passed|failed)( \([^)]*\))?:?\s*/i,
  decision_needed: /^needs a decision \([^)]*\):\s*/i,
};
function bodyText(item) {
  const prefix = PREFIXES[item.kind];
  const trimmed = prefix ? item.summary.replace(prefix, "") : item.summary;
  return trimmed || item.summary;
}

// capitalise a plain first word only; "greet(name)" or "write_file" are identifiers and stay as written
const sentence = (text) => (text && /^[a-z]+(\s|$)/.test(text) ? text.charAt(0).toUpperCase() + text.slice(1) : text || "");
const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function colourOf(key) {
  const raw = state.colours.get(key);
  return SYSTEM_COLOURS[raw] || raw || "#8e8e93";
}

function initials(key) {
  const p = state.participants.get(key);
  return (p && p.avatar) || (key.match(/[A-Za-z0-9]/g) || ["?"]).slice(0, 2).join("").toUpperCase();
}

function makeAvatar(key) {
  const node = el("div", "avatar", initials(key));
  node.style.setProperty("--c", colourOf(key));
  node.setAttribute("aria-hidden", "true");
  return node;
}

function roleLine(key) {
  const p = state.participants.get(key);
  return p ? [p.role, p.model_tier].filter(Boolean).join(" · ") : "";
}

/* ---------- agent list ---------- */

function renderParticipants(participants) {
  const column = $("participants");
  column.replaceChildren();
  if (!participants.length) return;
  const list = el("div", "group-list");
  for (const p of participants) {
    const row = el("div", "participant" + (p.key === state.activeKey && isRunning() ? " active" : ""));
    const info = el("div", "info");
    info.append(el("div", "name", p.key));
    const meta = [p.role, p.model_tier, p.current_task && "task " + p.current_task].filter(Boolean).join(" · ");
    if (meta) info.append(el("div", "meta", meta));
    if (p.last_result) info.append(el("div", "last", sentence(p.last_result)));
    const presence = el("span", "presence");
    presence.title = "Working now";
    row.append(makeAvatar(p.key), info, presence);
    list.append(row);
  }
  column.append(el("h2", null, "Agents"), list);
}

function isRunning() {
  return !QUIET_STATUSES.has(String(state.status || "UNKNOWN").toUpperCase());
}

/* ---------- hand-offs: a message to another agent with a delivery receipt ---------- */

function receiptText(h) {
  return h.received_seq === null ? "Sent · waiting for " + h.to_participant : "Received by " + h.to_participant;
}

function updateReceipt(entry) {
  if (!entry.receipt) return;
  entry.receipt.textContent = receiptText(entry.h);
  entry.receipt.classList.toggle("done", entry.h.received_seq !== null);
}

function registerHandoffs(handoffs) {
  for (const h of handoffs) {
    const known = state.handoffs.get(h.sent_seq);
    if (known) {
      known.h = h;
      updateReceipt(known);
    } else {
      state.handoffs.set(h.sent_seq, { h, receipt: null });
    }
    if (h.received_seq !== null) state.handoffByReceipt.set(h.received_seq, h);
  }
}

// A hand-off that was sent on an earlier page cannot be paired by the server: pair it here by the receiving agent's name or role.
function matchReceipt(item) {
  const exact = state.handoffByReceipt.get(item.seq);
  if (exact) return exact;
  const who = item.participant.toLowerCase();
  const role = (roleLine(item.participant).split(" · ")[0] || "").toLowerCase();
  for (const entry of state.handoffs.values()) {
    const to = entry.h.to_participant.toLowerCase();
    if (entry.h.received_seq === null && (to === who || (role && to === role))) {
      entry.h = { ...entry.h, received_seq: item.seq };
      state.handoffByReceipt.set(item.seq, entry.h);
      updateReceipt(entry);
      return entry.h;
    }
  }
  return null;
}

/* ---------- conversation ---------- */

function clearEmpty() {
  const empty = document.querySelector(".empty");
  if (empty) empty.remove();
}

function newGroup(item, animate) {
  const root = el("div", "group" + (animate ? " enter" : ""));
  root.style.setProperty("--c", colourOf(item.participant));
  const stack = el("div", "stack");
  const sender = el("div", "sender" + (item.internal ? " internal" : ""));
  sender.append(el("b", null, item.participant));
  const role = roleLine(item.participant);
  if (role && role.split(" · ")[0].toLowerCase() !== item.participant.toLowerCase()) sender.append(el("span", null, role));
  stack.append(sender);
  root.append(makeAvatar(item.participant), stack);
  $("inner").append(root);
  state.group = { who: item.participant, internal: item.internal, stack, last: null };
  return state.group;
}

function detailLink(item) {
  const button = el("button", "link", "View details");
  button.type = "button";
  button.addEventListener("click", () => showDetail(item.detail_ref, button));
  return button;
}

function appendActivity(item, group) {
  const line = el("div", "activity");
  line.append(icon(item.kind === "tool_called" ? "terminal" : "check"), el("span", null, sentence(item.summary)));
  if (item.detail_ref) line.append(detailLink(item));
  line.title = "#" + item.seq + " " + item.kind.replaceAll("_", " ");
  group.stack.append(line);
}

function appendBubble(item, group) {
  const bubble = el("div", "bubble");
  bubble.title = "#" + item.seq + " " + item.kind.replaceAll("_", " ");
  let handoff = null;
  if (item.internal) bubble.classList.add("internal");
  if (item.kind === "handoff_sent") {
    bubble.classList.add("handoff");
    handoff = state.handoffs.get(item.seq) || null;
    const to = handoff ? handoff.h.to_participant : "another agent";
    const tag = el("div", "tag");
    tag.append(icon("arrow-right"), el("span", null, "To " + to));
    bubble.append(tag);
  } else if (item.kind === "handoff_received") {
    const from = matchReceipt(item);
    if (from) {
      const reply = el("div", "reply");
      reply.append(icon("reply"), el("span", null, "Hand-off from " + from.from_participant));
      bubble.append(reply);
    }
  } else if (item.kind === "gate_result") {
    const passed = /^gate passed/i.test(item.summary);
    bubble.classList.add(passed ? "gate-pass" : "gate-fail");
    const tag = el("div", "tag");
    tag.append(icon(passed ? "check" : "xmark"), el("span", null, passed ? "Gate passed" : "Gate failed"));
    bubble.append(tag);
  } else if (item.kind === "decision_needed") {
    bubble.classList.add("decision");
    const tag = el("div", "tag");
    tag.append(icon("alert"), el("span", null, "Needs a decision"));
    bubble.append(tag);
  }
  bubble.append(el("p", "what", sentence(bodyText(item))));
  const previous = group.stack.lastElementChild;
  if (previous && previous === group.last) {
    previous.classList.add("followed");
    bubble.classList.add("cont");
  }
  group.stack.append(bubble);
  group.last = bubble;
  if (handoff) {
    const receipt = el("div", "under receipt");
    handoff.receipt = receipt;
    updateReceipt(handoff);
    group.stack.append(receipt);
  }
  if (item.detail_ref) {
    const under = el("div", "under");
    under.append(detailLink(item));
    group.stack.append(under);
  }
}

function appendItem(item, animate) {
  clearEmpty();
  const reused = Boolean(state.group && state.group.who === item.participant && state.group.internal === item.internal);
  const group = reused ? state.group : newGroup(item, animate);
  const before = group.stack.childElementCount;
  if (ACTIVITY_KINDS.has(item.kind)) appendActivity(item, group);
  else appendBubble(item, group);
  if (animate && reused) {
    for (const child of Array.from(group.stack.children).slice(before)) child.classList.add("enter");
  }
  state.count += 1;
}

function syncTyping() {
  if (state.typing) state.typing.remove();
  state.typing = null;
  if (!state.activeKey || !isRunning() || !state.count) return;
  const row = el("div", "group");
  row.style.setProperty("--c", colourOf(state.activeKey));
  const bubble = el("div", "typing");
  bubble.setAttribute("role", "img");
  bubble.setAttribute("aria-label", state.activeKey + " is working");
  bubble.append(el("i"), el("i"), el("i"));
  const avatar = makeAvatar(state.activeKey);
  if (state.group && state.group.who === state.activeKey) avatar.style.visibility = "hidden"; // the agent's own messages sit right above
  row.append(avatar, bubble);
  $("inner").append(row);
  state.typing = row;
}

function showEmpty(message, detail, retry) {
  const empty = el("div", "empty");
  empty.append(el("strong", null, message), document.createTextNode(detail));
  if (retry) {
    const button = el("button", "link", "Try again");
    button.type = "button";
    button.addEventListener("click", retry);
    empty.append(document.createElement("br"), button);
  }
  state.group = null;
  state.typing = null;
  $("inner").replaceChildren(empty);
}

function nearBottom(thread) {
  return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 96;
}

function renderPage(page) {
  const thread = $("thread");
  const stick = !state.live || nearBottom(thread);
  state.status = page.status;
  $("run-title").textContent = "Run " + page.run_id;
  const status = String(page.status || "").toLowerCase().replaceAll("_", " ");
  $("run-status").textContent = sentence(status);
  for (const p of page.participants) state.colours.set(p.key, p.colour);
  state.participants = new Map(page.participants.map((p) => [p.key, p]));
  registerHandoffs(page.handoffs);
  const animate = state.live && !reduceMotion();
  for (const item of page.items) appendItem(item, animate);
  if (page.items.length) state.activeKey = page.items[page.items.length - 1].participant;
  renderParticipants(page.participants);
  state.cursor = Math.max(state.cursor, page.next_seq);
  if (!state.count && !state.live) showEmpty("No messages yet", "The agents appear here as soon as the run starts.");
  syncTyping();
  if (stick) {
    thread.scrollTo({ top: thread.scrollHeight, behavior: state.live && !reduceMotion() ? "smooth" : "auto" });
    setUnseen(0);
  } else if (page.items.length) {
    setUnseen(state.unseen + page.items.length);
  }
}

function setUnseen(count) {
  state.unseen = count;
  const jump = $("jump");
  jump.hidden = count === 0;
  if (count) jump.replaceChildren(icon("arrow-down"), document.createTextNode(" " + count + (count === 1 ? " new message" : " new messages")));
}

/* ---------- data ---------- */

async function getJson(url) {
  const response = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || response.statusText);
  return body;
}

async function replay() {
  $("thread").setAttribute("aria-busy", "true");
  try {
    for (;;) {
      const page = await getJson("/api/runs/current/events?after=" + state.cursor + "&limit=200" + (state.includeInternal ? "&internal=1" : ""));
      renderPage(page);
      if (!page.more) return;
    }
  } finally {
    $("thread").removeAttribute("aria-busy");
  }
}

function setConnection(kind, text) {
  const node = $("connection");
  node.className = "conn " + kind;
  node.textContent = text;
}

function follow() {
  if (state.source) state.source.close();
  state.live = true;
  const url = "/api/runs/current/stream?after=" + state.cursor + (state.includeInternal ? "&internal=1" : "");
  state.source = new EventSource(url);
  state.source.addEventListener("open", () => setConnection("live", "Live"));
  state.source.addEventListener("page", (event) => {
    setConnection("live", "Live");
    renderPage(JSON.parse(event.data));
  });
  state.source.addEventListener("error", () => setConnection("retry", "Reconnecting"));
}

function start() {
  state.live = false;
  setConnection("", "Connecting");
  replay().then(follow).catch(showError);
}

function showError(err) {
  setConnection("retry", "Offline");
  state.count = 0;
  showEmpty("Can't load this run", String(err.message || err), start);
}

/* ---------- details sheet ---------- */

async function showDetail(ref, opener) {
  state.opener = opener || null;
  $("detail-ref").textContent = ref;
  $("detail-text").textContent = "Loading…";
  $("detail").hidden = false;
  $("scrim").hidden = false;
  $("detail-close").focus();
  try {
    const detail = await getJson("/api/details/" + encodeURIComponent(ref));
    $("detail-text").textContent = (detail.text || detail.error || "") + (detail.truncated ? "\n\n[truncated]" : "");
  } catch (err) {
    $("detail-text").textContent = String(err.message || err);
  }
}

function closeDetail() {
  $("detail").hidden = true;
  $("scrim").hidden = true;
  if (state.opener && state.opener.isConnected) state.opener.focus();
  state.opener = null;
}

function main() {
  const inner = el("div", "thread-inner");
  inner.id = "inner";
  $("thread").append(inner);
  $("detail-close").addEventListener("click", closeDetail);
  $("scrim").addEventListener("click", closeDetail);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("detail").hidden) closeDetail();
  });
  $("jump").addEventListener("click", () => {
    $("thread").scrollTo({ top: $("thread").scrollHeight, behavior: reduceMotion() ? "auto" : "smooth" });
    setUnseen(0);
  });
  $("thread").addEventListener("scroll", () => {
    if (state.unseen && nearBottom($("thread"))) setUnseen(0);
  }, { passive: true });
  $("show-internal").addEventListener("change", (event) => {
    state.includeInternal = event.target.checked;
    state.cursor = 0;
    state.count = 0;
    state.group = null;
    state.typing = null;
    state.handoffs.clear();
    state.handoffByReceipt.clear();
    setUnseen(0);
    inner.replaceChildren();
    if (state.source) state.source.close();
    start();
  });
  start();
}

main();
