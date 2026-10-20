// Отрисовка FPV-вида: перспектива с креном, неоновые ворота, декорации, «призрак» и OSD как в очках.
const NEAR = 0.6;
const GATE_BAR = 0.2;
const GRID_STEP = 5;
const FINISH_HALF = 9;
const FINISH_HEIGHT = 7;
const NOISE_STRENGTH = 0.32;

let noiseTile = null;

function noiseCanvas() {
  if (noiseTile) return noiseTile;
  noiseTile = document.createElement("canvas");
  noiseTile.width = noiseTile.height = 128;
  const ctx = noiseTile.getContext("2d");
  const image = ctx.createImageData(128, 128);
  for (let i = 0; i < image.data.length; i += 4) {
    const value = Math.random() * 255;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = value;
    image.data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  return noiseTile;
}

function camera(sim, W, H) {
  const shake = sim.shake > 0 ? (Math.random() - 0.5) * sim.shake : 0;
  return { x: sim.x + shake, y: sim.y + 0.12 + shake * 0.5, z: sim.z - 0.4, F: W * 1.05, hOff: H * 0.02 };
}

function project(cam, x, y, z) {
  const dz = z - cam.z;
  if (dz < NEAR) return null;
  const s = cam.F / dz;
  return { x: (x - cam.x) * s, y: -(y - cam.y) * s + cam.hOff, s, dz };
}

function glowLine(ctx, color, width, draw) {
  ctx.strokeStyle = color;
  ctx.globalAlpha *= 0.28;
  ctx.lineWidth = width * 3.2;
  draw();
  ctx.globalAlpha /= 0.28;
  ctx.lineWidth = width;
  draw();
}

function drawWorld(ctx, W, H, cam, theme, view) {
  const span = Math.max(W, H) * 2;
  const sky = ctx.createLinearGradient(0, -H, 0, cam.hOff);
  sky.addColorStop(0, theme.sky[0]);
  sky.addColorStop(1, theme.sky[1]);
  ctx.fillStyle = sky;
  ctx.fillRect(-span, -span, span * 2, span + cam.hOff);
  const ground = ctx.createLinearGradient(0, cam.hOff, 0, H / 2);
  ground.addColorStop(0, theme.fog);
  ground.addColorStop(1, theme.ground);
  ctx.fillStyle = ground;
  ctx.fillRect(-span, cam.hOff, span * 2, span);
  ctx.strokeStyle = theme.grid;
  ctx.lineWidth = 1;
  const start = Math.ceil(cam.z / GRID_STEP) * GRID_STEP;
  for (let z = start; z < cam.z + view; z += GRID_STEP) {
    const left = project(cam, -90, 0, z);
    const right = project(cam, 90, 0, z);
    if (!left || !right) continue;
    ctx.globalAlpha = Math.max(0, 0.9 * (1 - left.dz / view));
    ctx.beginPath();
    ctx.moveTo(left.x, left.y);
    ctx.lineTo(right.x, right.y);
    ctx.stroke();
  }
  ctx.strokeStyle = theme.grid;
  ctx.globalAlpha = 0.5;
  for (let x = -60; x <= 60; x += GRID_STEP) {
    const near = project(cam, x, 0, cam.z + 1);
    const far = project(cam, x, 0, cam.z + view);
    if (!near || !far) continue;
    ctx.beginPath();
    ctx.moveTo(near.x, near.y);
    ctx.lineTo(far.x, far.y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  const haze = ctx.createLinearGradient(0, cam.hOff - H * 0.12, 0, cam.hOff + H * 0.05);
  haze.addColorStop(0, "transparent");
  haze.addColorStop(0.7, theme.fog);
  haze.addColorStop(1, "transparent");
  ctx.fillStyle = haze;
  ctx.globalAlpha = 0.65;
  ctx.fillRect(-span, cam.hOff - H * 0.12, span * 2, H * 0.17);
  ctx.globalAlpha = 0.9;
  ctx.strokeStyle = theme.next;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-span, cam.hOff);
  ctx.lineTo(span, cam.hOff);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function drawGate(ctx, cam, gate, theme, isNext, now, fade) {
  const c = project(cam, gate.x, gate.y, gate.z);
  if (!c) return;
  const half = gate.size * c.s;
  const bar = Math.max(1.5, GATE_BAR * c.s);
  const color = gate.state === "missed" ? "#ff3b5c" : isNext ? theme.next : theme.gate;
  ctx.globalAlpha = (gate.state === "ahead" ? 1 : 0.25) * fade * (isNext ? 0.75 + 0.25 * Math.sin(now / 120) : 1);
  const legL = project(cam, gate.x - gate.size, 0, gate.z);
  const legR = project(cam, gate.x + gate.size, 0, gate.z);
  glowLine(ctx, color, bar, () => {
    ctx.beginPath();
    ctx.rect(c.x - half, c.y - half, half * 2, half * 2);
    if (legL && legR) {
      ctx.moveTo(c.x - half, c.y + half);
      ctx.lineTo(legL.x, legL.y);
      ctx.moveTo(c.x + half, c.y + half);
      ctx.lineTo(legR.x, legR.y);
    }
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
}

function drawPole(ctx, cam, x, z, r, h, color, fade, canopy) {
  const base = project(cam, x, 0, z);
  const top = project(cam, x, h, z);
  if (!base || !top) return;
  const w = Math.max(1, r * 2 * base.s);
  ctx.globalAlpha = fade;
  ctx.fillStyle = color;
  ctx.fillRect(base.x - w / 2, top.y, w, base.y - top.y);
  if (canopy) {
    const spread = r * 5 * base.s;
    ctx.beginPath();
    ctx.moveTo(top.x, top.y - spread * 0.6);
    ctx.lineTo(top.x - spread, top.y + (base.y - top.y) * 0.55);
    ctx.lineTo(top.x + spread, top.y + (base.y - top.y) * 0.55);
    ctx.closePath();
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawDeco(ctx, cam, deco, theme, fade) {
  const base = project(cam, deco.x, 0, deco.z);
  const top = project(cam, deco.x, deco.h, deco.z);
  if (!base || !top) return;
  const w = deco.w * base.s;
  ctx.globalAlpha = fade * 0.9;
  ctx.fillStyle = theme.fog;
  ctx.strokeStyle = theme.grid;
  ctx.lineWidth = 1;
  if (theme.deco === "tree" || theme.deco === "rock") {
    ctx.beginPath();
    ctx.moveTo(base.x, top.y);
    ctx.lineTo(base.x - w, base.y);
    ctx.lineTo(base.x + w, base.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  } else {
    const height = theme.deco === "stand" ? (base.y - top.y) * 0.35 : base.y - top.y;
    ctx.fillRect(base.x - w / 2, base.y - height, w, height);
    ctx.strokeRect(base.x - w / 2, base.y - height, w, height);
    if (theme.deco === "building" || theme.deco === "stand") {
      ctx.fillStyle = theme.gate;
      ctx.globalAlpha = fade * 0.5;
      const rows = theme.deco === "stand" ? 1 : 5;
      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < 3; col += 1) {
          if (Math.sin(deco.seed * 1000 + row * 13 + col * 7) < 0.1) continue;
          ctx.fillRect(base.x - w / 2 + (col + 0.3) * (w / 3), base.y - height + (row + 0.3) * (height / rows), w / 9, height / rows / 4);
        }
      }
    }
  }
  ctx.globalAlpha = 1;
}

function drawFinish(ctx, cam, length, fade) {
  const left = project(cam, -FINISH_HALF, FINISH_HEIGHT, length);
  const right = project(cam, FINISH_HALF, FINISH_HEIGHT, length);
  const leftBase = project(cam, -FINISH_HALF, 0, length);
  if (!left || !right || !leftBase) return;
  ctx.globalAlpha = fade;
  ctx.fillStyle = "#fff";
  const pole = Math.max(2, 0.3 * left.s);
  ctx.fillRect(left.x - pole / 2, left.y, pole, leftBase.y - left.y);
  ctx.fillRect(right.x - pole / 2, right.y, pole, leftBase.y - left.y);
  const cells = 12;
  const cell = (right.x - left.x) / cells;
  for (let i = 0; i < cells; i += 1) {
    for (let row = 0; row < 2; row += 1) {
      ctx.fillStyle = (i + row) % 2 ? "#fff" : "#111";
      ctx.fillRect(left.x + i * cell, left.y - cell * (row + 1), cell, cell);
    }
  }
  ctx.globalAlpha = 1;
}

function drawGhost(ctx, cam, ghost, now) {
  const p = project(cam, ghost.x, ghost.y, ghost.z);
  if (!p) return;
  const size = Math.max(6, 0.45 * p.s);
  ctx.globalAlpha = 0.75 + 0.2 * Math.sin(now / 90);
  ctx.fillStyle = "rgba(255,43,214,0.35)";
  ctx.strokeStyle = "#ff2bd6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(p.x, p.y - size);
  ctx.lineTo(p.x + size, p.y);
  ctx.lineTo(p.x, p.y + size);
  ctx.lineTo(p.x - size, p.y);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.font = "700 11px JetBrains Mono, monospace";
  ctx.fillStyle = "#ff8ef0";
  ctx.textAlign = "center";
  ctx.fillText(`👻 ${ghost.name}`, p.x, p.y - size - 6);
  ctx.globalAlpha = 1;
}

function drawScene(ctx, W, H, sim, cam, now) {
  const { theme, gates, obstacles, deco, length } = sim.track;
  const view = sim.flight.view;
  drawWorld(ctx, W, H, cam, theme, view);
  const visible = (z) => z - cam.z > NEAR && z - cam.z < view;
  const fade = (z) => Math.max(0, Math.min(1, 1.15 - (z - cam.z) / view));
  const items = [];
  deco.forEach((d) => visible(d.z) && items.push({ z: d.z, draw: () => drawDeco(ctx, cam, d, theme, fade(d.z)) }));
  obstacles.forEach((o) => visible(o.z) && items.push({
    z: o.z, draw: () => drawPole(ctx, cam, o.x, o.z, o.r, o.h, theme.deco === "tree" ? "#1f5a2c" : "#ff3b5c", fade(o.z), theme.deco === "tree"),
  }));
  gates.forEach((g, index) => visible(g.z) && items.push({ z: g.z, draw: () => drawGate(ctx, cam, g, theme, index === sim.nextGate, now, fade(g.z)) }));
  if (visible(length)) items.push({ z: length, draw: () => drawFinish(ctx, cam, length, fade(length)) });
  if (sim.ghost && visible(sim.ghost.z)) items.push({ z: sim.ghost.z, draw: () => drawGhost(ctx, cam, sim.ghost, now) });
  items.sort((a, b) => b.z - a.z).forEach((entry) => entry.draw());
}

function text(ctx, value, x, y, { size = 14, color = "#e8f7ff", align = "left", weight = 700 } = {}) {
  ctx.font = `${weight} ${size}px JetBrains Mono, monospace`;
  ctx.textAlign = align;
  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillText(value, x + 1.5, y + 1.5);
  ctx.fillStyle = color;
  ctx.fillText(value, x, y);
}

function formatTime(ms) {
  const total = Math.max(0, ms) / 1000;
  return `${Math.floor(total / 60)}:${(total % 60).toFixed(2).padStart(5, "0")}`;
}

function drawNextArrow(ctx, W, H, cam, sim) {
  const gate = sim.track.gates[sim.nextGate];
  if (!gate) return;
  const p = project(cam, gate.x, gate.y, gate.z);
  const margin = 40;
  if (p && Math.abs(p.x) < W / 2 - margin && Math.abs(p.y) < H / 2 - margin) return;
  const dx = p ? p.x : (gate.x - cam.x) * 100;
  const dy = p ? p.y : -(gate.y - cam.y) * 100;
  const angle = Math.atan2(dy, dx);
  const radius = Math.min(W, H) / 2 - margin;
  ctx.save();
  ctx.translate(W / 2 + Math.cos(angle) * radius, H / 2 + Math.sin(angle) * radius);
  ctx.rotate(angle);
  ctx.fillStyle = sim.track.theme.next;
  ctx.beginPath();
  ctx.moveTo(14, 0);
  ctx.lineTo(-8, -10);
  ctx.lineTo(-8, 10);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawOSD(ctx, W, H, sim, now) {
  const size = Math.max(12, Math.min(18, W / 28));
  const top = 54;
  const color = "#e8f7ff";
  text(ctx, formatTime(sim.time), 16, top, { size: size + 4 });
  text(ctx, `GATE ${Math.min(sim.gatesPassed + sim.missed, sim.track.gates.length)}/${sim.track.gates.length}`, 16, top + size + 8, { size, color: "#00f0ff" });
  if (sim.missed) text(ctx, `+${sim.missed * 3}s`, 16, top + size * 2 + 14, { size, color: "#ffb020" });
  const cells = { whoop: 1, cine: 4, five: 6, seven: 6 }[sim.flight.cls] || 4;
  const voltage = (cells * (3.3 + 0.9 * sim.battery)).toFixed(1);
  const low = sim.battery < 0.2;
  const right = W - 64;  // справа сверху — кнопка выхода
  text(ctx, `${voltage}V`, right, top, { size: size + 4, align: "right", color: low && Math.floor(now / 250) % 2 ? "#ff3b5c" : color });
  text(ctx, `${cells}S ${Math.round(sim.battery * 100)}%  LQ 99`, right, top + size + 8, { size: size - 2, align: "right", color: "#7f93ad" });
  text(ctx, `${Math.round(sim.speed * 3.6)} km/h`, 16, H - 120, { size: size + 2 });
  text(ctx, `ALT ${sim.y.toFixed(1)}m`, 16, H - 120 + size + 6, { size: size - 2, color: "#7f93ad" });
  const hearts = Array.from({ length: sim.flight.max_crashes + 1 }, (_, i) => (i < sim.flight.max_crashes + 1 - sim.crashes ? "◆" : "◇")).join("");
  text(ctx, hearts, W / 2, H - 120, { size, align: "center", color: "#ff2bd6" });
  if (sim.boost) text(ctx, "BOOST", W / 2, top, { size, align: "center", color: "#ff2bd6" });
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.strokeStyle = "rgba(232,247,255,0.8)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-10, 0); ctx.lineTo(-4, 0); ctx.moveTo(4, 0); ctx.lineTo(10, 0);
  ctx.moveTo(0, -4); ctx.lineTo(0, 4);
  ctx.stroke();
  ctx.rotate(-sim.roll);
  ctx.strokeStyle = "rgba(0,240,255,0.6)";
  ctx.beginPath();
  ctx.moveTo(-60, 0); ctx.lineTo(-28, 0); ctx.moveTo(28, 0); ctx.lineTo(60, 0);
  ctx.stroke();
  ctx.restore();
}

function drawNoise(ctx, W, H, amount) {
  if (amount <= 0.01) return;
  const tile = noiseCanvas();
  ctx.globalAlpha = Math.min(0.85, amount);
  ctx.globalCompositeOperation = "screen";
  const ox = Math.random() * 128;
  const oy = Math.random() * 128;
  for (let x = -ox; x < W; x += 128) {
    for (let y = -oy; y < H; y += 128) ctx.drawImage(tile, x, y);
  }
  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = Math.min(0.6, amount * 1.2);
  ctx.fillStyle = "#fff";
  if (Math.random() < amount * 2) ctx.fillRect(0, Math.random() * H, W, 1 + Math.random() * 2);
  ctx.globalAlpha = 1;
}

export function render(ctx, W, H, sim, now) {
  const cam = camera(sim, W, H);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.rotate(-sim.roll);
  drawScene(ctx, W, H, sim, cam, now);
  ctx.restore();
  drawNextArrow(ctx, W, H, cam, sim);
  const analog = sim.flight.system === "analog";
  const crashBurst = sim.flash?.type === "crash" && now < sim.flash.until ? 0.7 : 0;
  drawNoise(ctx, W, H, (analog ? sim.flight.noise * NOISE_STRENGTH * (0.7 + 0.6 * Math.random()) : 0) + crashBurst);
  if (sim.flash && now < sim.flash.until && sim.flash.type !== "crash") {
    ctx.fillStyle = sim.flash.type === "gate" ? "rgba(182,255,59,0.12)" : "rgba(255,176,32,0.18)";
    ctx.fillRect(0, 0, W, H);
  }
  drawOSD(ctx, W, H, sim, now);
  if (sim.message && now < sim.message.until) {
    text(ctx, sim.message.text, W / 2, H * 0.36, { size: Math.min(46, W / 9), align: "center", color: sim.message.color });
  }
}
