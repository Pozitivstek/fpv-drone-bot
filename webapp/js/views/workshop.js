// Мастерская: апгрейд (ставка деталями → цель с шансом) и контракт (5 одной редкости → 1 выше).
import { api } from "../api.js";
import { icon } from "../icons.js";
import { item, rarityTitle, refreshMe, slotTitle, state } from "../state.js";
import { confirmSheet, emptyState, errorToast, esc, fmt, fullscreen, haptic, itemCard, sheet, toast } from "../ui.js";

const RARITIES = ["common", "uncommon", "rare", "epic", "legendary", "mythic"];
const view = { mode: "upgrade", stake: new Set(), target: null, contract: new Set(), slot: "all" };

const stakeValue = (owned) => Math.round(owned.value * (1 - owned.wear / 200));

function chanceFor(stake, target) {
  const rules = state.catalog.rules;
  if (!stake || !target || target <= stake) return 0;
  const luck = Math.max(0.25, Math.min(10, state.me.luck * state.me.events.luck_event));
  const chance = (stake / target) * rules.upgrade_edge * luck ** rules.upgrade_luck_exp;
  return chance < rules.upgrade_min ? 0 : Math.min(rules.upgrade_max, chance);
}

function stakeBox(free) {
  const chosen = free.filter((owned) => view.stake.has(owned.uid));
  if (!chosen.length) return '<button class="pick-box" data-pick-stake>Положите<br>детали<br><b>до 6 шт.</b></button>';
  const total = chosen.reduce((sum, owned) => sum + stakeValue(owned), 0);
  return `<button class="pick-box filled" data-pick-stake><div><div class="stack-mini">${chosen.map((owned) =>
    `<span class="r-${owned.rarity}" style="color:var(--rc)">${icon(owned.slot)}</span>`).join("")}</div>
    <div class="mono" style="margin-top:6px;color:var(--amber)">${fmt(total)}</div><div class="muted" style="font-size:11px">${chosen.length} шт.</div></div></button>`;
}

function targetBox() {
  if (!view.target) return '<button class="pick-box" data-pick-target>Выберите<br>цель</button>';
  const data = item(view.target);
  return `<button class="pick-box filled r-${data.rarity}" data-pick-target><div>
    <span style="color:var(--rc)">${icon(data.slot, 'style="width:44px;height:44px"')}</span>
    <div style="font-weight:700;font-size:12px">${esc(data.name)}</div>
    <div class="mono" style="color:var(--amber);font-size:12px">${fmt(data.value)}</div></div></button>`;
}

function upgradeMarkup(free) {
  const stake = free.filter((owned) => view.stake.has(owned.uid)).reduce((sum, owned) => sum + stakeValue(owned), 0);
  const target = view.target ? item(view.target).value : 0;
  const chance = chanceFor(stake, target);
  const pct = Math.round(chance * 1000) / 10;
  return `
    <section class="panel osd">
      <div class="upgrade-stage">
        ${stakeBox(free)}
        <div class="ring" id="ring" style="--p:${pct}"><div class="needle"></div><b>${chance ? `${pct}%` : "—"}</b></div>
        ${targetBox()}
      </div>
      <button class="btn hot block" style="margin-top:14px" data-upgrade ${chance ? "" : "disabled"}>${icon("bolt")} Апгрейд</button>
      <p class="muted center" style="font-size:12px;margin-bottom:0">Неудача — ставка сгорает. Чем дороже цель, тем ниже шанс (максимум ${state.catalog.rules.upgrade_max * 100}%).</p>
    </section>`;
}

function contractMarkup(free) {
  const chosen = free.filter((owned) => view.contract.has(owned.uid));
  const rarity = chosen[0]?.rarity;
  const nextRarity = rarity ? RARITIES[RARITIES.indexOf(rarity) + 1] : null;
  const size = state.catalog.rules.contract_size;
  const eligible = free.filter((owned) => owned.rarity !== "mythic");
  return `
    <section class="panel osd">
      <div class="row between"><b>Контракт ${chosen.length}/${size}</b>
        ${nextRarity ? `<span class="rarity-text r-${nextRarity}">→ ${esc(rarityTitle(nextRarity))}</span>` : '<span class="muted" style="font-size:12px">5 одной редкости</span>'}</div>
      <div class="bar" style="margin:10px 0"><i style="width:${(chosen.length / size) * 100}%"></i></div>
      <button class="btn hot block" data-contract ${chosen.length === size ? "" : "disabled"}>${icon("flask")} Подписать контракт</button>
    </section>
    <div class="section-title">Свободные детали</div>
    ${eligible.length ? `<div class="items-grid">${eligible.map((owned) => itemCard(owned, {
      selected: view.contract.has(owned.uid), disabled: Boolean(rarity) && owned.rarity !== rarity,
    })).join("")}</div>` : emptyState("🧪", "Нет свободных деталей для контракта")}`;
}

function pickStake(free, rerender) {
  const max = state.catalog.rules.upgrade_max_inputs;
  const { el, close } = sheet(`<h2>Ставка</h2><p class="muted" style="margin-top:0">До ${max} деталей. Изношенные стоят дешевле.</p>
    <div class="items-grid">${free.map((owned) => itemCard(owned, { selected: view.stake.has(owned.uid) })).join("")}</div>
    <button class="btn primary block" style="margin-top:12px" data-done>Готово</button>`, { onClose: rerender });
  el.querySelectorAll(".item").forEach((card) => card.addEventListener("click", () => {
    const uid = Number(card.dataset.uid);
    if (view.stake.has(uid)) view.stake.delete(uid);
    else if (view.stake.size < max) view.stake.add(uid);
    else return toast(`Максимум ${max} деталей`, "error");
    card.classList.toggle("selected", view.stake.has(uid));
    haptic("select");
  }));
  el.querySelector("[data-done]").onclick = close;
}

function pickTarget(free, rerender) {
  const stake = free.filter((owned) => view.stake.has(owned.uid)).reduce((sum, owned) => sum + stakeValue(owned), 0);
  const slots = ["all", "frame", "motors", "stack", "video", "props", "battery", "goggles", "radio"];
  const draw = () => {
    const options = state.catalog.items
      .filter((data) => data.value > stake && (view.slot === "all" || data.slot === view.slot))
      .map((data) => ({ data, chance: chanceFor(stake, data.value) }))
      .filter((entry) => entry.chance > 0)
      .sort((a, b) => a.data.value - b.data.value);
    return `<div class="chips">${slots.map((slot) => `<button class="chip ${view.slot === slot ? "active" : ""}" data-filter="${slot}">${slot === "all" ? "Все" : esc(slotTitle(slot))}</button>`).join("")}</div>
      <div class="targets">${options.length ? options.map(({ data, chance }) => `
        <button class="target-row r-${data.rarity} ${view.target === data.id ? "active" : ""}" data-target="${data.id}">${icon(data.slot)}
          <div><div style="font-weight:600;font-size:13px">${esc(data.name)}</div><div class="item-spec">${fmt(data.value)} монет</div></div>
          <div class="pct">${(chance * 100).toFixed(1)}%</div></button>`).join("")
        : emptyState("🎯", stake ? "Нет целей с шансом выше 2%" : "Сначала положите детали в ставку")}</div>`;
  };
  const { el, close } = sheet(`<h2>Цель апгрейда</h2><div id="target-body">${draw()}</div>`, { onClose: rerender });
  el.addEventListener("click", (event) => {
    const filter = event.target.closest("[data-filter]");
    const target = event.target.closest("[data-target]");
    if (filter) {
      view.slot = filter.dataset.filter;
      el.querySelector("#target-body").innerHTML = draw();
    } else if (target) {
      view.target = target.dataset.target;
      haptic("select");
      close();
    }
  });
}

async function runUpgrade(root, free, rerender) {
  const target = item(view.target);
  if (!(await confirmSheet(`Рискнуть ставкой ради «${target.name}»?`, "Поехали"))) return;
  let result;
  try {
    result = await api.post("/api/workshop/upgrade", { uids: [...view.stake], target: view.target });
  } catch (error) {
    errorToast(error);
    return;
  }
  const ring = root.querySelector("#ring");
  const winArc = result.chance * 360;
  const landing = result.success ? Math.random() * winArc * 0.9 : winArc + Math.random() * (360 - winArc - 4) + 2;
  ring.style.setProperty("--turn", `${1440 + landing}deg`);
  ring.classList.add("spinning");
  haptic("medium");
  await new Promise((resolve) => setTimeout(resolve, 2500));
  view.stake.clear();
  view.target = null;
  if (result.success) {
    haptic("heavy");
    showPrize(result.item, "АПГРЕЙД УДАЛСЯ", rerender);
  } else {
    haptic("error");
    toast(`Не повезло: сгорело деталей — ${result.lost}`, "error");
    rerender();
  }
  refreshMe().catch(() => {});
}

function showPrize(prize, title, rerender) {
  const layer = fullscreen("opening");
  layer.el.innerHTML = `
    <div class="osd-head"><span class="rec">REC</span><span>${title}</span><span></span></div>
    <div class="reveal"><div class="reveal-card r-${prize.rarity}" style="position:relative"><div class="rays"></div>
      ${icon(prize.slot)}<div class="rarity-text">${esc(rarityTitle(prize.rarity))}</div><h3>${esc(prize.name)}</h3>
      <div class="mono" style="color:var(--amber)">${fmt(prize.value)}</div></div></div>
    <div class="reveal-actions"><button class="btn primary" style="grid-column:span 2" data-ok>Забрать</button></div>`;
  layer.el.querySelector("[data-ok]").onclick = () => {
    layer.close();
    rerender();
  };
}

export async function render(root, params) {
  const inventory = await api.get("/api/inventory");
  const free = inventory.items.filter((owned) => !owned.locked);
  const preset = Number(params?.get("uid"));
  if (preset && free.some((owned) => owned.uid === preset)) {
    view.mode = "upgrade";
    view.stake = new Set([preset]);
    history.replaceState(null, "", "#/workshop");
  }
  const freeIds = new Set(free.map((owned) => owned.uid));
  view.stake = new Set([...view.stake].filter((uid) => freeIds.has(uid)));
  view.contract = new Set([...view.contract].filter((uid) => freeIds.has(uid)));
  const rerender = () => render(root);
  root.innerHTML = `
    <div class="page-title"><h1><small>// WORKSHOP</small>Мастерская</h1></div>
    <div class="segmented" style="margin-bottom:14px">
      <button data-mode="upgrade" class="${view.mode === "upgrade" ? "active" : ""}">Апгрейд</button>
      <button data-mode="contract" class="${view.mode === "contract" ? "active" : ""}">Контракт</button>
    </div>
    ${view.mode === "upgrade" ? upgradeMarkup(free) : contractMarkup(free)}`;

  root.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
    view.mode = button.dataset.mode;
    rerender();
  }));
  root.querySelector("[data-pick-stake]")?.addEventListener("click", () => pickStake(free, rerender));
  root.querySelector("[data-pick-target]")?.addEventListener("click", () => pickTarget(free, rerender));
  root.querySelector("[data-upgrade]")?.addEventListener("click", () => runUpgrade(root, free, rerender));
  root.querySelectorAll(".items-grid .item").forEach((card) => card.addEventListener("click", () => {
    if (view.mode !== "contract" || card.classList.contains("disabled")) return;
    const uid = Number(card.dataset.uid);
    if (view.contract.has(uid)) view.contract.delete(uid);
    else if (view.contract.size < state.catalog.rules.contract_size) view.contract.add(uid);
    haptic("select");
    rerender();
  }));
  root.querySelector("[data-contract]")?.addEventListener("click", async () => {
    try {
      const result = await api.post("/api/workshop/contract", { uids: [...view.contract] });
      view.contract.clear();
      haptic("heavy");
      showPrize(result.item, "КОНТРАКТ ВЫПОЛНЕН", rerender);
      refreshMe().catch(() => {});
    } catch (error) {
      errorToast(error);
    }
  });
}
