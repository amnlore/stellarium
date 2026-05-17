// Stellarium web app: Play and Watch-solver modes, pan/zoom, random
// instance picker. Delaunay candidate edges are planar, so the no-crossings
// rule cannot be violated by selection alone; only degree violations surface
// to the player.

const SVG_NS = "http://www.w3.org/2000/svg";
const TYPE_DEG = { anchor: 2, relay: 1, dim: 0 };
const SIZE_CLASSES = ["XS", "S", "M", "L", "XL"];

const state = {
  instance: null,
  mode: "play",                // "play" | "solve"
  size: null,                  // current size filter

  // Play mode
  selected: new Set(),

  // Solver mode
  solverAssignment: null,
  solverRunning: false,
  solverPaused: false,
  solverAborted: false,
  pendingResume: null,
  singleStepPending: false,
  speedSlider: 60,

  // Pan/zoom
  view: { x: -0.06, y: -0.06, w: 1.12, h: 1.12 },
  viewDefault: { x: -0.06, y: -0.06, w: 1.12, h: 1.12 },
  panning: null,
};

function init() {
  state.size = window.STELLARIUM_INSTANCES[0].size_class;

  document.querySelectorAll("#size-tabs .size-tab").forEach((btn) => {
    btn.addEventListener("click", () => setSize(btn.dataset.size));
  });
  document.querySelectorAll("#mode-tabs .mode-tab").forEach((btn) => {
    btn.addEventListener("click", () => setMode(btn.dataset.mode));
  });

  document.getElementById("btn-new").addEventListener("click", pickRandom);
  document.getElementById("btn-help").addEventListener("click", openHelp);
  document.getElementById("help-close").addEventListener("click", closeHelp);
  document.getElementById("btn-zoom-in").addEventListener("click", () => zoomBy(0.85));
  document.getElementById("btn-zoom-out").addEventListener("click", () => zoomBy(1.18));
  document.getElementById("btn-zoom-reset").addEventListener("click", resetView);

  document.getElementById("btn-clear").addEventListener("click", clearSelection);
  document.getElementById("btn-reveal").addEventListener("click", revealSolution);

  document.getElementById("btn-start").addEventListener("click", startSolver);
  document.getElementById("btn-pause").addEventListener("click", togglePause);
  document.getElementById("btn-step").addEventListener("click", stepSolver);
  document.getElementById("btn-reset").addEventListener("click", resetSolver);

  document.getElementById("speed").addEventListener("input", (e) => {
    state.speedSlider = Number(e.target.value);
  });

  document.getElementById("overlay-close").addEventListener("click", dismissOverlay);
  document.getElementById("overlay-next").addEventListener("click", () => {
    dismissOverlay();
    pickRandom();
  });
  document.getElementById("overlay").addEventListener("click", (e) => {
    if (e.target.id === "overlay") dismissOverlay();
  });
  document.getElementById("help-modal").addEventListener("click", (e) => {
    if (e.target.id === "help-modal") closeHelp();
  });

  const svg = document.getElementById("board");
  svg.addEventListener("wheel", onWheel, { passive: false });
  svg.addEventListener("pointerdown", onPanStart);
  window.addEventListener("pointermove", onPanMove);
  window.addEventListener("pointerup", onPanEnd);
  window.addEventListener("keydown", onKey);

  updateModeUI();
  updateSizeTabs();
  pickRandom();

  try {
    if (!localStorage.getItem("stellarium_seen_help")) {
      openHelp();
      localStorage.setItem("stellarium_seen_help", "1");
    }
  } catch {}
}

function onKey(e) {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.key === "Escape") {
    dismissOverlay();
    closeHelp();
    return;
  }
  // Don't shadow browser/OS shortcuts like Cmd+R.
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "?" || e.key === "/") { e.preventDefault(); openHelp(); return; }
  if (e.key === "n" || e.key === "N") { pickRandom(); return; }
  if (e.key === "0") { resetView(); return; }
  if (e.key === "r" || e.key === "R") {
    if (state.mode === "play") revealSolution();
    return;
  }
  if (e.key === "c" || e.key === "C") {
    if (state.mode === "play") clearSelection();
    return;
  }
  if (e.key === " " && state.mode === "solve") {
    e.preventDefault();
    if (!state.solverRunning) startSolver();
    else togglePause();
  }
}

function setMode(mode) {
  if (mode === state.mode) return;
  if (state.solverRunning) {
    state.solverAborted = true;
    if (state.pendingResume) state.pendingResume();
  }
  state.mode = mode;
  state.selected = new Set();
  state.solverAssignment = null;
  state.solverRunning = false;
  state.solverPaused = false;
  setStatus(mode === "play"
    ? "Click candidate edges to build a constellation."
    : "Press Start to watch the solver search.", "");
  dismissOverlay();
  updateModeUI();
  render();
}

function updateModeUI() {
  document.querySelectorAll("#mode-tabs .mode-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === state.mode);
  });
  document.getElementById("play-actions").hidden = state.mode !== "play";
  document.getElementById("solve-actions").hidden = state.mode !== "solve";
  document.getElementById("progress").hidden = state.mode !== "play";
  document.getElementById("solver-stats").hidden = state.mode !== "solve";
  document.getElementById("solver-action").hidden = state.mode !== "solve";
}

function setSize(size) {
  if (size === state.size) return;
  state.size = size;
  updateSizeTabs();
  pickRandom();
}

function updateSizeTabs() {
  document.querySelectorAll("#size-tabs .size-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.size === state.size);
  });
}

function pickRandom() {
  const pool = window.STELLARIUM_INSTANCES.filter((i) => i.size_class === state.size);
  if (pool.length === 0) return;
  let pick;
  do {
    pick = pool[Math.floor(Math.random() * pool.length)];
  } while (pool.length > 1 && state.instance && pick.id === state.instance.id);
  loadInstance(pick);
}

function loadInstance(inst) {
  state.instance = inst;
  state.selected = new Set();
  state.solverAssignment = null;
  state.solverRunning = false;
  state.solverPaused = false;
  state.solverAborted = true;
  if (state.pendingResume) state.pendingResume();
  state.crossings = window.StellariumSolver.computeCrossings(inst);
  state.view = { ...state.viewDefault };
  applyView();
  resetSolverStats();
  dismissOverlay();
  setStatus(state.mode === "play"
    ? "Click candidate edges to build a constellation."
    : "Press Start to watch the solver search.", "");
  document.getElementById("chip-id").textContent = inst.id.replace("stellarium_", "");
  document.getElementById("chip-meta").textContent =
    `n=${inst.stars.length} · edges=${inst.edges.length}`;
  render();
}

function applyView() {
  const { x, y, w, h } = state.view;
  document.getElementById("board").setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
}

function resetView() {
  state.view = { ...state.viewDefault };
  applyView();
}

function onWheel(e) {
  e.preventDefault();
  const svg = document.getElementById("board");
  const rect = svg.getBoundingClientRect();
  const mx = (e.clientX - rect.left) / rect.width;
  const my = (e.clientY - rect.top) / rect.height;
  const sx = state.view.x + mx * state.view.w;
  const sy = state.view.y + my * state.view.h;
  const factor = Math.exp(e.deltaY * 0.0018);
  const newW = clamp(state.view.w * factor, 0.05, 6);
  const newH = state.view.h * (newW / state.view.w);
  state.view.w = newW;
  state.view.h = newH;
  state.view.x = sx - mx * state.view.w;
  state.view.y = sy - my * state.view.h;
  applyView();
}

function onPanStart(e) {
  if (e.target.tagName === "line" || e.target.tagName === "circle") return;
  document.querySelector(".canvas-wrap").classList.add("panning");
  state.panning = {
    sx: e.clientX,
    sy: e.clientY,
    vx: state.view.x,
    vy: state.view.y,
  };
}

function onPanMove(e) {
  if (!state.panning) return;
  const svg = document.getElementById("board");
  const rect = svg.getBoundingClientRect();
  const dx = (e.clientX - state.panning.sx) / rect.width * state.view.w;
  const dy = (e.clientY - state.panning.sy) / rect.height * state.view.h;
  state.view.x = state.panning.vx - dx;
  state.view.y = state.panning.vy - dy;
  applyView();
}

function onPanEnd() {
  state.panning = null;
  document.querySelector(".canvas-wrap").classList.remove("panning");
}

function zoomBy(factor) {
  const cx = state.view.x + state.view.w / 2;
  const cy = state.view.y + state.view.h / 2;
  state.view.w = clamp(state.view.w * factor, 0.05, 6);
  state.view.h = state.view.w; // keep square
  state.view.x = cx - state.view.w / 2;
  state.view.y = cy - state.view.h / 2;
  applyView();
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function render() {
  const svg = document.getElementById("board");
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const inst = state.instance;
  if (!inst) return;

  const gEdges = document.createElementNS(SVG_NS, "g");
  gEdges.setAttribute("id", "edges");
  svg.appendChild(gEdges);
  const gHits = document.createElementNS(SVG_NS, "g");
  gHits.setAttribute("id", "hits");
  svg.appendChild(gHits);
  const gStars = document.createElementNS(SVG_NS, "g");
  gStars.setAttribute("id", "stars");
  svg.appendChild(gStars);

  const pos = new Map(inst.stars.map((s) => [s.id, [s.x, s.y]]));

  for (const e of inst.edges) {
    const [x1, y1] = pos.get(e.u);
    const [x2, y2] = pos.get(e.v);
    const ln = document.createElementNS(SVG_NS, "line");
    ln.setAttribute("x1", x1);
    ln.setAttribute("y1", y1);
    ln.setAttribute("x2", x2);
    ln.setAttribute("y2", y2);
    ln.setAttribute("class", edgeClass(e.id));
    ln.dataset.edgeId = e.id;
    gEdges.appendChild(ln);

    if (state.mode === "play") {
      const hit = document.createElementNS(SVG_NS, "line");
      hit.setAttribute("x1", x1);
      hit.setAttribute("y1", y1);
      hit.setAttribute("x2", x2);
      hit.setAttribute("y2", y2);
      hit.setAttribute("class", "edge click-hit");
      hit.dataset.edgeId = e.id;
      hit.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleEdge(e.id);
      });
      hit.addEventListener("pointerenter", () => {
        const visible = document.querySelector(`#edges line[data-edge-id="${e.id}"]`);
        if (visible && !visible.classList.contains("selected")) {
          visible.classList.add("hover");
        }
      });
      hit.addEventListener("pointerleave", () => {
        const visible = document.querySelector(`#edges line[data-edge-id="${e.id}"]`);
        if (visible) visible.classList.remove("hover");
      });
      gHits.appendChild(hit);
    }
  }

  const radius = { anchor: 0.018, relay: 0.014, dim: 0.011 };
  for (const s of inst.stars) {
    const c = document.createElementNS(SVG_NS, "circle");
    c.setAttribute("cx", s.x);
    c.setAttribute("cy", s.y);
    c.setAttribute("r", radius[s.star_type]);
    c.setAttribute("class", `star ${s.star_type} ${starSatisfactionClass(s)}`);
    c.dataset.starId = s.id;
    gStars.appendChild(c);
  }

  updateProgress();
  applyView();
}

function edgeClass(eid) {
  if (state.mode === "play") {
    return state.selected.has(eid) ? "edge selected" : "edge";
  }
  const a = state.solverAssignment;
  if (!a) return "edge unassigned";
  const v = a.get(eid);
  if (v === undefined) return "edge unassigned";
  if (v === true) return "edge propagated-true";
  return "edge propagated-false";
}

function starSatisfactionClass(s) {
  const need = TYPE_DEG[s.star_type];
  const deg = currentDegree(s.id);
  if (state.mode === "play") {
    if (state.selected.size === 0) return "";
    if (deg > need) return "unsatisfied";
    if (deg === need && deg > 0) return "satisfied";
    return "";
  }
  if (state.solverAssignment && deg === need && unassignedDegree(s.id) === 0)
    return "satisfied";
  return "";
}

function currentDegree(starId) {
  const inst = state.instance;
  if (state.mode === "play") {
    let d = 0;
    for (const e of inst.edges)
      if (state.selected.has(e.id) && (e.u === starId || e.v === starId)) d++;
    return d;
  }
  if (!state.solverAssignment) return 0;
  let d = 0;
  for (const e of inst.edges)
    if ((e.u === starId || e.v === starId) && state.solverAssignment.get(e.id) === true) d++;
  return d;
}

function unassignedDegree(starId) {
  if (!state.solverAssignment) return 0;
  let d = 0;
  for (const e of state.instance.edges)
    if ((e.u === starId || e.v === starId) &&
        state.solverAssignment.get(e.id) === undefined) d++;
  return d;
}

function toggleEdge(eid) {
  if (state.mode !== "play") return;
  if (state.selected.has(eid)) state.selected.delete(eid);
  else state.selected.add(eid);
  const ln = document.querySelector(`#edges line[data-edge-id="${eid}"]`);
  if (ln) ln.setAttribute("class", edgeClass(eid));
  refreshAllStarMarks();
  updateProgress();
  evaluateWinCondition();
}

function refreshAllStarMarks() {
  for (const s of state.instance.stars) {
    const node = document.querySelector(`#stars circle[data-star-id="${s.id}"]`);
    if (node) node.setAttribute("class", `star ${s.star_type} ${starSatisfactionClass(s)}`);
  }
}

function evaluateWinCondition() {
  const inst = state.instance;
  let ok = true;
  for (const s of inst.stars) {
    if (currentDegree(s.id) !== TYPE_DEG[s.star_type]) { ok = false; break; }
  }
  if (ok && state.selected.size > 0) {
    setStatus("Solved.", "success");
    showOverlay({
      title: "Solved",
      subtitle: `${state.selected.size} edges · ${state.instance.stars.length} stars satisfied`,
      icon: "✦",
      kind: "success",
    });
  } else if (state.selected.size === 0) {
    setStatus("Click candidate edges to build a constellation.", "");
  } else {
    const remaining = inst.stars.reduce(
      (acc, s) => acc + (currentDegree(s.id) === TYPE_DEG[s.star_type] ? 0 : 1),
      0
    );
    setStatus(
      `${state.selected.size} edge${state.selected.size === 1 ? "" : "s"} selected · ${remaining} star${remaining === 1 ? "" : "s"} not yet satisfied`,
      ""
    );
  }
}

function clearSelection() {
  state.selected = new Set();
  setStatus("Selection cleared.", "");
  dismissOverlay();
  render();
}

function revealSolution() {
  const sol = state.instance.solution || [];
  state.selected = new Set(sol);
  render();
  setStatus("Solution revealed.", "info");
  showOverlay({
    title: "Solution",
    subtitle: `Found by the SAT solver — ${sol.length} edges`,
    icon: "✦",
    kind: "success",
  });
}

function resetSolverStats() {
  document.getElementById("ss-step").textContent = "0";
  document.getElementById("ss-decisions").textContent = "0";
  document.getElementById("ss-propagations").textContent = "0";
  document.getElementById("ss-conflicts").textContent = "0";
  document.getElementById("solver-action").textContent = "Idle.";
}

async function startSolver() {
  if (state.solverRunning) return;
  state.solverRunning = true;
  state.solverPaused = false;
  state.solverAborted = false;
  state.solverAssignment = new Map(state.instance.edges.map((e) => [e.id, undefined]));
  setStatus("Solver running…", "info");
  dismissOverlay();
  resetSolverStats();
  render();
  try {
    const result = await window.StellariumSolver.dpllSolve(
      state.instance,
      onSolverStep
    );
    if (state.solverAborted) return;
    if (result.sat) {
      setStatus("Solver found a model.", "success");
      showOverlay({
        title: "Model found",
        subtitle: `${result.state.decisions} decisions · ${result.state.propagations} propagations · ${result.state.conflicts} conflicts`,
        icon: "✦",
        kind: "success",
      });
    } else {
      setStatus("Unsatisfiable.", "error");
      showOverlay({
        title: "Unsatisfiable",
        subtitle: "Search exhausted with no model",
        icon: "✕",
        kind: "failure",
      });
    }
  } catch (err) {
    if (!state.solverAborted) {
      console.error(err);
      setStatus(`Solver error: ${err.message}`, "error");
    }
  } finally {
    state.solverRunning = false;
    state.solverPaused = false;
  }
}

function togglePause() {
  if (!state.solverRunning) return;
  state.solverPaused = !state.solverPaused;
  if (!state.solverPaused && state.pendingResume) {
    const r = state.pendingResume;
    state.pendingResume = null;
    r();
  }
  setStatus(state.solverPaused ? "Paused." : "Solver running…", "info");
}

function stepSolver() {
  if (!state.solverRunning) return;
  if (!state.solverPaused) state.solverPaused = true;
  if (state.pendingResume) {
    const r = state.pendingResume;
    state.pendingResume = null;
    state.singleStepPending = true;
    r();
  }
}

function resetSolver() {
  state.solverAborted = true;
  if (state.pendingResume) {
    const r = state.pendingResume;
    state.pendingResume = null;
    r();
  }
  state.solverRunning = false;
  state.solverPaused = false;
  state.solverAssignment = null;
  resetSolverStats();
  setStatus("Reset.", "");
  dismissOverlay();
  render();
}

async function onSolverStep(step) {
  if (state.solverAborted) throw new Error("aborted");
  state.solverAssignment = step.state.assignment;
  applyStepToDOM(step);
  document.getElementById("ss-step").textContent = step.state.step;
  document.getElementById("ss-decisions").textContent = step.state.decisions;
  document.getElementById("ss-propagations").textContent = step.state.propagations;
  document.getElementById("ss-conflicts").textContent = step.state.conflicts;
  document.getElementById("solver-action").textContent = describeStep(step);

  const delay = Math.max(4, Math.round(800 - state.speedSlider * 7.96));
  await sleep(delay);
  if (state.solverAborted) throw new Error("aborted");

  if (state.solverPaused) {
    await new Promise((resolve) => { state.pendingResume = resolve; });
    if (state.singleStepPending) {
      state.singleStepPending = false;
      state.solverPaused = true;
    }
  }
}

function describeStep(step) {
  switch (step.kind) {
    case "decision":     return `▸ Decide  edge ${step.edge} = ${step.value}`;
    case "propagation": {
      const r = step.reason;
      if (r.type === "dim")        return `· Propagate (dim ${r.star})  edge ${step.edge} = false`;
      if (r.type === "saturated")  return `· Propagate (full ${r.star})  edge ${step.edge} = false`;
      if (r.type === "forced")     return `· Propagate (need ${r.star})  edge ${step.edge} = true`;
      if (r.type === "crossing")   return `· Propagate (xing ${r.with})  edge ${step.edge} = false`;
      return `· Propagate  edge ${step.edge} = ${step.value}`;
    }
    case "conflict":  return "✕ Conflict — backtracking";
    case "backtrack": return `↺ Backtrack  edge ${step.edge} = ${step.value}`;
    case "model":     return "✦ Model found";
    default:          return "";
  }
}

function applyStepToDOM(step) {
  const inst = state.instance;
  for (const e of inst.edges) {
    const ln = document.querySelector(`#edges line[data-edge-id="${e.id}"]`);
    if (!ln) continue;
    ln.setAttribute("class", edgeClass(e.id));
  }
  for (const s of inst.stars) {
    const node = document.querySelector(`#stars circle[data-star-id="${s.id}"]`);
    if (node) node.setAttribute("class", `star ${s.star_type} ${starSatisfactionClass(s)}`);
  }
  if (step.edge !== undefined && step.kind !== "conflict") {
    const ln = document.querySelector(`#edges line[data-edge-id="${step.edge}"]`);
    if (ln) {
      if (step.kind === "decision") ln.setAttribute("class", "edge decision");
      else if (step.kind === "backtrack") ln.classList.add("bad");
    }
  } else if (step.kind === "conflict" && step.info && step.info.conflictPair) {
    for (const id of step.info.conflictPair) {
      const ln = document.querySelector(`#edges line[data-edge-id="${id}"]`);
      if (ln) ln.classList.add("bad");
    }
  }
  updateProgress();
}

function updateProgress() {
  // Counts satisfied stars / total per type. Dims start satisfied because
  // their required degree is 0 and nothing is selected yet.
  const inst = state.instance;
  const counts = {
    anchor: { sat: 0, total: 0 },
    relay:  { sat: 0, total: 0 },
    dim:    { sat: 0, total: 0 },
  };
  for (const s of inst.stars) {
    counts[s.star_type].total++;
    if (currentDegree(s.id) === TYPE_DEG[s.star_type]) {
      counts[s.star_type].sat++;
    }
  }
  document.getElementById("prog-anchor").textContent =
    `${counts.anchor.sat}/${counts.anchor.total}`;
  document.getElementById("prog-relay").textContent =
    `${counts.relay.sat}/${counts.relay.total}`;
  document.getElementById("prog-dim").textContent =
    `${counts.dim.sat}/${counts.dim.total}`;
}

function setStatus(msg, kind) {
  const el = document.getElementById("status");
  el.className = `status-toast ${kind || ""}`;
  el.textContent = msg;
}


function showOverlay({ title, subtitle, icon, kind }) {
  const o = document.getElementById("overlay");
  const card = o.querySelector(".overlay-card");
  card.classList.remove("failure");
  if (kind === "failure") card.classList.add("failure");
  document.getElementById("overlay-title").textContent = title || "";
  document.getElementById("overlay-sub").textContent = subtitle || "";
  document.getElementById("overlay-icon").textContent = icon || "✦";
  o.hidden = false;
}

function dismissOverlay() {
  document.getElementById("overlay").hidden = true;
}

function openHelp() { document.getElementById("help-modal").hidden = false; }
function closeHelp() { document.getElementById("help-modal").hidden = true; }

function sleep(ms) { return new Promise((res) => setTimeout(res, ms)); }

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
