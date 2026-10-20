// UI-хелперы: экранирование, форматирование, тосты, шторки, вибро, карточки деталей.
import { icon } from "./icons.js";
import { classTitle, item as catalogItem, rarityTitle, systemTitle } from "./state.js";

export const tg = window.Telegram?.WebApp;

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
export const fmt = (value) => Math.round(Number(value) || 0).toLocaleString("ru-RU");
export const coins = (value) => `<span class="mono" style="color:var(--amber)">${fmt(value)}</span> ${icon("coin", 'style="color:var(--amber)"')}`;

export function msToTime(ms) {
  if (ms == null) return "—";
  const total = Math.max(0, ms) / 1000;
  const minutes = Math.floor(total / 60);
  const seconds = (total % 60).toFixed(2).padStart(5, "0");
  return `${minutes}:${seconds}`;
}

export function html(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

export function haptic(kind = "light") {
  const feedback = tg?.HapticFeedback;
  if (!feedback) return;
  if (["success", "error", "warning"].includes(kind)) feedback.notificationOccurred(kind);
  else if (kind === "select") feedback.selectionChanged();
  else feedback.impactOccurred(kind);
}

export function toast(message, kind = "") {
  const box = document.getElementById("toasts");
  const node = html(`<div class="toast ${kind}">${esc(message)}</div>`);
  box.appendChild(node);
  if (kind === "error") haptic("error");
  setTimeout(() => node.remove(), 3200);
}

export function errorToast(error) {
  toast(error?.message || "Что-то пошло не так", "error");
}

const layer = () => document.getElementById("layer");
const openLayers = new Set();

/** Закрывает все шторки и полноэкранные слои (при переходе между разделами). */
export function closeLayers() {
  [...openLayers].forEach((close) => close());
}

/** Шторка снизу. content — HTML-строка или элемент. Возвращает { el, close }. */
export function sheet(content, { onClose } = {}) {
  const root = html('<div><div class="backdrop-dim"></div><div class="sheet"><div class="sheet-grip"></div></div></div>');
  const panel = root.querySelector(".sheet");
  if (typeof content === "string") panel.insertAdjacentHTML("beforeend", content);
  else panel.appendChild(content);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    openLayers.delete(close);
    root.remove();
    tg?.BackButton?.offClick(close);
    syncBackButton();
    onClose?.();
  };
  root.querySelector(".backdrop-dim").addEventListener("click", close);
  openLayers.add(close);
  layer().appendChild(root);
  tg?.BackButton?.show();
  tg?.BackButton?.onClick(close);
  return { el: panel, close };
}

/** Полноэкранный слой (открытие кейса, гонка). onClose — остановить анимации и циклы. */
export function fullscreen(className = "", { onClose } = {}) {
  const root = html(`<div class="fullscreen ${className}"></div>`);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    openLayers.delete(close);
    root.remove();
    onClose?.();
  };
  openLayers.add(close);
  layer().appendChild(root);
  return { el: root, close };
}

let backHandler = null;
export function setBack(handler) {
  backHandler = handler;
  syncBackButton();
}

function syncBackButton() {
  const button = tg?.BackButton;
  if (!button) return;
  button.offClick(runBack);
  if (backHandler && !layer().querySelector(".sheet")) {
    button.show();
    button.onClick(runBack);
  } else if (!layer().querySelector(".sheet")) {
    button.hide();
  }
}

function runBack() {
  backHandler?.();
}

export function confirmSheet(text, okLabel = "Да", { danger = false } = {}) {
  return new Promise((resolve) => {
    let answered = false;
    const { el, close } = sheet(`
      <p style="font-size:16px;font-weight:600;margin:6px 0 16px">${esc(text)}</p>
      <div class="row"><button class="btn grow" data-no>Отмена</button>
      <button class="btn grow ${danger ? "danger" : "primary"}" data-yes>${esc(okLabel)}</button></div>`,
    { onClose: () => !answered && resolve(false) });
    el.querySelector("[data-yes]").onclick = () => { answered = true; close(); resolve(true); };
    el.querySelector("[data-no]").onclick = () => { answered = true; close(); resolve(false); };
  });
}

export function itemArt(itemId) {
  const data = catalogItem(itemId);
  return icon(data?.slot || "case");
}

/** Карточка детали. owned — экземпляр из инвентаря (uid, wear, locked, sell). */
export function itemCard(owned, { selected = false, disabled = false, footer = "value" } = {}) {
  const data = catalogItem(owned.id) || owned;
  const wear = owned.wear || 0;
  const tag = owned.locked ? '<span class="tag lock">В СБОРКЕ</span>'
    : wear >= 100 ? '<span class="tag" style="color:var(--red)">СЛОМАНО</span>' : "";
  const foot = footer === "sell" ? `<span class="value">${fmt(owned.sell)}</span>`
    : footer === "price" ? `<span class="value">${fmt(owned.price)}</span>`
      : `<span class="value">${fmt(data.value)}</span>`;
  return `
    <button class="item r-${data.rarity} ${selected ? "selected" : ""} ${disabled ? "disabled" : ""}" data-uid="${owned.uid ?? ""}" data-id="${esc(data.id)}">
      ${tag}
      <div class="item-art">${icon(data.slot)}</div>
      <div class="rarity-text">${esc(rarityTitle(data.rarity))}</div>
      <div class="item-name">${esc(data.name)}</div>
      <div class="item-spec">${esc(data.spec || "")}</div>
      ${owned.uid ? `<div class="wear" title="Износ ${wear}%"><i style="width:${wear}%;background-position:${wear}% 0"></i></div>` : ""}
      <div class="item-foot"><span class="dim">Q${data.q}</span>${foot}</div>
    </button>`;
}

export function itemDetails(data) {
  const fits = data.cls ? data.cls.map(classTitle).join(", ") : "";
  const systems = data.systems ? data.systems.map(systemTitle).join(", ") : "";
  return `
    <div class="row" style="gap:14px;margin:6px 0 12px">
      <div class="item-art r-${data.rarity}" style="width:86px;height:86px;flex:none">${icon(data.slot)}</div>
      <div class="grow">
        <div class="rarity-text r-${data.rarity}">${esc(rarityTitle(data.rarity))} · Q${data.q}</div>
        <h2 style="margin:4px 0">${esc(data.name)}</h2>
        <div class="muted mono" style="font-size:12px">${esc(data.spec || "")}</div>
      </div>
    </div>
    ${data.desc ? `<p class="muted" style="margin:0 0 10px">${esc(data.desc)}</p>` : ""}
    <div class="meta" style="margin-bottom:12px">
      ${fits ? `<span>Класс: ${esc(fits)}</span>` : ""}
      ${data.system ? `<span>Видео: ${esc(systemTitle(data.system))}</span>` : ""}
      ${systems ? `<span>Принимает: ${esc(systems)}</span>` : ""}
      ${data.lat ? `<span>Задержка ${data.lat} мс</span>` : ""}
      <span class="gold">Цена ${fmt(data.value)}</span>
    </div>`;
}

export const nav = (path) => {
  location.hash = path;
};

export function emptyState(emoji, text) {
  return `<div class="empty"><div class="big">${emoji}</div>${esc(text)}</div>`;
}
