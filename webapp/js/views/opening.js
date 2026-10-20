// Открытие кейса: аналоговые помехи «поиск сигнала», лента-рулетка, раскрытие выигрыша.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { patchMe, rarityTitle, refreshMe } from "../state.js";
import { levelUp } from "../rewards.js";
import { errorToast, esc, fmt, fullscreen, haptic, toast } from "../ui.js";

const STRIP_LENGTH = 48;
const WIN_INDEX = 40;
const SPIN_MS = 5200;
const STAGGER_MS = 450;
const STATIC_MS = 750;
const BIG_TIERS = new Set(["epic", "legendary", "mythic"]);

function weightedPick(pool) {
  const total = pool.reduce((sum, entry) => sum + entry.chance, 0);
  let point = Math.random() * total;
  for (const entry of pool) {
    point -= entry.chance;
    if (point <= 0) return entry;
  }
  return pool[pool.length - 1];
}

function stripCard(data) {
  return `<div class="strip-card r-${data.rarity}">${icon(data.slot)}<span>${esc(data.name)}</span></div>`;
}

function runStatic(canvas, duration) {
  const ctx = canvas.getContext("2d");
  canvas.width = 160;
  canvas.height = 280;
  const image = ctx.createImageData(canvas.width, canvas.height);
  const started = performance.now();
  canvas.classList.add("on");
  return new Promise((resolve) => {
    const frame = (now) => {
      for (let i = 0; i < image.data.length; i += 4) {
        const value = Math.random() * 255;
        image.data[i] = image.data[i + 1] = image.data[i + 2] = value;
        image.data[i + 3] = 255;
      }
      ctx.putImageData(image, 0, 0);
      if (now - started < duration) requestAnimationFrame(frame);
      else {
        canvas.classList.remove("on");
        resolve();
      }
    };
    requestAnimationFrame(frame);
  });
}

function spinStrip(strip, delay) {
  const track = strip.querySelector(".strip-track");
  const card = track.children[0];
  const step = card.getBoundingClientRect().width + 8;
  const jitter = (Math.random() - 0.5) * step * 0.6;
  const offset = -(WIN_INDEX * step + step / 2 - strip.clientWidth / 2 + jitter);
  const animation = track.animate([{ transform: "translateX(0)" }, { transform: `translateX(${offset}px)` }],
    { duration: SPIN_MS + delay, easing: "cubic-bezier(0.08, 0.6, 0.12, 1)", fill: "forwards" });
  let lastIndex = -1;
  const tick = () => {
    if (animation.playState !== "running") return;
    const x = new DOMMatrixReadOnly(getComputedStyle(track).transform).m41;
    const index = Math.floor((-x + strip.clientWidth / 2) / step);
    if (index !== lastIndex) {
      lastIndex = index;
      haptic("select");
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return animation.finished;
}

function revealMarkup(items) {
  if (items.length === 1) {
    const data = items[0];
    return `<div class="reveal-card r-${data.rarity}" style="position:relative">
        ${BIG_TIERS.has(data.rarity) ? '<div class="rays"></div>' : ""}
        ${icon(data.slot)}
        <div class="rarity-text">${esc(rarityTitle(data.rarity))}</div>
        <h3>${esc(data.name)}</h3>
        <div class="muted mono" style="font-size:12px">${esc(data.spec || "")}</div>
        <div class="mono" style="margin-top:8px;color:var(--amber)">${fmt(data.value)} ${icon("coin")}</div>
      </div>`;
  }
  return `<div class="reveal-grid">${items.map((data) => `
      <div class="reveal-card r-${data.rarity}" style="width:auto;padding:12px">
        ${icon(data.slot)}<div class="rarity-text">${esc(rarityTitle(data.rarity))}</div>
        <div style="font-weight:700;font-size:13px">${esc(data.name)}</div>
        <div class="mono" style="color:var(--amber);font-size:12px">${fmt(data.value)}</div>
      </div>`).join("")}</div>`;
}

/**
 * Открывает кейс через API и проигрывает анимацию.
 * detail — ответ /api/cases/{id} (шансы), onAgain — повтор с теми же параметрами.
 */
export async function openCase(detail, { count = 1, useKeys = false, pool, onDone, onAgain }) {
  let result;
  try {
    result = await api.post(`/api/cases/${detail.id}/open`, { count, use_keys: useKeys });
  } catch (error) {
    errorToast(error);
    return;
  }
  patchMe({ coins: result.coins });
  const layer = fullscreen("opening");
  const root = layer.el;
  root.innerHTML = `
    <canvas class="static"></canvas>
    <div class="osd-head"><span class="rec">REC</span><span>${esc(detail.name.toUpperCase())}</span><span>CH ${String(count).padStart(2, "0")}</span></div>
    <div class="strips ${count > 1 ? "compact" : ""}"></div>
    <div class="reveal-actions" style="visibility:hidden"></div>`;
  const strips = root.querySelector(".strips");
  result.items.forEach((won) => {
    const cards = Array.from({ length: STRIP_LENGTH }, (_, index) => index === WIN_INDEX ? won : weightedPick(pool));
    strips.insertAdjacentHTML("beforeend", `<div class="strip"><div class="strip-marker"></div>
      <div class="strip-track">${cards.map(stripCard).join("")}</div></div>`);
  });
  await runStatic(root.querySelector("canvas.static"), STATIC_MS);
  await Promise.all([...strips.children].map((strip, index) => spinStrip(strip, index * STAGGER_MS)));

  const best = result.items.reduce((top, data) => (data.value > top.value ? data : top), result.items[0]);
  haptic(BIG_TIERS.has(best.rarity) ? "heavy" : "success");
  strips.outerHTML = `<div class="reveal">${revealMarkup(result.items)}</div>`;
  const sellSum = result.items.reduce((sum, data) => sum + data.sell, 0);
  const actions = root.querySelector(".reveal-actions");
  actions.style.visibility = "visible";
  actions.innerHTML = `
    <button class="btn" data-sell>Продать · ${fmt(sellSum)}</button>
    <button class="btn primary" data-keep>В ангар</button>
    ${onAgain ? `<button class="btn hot" data-again style="grid-column:span 2">Ещё раз</button>` : ""}`;
  const finish = () => {
    layer.close();
    if (result.level_up) levelUp(result.level_up);
    onDone?.();
  };
  actions.querySelector("[data-keep]").onclick = finish;
  actions.querySelector("[data-sell]").onclick = async (event) => {
    event.currentTarget.disabled = true;
    try {
      const sold = await api.post("/api/inventory/sell", { uids: result.items.map((data) => data.uid) });
      toast(`Продано за ${fmt(sold.earned)} монет`, "good");
      patchMe({ coins: sold.coins });
      finish();
    } catch (error) {
      errorToast(error);
    }
  };
  actions.querySelector("[data-again]")?.addEventListener("click", () => {
    layer.close();
    if (result.level_up) levelUp(result.level_up);
    onAgain();
  });
  refreshMe().catch(() => {});
}
