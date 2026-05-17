// Async DPLL-style solver. One Boolean per edge. Per star: ANCHOR == 2 true,
// RELAY == 1, DIM == 0. Per crossing pair: not both true.
//
// Propagation rules:
//   - DIM-incident edges are forced false at start.
//   - When a non-dim star reaches its required true count, remaining undecided
//     incident edges become false.
//   - When required - assignedTrue equals the count of undecided incident edges,
//     all of them become true.
//   - When one of a crossing pair becomes true, the other becomes false.
//   - Any violation of these counts at a star is a conflict.
//
// Each step yields a description to `onStep`, which the caller awaits to pace
// the animation.

const STAR_DEG = { anchor: 2, relay: 1, dim: 0 };

class SolverState {
  constructor(instance) {
    this.instance = instance;
    this.n = instance.stars.length;
    this.starById = new Map(instance.stars.map((s) => [s.id, s]));
    this.edgeById = new Map(instance.edges.map((e) => [e.id, e]));
    this.edgeIds = instance.edges.map((e) => e.id);

    this.adj = new Map();
    for (const s of instance.stars) this.adj.set(s.id, []);
    for (const e of instance.edges) {
      this.adj.get(e.u).push(e.id);
      this.adj.get(e.v).push(e.id);
    }

    this.crossings = computeCrossings(instance);
    this.crossingPairs = new Set();
    for (const [a, partners] of this.crossings) {
      for (const b of partners) {
        if (a < b) this.crossingPairs.add(`${a}|${b}`);
      }
    }

    this.assignment = new Map(this.edgeIds.map((id) => [id, undefined]));
    this.trail = [];
    this.decisionLevel = 0;

    this.trueCount = new Map();
    this.unassignedCount = new Map();
    for (const s of instance.stars) {
      this.trueCount.set(s.id, 0);
      this.unassignedCount.set(s.id, this.adj.get(s.id).length);
    }

    this.decisions = 0;
    this.propagations = 0;
    this.conflicts = 0;
    this.step = 0;
  }

  partnersOf(edgeId) {
    return this.crossings.get(edgeId) || [];
  }

  setVar(edgeId, value, reason) {
    const prev = this.assignment.get(edgeId);
    if (prev === value) return { conflict: false, noop: true };
    if (prev !== undefined && prev !== value) {
      return { conflict: true, conflictEdge: edgeId };
    }
    this.assignment.set(edgeId, value);
    this.trail.push({ edge: edgeId, value, reason, level: this.decisionLevel });

    const e = this.edgeById.get(edgeId);
    const stars = [e.u, e.v];
    for (const sid of stars) {
      this.unassignedCount.set(sid, this.unassignedCount.get(sid) - 1);
      if (value === true) {
        this.trueCount.set(sid, this.trueCount.get(sid) + 1);
      }
    }
    for (const sid of stars) {
      const star = this.starById.get(sid);
      const need = STAR_DEG[star.star_type];
      const t = this.trueCount.get(sid);
      const u = this.unassignedCount.get(sid);
      if (t > need) return { conflict: true, conflictStar: sid };
      if (t + u < need) return { conflict: true, conflictStar: sid };
    }
    if (value === true) {
      for (const partner of this.partnersOf(edgeId)) {
        if (this.assignment.get(partner) === true) {
          return { conflict: true, conflictPair: [edgeId, partner] };
        }
      }
    }
    return { conflict: false };
  }

  // Pop assignments above `level` from the trail.
  backtrackTo(level) {
    while (this.trail.length && this.trail[this.trail.length - 1].level > level) {
      const { edge, value } = this.trail.pop();
      const e = this.edgeById.get(edge);
      for (const sid of [e.u, e.v]) {
        this.unassignedCount.set(sid, this.unassignedCount.get(sid) + 1);
        if (value === true) {
          this.trueCount.set(sid, this.trueCount.get(sid) - 1);
        }
      }
      this.assignment.set(edge, undefined);
    }
    this.decisionLevel = level;
  }

  // Branch on an undecided edge incident to the non-dim star with the
  // fewest unassigned incident edges.
  pickBranchEdge() {
    let bestStar = null;
    let bestU = Infinity;
    for (const s of this.instance.stars) {
      const u = this.unassignedCount.get(s.id);
      if (u > 0 && u < bestU && s.star_type !== "dim") {
        bestU = u;
        bestStar = s.id;
      }
    }
    if (bestStar === null) {
      // No non-dim star has undecided edges left; fall back to any undecided.
      for (const id of this.edgeIds) {
        if (this.assignment.get(id) === undefined) return id;
      }
      return null;
    }
    for (const eid of this.adj.get(bestStar)) {
      if (this.assignment.get(eid) === undefined) return eid;
    }
    return null;
  }

  snapshot() {
    return {
      assignment: new Map(this.assignment),
      decisionLevel: this.decisionLevel,
      step: this.step,
      decisions: this.decisions,
      propagations: this.propagations,
      conflicts: this.conflicts,
    };
  }
}

function computeCrossings(instance) {
  const pos = new Map(instance.stars.map((s) => [s.id, [s.x, s.y]]));
  const out = new Map(instance.edges.map((e) => [e.id, []]));
  const eps = 1e-12;
  const n = instance.edges.length;
  for (let i = 0; i < n; i++) {
    const ei = instance.edges[i];
    const [ax, ay] = pos.get(ei.u);
    const [bx, by] = pos.get(ei.v);
    for (let j = i + 1; j < n; j++) {
      const ej = instance.edges[j];
      if (ei.u === ej.u || ei.u === ej.v || ei.v === ej.u || ei.v === ej.v) continue;
      const [cx, cy] = pos.get(ej.u);
      const [dx, dy] = pos.get(ej.v);
      const o1 = orient(ax, ay, bx, by, cx, cy);
      const o2 = orient(ax, ay, bx, by, dx, dy);
      const o3 = orient(cx, cy, dx, dy, ax, ay);
      const o4 = orient(cx, cy, dx, dy, bx, by);
      if (((o1 > eps && o2 < -eps) || (o1 < -eps && o2 > eps)) &&
          ((o3 > eps && o4 < -eps) || (o3 < -eps && o4 > eps))) {
        out.get(ei.id).push(ej.id);
        out.get(ej.id).push(ei.id);
      }
    }
  }
  return out;
}

function orient(ax, ay, bx, by, cx, cy) {
  return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
}

async function dpllSolve(instance, onStep, opts = {}) {
  const state = new SolverState(instance);

  // DIM stars force all incident edges to false.
  for (const star of instance.stars) {
    if (star.star_type !== "dim") continue;
    for (const eid of state.adj.get(star.id)) {
      if (state.assignment.get(eid) === undefined) {
        state.propagations++;
        state.step++;
        const r = state.setVar(eid, false, { type: "dim", star: star.id });
        await onStep({
          kind: "propagation",
          reason: { type: "dim", star: star.id },
          edge: eid,
          value: false,
          state: state.snapshot(),
        });
        if (r.conflict) {
          state.conflicts++;
          await onStep({ kind: "conflict", state: state.snapshot(), info: r });
          return { sat: false, state };
        }
      }
    }
  }

  if (!(await propagate(state, onStep))) return { sat: false, state };

  while (true) {
    const branchEdge = state.pickBranchEdge();
    if (branchEdge === null) {
      if (isModel(state)) {
        await onStep({ kind: "model", state: state.snapshot() });
        return { sat: true, state };
      }
      if (!(await backtrack(state, onStep))) return { sat: false, state };
      continue;
    }
    // Try TRUE first; backtracking will flip if it fails.
    state.decisionLevel++;
    state.decisions++;
    state.step++;
    const r = state.setVar(branchEdge, true, { type: "decision" });
    await onStep({
      kind: "decision",
      edge: branchEdge,
      value: true,
      state: state.snapshot(),
    });
    if (r.conflict) {
      state.conflicts++;
      await onStep({ kind: "conflict", state: state.snapshot(), info: r });
      if (!(await backtrack(state, onStep))) return { sat: false, state };
      continue;
    }
    if (!(await propagate(state, onStep))) {
      if (!(await backtrack(state, onStep))) return { sat: false, state };
    }
  }
}

// Unit-propagation loop. Returns true on success, false on conflict.
async function propagate(state, onStep) {
  let changed = true;
  while (changed) {
    changed = false;
    for (const star of state.instance.stars) {
      if (star.star_type === "dim") continue;
      const need = STAR_DEG[star.star_type];
      const incidents = state.adj.get(star.id);
      const t = state.trueCount.get(star.id);
      const u = state.unassignedCount.get(star.id);
      if (t > need || t + u < need) {
        state.conflicts++;
        await onStep({
          kind: "conflict",
          state: state.snapshot(),
          info: { conflictStar: star.id, t, u, need },
        });
        return false;
      }
      if (t === need && u > 0) {
        for (const eid of incidents) {
          if (state.assignment.get(eid) === undefined) {
            state.propagations++;
            state.step++;
            const r = state.setVar(eid, false, {
              type: "saturated",
              star: star.id,
            });
            changed = true;
            await onStep({
              kind: "propagation",
              reason: { type: "saturated", star: star.id },
              edge: eid,
              value: false,
              state: state.snapshot(),
            });
            if (r.conflict) {
              await onStep({ kind: "conflict", state: state.snapshot(), info: r });
              return false;
            }
          }
        }
      } else if (t + u === need && u > 0) {
        for (const eid of incidents) {
          if (state.assignment.get(eid) === undefined) {
            state.propagations++;
            state.step++;
            const r = state.setVar(eid, true, {
              type: "forced",
              star: star.id,
            });
            changed = true;
            await onStep({
              kind: "propagation",
              reason: { type: "forced", star: star.id },
              edge: eid,
              value: true,
              state: state.snapshot(),
            });
            if (r.conflict) {
              await onStep({ kind: "conflict", state: state.snapshot(), info: r });
              return false;
            }
          }
        }
      }
    }
    for (const e of state.instance.edges) {
      if (state.assignment.get(e.id) !== true) continue;
      for (const partner of state.partnersOf(e.id)) {
        if (state.assignment.get(partner) === undefined) {
          state.propagations++;
          state.step++;
          const r = state.setVar(partner, false, {
            type: "crossing",
            with: e.id,
          });
          changed = true;
          await onStep({
            kind: "propagation",
            reason: { type: "crossing", with: e.id },
            edge: partner,
            value: false,
            state: state.snapshot(),
          });
          if (r.conflict) {
            await onStep({ kind: "conflict", state: state.snapshot(), info: r });
            return false;
          }
        }
      }
    }
  }
  return true;
}

// Pop to the most recent decision and flip its polarity.
// Returns false when no decisions remain (search exhausted).
async function backtrack(state, onStep) {
  while (state.trail.length) {
    let idx = state.trail.length - 1;
    while (idx >= 0 && state.trail[idx].reason?.type !== "decision") idx--;
    if (idx < 0) return false;

    const decision = state.trail[idx];
    const flippedEdge = decision.edge;
    const flippedValue = !decision.value;
    const targetLevel = decision.level - 1;
    state.backtrackTo(targetLevel);
    state.decisionLevel = targetLevel + 1;
    state.step++;

    if (decision.reason?.alsoTried) {
      state.backtrackTo(targetLevel);
      state.decisionLevel = targetLevel;
      continue;
    }
    decision.reason.alsoTried = true;
    const r = state.setVar(flippedEdge, flippedValue, {
      type: "flip",
      from: decision.value,
    });
    await onStep({
      kind: "backtrack",
      edge: flippedEdge,
      value: flippedValue,
      state: state.snapshot(),
    });
    if (r.conflict) {
      state.conflicts++;
      await onStep({ kind: "conflict", state: state.snapshot(), info: r });
      continue;
    }
    if (!(await propagate(state, onStep))) continue;
    return true;
  }
  return false;
}

function isModel(state) {
  for (const s of state.instance.stars) {
    const need = STAR_DEG[s.star_type];
    if (state.trueCount.get(s.id) !== need) return false;
  }
  for (const pair of state.crossingPairs) {
    const [a, b] = pair.split("|").map(Number);
    if (state.assignment.get(a) === true && state.assignment.get(b) === true)
      return false;
  }
  return true;
}

window.StellariumSolver = { dpllSolve, computeCrossings, SolverState };
