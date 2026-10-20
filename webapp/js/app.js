// Запуск мини-приложения: Telegram WebApp, роутер по hash, шапка с балансом и нижняя навигация.
import { hydrateIcons, icon } from "./icons.js";
import { loadCatalog, onMe, refreshMe, state } from "./state.js";
import { closeLayers, errorToast, esc, fmt, setBack, tg } from "./ui.js";
import * as admin from "./views/admin.js";
import * as cases from "./views/cases.js";
import * as hangar from "./views/hangar.js";
import * as home from "./views/home.js";
import * as inventory from "./views/inventory.js";
import * as race from "./views/race.js";
import * as top from "./views/top.js";
import * as workshop from "./views/workshop.js";

const ROUTES = {
  "/home": home, "/cases": cases, "/hangar": hangar, "/race": race, "/workshop": workshop,
  "/inventory": inventory, "/top": top, "/admin": admin,
};
const TABS = new Set(["/home", "/cases", "/hangar", "/race", "/workshop"]);
const app = document.getElementById("app");
const topbar = document.getElementById("topbar");
const tabbar = document.getElementById("tabbar");
let cleanup = null;
let renderToken = 0;

function setupTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor("#04060c");
    tg.setBackgroundColor("#04060c");
    tg.disableVerticalSwipes?.();
  } catch { /* старые клиенты Telegram */ }
}

function renderTopbar(me) {
  if (!me) return;
  const rank = me.progress.rank;
  const keys = Object.values(me.keys).reduce((sum, qty) => sum + qty, 0);
  topbar.innerHTML = `
    <div class="topbar-inner">
      <button class="pilot" data-go="/home">
        <div class="pilot-rank">${rank.icon}</div>
        <div class="grow">
          <div class="pilot-name ellipsis">${esc(me.name)}</div>
          <div class="pilot-level">LVL ${me.progress.level} · ${esc(rank.title)}</div>
          <div class="xpbar"><i style="width:${me.progress.pct}%"></i></div>
        </div>
      </button>
      <div class="wallet">
        ${keys ? `<button class="pill keys" data-go="/cases">${icon("key")}${keys}</button>` : ""}
        <button class="pill coins" id="coins-pill" data-go="/inventory">${icon("coin")}${fmt(me.coins)}</button>
      </div>
    </div>`;
  topbar.classList.remove("hidden");
}

onMe((me, previous) => {
  renderTopbar(me);
  if (previous && previous.coins !== me.coins) {
    document.getElementById("coins-pill")?.classList.add("bump");
  }
  const tasksReady = me && state.tasksReady;
  tabbar.querySelector('[data-tab="/home"]').classList.toggle("has-badge", Boolean(tasksReady));
});

export function go(path) {
  if (location.hash !== `#${path}`) location.hash = path;
  else render();
}

async function render() {
  const [path, query = ""] = (location.hash.slice(1) || "/home").split("?");
  const view = ROUTES[path] || home;
  const token = ++renderToken;
  cleanup?.();
  cleanup = null;
  closeLayers();
  tabbar.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === path));
  setBack(TABS.has(path) ? null : () => history.length > 1 ? history.back() : go("/home"));
  app.scrollTo?.(0, 0);
  window.scrollTo(0, 0);
  try {
    const result = await view.render(app, new URLSearchParams(query));
    if (token === renderToken) cleanup = typeof result === "function" ? result : null;
  } catch (error) {
    errorToast(error);
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-go]");
  if (target) {
    event.preventDefault();
    go(target.dataset.go);
  }
});
tabbar.addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (tab) go(tab.dataset.tab);
});
window.addEventListener("hashchange", render);

function bannedScreen() {
  app.innerHTML = `<div class="empty" style="padding-top:80px"><div class="big">⛔</div>
    <h2>Аккаунт заблокирован</h2><p class="muted">Если это ошибка — напишите администратору.</p></div>`;
}

async function boot() {
  setupTelegram();
  hydrateIcons(tabbar);
  try {
    await Promise.all([loadCatalog(), refreshMe()]);
  } catch (error) {
    app.innerHTML = `<div class="empty" style="padding-top:80px"><div class="big">📡</div>
      <h2>Нет сигнала</h2><p class="muted">${esc(error.message)}</p>
      <button class="btn primary" onclick="location.reload()">Переподключиться</button></div>`;
    return;
  }
  if (state.me.banned) return bannedScreen();
  tabbar.classList.remove("hidden");
  const startParam = tg?.initDataUnsafe?.start_param || "";
  if (!location.hash && startParam === "admin" && state.me.is_admin) location.hash = "/admin";
  await render();
}

boot();
