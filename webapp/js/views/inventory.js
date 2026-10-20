// Инвентарь (фильтры, продажа поштучно и пачкой) и магазин запчастей.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { caseName } from "../rewards.js";
import { item, patchMe, refreshMe, slotTitle, state } from "../state.js";
import { confirmSheet, emptyState, errorToast, esc, fmt, haptic, itemCard, itemDetails, nav, sheet, toast } from "../ui.js";

const SLOT_FILTERS = ["all", "frame", "motors", "stack", "video", "props", "battery", "goggles", "radio"];
const view = { tab: "items", slot: "all", selecting: false, selected: new Set() };

function filterChips() {
  return `<div class="chips">${SLOT_FILTERS.map((slot) =>
    `<button class="chip ${view.slot === slot ? "active" : ""}" data-slot="${slot}">${slot === "all" ? "Все" : esc(slotTitle(slot))}</button>`).join("")}</div>`;
}

function itemsTab(inventory) {
  const list = inventory.items.filter((owned) => view.slot === "all" || owned.slot === view.slot);
  const selectedValue = list.filter((owned) => view.selected.has(owned.uid)).reduce((sum, owned) => sum + owned.sell, 0);
  const keys = Object.entries(inventory.keys);
  return `
    ${keys.length ? `<div class="chips">${keys.map(([caseId, qty]) =>
      `<button class="chip" data-go="/cases">${icon("key")} ${esc(caseName(caseId))} ×${qty}</button>`).join("")}</div>` : ""}
    <div class="row between" style="margin:6px 2px 8px">
      <span class="muted mono" style="font-size:12px">${inventory.items.length} шт. · ${fmt(inventory.value)} монет</span>
      <div class="row">
        <button class="btn small ghost" data-bulk>Распродажа</button>
        <button class="btn small ${view.selecting ? "primary" : ""}" data-select>${view.selecting ? "Готово" : "Выбрать"}</button>
      </div>
    </div>
    ${filterChips()}
    ${list.length ? `<div class="items-grid">${list.map((owned) => itemCard(owned, {
      selected: view.selected.has(owned.uid), disabled: view.selecting && owned.locked, footer: "sell",
    })).join("")}</div>` : emptyState("📦", "Тут пусто. Открой кейс — и детали появятся!")}
    ${view.selecting && view.selected.size ? `<div style="position:sticky;bottom:calc(var(--tabbar-h) + 12px);margin-top:12px">
      <button class="btn hot block" data-sell>Продать ${view.selected.size} шт. за ${fmt(selectedValue)}</button></div>` : ""}`;
}

function shopTab(shop) {
  const list = shop.filter((entry) => view.slot === "all" || entry.slot === view.slot);
  return `
    <p class="muted" style="margin:0 0 10px;font-size:13px">Базовые детали всегда в наличии — чтобы собрать дрон, не дожидаясь удачи.</p>
    ${filterChips()}
    <div class="items-grid">${list.map((entry) => itemCard({ ...entry, uid: undefined }, { footer: "price" })).join("")}</div>`;
}

function detailSheet(owned, rerender) {
  const data = item(owned.id);
  const actions = [];
  if (!owned.locked) actions.push(`<button class="btn hot grow" data-sell-one>Продать · ${fmt(owned.sell)}</button>`);
  if (!owned.locked) actions.push('<button class="btn grow" data-upgrade>В мастерскую</button>');
  if (owned.wear > 0) actions.push(`<button class="btn gold grow" data-repair>Починить · ${fmt(owned.repair)}</button>`);
  const { el, close } = sheet(`${itemDetails(data)}
    <div class="stat" style="margin-bottom:12px"><span class="label">Износ</span><div class="bar pink"><i style="width:${owned.wear}%"></i></div><span class="val">${owned.wear}%</span></div>
    ${owned.locked ? '<p class="muted" style="font-size:13px">Деталь стоит в сборке или надета. Снимите её в ангаре, чтобы продать.</p>' : ""}
    <div class="row wrap">${actions.join("")}</div>`);
  el.querySelector("[data-sell-one]")?.addEventListener("click", async () => {
    try {
      const sold = await api.post("/api/inventory/sell", { uids: [owned.uid] });
      patchMe({ coins: sold.coins });
      toast(`+${fmt(sold.earned)} монет`, "good");
      close();
      rerender();
    } catch (error) {
      errorToast(error);
    }
  });
  el.querySelector("[data-upgrade]")?.addEventListener("click", () => {
    close();
    nav(`/workshop?uid=${owned.uid}`);
  });
  el.querySelector("[data-repair]")?.addEventListener("click", async () => {
    try {
      const result = await api.post("/api/hangar/repair", { uids: [owned.uid] });
      patchMe({ coins: result.coins });
      toast("Как новенькая!", "good");
      close();
      rerender();
    } catch (error) {
      errorToast(error);
    }
  });
}

function buySheet(entry, rerender) {
  const { el, close } = sheet(`${itemDetails(item(entry.id))}
    <button class="btn primary block" data-buy ${entry.price > state.me.coins ? "disabled" : ""}>Купить за ${fmt(entry.price)}</button>`);
  el.querySelector("[data-buy]").onclick = async () => {
    try {
      const result = await api.post("/api/shop/buy", { item_id: entry.id, qty: 1 });
      patchMe({ coins: result.coins });
      haptic("success");
      toast("Куплено — деталь в инвентаре", "good");
      close();
      rerender();
    } catch (error) {
      errorToast(error);
    }
  };
}

function bulkSheet(rerender) {
  const { el, close } = sheet(`
    <h2>Распродажа</h2>
    <p class="muted" style="margin-top:0">Продаст все свободные детали до выбранной редкости. Детали в сборках не трогаем.</p>
    <div class="stack">
      <button class="btn" data-max="common">Только обычные</button>
      <button class="btn" data-max="uncommon">Обычные и необычные</button>
      <button class="btn danger" data-max="rare">Всё до редких включительно</button>
    </div>`);
  el.querySelectorAll("[data-max]").forEach((button) => button.addEventListener("click", async () => {
    close();
    if (!(await confirmSheet("Точно продать всё выбранное?", "Продать", { danger: true }))) return;
    try {
      const sold = await api.post("/api/inventory/sell-bulk", { max_rarity: button.dataset.max });
      patchMe({ coins: sold.coins });
      toast(`Продано ${sold.sold} шт. за ${fmt(sold.earned)}`, "good");
      rerender();
    } catch (error) {
      errorToast(error);
    }
  }));
}

export async function render(root, params) {
  if (params?.get("tab")) view.tab = params.get("tab") === "shop" ? "shop" : "items";
  const [inventory, shop] = await Promise.all([api.get("/api/inventory"), view.tab === "shop" ? api.get("/api/shop") : null]);
  const rerender = () => render(root);
  root.innerHTML = `
    <div class="page-title"><h1><small>// INVENTORY</small>Детали</h1></div>
    <div class="segmented" style="margin-bottom:12px">
      <button data-tab="items" class="${view.tab === "items" ? "active" : ""}">Инвентарь</button>
      <button data-tab="shop" class="${view.tab === "shop" ? "active" : ""}">Магазин</button>
    </div>
    ${view.tab === "shop" ? shopTab(shop) : itemsTab(inventory)}`;

  root.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
    view.tab = button.dataset.tab;
    view.selecting = false;
    view.selected.clear();
    rerender();
  }));
  root.querySelectorAll("[data-slot]").forEach((chip) => chip.addEventListener("click", () => {
    view.slot = chip.dataset.slot;
    rerender();
  }));
  root.querySelector("[data-select]")?.addEventListener("click", () => {
    view.selecting = !view.selecting;
    view.selected.clear();
    rerender();
  });
  root.querySelector("[data-bulk]")?.addEventListener("click", () => bulkSheet(rerender));
  root.querySelector("[data-sell]")?.addEventListener("click", async () => {
    try {
      const sold = await api.post("/api/inventory/sell", { uids: [...view.selected] });
      patchMe({ coins: sold.coins });
      toast(`Продано ${sold.sold} шт. за ${fmt(sold.earned)}`, "good");
      view.selected.clear();
      view.selecting = false;
      rerender();
      refreshMe().catch(() => {});
    } catch (error) {
      errorToast(error);
    }
  });
  root.querySelectorAll(".item").forEach((card) => card.addEventListener("click", () => {
    if (view.tab === "shop") {
      buySheet(shop.find((entry) => entry.id === card.dataset.id), rerender);
      return;
    }
    const owned = inventory.items.find((candidate) => candidate.uid === Number(card.dataset.uid));
    if (!view.selecting) return detailSheet(owned, rerender);
    if (owned.locked) return toast("Деталь в сборке — сначала снимите её", "error");
    if (view.selected.has(owned.uid)) view.selected.delete(owned.uid);
    else view.selected.add(owned.uid);
    haptic("select");
    rerender();
  }));
}
