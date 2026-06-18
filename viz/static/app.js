"use strict";

// ── state ───────────────────────────────────────────────────────────────
let rec = null;        // the loaded recording
let events = [];       // rec.events
let idx = -1;          // current event index (-1 = blank board, before start)
let playing = false;
let timer = null;

const cellEls = {};    // "x,y" -> cell <div>
let numberAt = {};     // "x,y" -> clue number (slot starts)
let slotCells = {};    // slot key -> [[x,y], ...]
let whiteTotal = 0;

const SPEEDS = [0.25, 0.5, 1, 2, 4, 8];   // index by slider value -2..3 -> +offset

const $ = (id) => document.getElementById(id);

// ── load / picker ───────────────────────────────────────────────────────
async function init() {
  const recs = await fetch("/api/recordings").then((r) => r.json());
  const sel = $("rec-select");
  sel.innerHTML = "";
  if (!recs.length) {
    sel.innerHTML = "<option>no recordings</option>";
    $("log").innerHTML =
      '<div class="empty">No recordings found. Generate one:<br><br>' +
      "<code>python scripts/record_solve.py --fake --day monday</code></div>";
    return;
  }
  for (const r of recs) {
    const m = r.meta || {};
    const acc = m.result ? ` · ${Math.round(m.result.accuracy * 100)}%` : "";
    const opt = document.createElement("option");
    opt.value = r.name;
    opt.textContent = `${m.date || r.name} · ${m.model || "?"}${acc}`;
    sel.appendChild(opt);
  }
  sel.onchange = () => load(sel.value);
  load(recs[0].name);
}

async function load(name) {
  stop();
  rec = await fetch("/api/recordings/" + encodeURIComponent(name)).then((r) => r.json());
  events = rec.events || [];
  buildGrid();
  buildLog();

  const scrub = $("scrub");
  scrub.min = -1;
  scrub.max = events.length - 1;
  scrub.value = -1;

  idx = -1;
  $("answers").checked = false;
  render();
}

// ── grid ────────────────────────────────────────────────────────────────
function buildGrid() {
  const W = rec.meta.width, H = rec.meta.height;
  const grid = $("grid");
  grid.style.setProperty("--w", W);
  grid.innerHTML = "";
  for (const k in cellEls) delete cellEls[k];

  numberAt = {};
  slotCells = {};
  for (const s of rec.slots) {
    slotCells[s.key] = s.cells;
    const [sx, sy] = s.cells[0];
    numberAt[`${sx},${sy}`] = s.number;
  }

  whiteTotal = rec.grid.filter((c) => c !== ".").length;

  for (let y = 1; y <= H; y++) {
    for (let x = 1; x <= W; x++) {
      const i = (y - 1) * W + (x - 1);
      const cell = document.createElement("div");
      cell.className = "cell";
      if (rec.grid[i] === ".") {
        cell.classList.add("black");
      } else {
        const key = `${x},${y}`;
        cellEls[key] = cell;
        if (numberAt[key] !== undefined) {
          const n = document.createElement("span");
          n.className = "num";
          n.textContent = numberAt[key];
          cell.appendChild(n);
        }
        const span = document.createElement("span");
        span.className = "letter";
        cell.appendChild(span);
      }
      grid.appendChild(cell);
    }
  }
}

function solutionAt(key) {
  const [x, y] = key.split(",").map(Number);
  const W = rec.meta.width;
  return rec.solution[(y - 1) * W + (x - 1)];
}

// ── log feed ────────────────────────────────────────────────────────────
function buildLog() {
  const log = $("log");
  log.innerHTML = "";
  events.forEach((e, i) => {
    const row = document.createElement("div");
    row.className = `row agent-${e.agent}`;
    row.dataset.i = i;
    const conf = e.confidence ? `<span class="conf">${e.confidence}</span>` : "";
    row.innerHTML =
      `<span class="i">${i}</span>` +
      `<span class="agent">${e.agent}</span>` +
      `<span class="action">${e.action}</span>` +
      `<span class="word">${e.word || ""}</span>` +
      conf;
    row.onclick = () => { stop(); setIdx(i); };
    log.appendChild(row);
  });
}

// ── rendering ───────────────────────────────────────────────────────────
function fillAt(i) {
  return i >= 0 && events[i] ? events[i].fill : {};
}

function render() {
  const fill = fillAt(idx);
  const showAnswers = $("answers").checked;
  let filled = 0;

  for (const key in cellEls) {
    const cell = cellEls[key];
    const ch = fill[key];
    cell.querySelector(".letter").textContent = ch || "";
    cell.classList.remove("active", "correct", "wrong", "flash-place", "flash-erase");
    if (ch) {
      filled++;
      if (showAnswers) {
        cell.classList.add(ch === solutionAt(key) ? "correct" : "wrong");
      }
    }
  }

  // highlight the active event's slot
  const ev = idx >= 0 ? events[idx] : null;
  if (ev && slotCells[ev.slot]) {
    for (const [x, y] of slotCells[ev.slot]) {
      const cell = cellEls[`${x},${y}`];
      if (cell) cell.classList.add("active");
    }
  }

  // stats + scrubber + now-line
  const r = rec.meta.result || {};
  $("stats").innerHTML =
    `<b>${filled}</b>/${whiteTotal} filled · ` +
    `final acc <b>${Math.round((r.accuracy || 0) * 100)}%</b> · ` +
    `${rec.meta.llm_calls} llm calls · ${rec.meta.duration_sec}s`;
  $("scrub").value = idx;

  if (ev) {
    const detail = ev.detail ? ` — ${ev.detail}` : "";
    $("now").innerHTML =
      `[${idx + 1}/${events.length}] <b>${ev.agent}</b> ${ev.action} ` +
      `${ev.slot}${ev.word ? " " + ev.word : ""}${detail}`;
  } else {
    $("now").innerHTML = `[0/${events.length}] ready`;
  }

  // active log row
  document.querySelectorAll(".row.active").forEach((r) => r.classList.remove("active"));
  if (idx >= 0) {
    const row = document.querySelector(`.row[data-i="${idx}"]`);
    if (row) {
      row.classList.add("active");
      row.scrollIntoView({ block: "nearest" });
    }
  }
}

function flashStep(from, to) {
  // Animate what changed between event `from` and event `to`.
  const ev = to >= 0 ? events[to] : null;
  if (!ev) return;
  const prev = fillAt(from), next = fillAt(to);
  if (ev.action === "place" && slotCells[ev.slot]) {
    for (const [x, y] of slotCells[ev.slot]) {
      const cell = cellEls[`${x},${y}`];
      if (cell) { cell.classList.remove("flash-place"); void cell.offsetWidth; cell.classList.add("flash-place"); }
    }
  } else if (ev.action === "erase" || ev.action === "blocked") {
    for (const key in prev) {
      if (next[key] === undefined) {
        const cell = cellEls[key];
        if (cell) { cell.classList.remove("flash-erase"); void cell.offsetWidth; cell.classList.add("flash-erase"); }
      }
    }
  }
}

function setIdx(i) {
  i = Math.max(-1, Math.min(events.length - 1, i));
  const from = idx;
  idx = i;
  render();
  if (i > from) flashStep(from, i);
}

// ── playback ────────────────────────────────────────────────────────────
function speed() {
  const v = parseInt($("speed").value, 10);
  return SPEEDS[v + 2];
}

function nextDelay() {
  const base = 320 / speed();
  if (!$("realtime").checked || idx < 0 || idx + 1 >= events.length) return base;
  const dt = (events[idx + 1].t - events[idx].t) * 1000 / speed();
  return Math.max(30, Math.min(2500, dt));
}

function tick() {
  if (idx + 1 >= events.length) { stop(); return; }
  setIdx(idx + 1);
  timer = setTimeout(tick, nextDelay());
}

function play() {
  if (playing) return;
  if (idx + 1 >= events.length) setIdx(-1);   // restart from blank if at end
  playing = true;
  $("play").textContent = "⏸";
  $("play").classList.add("playing");
  timer = setTimeout(tick, nextDelay());
}

function stop() {
  playing = false;
  if (timer) { clearTimeout(timer); timer = null; }
  const btn = $("play");
  if (btn) { btn.textContent = "▶"; btn.classList.remove("playing"); }
}

// ── wiring ──────────────────────────────────────────────────────────────
$("play").onclick = () => (playing ? stop() : play());
$("step-fwd").onclick = () => { stop(); setIdx(idx + 1); };
$("step-back").onclick = () => { stop(); setIdx(idx - 1); };
$("restart").onclick = () => { stop(); setIdx(-1); };
$("scrub").oninput = (e) => { stop(); setIdx(parseInt(e.target.value, 10)); };
$("speed").oninput = () => { $("speed-val").textContent = speed() + "×"; };
$("answers").onchange = render;
$("speed-val").textContent = speed() + "×";

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "SELECT") return;
  if (e.key === " ") { e.preventDefault(); playing ? stop() : play(); }
  else if (e.key === "ArrowRight") { stop(); setIdx(idx + 1); }
  else if (e.key === "ArrowLeft") { stop(); setIdx(idx - 1); }
});

init();
