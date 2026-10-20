// Кейсы: витрина с ценами и ключами, шторка с честными шансами, запуск открытия.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { item, rarityTitle, state } from "../state.js";
import { errorToast, esc, fmt, sheet } from "../ui.js";
import { openCase } from "./opening.js";

const PREVIEW_LIMIT = 40;

function caseCard(entry) {
  const locked = entry.locked;
  return `
    <button class="case-card ${locked ? "locked" : ""}" style="--cc:${entry.color}" data-case="${entry.id}">
      ${locked && !entry.keys ? `<div class="lock">🔒 с ${entry.min_level} уровня</div>` : ""}
      ${entry.keys ? `<span class="keys-badge">${icon("key")} ${entry.keys}</span>` : ""}
      <div class="crate"><div class="crate-box"></div></div>
      <h3>${esc(entry.name)}</h3>
      <p>${esc(entry.tagline)}</p>
      <div class="row between">
        <span class="price">${entry.buyable ? `${fmt(entry.price)} ${icon("coin")}` : "только ключ"}</span>
        <span class="mono muted" style="font-size:11px">${entry.count} шт.</span>
      </div>
    </button>`;
}

function oddsBar(odds) {
  const entries = Object.entries(odds);
  const bar = entries.map(([rarity, pct]) => `<i class="r-${rarity}" style="width:${pct}%"></i>`).join("");
  const legend = entries.map(([rarity, pct]) =>
    `<span class="r-${rarity}">${esc(rarityTitle(rarity))} ${pct < 1 ? pct.toFixed(2) : pct.toFixed(1)}%</span>`).join("");
  return `<div class="odds-bar">${bar}</div><div class="odds-legend">${legend}</div>`;
}

function openButtons(detail, coins) {
  const buttons = [];
  if (detail.keys) buttons.push(`<button class="btn hot" data-open="1" data-keys="1" style="grid-column:span 3">${icon("key")} Открыть ключом · осталось ${detail.keys}</button>`);
  if (detail.locked) {
    buttons.push(`<button class="btn" disabled style="grid-column:span 3">За монеты — с ${detail.min_level} уровня</button>`);
  } else if (detail.buyable) {
    for (const count of [1, 3, 5]) {
      const price = detail.price * count;
      buttons.push(`<button class="btn ${count === 1 ? "primary" : ""}" data-open="${count}" ${price > coins ? "disabled" : ""}>
        ×${count}<span class="price">${fmt(price)}</span></button>`);
    }
  }
  return buttons.length ? `<div class="open-row">${buttons.join("")}</div>`
    : '<p class="muted center">Этот кейс выдают за ежедневный бонус и задания.</p>';
}

async function caseSheet(entry, rerender) {
  let detail;
  try {
    detail = await api.get(`/api/cases/${entry.id}`);
  } catch (error) {
    errorToast(error);
    return;
  }
  const rows = detail.items.slice(0, PREVIEW_LIMIT).map((row) => {
    const data = item(row.id);
    return `<div class="odds-row r-${data.rarity}">${icon(data.slot)}
      <div><div class="nm">${esc(data.name)}</div><div class="item-spec">${esc(data.spec || "")}</div></div>
      <div class="ch">${row.chance < 0.01 ? "<0.01" : row.chance.toFixed(2)}%</div></div>`;
  }).join("");
  const { el, close } = sheet(`
    <div class="case-hero" style="--cc:${detail.color}">
      <div class="crate"><div class="crate-box"></div></div>
      <div><h2>${esc(detail.name)}</h2><p class="muted" style="margin:0">${esc(detail.tagline)}</p></div>
    </div>
    ${oddsBar(entry.odds)}
    <div class="odds-list">${rows}</div>
    ${detail.items.length > PREVIEW_LIMIT ? `<p class="muted center" style="font-size:12px">и ещё ${detail.items.length - PREVIEW_LIMIT}…</p>` : ""}
    ${openButtons(detail, state.me.coins)}`);
  const pool = detail.items.map((row) => ({ ...item(row.id), chance: row.chance }));
  el.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => {
    const count = Number(button.dataset.open);
    const useKeys = Boolean(button.dataset.keys);
    close();
    const launch = () => openCase(detail, {
      count, useKeys, pool, onDone: rerender,
      onAgain: useKeys ? null : launch,
    });
    launch();
  }));
}

export async function render(root) {
  const list = await api.get("/api/cases");
  const withKeys = list.filter((entry) => entry.keys);
  root.innerHTML = `
    <div class="page-title"><h1><small>// LOOT CRATES</small>Кейсы</h1>
      <span class="muted mono" style="font-size:11px">шансы открыты</span></div>
    ${withKeys.length ? `<div class="section-title" style="margin-top:0">Есть ключи</div>
      <div class="cases-grid">${withKeys.map(caseCard).join("")}</div>
      <div class="section-title">Все кейсы</div>` : ""}
    <div class="cases-grid">${list.filter((entry) => !entry.keys).map(caseCard).join("")}</div>`;
  root.querySelectorAll("[data-case]").forEach((card) => card.addEventListener("click", () => {
    const entry = list.find((candidate) => candidate.id === card.dataset.case);
    caseSheet(entry, () => render(root));
  }));
}
