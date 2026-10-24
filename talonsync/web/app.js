/* TalonSync window. Talks to the local Python service over /api (see server.py). */
"use strict";
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };

async function api(path, body, method) {
  const opt = { method: method || (body !== undefined ? "POST" : "GET"), headers: { "X-Token": TOKEN } };
  if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch("/api/" + path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, bad = false) {
  const el = h(`<div class="toast ${bad ? "bad" : ""}">${esc(msg)}</div>`);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), bad ? 6500 : 3800);
}
async function safely(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(typeof okMsg === "function" ? okMsg(r) : okMsg); return r; }
  catch (e) { toast(e.message || String(e), true); }
}

// ---------------------------------------------------------------- icons (24 x 24 line icons)
const I = {
  today: '<path d="M4 6h16v14H4zM4 10h16M9 3v4M15 3v4"/><circle cx="12" cy="15" r="2"/>',
  calendar: '<path d="M4 6h16v14H4zM4 10h16M9 3v4M15 3v4M8 14h3M13 14h3M8 17h3"/>',
  contacts: '<circle cx="12" cy="9" r="3.5"/><path d="M5 20c1-4 4-5.5 7-5.5s6 1.5 7 5.5"/>',
  tasks: '<path d="M4 7l2 2 3-4M11 7h9M4 14l2 2 3-4M11 14h9"/>',
  memos: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/>',
  notepad: '<path d="M5 19l3-1 10-10-2-2L6 16zM14 6l2 2"/><path d="M4 21h16"/>',
  hypno: '<path d="M12 12m-1 0a1 1 0 1 0 2 0a2.5 2.5 0 1 0-5 0a4 4 0 1 0 8 0a5.5 5.5 0 1 0-11 0a7 7 0 1 0 14 0"/>',
  talonstar: '<path d="M12 3l2.5 5.2 5.7.8-4.1 4 1 5.7L12 16l-5.1 2.7 1-5.7-4.1-4 5.7-.8z"/>',
  pclink: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/><path d="M6 10h3l1.5-3 2 6 1.5-3H18"/>',
  pet: '<path d="M6 8c0-3 3-5 6-5s6 2 6 5v5a6 6 0 0 1-12 0z"/><circle cx="9.5" cy="9.5" r="1.5"/><circle cx="14.5" cy="9.5" r="1.5"/><path d="M11 13l1 1.5 1-1.5"/>',
  music: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  nowplaying: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  remote: '<rect x="7" y="2" width="10" height="20" rx="3"/><circle cx="12" cy="15" r="2.5"/><path d="M10 6h4"/>',
  log: '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',
  files: '<path d="M3 7h6l2 2h10v10H3z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', trash: '<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/>',
  star: '<path d="M12 4l2.3 4.7 5.2.8-3.8 3.7.9 5.2L12 16l-4.6 2.4.9-5.2-3.8-3.7 5.2-.8z"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>', down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  play: '<path d="M8 5l11 7-11 7z"/>', next: '<path d="M6 5l9 7-9 7zM17 5v14"/>', prev: '<path d="M18 5l-9 7 9 7zM7 5v14"/>',
  full: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  jazz: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  pda: '<rect x="6" y="2" width="12" height="20" rx="3"/><rect x="8.5" y="5" width="7" height="8" rx="1"/>',
};
const icon = (k, cls = "") => `<svg viewBox="0 0 24 24" class="${cls}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${I[k] || ""}</svg>`;

// ---------------------------------------------------------------- app state
const S = { state: null, meta: null, settings: null, view: "today", rev: -1, cache: {}, sel: {}, dirty: false };
const VIEWS = [
  ["today", "Today"], ["calendar", "Calendar"], ["contacts", "Contacts"], ["tasks", "Tasks"], ["memos", "Memos"],
  "-", ["talonstar", "TalonStar 4000"], ["hypno", "Hypnospiral"], ["nowplaying", "Now Playing"], ["pclink", "PC Link"], ["pet", "Hoot Pet"], ["remote", "PDA Remote"],
  "-", ["log", "TalonSync Log"], ["files", "Import & Export"], ["settings", "Settings"],
];
const COUNT_OF = { calendar: "events", contacts: "contacts", tasks: "tasks", memos: "memos" };

function buildNav() {
  const nav = $("#nav"); nav.innerHTML = "";
  for (const v of VIEWS) {
    if (v === "-") { nav.append(h('<div class="nav-sep"></div>')); continue; }
    const b = h(`<button data-v="${v[0]}" title="${v[1]}">${icon(v[0])}<span>${v[1]}</span><span class="count" data-count="${v[0]}"></span></button>`);
    b.onclick = () => go(v[0]);
    nav.append(b);
  }
}
function go(view) {
  if (S.dirty && !confirm("You have unsaved changes. Leave without saving?")) return;
  S.dirty = false;
  if (S.view === "talonstar" && view !== "talonstar") TS.leave();
  S.view = view;
  try { localStorage.setItem("ts.view", view); } catch (e) {}
  $$("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.v === view));
  render();
}
function render() {
  const v = VIEWS.find((x) => x !== "-" && x[0] === S.view) || VIEWS[0];
  $("#view-title").textContent = v[1];
  $("#view-tools").innerHTML = "";
  const el = $("#view"); el.innerHTML = ""; el.scrollTop = 0;
  (R[S.view] || R.today)(el, $("#view-tools"));
}

// ---------------------------------------------------------------- polling
async function poll() {
  try {
    const st = await api("state");
    S.state = st;
    paintStatus(st);
    paintSync(st);
    if (st.revision !== S.rev) {
      const first = S.rev === -1; S.rev = st.revision; S.cache = {};
      if (!first && !S.dirty && ["today", "calendar", "contacts", "tasks", "memos", "pet", "nowplaying"].includes(S.view)) refreshView();
    }
    if (S.view === "today") paintTodayLive(st);
    if (S.view === "nowplaying") paintNowLive(st);
    if (S.view === "pclink") paintPcLive(st);
  } catch (e) { paintStatus(null); }
  setTimeout(poll, S.state && S.state.sync && S.state.sync.running ? 250 : 700);
}
function refreshView() { const keep = $("#view").scrollTop; render(); $("#view").scrollTop = keep; }

function paintStatus(st) {
  const box = $("#status");
  if (!st) { box.innerHTML = '<div class="row"><span class="dot bad"></span>TalonSync service stopped</div>'; return; }
  const c = st.connection;
  const row = (ok, label) => `<div class="row"><span class="dot ${ok === true ? "ok" : ok === "warn" ? "warn" : "bad"}"></span>${label}</div>`;
  box.innerHTML = (c.demo ? row("warn", "Demo PDA (no VRChat)") : row(c.vrchat || "warn", c.vrchat ? "VRChat OSC connected" : "Waiting for VRChat OSC"))
    + row(c.pda || (c.vrchat ? "warn" : false), c.pda ? "Talon Pilot answering" : "PDA not seen yet")
    + `<div class="faint small">UDP ${c.port}${c.oscquery ? " · OSCQuery" : ""} → ${esc(c.send)}</div>`
    // the folded (icon-only) sidebar shows the two lights with their meaning as a tooltip
    + `<div class="rail-dots"><span class="dot ${c.demo ? "warn" : c.vrchat ? "ok" : "warn"}" title="${c.demo ? "Demo PDA" : c.vrchat ? "VRChat OSC connected" : "Waiting for VRChat OSC"}"></span>`
    + `<span class="dot ${c.pda ? "ok" : c.vrchat ? "warn" : "bad"}" title="${c.pda ? "Talon Pilot answering" : "PDA not seen yet"}"></span></div>`;
  for (const [v, k] of Object.entries(COUNT_OF)) { const el = $(`[data-count="${v}"]`); if (el) el.textContent = st.counts[k] || ""; }
  const btn = $("#sync-btn"), hint = $("#hs-hint");
  btn.classList.toggle("busy", !!st.sync.running);
  btn.classList.toggle("waiting", !st.sync.running && c.pda_waiting);
  hint.textContent = st.sync.running ? st.sync.stage_name + "..." : c.pda_waiting ? "Your PDA is waiting!" : st.last_sync ? "Last sync " + ago(st.last_sync) : "Press to sync your PDA";
  $("#brand-sub").textContent = "v" + st.version + " · " + (st.device.owner ? `${st.device.owner}'s Talon Pilot` : "for Talon Pilot");
  document.title = "TalonSync " + st.version;
  // an exe built from older files than the ones next to it: say so, loudly
  let ban = $("#stale-banner");
  if (st.stale_exe && !ban) {
    ban = document.createElement("div"); ban.id = "stale-banner";
    ban.style.cssText = "position:fixed;left:0;right:0;top:0;z-index:999;padding:10px 16px;background:#b8860b;color:#fff;font-weight:600;text-align:center";
    ban.textContent = `This TalonSync.exe is v${st.version}, but the files next to it are v${st.stale_exe}. Quit TalonSync (tray owl › Quit) and double-click "Build TalonSync.bat" to get the new features.`;
    document.body.appendChild(ban);
  }
}
function ago(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now"; if (s < 3600) return Math.round(s / 60) + " min ago";
  if (s < 86400) return Math.round(s / 3600) + " h ago"; return new Date(iso).toLocaleDateString();
}

// ---------------------------------------------------------------- TalonSync dialog
const STAGES = [[0, "Connecting"], [7, "Reading your PDA"], [1, "Settings"], [2, "Tasks"], [3, "Memos"], [4, "Calendar"], [5, "Contacts"], [8, "Backing up"]];
let syncShown = false, syncCloseTimer = null;
function paintSync(st) {
  const s = st.sync, m = $("#sync-modal"), win = $(".sync-win", m);
  if (s.running && !syncShown) {
    syncShown = true; m.hidden = false; win.classList.remove("done", "failed");
    $("#sync-summary").textContent = ""; $("#sync-cancel").textContent = "Cancel";
    $("#sync-title").textContent = s.initiated_by === "pda" ? "TalonSync Progress — started on your PDA" : "TalonSync Progress";
    clearTimeout(syncCloseTimer);
  }
  if (!syncShown) return;
  $("#sync-status").textContent = s.message || "";
  $("#sync-bar").style.width = Math.round((s.progress || 0) * 100) + "%";
  const order = STAGES.map((x) => x[0]), idx = order.indexOf(s.stage);
  $("#sync-stages").innerHTML = STAGES.map(([n, label], i) => `<li class="${i < idx || (!s.running && s.result === "ok") ? "past" : i === idx && s.running ? "now" : ""}">${label}</li>`).join("");
  if (!s.running) {
    const rep = (st.reports || [])[0];
    win.classList.toggle("done", s.result === "ok"); win.classList.toggle("failed", s.result !== "ok");
    if (s.result === "ok") $("#sync-status").textContent = "TalonSync complete!";
    $("#sync-summary").textContent = rep ? (rep.ok ? rep.lines.filter((l) => l.includes("Summary")).map((l) => l.split("Summary - ")[1]).join("") + ` (${rep.seconds}s)` : rep.error) : "";
    $("#sync-cancel").textContent = "Close";
    if (s.result === "ok" && !syncCloseTimer) syncCloseTimer = setTimeout(closeSync, 4500);
  }
}
function closeSync() { $("#sync-modal").hidden = true; syncShown = false; syncCloseTimer = null; if (["today", "calendar", "contacts", "tasks", "memos", "notepad"].includes(S.view)) refreshView(); }
$("#sync-cancel").onclick = () => { if (S.state && S.state.sync.running) api("sync/cancel", {}); else closeSync(); };
$("#sync-btn").onclick = () => runSync();
async function runSync() {
  const r = await safely(() => api("sync", {}));
  if (r && !r.started) toast("A TalonSync is already running.");
}
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key.toLowerCase() === "h") { e.preventDefault(); runSync(); }
  if (e.key === "Escape" && !$("#sync-modal").hidden && !(S.state && S.state.sync.running)) closeSync();
});

// ---------------------------------------------------------------- data helpers
async function load(kind) { if (S.cache[kind]) return S.cache[kind]; const r = await api(kind); S.cache[kind] = r; return r; }
const lcd = (lines, width = 15) => `<div class="lcd">${lines.map((l) => esc((l || "").padEnd(width, " ")) || " ").join("\n")}</div>`;
const fmtDate = (iso, opts) => { const d = new Date(iso.length <= 10 ? iso + "T00:00" : iso); return isNaN(d) ? "" : d.toLocaleDateString(undefined, opts || { weekday: "short", month: "short", day: "numeric" }); };
const fmtTime = (iso) => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }); };

// ---------------------------------------------------------------- views
const R = {};

R.today = async (el, tools) => {
  tools.append(h(`<button class="btn" id="t-remote">${icon("pda")}Ping PDA</button>`));
  $("#t-remote").onclick = () => safely(() => api("remote", { action: "ping" }), (r) => r.message);
  const [events, tasks, w] = await Promise.all([load("events"), load("tasks"), api("weather").catch(() => null)]);
  const st = S.state || {};
  const hr = new Date().getHours(), owner = (st.device && st.device.owner) || "";
  const greet = hr < 5 ? "Up late" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
  const upcoming = events.filter((e) => new Date(e.end || e.start) >= new Date(new Date().toDateString())).sort((a, b) => a.start.localeCompare(b.start)).slice(0, 5);
  const open = tasks.filter((t) => !t.done).sort((a, b) => a.priority - b.priority).slice(0, 6);
  const wx = w && w.weather && w.weather.ok ? w.weather : null;
  el.append(h(`<div class="grid today">
    <div class="grid">
      <div class="panel">
        <p class="hello">${greet}${owner ? ", " + esc(owner) : ""}.</p>
        <p class="muted">${wx ? `${wx.current.temp}°${wx.units.temp} and ${esc(wx.current.text.toLowerCase())} in ${esc(wx.place.name)}. ` : ""}${upcoming.length ? `Next up: ${esc(upcoming[0].title)}, ${fmtDate(upcoming[0].start)}.` : "Your calendar is clear."}</p>
        <div class="conn" id="today-conn"></div>
      </div>
      <div class="panel">
        <h2>Coming up</h2>
        <div class="agenda-mini">${upcoming.length ? upcoming.map((e) => `<div class="item"><span class="ev-time">${fmtDate(e.start, { month: "short", day: "numeric" })}</span><div class="grow"><div class="t">${esc(e.title)}</div><div class="s">${e.all_day ? "All day" : fmtTime(e.start)}${e.location ? " · " + esc(e.location) : ""}</div></div>${e.pda_pos >= 0 ? '<span class="pda-badge">on PDA</span>' : ""}</div>`).join("") : '<div class="empty">Nothing scheduled. <br><button class="btn" data-go="calendar">Add an event</button></div>'}</div>
      </div>
      <div class="panel">
        <h2>To do</h2>
        ${open.length ? open.map((t) => `<label class="task"><input type="checkbox" data-done="${t.id}"><span class="t">${esc(t.title)}</span>${t.due ? `<span class="faint small">due ${fmtDate(t.due)}</span>` : ""}</label>`).join("") : '<div class="empty">All done. Clever work!</div>'}
      </div>
    </div>
    <div class="grid">
      <div class="panel device">
        <div class="device-shell">${lcd(pdaPreview(tasks, events), 15).replace('class="lcd"', 'class="lcd"')}</div>
        <div>
          <h2>Your Talon Pilot</h2>
          <dl class="kv" id="today-pda"></dl>
          <p class="small faint" style="margin-top:10px">The screen shows what your PDA will have after the next TalonSync.</p>
        </div>
      </div>
      <div class="panel" id="today-np"></div>
      <div class="panel"><h2>Last TalonSync</h2><div id="today-last" class="small muted"></div></div>
    </div>
  </div>`));
  $$("[data-go]", el).forEach((b) => (b.onclick = () => go(b.dataset.go)));
  $$("[data-done]", el).forEach((cb) => (cb.onchange = () => safely(() => api("tasks", { id: cb.dataset.done, done: cb.checked }), "Task done. Hoot!")));
  paintTodayLive(S.state);
};
function pdaPreview(tasks, events) {
  const pos = (arr, n) => { const out = Array(n).fill(null); arr.forEach((r) => { if (r.pda_pos >= 0 && r.pda_pos < n) out[r.pda_pos] = r; }); return out; };
  const lines = ["Tasks"];
  pos(tasks, 8).slice(0, 5).forEach((t) => lines.push(t ? (t.done ? "✓" : "□") + t.pda_lines[0].slice(0, 13) : ""));
  lines.push("", "Calendar");
  pos(events, 6).slice(0, 3).forEach((e) => lines.push(e ? e.pda_lines[0] : ""));
  return lines;
}
function paintTodayLive(st) {
  if (!st || S.view !== "today") return;
  const c = st.connection, conn = $("#today-conn"); if (!conn) return;
  const tile = (ok, k, v) => `<div><div class="k"><span class="dot ${ok ? "ok" : "warn"}"></span>${k}</div><div class="v">${v}</div></div>`;
  conn.innerHTML = tile(c.vrchat, "VRChat", c.demo ? "Demo PDA" : c.vrchat ? "Connected" : "Not seen") + tile(c.pda, "PDA", c.pda ? "Answering" : "Not seen")
    + tile(true, "Synced", st.sync_count ? `${st.sync_count} time${st.sync_count > 1 ? "s" : ""}` : "Never");
  const info = st.device.pda_info || {};
  $("#today-pda").innerHTML = `<dt>Owner</dt><dd>${esc(st.device.owner)}</dd><dt>Link</dt><dd>${info.version ? "v" + info.version : "unknown"}</dd>
    <dt>Text lines</dt><dd>${info.slots || "—"}</dd>`;
  const np = st.now_playing;
  $("#today-np").innerHTML = `<h2>Now playing</h2>${np.title ? `<div class="t">${esc(np.title)}</div><div class="muted">${esc(np.artist)}</div>` : '<div class="muted">Nothing playing on this PC.</div>'}`;
  const rep = (st.reports || [])[0];
  $("#today-last").innerHTML = rep ? `${rep.ok ? "Completed" : "Failed"} ${ago(rep.started)} in ${rep.seconds}s. ${esc(rep.ok ? (rep.lines.find((l) => l.includes("Summary")) || "").split("Summary - ")[1] || "" : rep.error)}` : "No TalonSync yet. Press the big button!";
}

// -------- generic record views (contacts, calendar, memos)
const FIELDS = {
  contacts: [["first", "First name"], ["last", "Last name"], ["company", "Company"], ["job", "Job title"], ["mobile", "Mobile"], ["phone", "Phone"],
             ["email", "Email", "wide"], ["address", "Address", "wide"], ["birthday", "Birthday", "", "date"], ["category", "Category"], ["notes", "Notes", "wide", "textarea"]],
  events: [["title", "Event", "wide"], ["start", "Starts", "", "datetime-local"], ["end", "Ends", "", "datetime-local"], ["all_day", "All day", "", "check"],
           ["alarm_min", "Reminder (minutes before, -1 = none)", "", "number"], ["location", "Where", "wide"], ["category", "Category"], ["notes", "Notes", "wide", "textarea"]],
  memos: [["title", "Title", "wide"], ["body", "Memo", "wide", "textarea"], ["category", "Category"], ["pinned", "Pinned to the top (and the PDA)", "", "check"]],
};
const TITLE_OF = { contacts: (r) => [r.first, r.last].filter(Boolean).join(" ") || r.company || "No name", events: (r) => r.title || "Untitled event", memos: (r) => r.title || "Untitled memo" };
const SUB_OF = {
  contacts: (r) => r.mobile || r.phone || r.email || r.company,
  events: (r) => (r.all_day ? fmtDate(r.start) : fmtDate(r.start) + " " + fmtTime(r.start)) + (r.location ? " · " + r.location : ""),
  memos: (r) => (r.body || "").split("\n")[0],
};

async function recordView(kind, el, tools, opts = {}) {
  const recs = await load(kind);
  let q = S.sel[kind + ":q"] || "";
  const search = h(`<input type="search" class="search" placeholder="Search" value="${esc(q)}">`);
  const add = h(`<button class="btn primary">${icon("plus")}New</button>`);
  tools.append(search, add);
  const wrap = h(`<div class="split"><div class="list" id="rec-list"></div><div class="editor" id="rec-edit"></div></div>`);
  if (opts.side) wrap.prepend(opts.side);
  el.append(wrap);
  const list = $("#rec-list", el), ed = $("#rec-edit", el);
  const sorted = () => {
    let r = recs.filter((x) => !q || JSON.stringify(x).toLowerCase().includes(q.toLowerCase()));
    if (kind === "contacts") r.sort((a, b) => (b.favorite - a.favorite) || TITLE_OF.contacts(a).localeCompare(TITLE_OF.contacts(b)));
    if (kind === "events") r.sort((a, b) => a.start.localeCompare(b.start));
    if (kind === "memos") r.sort((a, b) => (b.pinned - a.pinned) || b.modified.localeCompare(a.modified));
    if (opts.filter) r = r.filter(opts.filter);
    return r;
  };
  const paintList = () => {
    const r = sorted();
    if (!r.length) { list.innerHTML = `<div class="empty">${q ? "Nothing matches that search." : "Nothing here yet."}<br><button class="btn" id="empty-add">${icon("plus")}Add one</button></div>`; $("#empty-add", list).onclick = () => edit({}); return; }
    let html = "", lastGroup = null;
    for (const x of r) {
      if (kind === "events") { const g = fmtDate(x.start, { weekday: "long", month: "long", day: "numeric" }); if (g !== lastGroup) { html += `<div class="group-h">${esc(g)}</div>`; lastGroup = g; } }
      html += `<button class="item ${S.sel[kind] === x.id ? "on" : ""}" data-id="${x.id}">
        ${kind === "events" ? `<span class="ev-time">${x.all_day ? "All day" : fmtTime(x.start)}</span>` : ""}
        <div class="grow"><div class="t">${kind === "contacts" && x.favorite ? '<span class="star">★</span> ' : ""}${kind === "memos" && x.pinned ? '<span class="star">★</span> ' : ""}${esc(TITLE_OF[kind](x))}</div><div class="s">${esc(kind === "events" ? (x.location || "") : SUB_OF[kind](x) || "")}</div></div>
        ${x.pda_pos >= 0 ? '<span class="pda-badge">on PDA</span>' : ""}</button>`;
    }
    list.innerHTML = html;
    $$(".item", list).forEach((b) => (b.onclick = () => edit(recs.find((x) => x.id === b.dataset.id))));
  };
  const edit = (rec) => {
    if (S.dirty && !confirm("Discard your unsaved changes?")) return;
    S.dirty = false;
    S.sel[kind] = rec.id || null; paintList();
    const isNew = !rec.id;
    const val = (k, type) => {
      let v = rec[k];
      if (type === "datetime-local" && v) v = v.length <= 10 ? v + "T09:00" : v.slice(0, 16);
      if (v === undefined) v = k === "alarm_min" ? -1 : k === "category" ? "Unfiled" : "";
      return v;
    };
    if (isNew && kind === "events") { const d = new Date(); d.setMinutes(0); d.setHours(d.getHours() + 1); rec.start = d.toISOString().slice(0, 16); }
    ed.innerHTML = `<form class="form" autocomplete="off">${FIELDS[kind].map(([k, label, wide, type]) => {
      if (type === "check") return `<label class="check ${wide || ""}"><input type="checkbox" name="${k}" ${rec[k] ? "checked" : ""}>${label}</label>`;
      if (type === "textarea") return `<label class="field ${wide}">${label}<textarea name="${k}" rows="${kind === "memos" ? 12 : 4}">${esc(val(k))}</textarea></label>`;
      return `<label class="field ${wide || ""}">${label}<input type="${type || "text"}" name="${k}" value="${esc(val(k, type))}"></label>`;
    }).join("")}
      <label class="check wide"><input type="checkbox" name="on_pda" ${rec.on_pda !== false ? "checked" : ""}>Put this on my Talon Pilot</label>
      ${kind === "contacts" ? `<label class="check wide"><input type="checkbox" name="favorite" ${rec.favorite ? "checked" : ""}>Favorite (favorites go on the PDA first)</label>` : ""}
    </form>
    <div class="lcd-cap">On the PDA ${rec.pda_pos >= 0 ? `(record ${rec.pda_pos + 1})` : rec.id ? "(not on the PDA right now - it only has room for a few)" : ""}</div>
    <div id="pda-prev">${lcd(rec.pda_lines || [""])}</div>
    <div class="editor-foot"><button class="btn primary" id="save">Save</button>${isNew ? "" : `<button class="btn danger ghost" id="del">${icon("trash")}Delete</button>`}<span class="spacer"></span><span class="faint small">${rec.modified ? "Changed " + ago(rec.modified) : ""}</span></div>`;
    const form = $("form", ed);
    form.oninput = () => { S.dirty = true; $("#pda-prev", ed).innerHTML = lcd(previewLines(kind, formData(form))); };
    $("#save", ed).onclick = async () => {
      const data = formData(form); if (rec.id) data.id = rec.id;
      if (kind === "events" && data.all_day && data.start) data.start = data.start.slice(0, 10);
      if (kind === "events" && data.all_day && data.end) data.end = data.end.slice(0, 10);
      const saved = await safely(() => api(kind, data), "Saved");
      if (saved) { S.dirty = false; S.sel[kind] = saved.id; S.cache[kind] = null; refreshView(); }
    };
    if (!isNew) $("#del", ed).onclick = async () => {
      if (S.settings && S.settings.confirm_destructive && !confirm(`Delete "${TITLE_OF[kind](rec)}"?`)) return;
      await safely(() => api("delete/" + kind, { id: rec.id }), "Deleted");
      S.sel[kind] = null; S.cache[kind] = null; S.dirty = false; refreshView();
    };
    $("input,textarea", form) && $("input,textarea", form).focus({ preventScroll: true });
  };
  search.oninput = () => { q = search.value; S.sel[kind + ":q"] = q; paintList(); };
  add.onclick = () => edit({});
  paintList();
  const cur = recs.find((x) => x.id === S.sel[kind]) || sorted()[0];
  if (cur) edit(cur); else ed.innerHTML = '<div class="empty">Choose something on the left, or make a new one.</div>';
  if (opts.after) opts.after({ edit, paintList });
}
function formData(form) {
  const d = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    d[el.name] = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
  }
  return d;
}
function clean15(s) { return (s || "").normalize("NFKD").replace(/[^\x20-\x7e]/g, "").slice(0, 15); }
function previewLines(kind, d) {
  if (kind === "contacts") return [clean15([d.first, d.last].filter(Boolean).join(" ") || d.company), clean15(d.mobile || d.phone || d.email || d.company)];
  if (kind === "events") {
    const s = new Date(d.start || ""); let when = "";
    if (!isNaN(s)) { const days = Math.floor((s - new Date(new Date().toDateString())) / 864e5); const day = days >= 0 && days < 7 ? s.toLocaleDateString("en-US", { weekday: "short" }) : `${String(s.getMonth() + 1).padStart(2, "0")}/${String(s.getDate()).padStart(2, "0")}`; when = d.all_day ? day : `${day} ${String(s.getHours()).padStart(2, "0")}:${String(s.getMinutes()).padStart(2, "0")}`; }
    return [clean15(d.title), clean15(`${when} ${d.location || ""}`.trim())];
  }
  if (kind === "memos") {
    const words = (d.body || "").replace(/\n/g, " ").split(" "); const out = []; let line = "";
    for (const w of words) { if ((line + " " + w).trim().length <= 15) line = (line + " " + w).trim(); else { out.push(line); line = w.slice(0, 15); } if (out.length >= 2) break; }
    if (out.length < 2) out.push(line);
    return [clean15(d.title), clean15(out[0]), clean15(out[1])];
  }
  return [""];
}

R.contacts = (el, tools) => recordView("contacts", el, tools);
R.memos = (el, tools) => recordView("memos", el, tools);
R.calendar = async (el, tools) => {
  const events = await load("events");
  const side = h('<div class="month" id="month"></div>');
  let view = S.sel.month ? new Date(S.sel.month) : new Date(); view.setDate(1);
  let day = S.sel.day || null;
  const paintMonth = () => {
    const y = view.getFullYear(), m = view.getMonth();
    const first = new Date(y, m, 1), start = new Date(y, m, 1 - first.getDay());
    const has = new Set(events.map((e) => e.start.slice(0, 10)));
    const today = new Date().toISOString().slice(0, 10);
    let cells = "";
    for (let i = 0; i < 42; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      cells += `<button data-d="${iso}" class="${d.getMonth() !== m ? "out" : ""} ${iso === today ? "today" : ""} ${iso === day ? "sel" : ""} ${has.has(iso) ? "has" : ""}">${d.getDate()}</button>`;
    }
    side.innerHTML = `<div class="month-h"><button class="btn ghost" id="m-prev">‹</button><h3 style="margin:0">${view.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h3><button class="btn ghost" id="m-next">›</button></div>
      <div class="mgrid">${["S", "M", "T", "W", "T", "F", "S"].map((x) => `<div class="wd">${x}</div>`).join("")}${cells}</div>
      <div style="margin-top:12px;display:flex;gap:8px"><button class="btn" id="m-all">Show all</button><button class="btn" id="m-today">Today</button></div>`;
    $("#m-prev", side).onclick = () => { view.setMonth(view.getMonth() - 1); S.sel.month = view.toISOString(); paintMonth(); };
    $("#m-next", side).onclick = () => { view.setMonth(view.getMonth() + 1); S.sel.month = view.toISOString(); paintMonth(); };
    $("#m-today", side).onclick = () => { view = new Date(); view.setDate(1); day = new Date().toISOString().slice(0, 10); S.sel.day = day; refreshView(); };
    $("#m-all", side).onclick = () => { day = null; S.sel.day = null; refreshView(); };
    $$("[data-d]", side).forEach((b) => (b.onclick = () => { day = b.dataset.d; S.sel.day = day; refreshView(); }));
  };
  paintMonth();
  const wrap = h('<div class="cal"></div>');
  el.append(wrap);
  const inner = h("<div style='min-height:0'></div>"); wrap.append(inner, side);
  await recordView("events", inner, tools, { filter: day ? (e) => e.start.slice(0, 10) === day : null });
  $(".split", inner).style.height = "100%";
};

R.tasks = async (el, tools) => {
  const tasks = await load("tasks");
  let showDone = S.sel.showDone ?? true;
  const tg = h(`<label class="check small"><input type="checkbox" ${showDone ? "checked" : ""}>Show done</label>`);
  tools.append(tg);
  $("input", tg).onchange = (e) => { S.sel.showDone = e.target.checked; refreshView(); };
  const box = h(`<div class="panel"><div class="add-row"><input type="text" id="new-task" placeholder="Add a task and press Enter"><button class="btn primary" id="add-task">${icon("plus")}Add</button></div><div id="task-list"></div>
    <p class="small faint" style="margin-top:14px">The first 8 open tasks (highest priority first) go on your PDA. Checking one off on the PDA checks it off here at the next TalonSync.</p></div>`);
  el.append(box);
  const add = async () => { const v = $("#new-task").value.trim(); if (!v) return; await safely(() => api("tasks", { title: v })); S.cache.tasks = null; refreshView(); setTimeout(() => $("#new-task") && $("#new-task").focus(), 50); };
  $("#add-task").onclick = add; $("#new-task").onkeydown = (e) => { if (e.key === "Enter") add(); };
  const list = $("#task-list", box);
  const rows = tasks.filter((t) => showDone || !t.done).sort((a, b) => (a.done - b.done) || (a.priority - b.priority) || (a.due || "9").localeCompare(b.due || "9"));
  if (!rows.length) list.innerHTML = '<div class="empty">No tasks. Enjoy the perch.</div>';
  for (const t of rows) {
    const row = h(`<div class="task ${t.done ? "done" : ""}">
      <input type="checkbox" ${t.done ? "checked" : ""} title="Done">
      <button class="prio p${t.priority}" title="Priority (click to change)">${t.priority}</button>
      <input type="text" class="t" value="${esc(t.title)}">
      <input type="date" class="due" value="${esc(t.due)}" title="Due date">
      ${t.pda_pos >= 0 ? '<span class="pda-badge">on PDA</span>' : '<span class="pda-badge" style="opacity:0">on PDA</span>'}
      <button class="btn ghost" title="Delete">${icon("trash")}</button></div>`);
    const [cb, title, due] = [$("input[type=checkbox]", row), $("input.t", row), $("input.due", row)];
    const save = (patch) => safely(() => api("tasks", { id: t.id, ...patch })).then(() => { S.cache.tasks = null; });
    cb.onchange = () => { save({ done: cb.checked }); row.classList.toggle("done", cb.checked); };
    title.onchange = () => save({ title: title.value });
    due.onchange = () => save({ due: due.value });
    $(".prio", row).onclick = async () => { await save({ priority: (t.priority % 5) + 1 }); refreshView(); };
    $(".btn.ghost", row).onclick = async () => { await safely(() => api("delete/tasks", { id: t.id })); S.cache.tasks = null; refreshView(); };
    list.append(row);
  }
};

R.notepad = async (el, tools) => {
  const np = await api("notepad");
  const info = (S.state && S.state.device.pda_info) || {};
  const coarse = (info.ink_cols || 12) === 12;
  let bits = np.bits.slice(), mode = 1, down = false, changed = false;
  tools.append(h(`<span class="small faint">${coarse ? "Your PDA uses the standard 12 × 16 Note Pad: each square here is half a PDA pixel." : "Fine 24 × 32 Note Pad"}</span>`));
  el.append(h(`<div class="notepad">
    <div class="ink-wrap"><div class="ink ${coarse ? "coarse" : ""}" id="ink"></div></div>
    <div class="panel">
      <div class="ink-tools"><div class="seg"><button data-m="1" class="on">Pen</button><button data-m="0">Eraser</button></div>
        <button class="btn" id="ink-clear">Clear</button><button class="btn" id="ink-invert">Invert</button><button class="btn primary" id="ink-save">Save</button></div>
      <p class="muted">Draw with the mouse (right-click erases). Save, then TalonSync to put it on your PDA. Drawings made on the PDA come here too.</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn" id="ink-png">Export PNG</button><label class="btn">Import picture<input type="file" accept="image/*" hidden id="ink-imp"></label></div>
    </div></div>`));
  const grid = $("#ink", el);
  const paint = () => { grid.innerHTML = bits.map((b, i) => `<i data-i="${i}" class="${b ? "on" : ""}"></i>`).join(""); };
  paint();
  const set = (e, erase) => { const i = e.target.dataset && e.target.dataset.i; if (i === undefined) return; const v = erase ? 0 : mode; if (bits[i] !== v) { bits[i] = v; e.target.classList.toggle("on", !!v); changed = true; } };
  grid.onpointerdown = (e) => { down = true; grid.setPointerCapture(e.pointerId); set(e, e.button === 2); };
  grid.onpointermove = (e) => { if (!down) return; const t = document.elementFromPoint(e.clientX, e.clientY); if (t && t.parentNode === grid) set({ target: t }, e.buttons === 2); };
  grid.onpointerup = () => (down = false);
  grid.oncontextmenu = (e) => e.preventDefault();
  $$(".seg button", el).forEach((b) => (b.onclick = () => { mode = +b.dataset.m; $$(".seg button", el).forEach((x) => x.classList.toggle("on", x === b)); }));
  $("#ink-clear").onclick = () => { bits = bits.map(() => 0); changed = true; paint(); };
  $("#ink-invert").onclick = () => { bits = bits.map((b) => (b ? 0 : 1)); changed = true; paint(); };
  $("#ink-save").onclick = () => safely(() => api("notepad", { bits }), "Note Pad saved. TalonSync to send it.").then(() => (changed = false));
  $("#ink-png").onclick = () => download("notepad.png");
  $("#ink-imp").onchange = async (e) => { await importFiles(e.target.files, "notepad"); refreshView(); };
};

// -------- TalonStar 4000
const TS = {
  star: null, jazz: new TalonJazz("talonstar_jazz.ogg"), timer: null, data: null,
  settingsFor(s) { return { pages: s.ts_pages, page_seconds: s.ts_page_seconds, theme: s.ts_theme, crt: s.ts_crt, scanlines: s.ts_scanlines, crawl: s.ts_crawl, crawl_text: s.ts_crawl_text, crawl_speed: s.ts_crawl_speed, clock24: s.ts_clock24, show_seconds: s.ts_show_seconds, animations: s.ts_animations }; },
  async enter(el, tools) {
    const s = S.settings;
    const wrap = h(`<div class="ts-wrap"><div class="ts-stage" id="ts-stage"><canvas id="ts-canvas"></canvas></div>
      <div class="ts-side panel" id="ts-side"></div></div>`);
    el.append(wrap);
    tools.append(
      h(`<button class="btn" id="ts-prev" title="Previous page">${icon("prev")}</button>`), h(`<button class="btn" id="ts-next" title="Next page">${icon("next")}</button>`),
      h(`<button class="btn ${s.ts_music ? "primary" : ""}" id="ts-jazz">${icon("jazz")}${s.ts_music ? "Jazz on" : "Jazz off"}</button>`),
      h(`<button class="btn" id="ts-full" title="Full screen">${icon("full")}</button>`));
    const cv = $("#ts-canvas", el);
    this.star = new TalonStar(cv);
    this.star.setSettings(this.settingsFor(s));
    new ResizeObserver(() => this.star && this.star.resize()).observe($("#ts-stage", el));
    await this.refresh();
    this.star.start();
    this.timer = setInterval(() => this.refresh(), 60000);
    $("#ts-next").onclick = () => this.star.next();
    $("#ts-prev").onclick = () => this.star.prevPage();
    $("#ts-full").onclick = () => { const st = $("#ts-stage"); (document.fullscreenElement ? document.exitFullscreen() : st.requestFullscreen()).catch(() => {}); };
    $("#ts-jazz").onclick = async () => { const on = !S.settings.ts_music; await saveSettings({ ts_music: on }); this.music(); const b = $("#ts-jazz"); b.classList.toggle("primary", on); b.innerHTML = icon("jazz") + (on ? "Jazz on" : "Jazz off"); };
    this.music();
    this.side();
  },
  music() {
    const s = S.settings; this.jazz.setVolume(s.ts_volume);
    if (s.ts_music && S.view === "talonstar") this.jazz.play().then(() => { if (this.jazz.blocked) toast("Click anywhere to start the jazz."); }); else this.jazz.stop();
  },
  async refresh() {
    const r = await api("weather").catch(() => null);
    if (r && this.star) { this.data = r; this.star.setData(r.weather, r.extras); if (this.star.queue.length <= 1) this.star.rebuild(false); this.paintInfo(); }
  },
  paintInfo() {
    const box = $("#ts-info"); if (!box || !this.data) return;
    const w = this.data.weather;
    box.innerHTML = w.ok ? `<b>${esc(w.place.name)}${w.place.admin1 ? ", " + esc(w.place.admin1) : ""}</b><br><span class="muted small">${w.sample ? "Sample weather" + (w.error ? ": " + esc(w.error) : "") : "Updated " + ago(w.fetched)}${this.data.pda_sent ? " · sent to PDA " + ago(this.data.pda_sent) : ""}</span>`
      : `<span class="muted">${esc(w.error || "")}</span>`;
  },
  side() {
    const s = S.settings, box = $("#ts-side");
    const pages = Object.entries(TalonStarPages);
    box.innerHTML = `<h3>Location</h3><div id="ts-info" class="small"></div>
      <div class="add-row" style="margin-top:12px"><input type="search" id="ts-city" placeholder="Type a city, then Find"><button class="btn" id="ts-find">Find</button></div>
      <button class="btn ghost small" id="ts-here" style="margin:-4px 0 6px">Use where this PC is</button>
      <div id="ts-results"></div>
      <div class="set"><div class="lab">Units</div><div class="ctl"><div class="seg"><button data-u="imperial" class="${s.ts_units !== "metric" ? "on" : ""}">°F</button><button data-u="metric" class="${s.ts_units === "metric" ? "on" : ""}">°C</button></div></div></div>
      <div class="set"><div class="lab">Jazz volume</div><div class="ctl"><input type="range" min="0" max="1" step="0.05" value="${s.ts_volume}" id="ts-vol" style="width:140px"></div></div>
      <h3 style="margin-top:14px">Pages</h3>
      ${pages.map(([k, t]) => `<label class="check" style="margin:5px 0"><input type="checkbox" data-page="${k}" ${s.ts_pages.includes(k) ? "checked" : ""}>${t.join(" ").trim()}</label>`).join("")}
      <div class="set"><div class="lab">Seconds per page</div><div class="ctl"><input type="number" min="4" max="60" value="${s.ts_page_seconds}" id="ts-sec" style="width:80px"></div></div>
      <div class="set"><div class="lab">Look</div><div class="ctl"><select id="ts-theme">${TalonStarThemes.map((t) => `<option ${t === s.ts_theme ? "selected" : ""} value="${t}">${{ classic: "Classic blue", owl: "Owl night", gryphon: "Gryphon gold", dusk: "Dusk" }[t]}</option>`).join("")}</select></div></div>
      <label class="check" style="margin:8px 0"><input type="checkbox" id="ts-crt" ${s.ts_crt ? "checked" : ""}>Old TV glass and scanlines</label>
      <label class="check" style="margin:8px 0"><input type="checkbox" id="ts-crawl" ${s.ts_crawl ? "checked" : ""}>Scrolling crawl</label>
      <label class="field">Ticker message (this window)<input type="text" id="ts-crawl-text" value="${esc(s.ts_crawl_text)}"></label>
      <h3 style="margin-top:16px">On your Talon Pilot</h3>
      <label class="check" style="margin:6px 0"><input type="checkbox" id="ts-pda" ${s.ts_send_pda ? "checked" : ""}>Send the weather to the PDA's TalonStar app</label>
      <label class="field" style="margin-top:8px">Ticker on the PDA<select id="ts-tick-mode"><option value="auto">Weather summary</option><option value="custom">My own message</option><option value="twitch">Twitch chat</option><option value="off">Off</option></select></label>
      <label class="field" id="ts-tick-row" style="margin-top:8px">PDA ticker message <span class="faint" id="ts-tick-count"></span><input type="text" id="ts-tick-text" maxlength="45" value="${esc(s.ts_pda_ticker_text)}" placeholder="Up to 45 letters"></label>
      <label class="field" style="margin-top:8px">Jazz on the PDA<select id="ts-pda-jazz"><option value="0">Off</option><option value="1">Only I can hear it</option><option value="2">Everyone nearby can hear it</option></select></label>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn" id="ts-push">Send to PDA now</button><button class="btn" id="ts-open">Open TalonStar on PDA</button><button class="btn ghost" id="ts-ref">${icon("refresh")}Refresh</button></div>
      <p class="small faint" style="margin-top:12px">More options in Settings › TalonStar 4000.</p>`;
    $("#ts-pda-jazz").value = String(s.ts_pda_jazz);
    $("#ts-tick-mode").value = s.ts_pda_ticker || "auto";
    const tickUi = () => { $("#ts-tick-row").style.display = $("#ts-tick-mode").value === "custom" ? "" : "none"; $("#ts-tick-count").textContent = `${$("#ts-tick-text").value.length}/45`; };
    tickUi();
    $("#ts-tick-mode").onchange = (e) => { tickUi(); set({ ts_pda_ticker: e.target.value }).then(() => api("weather/push", {}).catch(() => {})); };
    $("#ts-tick-text").oninput = tickUi;
    $("#ts-tick-text").onchange = (e) => set({ ts_pda_ticker_text: e.target.value }).then(() => safely(() => api("weather/push", {}), (r) => r.message));
    $("#ts-here").onclick = async () => {
      const r = await safely(() => api("locate"));
      if (!r) return;
      if (r.error) { toast(r.error, true); return; }
      await set({ ts_place: r.place }); toast(`Using ${r.place.name}. Getting the weather...`);
      setTimeout(() => this.refresh(), 2500); setTimeout(() => this.refresh(), 7000);
    };
    this.paintInfo();
    const set = async (patch) => { await saveSettings(patch); this.star.setSettings(this.settingsFor(S.settings)); };
    const find = async () => {
      const q = $("#ts-city").value.trim(); if (!q) return;
      const r = await safely(() => api("geocode?q=" + encodeURIComponent(q)));
      const res = $("#ts-results");
      if (!r || !r.results.length) { res.innerHTML = `<div class="small muted">${esc((r && r.error) || "No places found.")}</div>`; return; }
      res.innerHTML = r.results.map((p, i) => `<button class="item" data-i="${i}"><div class="grow"><div class="t">${esc(p.name)}</div><div class="s">${esc([p.admin1, p.country].filter(Boolean).join(", "))}</div></div></button>`).join("");
      $$(".item", res).forEach((b) => (b.onclick = async () => { await set({ ts_place: r.results[b.dataset.i] }); res.innerHTML = ""; toast("Getting the weather..."); setTimeout(() => this.refresh(), 2500); setTimeout(() => this.refresh(), 7000); }));
    };
    $("#ts-find").onclick = find; $("#ts-city").onkeydown = (e) => { if (e.key === "Enter") find(); };
    $$("[data-u]", box).forEach((b) => (b.onclick = async () => { $$("[data-u]", box).forEach((x) => x.classList.toggle("on", x === b)); await set({ ts_units: b.dataset.u }); setTimeout(() => this.refresh(), 2500); }));
    $("#ts-vol").oninput = (e) => { this.jazz.setVolume(+e.target.value); };
    $("#ts-vol").onchange = (e) => set({ ts_volume: +e.target.value });
    $$("[data-page]", box).forEach((cb) => (cb.onchange = () => set({ ts_pages: Object.keys(TalonStarPages).filter((k) => $(`[data-page="${k}"]`, box).checked) })));
    $("#ts-sec").onchange = (e) => set({ ts_page_seconds: +e.target.value });
    $("#ts-theme").onchange = (e) => set({ ts_theme: e.target.value });
    $("#ts-crt").onchange = (e) => set({ ts_crt: e.target.checked });
    $("#ts-crawl").onchange = (e) => set({ ts_crawl: e.target.checked });
    $("#ts-crawl-text").onchange = (e) => set({ ts_crawl_text: e.target.value });
    $("#ts-pda").onchange = (e) => set({ ts_send_pda: e.target.checked });
    $("#ts-pda-jazz").onchange = (e) => set({ ts_pda_jazz: +e.target.value }).then(() => toast(["Jazz off on the PDA", "PDA jazz: only you can hear it", "PDA jazz: everyone nearby can hear it"][+e.target.value]));
    $("#ts-push").onclick = () => safely(() => api("weather/push", {}), (r) => r.message);
    $("#ts-open").onclick = () => safely(() => api("remote", { action: "open_app", app: 27 }), (r) => r.message);
    $("#ts-ref").onclick = () => safely(() => api("weather/refresh", {}), "Checking the sky...").then(() => setTimeout(() => this.refresh(), 3000));
  },
  leave() { if (this.star) this.star.stop(); this.star = null; clearInterval(this.timer); this.jazz.stop(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); },
};
document.addEventListener("pointerdown", () => { if (TS.jazz.want && TS.jazz.blocked) TS.jazz.ctx.resume(); }, true);
R.talonstar = (el, tools) => TS.enter(el, tools);

// -------- Hypnospiral
const HYP_STYLES = ["Rainbow spiral", "Black & white spiral", "Rainbow rings"];
function hypColor(t) { const h = (x) => Math.max(0, Math.min(1, Math.abs(((t * 6 + x) % 6) - 3) - 1)); return [h(0), h(4), h(2)]; }
function hypDraw(cv, speed, style, caption, time) {
  const g = cv.getContext("2d"), W = cv.width, H = cv.height, img = g.createImageData(W, H), d = img.data;
  const cx = W / 2, cy = H * 0.42, step = 2;
  for (let y = 0; y < H; y += step) for (let x = 0; x < W; x += step) {
    const vx = (x - cx) * 320 / W, vy = (y - cy) * 320 / W, r = Math.hypot(vx, vy) + 1e-3, a = Math.atan2(vy, vx);
    let c;
    if (style > 1.5) { const ph = Math.log(r) * 3 - time * speed * 0.6, ring = 0.5 + 0.5 * Math.sin(ph * 6.2832); c = hypColor(((ph * 0.25) % 1 + 1) % 1).map((v) => v * (0.35 + 0.65 * ring)); }
    else {
      const ph = a / 6.2832 * 2 + Math.log(r) * 1.6 - time * speed * 0.35, stripe = 0.5 + 0.5 * Math.sin(ph * 6.2832 * 2);
      if (style > 0.5) { const v = stripe < 0.42 ? 0 : stripe > 0.58 ? 1 : (stripe - 0.42) / 0.16; c = [v, v, v]; }
      else c = hypColor((((ph * 0.5 + r * 0.004 + time * 0.05) % 1) + 1) % 1).map((v) => v * (0.25 + 0.75 * stripe) + 0.15 * stripe);
    }
    for (let yy = 0; yy < step; yy++) for (let xx = 0; xx < step; xx++) { const i = ((y + yy) * W + x + xx) * 4; d[i] = c[0] * 255; d[i + 1] = c[1] * 255; d[i + 2] = c[2] * 255; d[i + 3] = 255; }
  }
  g.putImageData(img, 0, 0);
  const text = caption || "Just relax...", sc = W / 320;
  g.font = `bold ${Math.round(34 * sc)}px Consolas, monospace`; g.textAlign = "center"; g.textBaseline = "middle";
  const tw = g.measureText(text).width, y = cy + 120 * sc + 12 * sc;
  g.fillStyle = "rgba(5,5,13,.65)"; g.beginPath(); g.roundRect(cx - tw / 2 - 14 * sc, y - 26 * sc, tw + 28 * sc, 52 * sc, 18 * sc); g.fill();
  g.fillStyle = "#fff"; g.fillText(text, cx, y);
}
R.hypno = async (el, tools) => {
  const dev = await api("device");
  let caption = dev.hypno_caption || "", speed = Math.round(dev.prefs.hypSpeed || 2), style = Math.round(dev.prefs.hypStyle || 0);
  tools.append(h(`<button class="btn" id="hy-open">Open Hypno on the PDA</button>`));
  el.append(h(`<div class="np">
    <div class="panel" style="display:grid;place-items:center"><canvas id="hy-cv" width="320" height="400" style="width:min(100%,360px);border-radius:16px;background:#000"></canvas></div>
    <div class="panel">
      <label class="field">Caption <span class="faint" id="hy-count"></span><input type="text" id="hy-cap" maxlength="15" value="${esc(caption)}" placeholder="Just relax..."></label>
      <p class="small faint" style="margin:6px 0 0">Up to 15 letters. Leave it empty for "Just relax...".</p>
      <div class="set"><div class="lab">Speed</div><div class="ctl"><input type="range" id="hy-speed" min="1" max="5" step="1" value="${speed}" style="width:180px"></div></div>
      <div class="set"><div class="lab">Style</div><div class="ctl"><select id="hy-style">${HYP_STYLES.map((n, i) => `<option value="${i}" ${i === style ? "selected" : ""}>${n}</option>`).join("")}</select></div></div>
      <div class="editor-foot"><button class="btn primary" id="hy-send">Send to PDA</button><button class="btn" id="hy-saver">Use as screensaver</button></div>
      <p class="small faint" style="margin-top:10px">Sends right away when VRChat is running. Otherwise it's saved and goes across at your next TalonSync.</p>
    </div></div>`));
  const cv = $("#hy-cv"), t0 = performance.now();
  const count = () => ($("#hy-count").textContent = `${$("#hy-cap").value.length}/15`); count();
  const loop = () => { if (S.view !== "hypno" || !document.body.contains(cv)) return; hypDraw(cv, speed, style, clean15($("#hy-cap").value), (performance.now() - t0) / 1000); requestAnimationFrame(loop); };
  loop();
  $("#hy-cap").oninput = count;
  $("#hy-speed").oninput = (e) => (speed = +e.target.value);
  $("#hy-style").onchange = (e) => (style = +e.target.value);
  const send = (open) => safely(() => api("hypno", { caption: $("#hy-cap").value, speed, style, send: true, open }), (r) => r.message);
  $("#hy-send").onclick = () => send(false);
  $("#hy-open").onclick = () => send(true);
  $("#hy-saver").onclick = () => safely(() => api("remote", { action: "set_pref", key: "Saver", value: 3 }), () => "The PDA's screensaver is now the Hypnospiral");
};

// -------- Now Playing
R.nowplaying = (el, tools) => {
  const s = S.settings;
  el.append(h(`<div class="np">
    <div class="grid">
      <div class="panel" id="np-live"></div>
      <div class="panel">
        <h2>Send a message to your PDA</h2>
        <p class="muted small">It shows on the PDA's Now Playing card (TalonSync and Scope screens) until the next song.</p>
        <div class="form"><label class="field">Heading<input type="text" id="msg-title" value="Message from PC" maxlength="15"></label><label class="field">Message<input type="text" id="msg-text" maxlength="15" placeholder="15 letters max"></label></div>
        <div class="editor-foot"><button class="btn primary" id="msg-send">Send to PDA</button></div>
      </div>
    </div>
    <div class="panel">
      <h3>How it looks on the PDA</h3>
      <div class="np-card" id="np-card"></div>
      <div class="set"><div class="lab">Show what's playing</div><div class="ctl"><span class="switch"><input type="checkbox" data-k="now_playing" ${s.now_playing ? "checked" : ""}><span></span></span></div></div>
      <div class="set"><div class="lab">Source</div><div class="ctl"><select data-k="np_source">${[["auto", "Automatic"], ["windows", "This computer's media controls"], ["spotify_title", "Player window titles (Windows)"], ["manual", "Type it myself"]].map(([v, l]) => `<option value="${v}" ${s.np_source === v ? "selected" : ""}>${l}</option>`).join("")}</select></div></div>
      <div class="set"><div class="lab">Playback bar</div><div class="ctl"><span class="switch"><input type="checkbox" data-k="np_position" ${s.np_position ? "checked" : ""}><span></span></span></div></div>
      <div class="set"><div class="lab">Artist on top</div><div class="ctl"><span class="switch"><input type="checkbox" data-k="np_swap" ${s.np_swap ? "checked" : ""}><span></span></span></div></div>
      <div class="set"><div class="lab">ALL CAPS</div><div class="ctl"><span class="switch"><input type="checkbox" data-k="np_upper" ${s.np_upper ? "checked" : ""}><span></span></span></div></div>
      <div class="set"><div class="lab">Also post to the VRChat chatbox</div><div class="help">Everyone near you sees the song above your head.</div><div class="ctl"><span class="switch"><input type="checkbox" data-k="chatbox_now_playing" ${s.chatbox_now_playing ? "checked" : ""}><span></span></span></div></div>
      <label class="field" style="margin-top:8px">Manual title<input type="text" data-k="np_manual_title" value="${esc(s.np_manual_title)}"></label>
      <label class="field" style="margin-top:8px">Manual artist<input type="text" data-k="np_manual_artist" value="${esc(s.np_manual_artist)}"></label>
    </div></div>`));
  bindSettings(el);
  $("#msg-send").onclick = () => safely(() => api("remote", { action: "message", title: $("#msg-title").value, text: $("#msg-text").value }), (r) => r.message);
  paintNowLive(S.state);
};
function paintNowLive(st) {
  if (!st || S.view !== "nowplaying" || !$("#np-live")) return;
  const np = st.now_playing, s = S.settings;
  const playing = np.playing && (np.title || np.artist);
  $("#np-live").innerHTML = `<div class="np-track ${playing ? "playing" : ""}"><div class="np-art"><div class="eq"><i></i><i></i><i></i><i></i></div></div>
    <div><div class="np-title">${esc(np.title || "Nothing playing")}</div><div class="muted">${esc(np.artist || "Play something in Spotify, YouTube, or any player.")}</div>
    <div class="small faint" style="margin-top:6px">${np.source ? "From " + esc(np.app || np.source) : ""}${np.error ? " · " + esc(np.error) : ""}</div>
    ${np.position != null ? `<div class="bar" style="margin-top:10px;width:260px"><div class="bar-fill" style="width:${Math.round(np.position * 100)}%"></div></div>` : ""}</div></div>`;
  let t1 = clean15(np.title), t2 = clean15(np.artist);
  if (s.np_swap) [t1, t2] = [t2, t1];
  if (s.np_upper) { t1 = t1.toUpperCase(); t2 = t2.toUpperCase(); }
  $("#np-card").innerHTML = playing ? `<div class="cap">Now playing on PC</div><div>${esc(t1)}</div><div style="opacity:.75">${esc(t2)}</div>${s.np_position ? `<div class="pos"><div style="width:${Math.round((np.position || 0) * 100)}%"></div></div>` : ""}` : '<div class="cap">The card hides when nothing is playing.</div>';
}

// -------- Hoot Pet
// ---------------------------------------------------------------- PC Link (Talon Pilot 2.11+)
const PC_ROWS = [[8, "Heart rate", "bpm"], [5, "Headset battery", "%"], [6, "Left controller", "%"], [7, "Right controller", "%"],
  [0, "CPU load", "%"], [1, "GPU load", "%"], [4, "Memory", "%"], [2, "CPU temperature", "°C"], [3, "GPU temperature", "°C"]];
R.pclink = (el) => {
  const s = S.settings;
  const sw = (k, label, help) => `<div class="set"><div class="lab">${label}</div>${help ? `<div class="help">${help}</div>` : ""}<div class="ctl"><span class="switch"><input type="checkbox" data-k="${k}" ${s[k] ? "checked" : ""}><span></span></span></div></div>`;
  el.append(h(`<div class="pc">
    <div class="grid">
      <div class="panel"><h2>On your PDA now</h2><div id="pc-ready" class="small" style="margin-bottom:10px"></div><table class="pc-vals" id="pc-vals"></table></div>
      <div class="panel"><h2>Focus timer</h2><div id="pc-timer" class="pc-timer"></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn primary" data-t="start_focus">Start focus</button><button class="btn" data-t="start_break">Start break</button><button class="btn" data-t="stop">Stop</button></div>
        <p class="small faint" style="margin-top:10px">Tap the timer on the PDA's PC Link (Media &amp; Timer page) to start or stop it there. The PDA chirps when a focus or break ends.</p>
        <h3 style="margin-top:16px">Music on this PC</h3>
        <div style="display:flex;gap:8px"><button class="btn" data-m="previous">⏮ Previous</button><button class="btn primary" data-m="play_pause">⏯ Play / pause</button><button class="btn" data-m="next">Next ⏭</button></div>
      </div>
    </div>
    <div class="grid">
      <div class="panel"><h2>Messages</h2>
        <div class="form"><label class="field">Title<input type="text" id="pc-title" maxlength="15" value="Note to self"></label><label class="field">Message<input type="text" id="pc-text" maxlength="15" placeholder="15 letters on the PDA"></label></div>
        <div class="editor-foot"><button class="btn primary" id="pc-send">Send to PDA</button><button class="btn" id="pc-clear">Clear the PDA's messages</button></div>
        <div id="pc-msgs" style="margin-top:12px"></div>
        <p class="small faint" style="margin-top:10px">Messages also come from calendar reminders, Twitch mentions, ${navigator.platform.toLowerCase().includes("linux") ? "your desktop notifications, " : ""}and other programs over OSC: <code>/talonpilot/message "title" "text"</code> to TalonSync's port.</p>
      </div>
      <div class="panel"><h2>What PC Link sends</h2>
        ${sw("pc_link", "PC Link", "Your Talon Pilot 2.11 or newer shows these in its PC Link app.")}
        ${sw("pc_monitor", "CPU, GPU and memory")}
        ${sw("pc_batteries", "Headset and controller battery", "From SteamVR. The headset charge also fills the PDA's battery icon.")}
        ${sw("pc_heart", "Heart rate", "From any heart-rate app that sends the avatar parameter HR to VRChat.")}
        ${sw("pc_messages", "Messages")}
        ${sw("pc_message_chirp", "Chirp for new messages")}
        ${sw("pc_reminders", "Calendar reminders")}
        ${sw("pc_media_remote", "The PDA's music buttons control this PC")}
        <div class="set"><div class="lab">Focus minutes</div><div class="ctl"><input type="number" min="1" max="120" data-k="pc_focus_minutes" value="${s.pc_focus_minutes}" style="width:80px"></div></div>
        <div class="set"><div class="lab">Break minutes</div><div class="ctl"><input type="number" min="1" max="60" data-k="pc_break_minutes" value="${s.pc_break_minutes}" style="width:80px"></div></div>
        ${sw("pc_timer_loop", "Keep going (focus, break, focus...)")}
        <h3 style="margin-top:14px">Twitch chat</h3>
        <label class="field">Channel<input type="text" data-k="twitch_channel" value="${esc(s.twitch_channel)}" placeholder="your channel name"></label>
        <div id="pc-twitch" class="small" style="margin:6px 0 4px"></div>
        ${sw("pc_twitch_mentions", "@mentions become PDA messages")}
        <p class="small faint">To show the chat on the PDA's TalonStar ticker, choose <b>Twitch chat</b> under TalonStar › Ticker on the PDA. Read-only: no login needed.</p>
      </div>
    </div></div>`));
  bindSettings(el);
  $$("[data-t]", el).forEach((b) => (b.onclick = () => safely(() => api("pclink/timer", { action: b.dataset.t }))));
  $$("[data-m]", el).forEach((b) => (b.onclick = () => safely(() => api("pclink/media", { action: b.dataset.m }))));
  $("#pc-send").onclick = () => safely(() => api("pclink/message", { title: $("#pc-title").value, text: $("#pc-text").value }), (r) => r.message);
  $("#pc-clear").onclick = () => safely(() => api("pclink/clear", {}), "Messages cleared on the PDA");
  paintPcLive(S.state);
};
function paintPcLive(st) {
  if (!st || !st.pclink || S.view !== "pclink" || !$("#pc-vals")) return;
  const p = st.pclink, v = p.values || {};
  $("#pc-ready").innerHTML = p.pda_ready ? '<span class="dot ok"></span> Your PDA has PC Link.' : '<span class="dot"></span> Waiting for a Talon Pilot 2.11 or newer (wear it with OSC on, or try the Demo PDA).';
  $("#pc-vals").innerHTML = PC_ROWS.map(([k, label, unit]) => { const x = v[k]; const has = x != null && x !== 255;
    return `<tr><td>${label}</td><td style="text-align:right">${has ? x + " " + unit : '<span class="faint">--</span>'}</td></tr>`; }).join("")
    + `<tr><td colspan="2" class="small faint" style="padding-top:8px">${p.sources.batteries ? "" : "Batteries: " + esc(p.sources.batteries_why) + ". "}${p.sources.monitor ? "" : "CPU/RAM: install psutil. "}${p.sources.gpu ? "" : "GPU: NVIDIA only. "}${p.sources.heart ? "" : "Heart rate: no heart-rate app seen."}${p.pclink_open ? "" : " CPU and GPU are measured only while PC Link is open on your PDA (easier on your FPS)."}</td></tr>`;
  const tw = p.sources, tEl = $("#pc-twitch");
  if (tEl) tEl.innerHTML = !tw.twitch_channel ? '<span class="faint">Type your channel name to connect.</span>'
    : tw.twitch ? `<span class="dot ok"></span> Connected to #${esc(tw.twitch_channel)}${tw.twitch_count ? ` · ${tw.twitch_count} messages` : " · waiting for chat"}${p.chat ? `<div class="faint" style="margin-top:4px">${esc(p.chat)}</div>` : ""}`
    : `<span class="dot warn"></span> Connecting to #${esc(tw.twitch_channel)}…${tw.twitch_error ? ` <span class="faint">(${esc(tw.twitch_error)})</span>` : ""}`;
  const t = p.timer;
  $("#pc-timer").innerHTML = t.state ? `<div class="big">${Math.floor(t.left / 60)}:${String(t.left % 60).padStart(2, "0")}</div><div class="muted">${t.state === 1 ? "Focus" : "Break"}</div>` : '<div class="muted">Not running</div>';
  $("#pc-msgs").innerHTML = (p.messages || []).length ? p.messages.map((m) => `<div class="item"><div class="grow"><div class="t">${esc(m.title)}</div><div class="s">${esc(m.text)}</div></div><span class="small faint">${esc((m.time || "").slice(11, 16))}</span></div>`).join("") : '<div class="empty">No messages yet.</div>';
}

R.pet = (el, tools) => {
  const st = S.state, pet = (st && st.device.pet) || {};
  tools.append(h(`<button class="btn" id="pet-read">${icon("refresh")}Read from PDA</button>`));
  const pct = (v) => Math.round((v || 0) * 100);
  const hours = Math.round((pet.petAge || 0) * 255);
  const stage = hours < 1 ? "Egg" : hours < 24 ? "Owlet" : hours < 120 ? "Owl" : "Wise owl";
  el.append(h(`<div class="panel pet">
    <svg class="pet-owl" viewBox="0 0 32 32"><use href="#i-pet"/></svg>
    <div>
      <h2>${pet.petFood == null ? "Your Hoot-agotchi" : `${stage}, ${hours} hours old${pet.petSleep > 0.5 ? " — asleep" : ""}`}</h2>
      ${pet.petFood == null ? '<p class="muted">TalonSync or press Read from PDA to see how your owl is doing.</p>' : ""}
      ${[["Food", "petFood"], ["Joy", "petJoy"], ["Energy", "petEnergy"]].map(([l, k]) => `<div class="meter"><span>${l}</span><div class="bar"><div class="bar-fill" style="width:${pct(pet[k])}%"></div></div><span class="small muted">${pct(pet[k])}%</span></div>`).join("")}
      <div style="display:flex;gap:8px;margin-top:14px"><button class="btn primary" id="pet-feed">Feed from the PC</button><button class="btn" id="pet-play">Play from the PC</button></div>
      <p class="small faint" style="margin-top:10px">${st && st.device.pet_read ? "Read " + ago(st.device.pet_read) : ""}</p>
    </div></div>`));
  const act = async (action, extra) => { const r = await safely(() => api("remote", { action, ...extra }), (r) => r.message); await api("remote", { action: "read_pet" }).catch(() => {}); refreshView(); };
  $("#pet-read").onclick = () => act("read_pet");
  $("#pet-feed").onclick = () => act("pet", { what: "feed" });
  $("#pet-play").onclick = () => act("pet", { what: "play" });
};

// -------- Remote
R.remote = (el) => {
  const apps = S.meta ? S.meta.apps : {};
  el.append(h(`<div class="grid">
    <div class="panel"><h2>Open an app on your PDA</h2><div class="apps">${Object.entries(apps).map(([id, name]) => `<button class="app-tile" data-app="${id}">${icon(id == 27 ? "talonstar" : id == 26 ? "pet" : id == 1 ? "calendar" : id == 2 ? "contacts" : id == 3 ? "tasks" : id == 4 ? "memos" : id == 9 ? "notepad" : id == 25 ? "music" : "pda")}<span>${esc(name)}</span></button>`).join("")}</div></div>
    <div class="panel"><h2>Device</h2><div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn" data-a="power-on">Power on</button><button class="btn" data-a="power-off">Power off</button><button class="btn" data-a="ping">Ping</button>
      ${S.state && S.state.connection.demo ? '<button class="btn" data-a="demo_press">Press TalonSync on the demo PDA</button>' : ""}</div>
      <p class="small faint" style="margin-top:12px">${S.state && S.state.connection.demo ? "Demo PDA screen: " + esc(S.state.demo_screen) : "These work while VRChat is running with your Talon Pilot avatar and OSC on."}</p></div>
    <div class="panel"><h2>Handheld settings</h2><p class="muted small">Changes go straight to the PDA. TalonSync keeps them in step afterwards too.</p><div id="prefs"></div></div>
  </div>`));
  $$("[data-app]", el).forEach((b) => (b.onclick = () => safely(() => api("remote", { action: "open_app", app: +b.dataset.app }), (r) => r.message)));
  $$("[data-a]", el).forEach((b) => (b.onclick = () => {
    const a = b.dataset.a;
    const body = a.startsWith("power") ? { action: "power", on: a === "power-on" } : { action: a };
    if (a === "clear_ink" && !confirm("Clear the drawing on the PDA?")) return;
    safely(() => api("remote", body), (r) => r.message);
  }));
  api("device").then((dev) => {
    const box = $("#prefs"); if (!box) return;
    const vals = (S.meta.values || []).filter((v) => v.group === "prefs" || v.group === "apps");
    box.innerHTML = vals.map((v) => {
      const cur = dev.prefs[v.key];
      const ctl = v.labels ? `<select data-pref="${v.key}">${v.labels.map((l, i) => `<option value="${i + v.lo}" ${Number(cur) === i + v.lo ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`
        : v.kind === "float" ? `<input type="range" data-pref="${v.key}" min="${v.lo}" max="${v.hi}" step="0.05" value="${cur}" style="width:200px">`
        : `<input type="number" data-pref="${v.key}" min="${v.lo}" max="${v.hi}" value="${cur}" style="width:100px">`;
      return `<div class="set"><div class="lab">${esc(v.label)}</div><div class="ctl">${ctl}</div></div>`;
    }).join("");
    $$("[data-pref]", box).forEach((c) => (c.onchange = () => safely(() => api("remote", { action: "set_pref", key: c.dataset.pref, value: +c.value }), (r) => r.message)));
  });
};

// -------- TalonSync log
R.log = async (el, tools) => {
  const reps = await api("reports");
  tools.append(h(`<button class="btn" id="open-data">Open data folder</button>`));
  $("#open-data").onclick = () => api("open_folder", {});
  el.append(h(`<div class="panel">${reps.length ? reps.map((r, i) => `<details class="report" ${i === 0 ? "open" : ""}><summary><span class="dot ${r.ok ? "ok" : "bad"}"></span><b>${new Date(r.started).toLocaleString()}</b><span class="muted small">${r.ok ? "Completed" : "Failed"} in ${r.seconds}s · ${r.transfers} transfers · started by ${r.initiated_by === "pda" ? "the PDA" : r.initiated_by}</span></summary><pre>${esc(r.lines.join("\n"))}${r.error ? "\n\n" + esc(r.error) : ""}</pre></details>`).join("") : '<div class="empty">No syncs yet.</div>'}</div>`));
  const log = await api("log");
  el.append(h(`<div class="panel" style="margin-top:18px"><h2>Activity</h2><div class="logbox">${esc(log.slice(-200).join("\n"))}</div></div>`));
};

// -------- Import & export
const EXPORT_LIST = [
  ["contacts.vcf", "Contacts as vCard", "Outlook, Google Contacts, iCloud, phones"], ["contacts.csv", "Contacts as CSV", "Excel, Google Sheets, Outlook import"],
  ["calendar.ics", "Calendar as iCalendar", "Outlook, Google Calendar, Apple Calendar"], ["calendar.csv", "Calendar as CSV", "Spreadsheets"],
  ["tasks.ics", "Tasks as iCalendar", "Thunderbird, Apple Reminders"], ["tasks.md", "Tasks as Markdown", "Obsidian, Notion, any editor"], ["tasks.csv", "Tasks as CSV", "Spreadsheets"],
  ["memos.md", "Memos as Markdown", "Obsidian, Notion, Notepad"], ["memos.csv", "Memos as CSV", "Spreadsheets"],
  ["unity.json", "For Unity TalonSync", "Tools > Talon Pilot > TalonSync > Import JSON"], ["backup.json", "Full TalonSync backup", "Restore it on another PC"],
];
async function download(key) {
  const r = await fetch("/api/export/" + key, { headers: { "X-Token": TOKEN } });
  const blob = await r.blob();
  const name = (S.meta && S.meta.exports[key]) || key;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
    const b64 = await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(",")[1]); fr.readAsDataURL(blob); });
    const where = await window.pywebview.api.save_file(name, b64);
    if (where) toast("Saved " + where);
    return;
  }
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function importFiles(fileList, target = "auto") {
  const files = [];
  for (const f of fileList) {
    const b64 = await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(",")[1] || ""); fr.readAsDataURL(f); });
    files.push({ name: f.name, data: b64 });
  }
  if (!files.length) return;
  const r = await safely(() => api("import", { files, target }));
  if (r) {
    const parts = Object.entries(r).filter(([k, v]) => v && k !== "skipped").map(([k, v]) => `${v} ${k}`);
    toast(parts.length ? "Imported " + parts.join(", ") + (r.skipped ? ` (${r.skipped} already here)` : "") : r.skipped ? `Everything in there was already here (${r.skipped}).` : "Nothing to import in that file.");
    S.cache = {};
  }
}
R.files = async (el) => {
  const backups = await api("backups");
  el.append(h(`<div class="grid">
    <div class="panel"><h2>Import</h2>
      <div class="drop" id="drop"><p><b>Drop files here</b> or <label class="btn" style="display:inline-flex">choose files<input type="file" multiple hidden id="imp"></label></p>
      <p class="small">vCard (.vcf), iCalendar (.ics), CSV, Markdown or text, and Unity TalonSync JSON. Duplicates are skipped, and a backup is made first.</p>
      <label class="field" style="max-width:280px;margin:10px auto 0">CSV holds<select id="imp-target"><option value="auto">Work it out</option><option value="contacts">Contacts</option><option value="events">Calendar</option><option value="tasks">Tasks</option><option value="memos">Memos</option></select></label></div></div>
    <div class="panel"><h2>Export</h2><div class="exports">${EXPORT_LIST.map(([k, t, s]) => `<button class="exp" data-x="${k}"><b>${t}</b><span>${s}</span></button>`).join("")}</div>
      <div class="editor-foot"><button class="btn primary" id="exp-all">Export everything to a folder</button><span class="small faint" id="exp-where"></span></div></div>
    <div class="panel"><h2>Backups</h2><p class="small muted">A backup is saved after every TalonSync and before imports and restores.</p>
      <div class="editor-foot" style="margin:0 0 10px"><button class="btn" id="bk-new">Back up now</button><button class="btn ghost" id="bk-open">Open backups folder</button></div>
      ${backups.length ? backups.map((b) => `<div class="item"><div class="grow"><div class="t">${esc(b.name.replace(/^TalonSync |\.json$/g, ""))}</div><div class="s">${Math.round(b.size / 1024)} KB</div></div><button class="btn" data-restore="${esc(b.name)}">Restore</button></div>`).join("") : '<div class="empty">No backups yet.</div>'}</div>
  </div>`));
  const drop = $("#drop");
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = async (e) => { e.preventDefault(); drop.classList.remove("over"); await importFiles(e.dataTransfer.files, $("#imp-target").value); };
  $("#imp").onchange = (e) => importFiles(e.target.files, $("#imp-target").value);
  $$("[data-x]", el).forEach((b) => (b.onclick = () => download(b.dataset.x)));
  $("#exp-all").onclick = async () => { const r = await safely(() => api("export_all", { folder: S.settings.auto_export_folder || "" })); if (r) { $("#exp-where").textContent = `${r.files.length} files in ${r.folder}`; api("open_folder", { path: r.folder }); } };
  $("#bk-new").onclick = () => safely(() => api("backups/create", { label: "manual" }), "Backed up").then(refreshView);
  $("#bk-open").onclick = () => api("open_folder", { path: S.meta.data_dir + "/Backups" });
  $$("[data-restore]", el).forEach((b) => (b.onclick = async () => {
    if (!confirm(`Restore ${b.dataset.restore}? Your current data is backed up first.`)) return;
    await safely(() => api("backups/restore", { name: b.dataset.restore }), "Restored. Good as new!"); S.cache = {};
  }));
};

// -------- Settings
async function saveSettings(patch) {
  const r = await safely(() => api("settings", patch));
  if (r) { S.settings = r; applyLook(); }
  return r;
}
function bindSettings(root) {
  $$("[data-k]", root).forEach((c) => {
    c.onchange = () => {
      let v = c.type === "checkbox" ? c.checked : c.type === "number" || c.type === "range" ? Number(c.value) : c.value;
      saveSettings({ [c.dataset.k]: v }).then(() => { if (c.dataset.k === "ts_music") TS.music(); });
    };
  });
}
function applyLook() {
  const s = S.settings; if (!s) return;
  document.documentElement.dataset.theme = s.theme || "aerie";
  document.documentElement.classList.toggle("noanim", !s.animations);
  document.documentElement.classList.toggle("compact", !!s.compact);
  if (s.accent && s.theme !== "classic") document.documentElement.style.setProperty("--aur-a", s.accent); else document.documentElement.style.removeProperty("--aur-a");
}
const SETTINGS_TABS = {
  "TalonSync": [
    ["answer_pda_requests", "Start a TalonSync when I press TalonSync on the PDA", "switch"],
    ["auto_sync_minutes", "TalonSync automatically every", "select", [[0, "Never"], [10, "10 minutes"], [30, "30 minutes"], [60, "hour"], [180, "3 hours"]]],
    ["sync_on_start", "Sync when TalonSync starts", "switch"],
    ["conflict", "When something changed on both", "select", [["pc", "Keep the PC version"], ["pda", "Keep the PDA version"], ["duplicate", "Keep both"]], "Applies to records and settings."],
    ["pda_blank_removes", "Erasing a line on the PDA deletes it here", "switch", null, "Off: erased lines just stop going to the PDA, nothing is deleted."],
    ["done_hold_seconds", "Show \"TalonSync complete\" on the PDA for (seconds)", "number"],
    ["sound", "Sounds", "switch"], ["chirp_on_done", "Chirp when a TalonSync finishes", "switch"],
    ["__conduits"],
  ],
  "TalonStar 4000": [
    ["__location"],
    ["ts_enabled", "Get the weather", "switch"],
    ["ts_units", "Units", "select", [["imperial", "°F, mph, inches"], ["metric", "°C, km/h, hPa"]]],
    ["ts_refresh_minutes", "Check the weather every (minutes)", "number"],
    ["ts_region_count", "Nearby cities on the regional pages", "number"],
    ["ts_page_seconds", "Seconds per page", "number"],
    ["ts_theme", "Look", "select", [["classic", "Classic blue"], ["owl", "Owl night"], ["gryphon", "Gryphon gold"], ["dusk", "Dusk"]]],
    ["ts_animations", "Animation", "select", [["full", "Full"], ["calm", "Calm (icons only)"], ["off", "Off"]]],
    ["ts_crt", "Old TV glass", "switch"], ["ts_scanlines", "Scanline strength", "range", [0, 0.8, 0.05]],
    ["ts_crawl", "Scrolling ticker", "switch"], ["ts_crawl_text", "Ticker message (this window)", "text"], ["ts_crawl_speed", "Ticker speed", "range", [30, 200, 5]],
    ["ts_pda_ticker", "Ticker on the PDA", "select", [["auto", "Weather summary"], ["custom", "My own message"], ["twitch", "Twitch chat"], ["off", "Off"]]],
    ["ts_pda_ticker_text", "PDA ticker message (up to 45 letters)", "text"],
    ["ts_clock24", "24-hour clock", "switch"], ["ts_show_seconds", "Show seconds", "switch"],
    ["ts_music", "Smooth jazz", "switch"], ["ts_volume", "Jazz volume", "range", [0, 1, 0.05]],
    ["ts_send_pda", "Send the weather to the PDA", "switch"],
    ["ts_pda_jazz", "Jazz on the PDA", "select", [[0, "Off"], [1, "Only I can hear it"], [2, "Everyone nearby can hear it"]], "\"Only I\" plays it for you alone, everyone else hears nothing."],
    ["ts_demo_weather", "Show sample weather when offline", "switch"],
  ],
  "Now Playing": [
    ["now_playing", "Show what's playing on the PDA", "switch"],
    ["np_source", "Where the song comes from", "select", [["auto", "Automatic"], ["windows", "This computer's media controls"], ["spotify_title", "Player window titles (Windows)"], ["manual", "Type it myself"]]],
    ["np_interval", "Check every (seconds)", "number"], ["np_position", "Playback bar", "switch"], ["np_swap", "Artist on top", "switch"], ["np_upper", "ALL CAPS", "switch"],
    ["np_clear_when_paused", "Hide the card when paused", "switch"], ["np_only_when_connected", "Only while VRChat is running", "switch"],
    ["chatbox_now_playing", "Post the song to the VRChat chatbox", "switch"], ["chatbox_format", "Chatbox text ({title}, {artist}, {album})", "text"], ["chatbox_interval", "Chatbox every (seconds)", "number"],
  ],
  "Desktop mode": [
    ["desk_click", "Click button taps the PDA", "switch", null, "Talon Pilot 2.12+, Windows, VRChat desktop mode: aim the dot in the middle of your screen at the PDA and hold this button to tap. Only works while the VRChat window is in front."],
    ["desk_click_button", "Click button", "select", [["middle", "Middle mouse button"], ["side1", "Mouse side button (back)"], ["side2", "Mouse side button (forward)"], ["f1", "F1 key"], ["f2", "F2 key"], ["f3", "F3 key"], ["f4", "F4 key"], ["f5", "F5 key"], ["f6", "F6 key"], ["f7", "F7 key"], ["f8", "F8 key"], ["f9", "F9 key"], ["f10", "F10 key"], ["f11", "F11 key"], ["f12", "F12 key"]]],
    ["desk_here_button", "\u201CBring PDA in front\u201D button", "select", [["", "None"], ["middle", "Middle mouse button"], ["side1", "Mouse side button (back)"], ["side2", "Mouse side button (forward)"], ["f1", "F1 key"], ["f2", "F2 key"], ["f3", "F3 key"], ["f4", "F4 key"], ["f5", "F5 key"], ["f6", "F6 key"], ["f7", "F7 key"], ["f8", "F8 key"], ["f9", "F9 key"], ["f10", "F10 key"], ["f11", "F11 key"], ["f12", "F12 key"]], null, "Brings the parked PDA back in front of your view (the same as Expressions > Talon Pilot > Desktop)."],
  ],
  "Connection": [
    ["osc_send_host", "VRChat address", "text"], ["osc_send_port", "VRChat OSC input port", "number", null, "VRChat's default is 9000."],
    ["osc_listen_port", "TalonSync listens on port", "number", null, "VRChat's default output is 9001. Ignored when OSCQuery picks a port."],
    ["osc_listen_host", "Listen on", "text", null, "127.0.0.1 = this computer only. 0.0.0.0 = also other computers (VRChat on another PC)."],
    ["oscquery", "Use OSCQuery", "switch", null, "Lets VRChat find TalonSync even when other OSC apps are running."],
    ["oscquery_random_port", "Let OSCQuery choose the port", "switch"],
    ["demo_pda", "Demo PDA (try TalonSync without VRChat)", "switch"],
    ["connect_timeout", "Wait for the PDA to wake up (seconds)", "number"],
    ["__doctor"], ["__support"],
  ],
  "Files & backups": [
    ["backup_on_sync", "Back up after every TalonSync", "switch"], ["backup_keep", "Backups to keep", "number"],
    ["auto_export", "Export files after every TalonSync", "switch"], ["auto_export_folder", "Export folder", "text"],
    ["watch_import_folder", "Import anything dropped in this folder", "text", null, "Files are renamed .imported afterwards."],
    ["__wipe"],
  ],
  "Appearance & startup": [
    ["theme", "Theme", "select", [["aerie", "Aerie (night sky)"], ["classic", "Classic Desktop"], ["owl", "Owl Night"], ["gryphon", "Gryphon Gold"], ["light", "Daylight"]]],
    ["accent", "Accent color", "color"], ["animations", "Animations", "switch"], ["compact", "Compact lists", "switch"],
    ["start_with_windows", "Start when I log in", "switch"], ["start_minimized", "Start minimized to the tray", "switch"], ["close_to_tray", "Closing the window keeps TalonSync running in the tray", "switch"],
    ["confirm_destructive", "Ask before deleting", "switch"], ["__owner"],
  ],
  "Experimental": [
    ["__experimental"],
    ["exp_terminal", "Terminal CPU: TalonOS Enhanced and Talon Enhanced BASIC (experimental)", "switch", null, "Off by default. On: TalonSync becomes the CPU for the PDA's Terminal app (Talon Pilot 2.18+; the TalonOS Enhanced desktop needs 2.19), with a start menu for TalonOS Enhanced, Talon Enhanced BASIC or the local terminal. Off: the Terminal says \"No CPU found\"."],
  ],
  "Advanced": [
    ["ack_timeout", "Bus answer timeout (seconds)", "number"], ["bus_settle_ms", "Bus settle time (ms)", "number"], ["bus_gap_ms", "Pause between transfers (ms)", "number", null, "Raise this if syncs fail in busy instances."],
    ["bus_retries", "Retries per transfer", "number"], ["__reset"],
  ],
};
R.settings = (el) => {
  const tabs = Object.keys(SETTINGS_TABS);
  let tab = S.sel.settingsTab || tabs[0];
  el.append(h(`<div class="settings"><div class="tabs">${tabs.map((t) => `<button data-tab="${esc(t)}" class="${t === tab ? "on" : ""}">${esc(t)}</button>`).join("")}</div><div class="panel" id="set-body"></div></div>`));
  $$("[data-tab]", el).forEach((b) => (b.onclick = () => { S.sel.settingsTab = b.dataset.tab; refreshView(); }));
  const s = S.settings, body = $("#set-body", el);
  for (const row of SETTINGS_TABS[tab]) {
    const [k, label, type, opts, help] = row;
    if (k === "__conduits") { body.append(conduitTable()); continue; }
    if (k === "__doctor") { body.append(doctorBox()); continue; }
    if (k === "__support") { body.append(supportBox()); continue; }
    if (k === "__experimental") { body.append(h(`<div class="set"><div class="lab">⚗ Experimental features</div><div class="help">Still being tested. They are off until you switch them on here, and they may change or go away in a later version.</div></div>`)); continue; }
    if (k === "__wipe") { body.append(wipeBox()); continue; }
    if (k === "__reset") { const b = h(`<div class="set"><div class="lab">Reset all settings</div><div class="help">Your records stay. Only TalonSync's options go back to how they started.</div><div class="ctl"><button class="btn danger">Reset settings</button></div></div>`); $("button", b).onclick = async () => { if (confirm("Reset every setting?")) { S.settings = await api("settings/reset", {}); applyLook(); refreshView(); } }; body.append(b); continue; }
    if (k === "__owner") { body.append(ownerBox()); continue; }
    if (k === "__location") { body.append(locationBox()); continue; }
    const v = s[k];
    let ctl;
    if (type === "switch") ctl = `<span class="switch"><input type="checkbox" data-k="${k}" ${v ? "checked" : ""}><span></span></span>`;
    else if (type === "select") ctl = `<select data-k="${k}">${opts.map(([ov, ol]) => `<option value="${ov}" ${String(v) === String(ov) ? "selected" : ""}>${esc(ol)}</option>`).join("")}</select>`;
    else if (type === "range") ctl = `<input type="range" data-k="${k}" min="${opts[0]}" max="${opts[1]}" step="${opts[2]}" value="${v}" style="width:200px">`;
    else if (type === "color") ctl = `<input type="color" data-k="${k}" value="${esc(v)}">`;
    else ctl = `<input type="${type === "number" ? "number" : "text"}" data-k="${k}" value="${esc(v)}">`;
    body.append(h(`<div class="set"><div class="lab">${esc(label)}</div>${help ? `<div class="help">${esc(help)}</div>` : ""}<div class="ctl">${ctl}</div></div>`));
  }
  bindSettings(body);
  $$("select[data-k]", body).forEach((sel) => { const k = sel.dataset.k; if (typeof DEFAULTS_NUM[k] === "number") sel.onchange = () => saveSettings({ [k]: Number(sel.value) }); });
};
const DEFAULTS_NUM = { auto_sync_minutes: 0, ts_pda_jazz: 1 };
function conduitTable() {
  const s = S.settings;
  const names = { settings: "Handheld settings", tasks: "Tasks", memos: "Memos", calendar: "Calendar", contacts: "Contacts", hypno: "Hypno caption" };
  const acts = [["sync", "Synchronize the files"], ["pc_overwrites", "Desktop overwrites handheld"], ["pda_overwrites", "Handheld overwrites desktop"], ["nothing", "Do nothing"]];
  const el = h(`<div style="margin-top:16px"><h3>What each TalonSync does</h3><table class="conduits"><tr><th>Conduit</th><th>Action</th></tr>${Object.entries(names).map(([k, n]) => `<tr><td>${n}</td><td><select data-c="${k}">${acts.map(([a, l]) => `<option value="${a}" ${s.conduits[k] === a ? "selected" : ""}>${l}</option>`).join("")}</select></td></tr>`).join("")}</table></div>`);
  $$("[data-c]", el).forEach((sel) => (sel.onchange = () => saveSettings({ conduits: { ...S.settings.conduits, [sel.dataset.c]: sel.value } })));
  return el;
}
function doctorBox() {
  const el = h(`<div style="margin-top:16px"><div style="display:flex;align-items:center;gap:12px"><h3 style="margin:0">Connection doctor</h3><button class="btn" id="doc-run">Run checks</button><button class="btn ghost" id="doc-re">Reconnect</button></div><div id="doc-out" class="small muted" style="margin-top:8px">Checks OSC, VRChat, your avatar's OSC config and whether the PDA answers.</div></div>`);
  $("#doc-re", el).onclick = () => safely(() => api("reconnect", {}), "Reconnected");
  $("#doc-run", el).onclick = async () => {
    const out = $("#doc-out", el); out.textContent = "Checking...";
    const rows = await safely(() => api("doctor"));
    if (!rows) return;
    out.innerHTML = rows.map((r) => `<div class="doc-row"><span class="dot ${r.ok ? "ok" : "bad"}"></span><b>${esc(r.name)}</b><span>${esc(r.detail)}</span>${r.fix ? `<button class="btn" data-fix="${r.fix}">Fix</button>` : "<span></span>"}</div>`).join("");
    $$("[data-fix]", out).forEach((b) => (b.onclick = () => safely(() => api("doctor/fix", { what: b.dataset.fix }), (r) => r.message)));
  };
  return el;
}
function supportBox() {
  const el = h(`<div style="margin-top:20px"><div style="display:flex;align-items:center;gap:12px"><h3 style="margin:0">Need help?</h3><button class="btn" id="sup-copy">Copy support info</button></div>
    <div class="small muted" style="margin-top:4px">TalonSync ${esc(String((S.state && S.state.version) || ""))} &middot; Created by NevvyDrone &middot; nevvydrone.com</div>
    <div class="small muted" style="margin-top:6px">Copies versions, the connection checks, your settings and the last log lines, ready to paste into a help request. Your records, location, Twitch channel and Windows user name are left out. Have a look before you send it.</div>
    <textarea id="sup-text" readonly style="display:none;width:100%;height:180px;margin-top:8px;font:12px/1.4 ui-monospace,Consolas,monospace"></textarea></div>`);
  $("#sup-copy", el).onclick = async () => {
    const btn = $("#sup-copy", el); btn.disabled = true; btn.textContent = "Gathering...";
    const r = await safely(() => api("support"));
    btn.disabled = false; btn.textContent = "Copy support info";
    if (!r) return;
    const ta = $("#sup-text", el); ta.style.display = "block"; ta.value = r.text;
    let ok = false;
    try { await navigator.clipboard.writeText(r.text); ok = true; } catch (e) { ta.select(); try { ok = document.execCommand("copy"); } catch (e2) {} }
    toast(ok ? "Support info copied - paste it into your help request" : "Select the text below and copy it (Ctrl+C)");
  };
  return el;
}
function wipeBox() {
  const el = h(`<div style="margin-top:16px"><h3>Start over</h3><p class="small muted">Each of these makes a backup first.</p><div style="display:flex;gap:8px;flex-wrap:wrap">${[["contacts", "Clear contacts"], ["events", "Clear calendar"], ["tasks", "Clear tasks"], ["memos", "Clear memos"], ["sync_history", "Forget sync history (next TalonSync treats the PDA as new)"]].map(([k, l]) => `<button class="btn danger" data-w="${k}">${l}</button>`).join("")}</div></div>`);
  $$("[data-w]", el).forEach((b) => (b.onclick = async () => { if (!confirm(b.textContent + "?")) return; await safely(() => api("wipe", { what: b.dataset.w }), "Done. A backup was saved first."); S.cache = {}; }));
  return el;
}
function locationBox() {
  const p = S.settings.ts_place || {};
  const el = h(`<div class="set"><div class="lab">Location</div><div class="help" id="loc-now">${p.name ? esc([p.name, p.admin1, p.country].filter(Boolean).join(", ")) : "Not set yet - TalonStar shows sample weather."}</div>
    <div class="ctl" style="flex-wrap:wrap;gap:6px"><input type="search" id="loc-q" placeholder="City" style="width:160px"><button class="btn" id="loc-find">Find</button><button class="btn ghost" id="loc-here">Where this PC is</button></div></div>`);
  const res = h(`<div id="loc-res"></div>`);
  const wrap = h("<div></div>"); wrap.append(el, res);
  const use = async (place) => { await saveSettings({ ts_place: place }); $("#loc-now", el).textContent = [place.name, place.admin1, place.country].filter(Boolean).join(", "); res.innerHTML = ""; toast(`TalonStar is now set to ${place.name}`); };
  const find = async () => {
    const q = $("#loc-q", el).value.trim(); if (!q) return;
    const r = await safely(() => api("geocode?q=" + encodeURIComponent(q)));
    if (!r || !r.results.length) { res.innerHTML = `<div class="small muted">${esc((r && r.error) || "No places found.")}</div>`; return; }
    res.innerHTML = r.results.map((x, i) => `<button class="item" data-i="${i}"><div class="grow"><div class="t">${esc(x.name)}</div><div class="s">${esc([x.admin1, x.country].filter(Boolean).join(", "))}</div></div></button>`).join("");
    $$(".item", res).forEach((b) => (b.onclick = () => use(r.results[b.dataset.i])));
  };
  $("#loc-find", el).onclick = find; $("#loc-q", el).onkeydown = (e) => { if (e.key === "Enter") find(); };
  $("#loc-here", el).onclick = async () => { const r = await safely(() => api("locate")); if (r && r.place) use(r.place); else if (r) toast(r.error, true); };
  return wrap;
}
// first run: ask what to call you (nothing is assumed)
function askName() {
  const back = h(`<div class="modal-back" id="name-modal"><div class="panel" style="width:min(440px,92vw);padding:26px">
    <h2 style="margin:0 0 6px">Hoot! Welcome to TalonSync.</h2>
    <p class="faint" style="margin:0 0 16px">What should we call you? TalonSync and TalonStar greet you with it. You can change it later in Settings › Appearance &amp; startup.</p>
    <input type="text" id="name-in" maxlength="20" placeholder="Your name or nickname" style="width:100%">
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px"><button class="btn" id="name-skip">Not now</button><button class="btn primary" id="name-ok">Save</button></div>
  </div></div>`);
  document.body.appendChild(back);
  const inp = $("#name-in", back); setTimeout(() => inp.focus(), 50);
  const done = () => { back.remove(); refreshView(); };
  $("#name-skip", back).onclick = done;
  const save = async () => {
    const v = inp.value.trim(); if (!v) { inp.focus(); return; }
    try { await api("device", { owner: v }); S.state.device.owner = v; toast(`Nice to meet you, ${v}!`); } catch (e) { toast(e.message, true); }
    done();
  };
  $("#name-ok", back).onclick = save;
  inp.onkeydown = (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") done(); };
}
function ownerBox() {
  const el = h(`<div class="set"><div class="lab">Your name</div><div class="help">What TalonSync calls you. Also shown on TalonStar's agenda page.</div><div class="ctl"><input type="text" id="owner"></div></div>`);
  api("device").then((d) => { $("#owner", el).value = d.owner; });
  $("#owner", el).onchange = (e) => safely(() => api("device", { owner: e.target.value }), "Saved");
  return el;
}

// ---------------------------------------------------------------- boot
(async function boot() {
  buildNav();
  try {
    [S.settings, S.meta] = await Promise.all([api("settings"), api("meta")]);
    S.state = await api("state");
  } catch (e) { $("#view").innerHTML = `<div class="empty">Can't reach the TalonSync service (${esc(e.message)}).</div>`; return; }
  applyLook();
  if (!(S.state.device && S.state.device.owner)) askName();
  let v = "today"; try { v = localStorage.getItem("ts.view") || "today"; } catch (e) {}
  if (new URLSearchParams(location.search).get("view")) v = new URLSearchParams(location.search).get("view");
  if (S.settings.first_run) { saveSettings({ first_run: false }); v = "today"; }
  go(VIEWS.some((x) => x[0] === v) ? v : "today");
  poll();
})();
