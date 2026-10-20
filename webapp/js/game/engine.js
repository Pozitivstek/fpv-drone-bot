// Мини-игра: физика по параметрам сборки, управление пальцем/клавишами, запись траектории.
import { render } from "./render.js";
import { buildTrack } from "./track.js";

const COUNTDOWN_S = 3;
const ACCEL_S = 1.2;
const CRASH_SLOW = 0.25;
const CRASH_RECOVER_S = 1.1;
const X_BOUND = 14;
const Y_MIN = 0.45;
const Y_MAX = 10;
const GATE_FRAME = 0.35;
const PATH_STEP_MS = 100;
const STICK_RADIUS = 70;
const MISS_PENALTY_MS = 3000;
const BOOST_DRAIN = 2;
const RATES_KEY = "fpv-rates";

export function loadRates() {
  try {
    return { rate: 1, expo: 0.3, invert: false, ...JSON.parse(localStorage.getItem(RATES_KEY) || "{}") };
  } catch {
    return { rate: 1, expo: 0.3, invert: false };
  }
}

export function saveRates(rates) {
  try {
    localStorage.setItem(RATES_KEY, JSON.stringify(rates));
  } catch { /* приватный режим — настройки на один сеанс */ }
}

const expoCurve = (value, expo) => (1 - expo) * value + expo * value ** 3;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

function ghostAt(ghost, time) {
  const path = ghost?.path;
  if (!path?.length) return null;
  let index = path.findIndex((point) => point[0] >= time);
  if (index === -1) return null;
  if (index === 0) index = 1;
  const [t0, x0, y0, z0] = path[index - 1];
  const [t1, x1, y1, z1] = path[index];
  const k = t1 === t0 ? 0 : (time - t0) / (t1 - t0);
  return { x: x0 + (x1 - x0) * k, y: y0 + (y1 - y0) * k, z: z0 + (z1 - z0) * k, name: ghost.name };
}

/** Создаёт симуляцию заезда. Возвращает объект с методами step/ input / state. */
export function createSim(race, trackDef, haptic) {
  const flight = race.flight;
  const track = buildTrack(trackDef);
  const rates = loadRates();
  const sim = {
    track, flight, x: 0, y: 2.6, z: 0, vx: 0, vy: 0, speed: 0, roll: 0, time: 0, countdown: COUNTDOWN_S,
    battery: 1, crashes: 0, gatesPassed: 0, missed: 0, nextGate: 0, slow: 1, boost: false, shake: 0,
    flash: null, message: { text: "3", color: "#00f0ff", until: Infinity }, ghost: null, done: null, path: [],
  };
  const inputs = [];
  let stick = { x: 0, y: 0 };
  let lastSample = -PATH_STEP_MS;

  const say = (textValue, color, now, ms = 900) => { sim.message = { text: textValue, color, until: now + ms }; };

  function delayedStick(now) {
    inputs.push({ t: now, x: stick.x, y: stick.y });
    const target = now - flight.latency;
    while (inputs.length > 2 && inputs[1].t <= target) inputs.shift();
    return inputs[0];
  }

  function crash(now, reason) {
    sim.crashes += 1;
    sim.slow = CRASH_SLOW;
    sim.shake = 0.6;
    sim.flash = { type: "crash", until: now + 380 };
    haptic("heavy");
    if (sim.crashes > flight.max_crashes) {
      say("DRONE DOWN", "#ff3b5c", now, 5000);
      sim.done = "dnf";
    } else {
      say(reason, "#ff3b5c", now);
    }
  }

  function checkGates(prevZ, now) {
    const gate = track.gates[sim.nextGate];
    if (!gate || !(prevZ < gate.z && sim.z >= gate.z)) return;
    const dx = Math.abs(sim.x - gate.x);
    const dy = Math.abs(sim.y - gate.y);
    const inner = gate.size - flight.hitbox;
    const outer = gate.size + GATE_FRAME + flight.hitbox;
    if (dx < inner && dy < inner) {
      gate.state = "passed";
      sim.gatesPassed += 1;
      sim.flash = { type: "gate", until: now + 160 };
      haptic("light");
    } else if (dx < outer && dy < outer) {
      gate.state = "missed";
      sim.missed += 1;
      crash(now, "CRASH · ВОРОТА");
    } else {
      gate.state = "missed";
      sim.missed += 1;
      sim.flash = { type: "miss", until: now + 220 };
      say(`MISS +${MISS_PENALTY_MS / 1000}s`, "#ffb020", now);
      haptic("warning");
    }
    sim.nextGate += 1;
  }

  function checkObstacles(prevZ, now) {
    for (const obstacle of track.obstacles) {
      if (prevZ < obstacle.z && sim.z >= obstacle.z && sim.y < obstacle.h
        && Math.abs(sim.x - obstacle.x) < obstacle.r + flight.hitbox) {
        crash(now, "CRASH");
      }
    }
  }

  function step(dt, now) {
    if (sim.done) return;
    if (sim.countdown > 0) {
      sim.countdown -= dt;
      const shown = Math.ceil(sim.countdown);
      if (sim.countdown <= 0) {
        say("GO!", "#b6ff3b", now, 700);
        haptic("heavy");
      } else if (sim.message.text !== String(shown)) {
        sim.message = { text: String(shown), color: "#00f0ff", until: Infinity };
        haptic("light");
      }
      return;
    }
    sim.time += dt * 1000;
    const input = delayedStick(now);
    const sx = expoCurve(clamp(input.x, -1, 1), rates.expo) * rates.rate;
    const sy = expoCurve(clamp(input.y, -1, 1), rates.expo) * rates.rate * (rates.invert ? -1 : 1);
    const wobble = (1 - flight.smooth) * 0.9 * (Math.sin(sim.time / 137) + Math.sin(sim.time / 311 + 1)) * 0.5;
    const response = Math.min(1, flight.response * dt);
    sim.vx += (sx * flight.lateral + wobble - sim.vx) * response;
    sim.vy += (sy * flight.lateral * 0.75 - sim.vy) * response;
    sim.slow = Math.min(1, sim.slow + dt / CRASH_RECOVER_S);
    const accel = Math.min(1, sim.time / 1000 / ACCEL_S);
    sim.speed = flight.top_speed * (sim.boost ? 1.3 : 1) * accel * sim.slow;
    const prevZ = sim.z;
    sim.z += sim.speed * dt;
    sim.x = clamp(sim.x + sim.vx * dt, -X_BOUND, X_BOUND);
    sim.y = clamp(sim.y + sim.vy * dt, Y_MIN, Y_MAX);
    sim.roll += (clamp(sim.vx / 18, -0.6, 0.6) - sim.roll) * Math.min(1, dt * 6);
    sim.shake = Math.max(0, sim.shake - dt * 1.5);
    sim.battery -= (dt * (sim.boost ? BOOST_DRAIN : 1)) / flight.flight_time;
    checkGates(prevZ, now);
    checkObstacles(prevZ, now);
    if (sim.time - lastSample >= PATH_STEP_MS) {
      lastSample = sim.time;
      sim.path.push([Math.round(sim.time), +sim.x.toFixed(2), +sim.y.toFixed(2), +sim.z.toFixed(1)]);
    }
    sim.ghost = ghostAt(race.ghost, sim.time);
    if (sim.done) return;
    if (sim.battery <= 0) {
      say("LOW BATTERY", "#ff3b5c", now, 5000);
      sim.done = "dnf";
    } else if (sim.z >= track.length) {
      while (sim.nextGate < track.gates.length) {
        track.gates[sim.nextGate].state = "missed";
        sim.missed += 1;
        sim.nextGate += 1;
      }
      say("FINISH", "#b6ff3b", now, 5000);
      sim.done = "finished";
    }
  }

  return {
    sim,
    step,
    setStick(x, y) { stick = { x, y }; },
    setBoost(on) { sim.boost = on; },
    result() {
      return {
        finished: sim.done === "finished", time_ms: Math.round(sim.time), gates: sim.gatesPassed,
        missed: sim.missed, crashes: sim.crashes, path: sim.path,
      };
    },
  };
}

/** Подключает canvas, ввод и игровой цикл. onEnd(result) вызывается один раз. */
export function runGame({ canvas, boostButton, hint, race, trackDef, haptic, onEnd }) {
  const game = createSim(race, trackDef, haptic);
  const ctx = canvas.getContext("2d");
  const ratio = Math.min(2, window.devicePixelRatio || 1);
  let width = 0;
  let height = 0;
  let origin = null;
  let frame = 0;
  let last = performance.now();
  let ended = false;
  const keys = new Set();

  const resize = () => {
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  };
  const onDown = (event) => {
    origin = { x: event.clientX, y: event.clientY, id: event.pointerId };
    canvas.setPointerCapture?.(event.pointerId);
    hint.style.opacity = "0";
  };
  const onMove = (event) => {
    if (!origin || event.pointerId !== origin.id) return;
    game.setStick(clamp((event.clientX - origin.x) / STICK_RADIUS, -1, 1), clamp((origin.y - event.clientY) / STICK_RADIUS, -1, 1));
  };
  const onUp = (event) => {
    if (origin && event.pointerId === origin.id) {
      origin = null;
      game.setStick(0, 0);
    }
  };
  const keyStick = () => {
    const x = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
    const y = (keys.has("ArrowUp") || keys.has("w") ? 1 : 0) - (keys.has("ArrowDown") || keys.has("s") ? 1 : 0);
    game.setStick(x, y);
    game.setBoost(keys.has("Shift") || keys.has(" "));
  };
  const onKey = (event) => {
    if (event.type === "keydown") keys.add(event.key);
    else keys.delete(event.key);
    keyStick();
  };
  const boostOn = (event) => {
    event.preventDefault();
    game.setBoost(true);
    boostButton.classList.add("on");
  };
  const boostOff = () => {
    game.setBoost(false);
    boostButton.classList.remove("on");
  };

  const loop = (now) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!document.hidden) game.step(dt, now);
    render(ctx, width, height, game.sim, now);
    if (game.sim.done && !ended) {
      ended = true;
      setTimeout(() => onEnd(game.result()), 900);
    }
    frame = requestAnimationFrame(loop);
  };

  resize();
  window.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerup", onUp);
  canvas.addEventListener("pointercancel", onUp);
  window.addEventListener("keydown", onKey);
  window.addEventListener("keyup", onKey);
  boostButton.addEventListener("pointerdown", boostOn);
  boostButton.addEventListener("pointerup", boostOff);
  boostButton.addEventListener("pointerleave", boostOff);
  frame = requestAnimationFrame(loop);

  return () => {
    cancelAnimationFrame(frame);
    window.removeEventListener("resize", resize);
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("keyup", onKey);
  };
}
