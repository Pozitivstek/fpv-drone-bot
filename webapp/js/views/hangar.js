// Ангар: сборки, схема дрона, слоты деталей, очки и пульт, характеристики, ремонт.
import { api } from "../api.js";
import { droneSVG } from "../drone.js";
import { icon } from "../icons.js";
import { classTitle, item, patchMe, refreshMe, slotTitle, systemTitle } from "../state.js";
import { confirmSheet, emptyState, errorToast, esc, fmt, haptic, itemCard, sheet, toast } from "../ui.js";

const SLOTS = ["frame", "motors", "stack", "video", "props", "battery"];
let selectedId = null;

function statRow(label, value, pct, unit = "", pink = false) {
  return `<div class="stat"><span class="label">${label}</span>
    <div class="bar ${pink ? "pink" : ""}"><i style="width:${Math.max(3, Math.min(100, pct))}%"></i></div>
    <span class="val">${value}${unit}</span></div>`;
}

function statsPanel(stats) {
  if (!stats?.speed_kmh) return '<p class="muted center" style="margin:6px 0">Соберите все 6 деталей, чтобы увидеть характеристики.</p>';
  return `
    ${statRow("Скорость", stats.speed_kmh, stats.speed, " км/ч")}
    ${statRow("Отклик", stats.handling, stats.handling)}
    ${statRow("Прочность", stats.durability, stats.durability)}
    ${statRow("Полёт", stats.flight_time, stats.flight_time / 1.5, " с")}
    ${statRow("Картинка", stats.video, stats.video)}
    ${statRow("Задержка", stats.latency, 100 - stats.latency * 2, " мс", true)}
    ${statRow("Управление", stats.control, stats.control)}`;
}

function slotTile(slot, part, warn) {
  if (!part) {
    return `<button class="slot empty" data-slot="${slot}">${icon(slot)}
      <span class="slot-label">${esc(slotTitle(slot))}</span><span class="slot-name muted">+ установить</span></button>`;
  }
  return `<button class="slot r-${part.rarity} ${warn ? "warn" : ""}" data-slot="${slot}">${icon(slot)}
    <span class="slot-label">${esc(slotTitle(slot))}</span><span class="slot-name">${esc(part.name)}</span>
    <div class="wear"><i style="width:${part.wear}%;background-position:${part.wear}% 0"></i></div></button>`;
}

function wornParts(build, hangar) {
  const parts = [...SLOTS.map((slot) => build?.parts[slot]), hangar.goggles, hangar.radio];
  return parts.filter((part) => part && part.wear > 0);
}

function stage(build, hangar) {
  const worn = wornParts(build, hangar);
  const repairCost = worn.reduce((sum, part) => sum + part.repair, 0);
  const brokenSlots = new Set(SLOTS.filter((slot) => build.parts[slot]?.wear >= 100));
  return `
    <section class="panel osd drone-stage glow-cyan">
      <div class="stage-head">
        <div><div class="cls-label">${esc(classTitle(build.cls))}${build.active ? " · активная" : ""}</div><h2>${esc(build.name)}</h2></div>
        <div class="pwr"><b>${build.rating}</b><span>PWR</span></div>
      </div>
      ${droneSVG(Object.fromEntries(SLOTS.map((slot) => [slot, build.parts[slot]])), build.cls, { idle: !build.ready })}
      <div class="status-line">${build.ready ? '<span class="status-ok">● ГОТОВ К ВЗЛЁТУ</span>'
        : `<span class="status-bad">● НЕ ВЗЛЕТИТ: ${build.issues.length}</span>`}</div>
      <div class="row" style="margin-top:10px">
        ${build.active ? "" : `<button class="btn small primary grow" data-act="activate">${icon("star")} Сделать активной</button>`}
        ${repairCost ? `<button class="btn small gold grow" data-act="repair">${icon("wrench")} Ремонт · ${fmt(repairCost)}</button>` : ""}
        <button class="icon-btn" data-act="menu" aria-label="Меню сборки">⋯</button>
      </div>
    </section>
    <div class="section-title">Детали</div>
    <div class="slots">${SLOTS.map((slot) => slotTile(slot, build.parts[slot], brokenSlots.has(slot))).join("")}</div>
    ${build.issues.length ? `<div class="section-title">Что мешает взлететь</div>
      <div class="issues">${build.issues.map((issue) => `<div class="issue">⚠ ${esc(issue)}</div>`).join("")}</div>` : ""}
    <div class="section-title">Характеристики</div>
    <section class="panel stack" style="gap:10px">${statsPanel(build.stats)}</section>`;
}

function gearBlock(hangar) {
  const tile = (slot, part) => part
    ? `<button class="slot r-${part.rarity} ${part.wear >= 100 ? "warn" : ""}" data-gear="${slot}">${icon(slot)}<span class="slot-label">${esc(slotTitle(slot))}</span>
       <span class="slot-name">${esc(part.name)}</span><div class="wear"><i style="width:${part.wear}%"></i></div></button>`
    : `<button class="slot empty" data-gear="${slot}">${icon(slot)}<span class="slot-label">${esc(slotTitle(slot))}</span><span class="slot-name muted">+ выбрать</span></button>`;
  return `<div class="section-title">Комплект пилота</div><div class="gear-row">${tile("goggles", hangar.goggles)}${tile("radio", hangar.radio)}</div>`;
}

function compatibility(candidate, slot, build) {
  const data = item(candidate.id);
  const frameCls = build?.parts.frame ? item(build.parts.frame.id)?.cls?.[0] : null;
  if (slot === "goggles") {
    const system = build?.parts.video ? item(build.parts.video.id)?.system : null;
    return system && !data.systems?.includes(system) ? `не видит ${systemTitle(system)}` : "";
  }
  if (slot === "radio" || slot === "frame" || !frameCls) return "";
  return data.cls?.includes(frameCls) ? "" : `не для «${classTitle(frameCls)}»`;
}

async function pickPart({ slot, build, hangar, inventory, onChange }) {
  const current = slot === "goggles" || slot === "radio" ? hangar[slot] : build.parts[slot];
  const candidates = inventory.items.filter((owned) => owned.slot === slot && owned.uid !== current?.uid)
    .map((owned) => ({ owned, reason: compatibility(owned, slot, build) }))
    .sort((a, b) => Number(Boolean(a.reason)) - Number(Boolean(b.reason)) || b.owned.value - a.owned.value);
  const list = candidates.length ? candidates.map(({ owned, reason }) => `
      <div>${itemCard(owned)}${reason ? `<div class="badge-red center" style="margin-top:4px">${esc(reason)}</div>` : ""}</div>`).join("")
    : emptyState("📦", "Подходящих деталей нет — загляните в кейсы или магазин");
  const { el, close } = sheet(`
    <h2>${esc(slotTitle(slot))}</h2>
    ${current ? `<p class="muted" style="margin:0 0 10px">Сейчас: <b>${esc(current.name)}</b> · износ ${current.wear}%</p>` : ""}
    <div class="items-grid">${list}</div>
    <div class="row" style="margin-top:14px">
      ${current ? '<button class="btn danger grow" data-unequip>Снять</button>' : ""}
      <button class="btn grow" data-go="/inventory?tab=shop">${icon("shop")} Магазин</button>
    </div>`);
  const apply = async (uid) => {
    try {
      if (slot === "goggles" || slot === "radio") await api.put(`/api/hangar/gear/${slot}`, { uid });
      else await api.put(`/api/hangar/builds/${build.id}/slots/${slot}`, { uid });
      haptic("medium");
      close();
      onChange();
    } catch (error) {
      errorToast(error);
    }
  };
  el.querySelectorAll(".item[data-uid]").forEach((card) => card.addEventListener("click", () => apply(Number(card.dataset.uid))));
  el.querySelector("[data-unequip]")?.addEventListener("click", () => apply(null));
  el.querySelector("[data-go]")?.addEventListener("click", close);
}

function buildMenu(build, rerender) {
  const { el, close } = sheet(`
    <h2>${esc(build.name)}</h2>
    <div class="field" style="margin:10px 0"><label>Название</label><input class="input" id="build-name" maxlength="40" value="${esc(build.name)}"></div>
    <div class="row"><button class="btn primary grow" data-rename>Сохранить</button><button class="btn danger grow" data-delete>Разобрать</button></div>
    <p class="muted" style="font-size:12px">При разборке детали вернутся в инвентарь.</p>`);
  el.querySelector("[data-rename]").onclick = async () => {
    try {
      await api.patch(`/api/hangar/builds/${build.id}`, { name: el.querySelector("#build-name").value });
      close();
      rerender();
    } catch (error) {
      errorToast(error);
    }
  };
  el.querySelector("[data-delete]").onclick = async () => {
    close();
    if (!(await confirmSheet(`Разобрать «${build.name}»?`, "Разобрать", { danger: true }))) return;
    try {
      await api.del(`/api/hangar/builds/${build.id}`);
      selectedId = null;
      rerender();
    } catch (error) {
      errorToast(error);
    }
  };
}

async function createBuild(rerender) {
  try {
    const created = await api.post("/api/hangar/builds", { name: `Сборка ${new Date().toLocaleDateString("ru-RU")}` });
    selectedId = created.id;
    toast("Пустая рама в ангаре — ставьте детали", "good");
    rerender();
  } catch (error) {
    errorToast(error);
  }
}

export async function render(root) {
  const [hangar, inventory] = await Promise.all([api.get("/api/hangar"), api.get("/api/inventory")]);
  const rerender = () => render(root);
  const build = hangar.builds.find((candidate) => candidate.id === selectedId)
    || hangar.builds.find((candidate) => candidate.active) || hangar.builds[0];
  selectedId = build?.id ?? null;
  const tabs = hangar.builds.map((candidate) =>
    `<button class="chip ${candidate.id === selectedId ? "active" : ""}" data-build="${candidate.id}">${candidate.active ? "★ " : ""}${esc(candidate.name)}</button>`).join("");
  root.innerHTML = `
    <div class="page-title"><h1><small>// HANGAR</small>Ангар</h1>
      <div class="row"><button class="icon-btn" data-go="/inventory" aria-label="Инвентарь">${icon("bag")}</button>
      <button class="icon-btn" data-go="/inventory?tab=shop" aria-label="Магазин">${icon("shop")}</button></div></div>
    <div class="chips build-tabs">${tabs}${hangar.builds.length < hangar.max_builds ? `<button class="chip" data-new>${icon("plus")} Новая</button>` : ""}</div>
    ${build ? stage(build, hangar) : emptyState("🛠", "В ангаре пусто — создайте сборку")}
    ${gearBlock(hangar)}`;

  root.querySelectorAll("[data-build]").forEach((chip) => chip.addEventListener("click", () => {
    selectedId = Number(chip.dataset.build);
    rerender();
  }));
  root.querySelector("[data-new]")?.addEventListener("click", () => createBuild(rerender));
  root.querySelectorAll("[data-slot]").forEach((tile) => tile.addEventListener("click", () =>
    pickPart({ slot: tile.dataset.slot, build, hangar, inventory, onChange: rerender })));
  root.querySelectorAll("[data-gear]").forEach((tile) => tile.addEventListener("click", () =>
    pickPart({ slot: tile.dataset.gear, build, hangar, inventory, onChange: rerender })));
  root.querySelector('[data-act="menu"]')?.addEventListener("click", () => buildMenu(build, rerender));
  root.querySelector('[data-act="activate"]')?.addEventListener("click", async () => {
    try {
      await api.post(`/api/hangar/builds/${build.id}/activate`);
      haptic("success");
      rerender();
    } catch (error) {
      errorToast(error);
    }
  });
  root.querySelector('[data-act="repair"]')?.addEventListener("click", async () => {
    try {
      const result = await api.post("/api/hangar/repair", { uids: wornParts(build, hangar).map((part) => part.uid) });
      patchMe({ coins: result.coins });
      toast(`Починено деталей: ${result.repaired} за ${fmt(result.cost)} монет`, "good");
      rerender();
      refreshMe().catch(() => {});
    } catch (error) {
      errorToast(error);
    }
  });
}
