// Трасса строится детерминированно из seed: у всех игроков одинаковые ворота и препятствия.
export const THEMES = {
  hangar: { sky: ["#070a1c", "#2a1a52"], ground: "#070914", grid: "#5b3bff", gate: "#00f0ff", next: "#ff2bd6", deco: "pillar", fog: "#150f30" },
  forest: { sky: ["#04120f", "#1f5040"], ground: "#04100a", grid: "#1f7a40", gate: "#b6ff3b", next: "#ffb020", deco: "tree", fog: "#0b2a1e" },
  bando: { sky: ["#140c08", "#5e3c22"], ground: "#0e0906", grid: "#8a5530", gate: "#ffb020", next: "#00f0ff", deco: "pillar", fog: "#2a1a10" },
  stadium: { sky: ["#05011a", "#43106e"], ground: "#060312", grid: "#ff2bd6", gate: "#00f0ff", next: "#b6ff3b", deco: "stand", fog: "#1d0738" },
  ridge: { sky: ["#0b1830", "#8aa3cc"], ground: "#0c1424", grid: "#5577aa", gate: "#ffffff", next: "#ff3b5c", deco: "rock", fog: "#5a7299" },
  city: { sky: ["#010107", "#0b1d66"], ground: "#02030a", grid: "#2342ff", gate: "#ff2bd6", next: "#00f0ff", deco: "building", fog: "#060a26" },
  worlds: { sky: ["#100205", "#62200c"], ground: "#0b0303", grid: "#ffb020", gate: "#ffb020", next: "#ff2bd6", deco: "stand", fog: "#2c0b06" },
};

const BASE_HEIGHT = 2.6;
const MIN_HEIGHT = 1.4;
const MAX_HEIGHT = 6;
const DECO_STEP = 11;

export function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

function buildGates(def, rand) {
  const bound = 3 + def.wiggle;
  const gates = [];
  let x = 0;
  for (let i = 0; i < def.gates; i += 1) {
    x = clamp(x + (rand() * 2 - 1) * def.wiggle, -bound, bound);
    const y = clamp(BASE_HEIGHT + (rand() * 2 - 1) * def.wiggle * 0.45, MIN_HEIGHT, MAX_HEIGHT);
    gates.push({ z: def.lead_in + (i + 0.5) * def.spacing, x, y, size: def.gate_size, state: "ahead" });
  }
  return gates;
}

function buildObstacles(def, gates, rand) {
  const obstacles = [];
  gates.forEach((gate, index) => {
    if (rand() >= def.obstacles) return;
    const previous = index ? gates[index - 1] : { z: def.lead_in * 0.5, x: 0 };
    const t = 0.35 + rand() * 0.3;
    const side = rand() < 0.5 ? -1 : 1;
    obstacles.push({
      z: previous.z + (gate.z - previous.z) * t,
      x: previous.x + (gate.x - previous.x) * t + side * (gate.size * 0.6 + 0.8 + rand() * 2.5),
      r: 0.35 + rand() * 0.45,
      h: 5 + rand() * 9,
    });
  });
  return obstacles;
}

function buildDeco(def, rand) {
  const deco = [];
  for (let z = 0; z < def.length + 80; z += DECO_STEP) {
    for (const side of [-1, 1]) {
      if (rand() < 0.25) continue;
      deco.push({ z: z + rand() * DECO_STEP, x: side * (17 + rand() * 26), w: 2 + rand() * 5, h: 6 + rand() * 22, seed: rand() });
    }
  }
  return deco;
}

export function buildTrack(def) {
  const rand = mulberry32(def.seed);
  const gates = buildGates(def, rand);
  const obstacles = buildObstacles(def, gates, rand);
  const deco = buildDeco(def, mulberry32(def.seed + 1));
  return { def, gates, obstacles, deco, length: def.length, theme: THEMES[def.theme] || THEMES.hangar };
}
