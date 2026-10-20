// Админ-панель: обзор и события, игроки, промокоды, рассылка и журнал действий.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { state } from "../state.js";
import { emptyState, errorToast, esc, fmt, haptic, toast } from "../ui.js";
import { bindRewardFilter, readReward, rewardFields } from "./admin_forms.js";
import { openUserCard } from "./admin_user.js";

const TABS = [["overview", "Обзор"], ["users", "Игроки"], ["promos", "Промо"], ["log", "Журнал"]];
const view = { tab: "overview", query: "" };
const ACTIONS = {
  coins: "монеты", level: "уровень", luck: "удача", give: "подарок", ban: "бан", unban: "разбан", take_item: "изъятие",
  repair_all: "ремонт", event: "событие", broadcast: "рассылка", promo_create: "промокод", promo_toggle: "промо вкл/выкл",
  promo_delete: "промо удалён",
};

function when(iso) {
  return iso ? new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
}

async function overview() {
  const stats = await api.get("/api/admin/stats");
  const broadcast = stats.broadcast;
  return `
    <div class="kv-grid">
      <div class="kv"><b>${fmt(stats.users)}</b><span>игроков</span></div>
      <div class="kv"><b>${fmt(stats.active_24h)}</b><span>активны за сутки</span></div>
      <div class="kv"><b>${fmt(stats.new_24h)}</b><span>новых за сутки</span></div>
      <div class="kv"><b>${fmt(stats.races_24h)}</b><span>гонок за сутки</span></div>
      <div class="kv"><b>${fmt(stats.cases_opened)}</b><span>кейсов всего</span></div>
      <div class="kv"><b>${fmt(stats.rare_drops_24h)}</b><span>редких дропов за сутки</span></div>
      <div class="kv"><b>${fmt(stats.coins)}</b><span>монет у игроков</span></div>
      <div class="kv"><b>${fmt(stats.items)}</b><span>деталей в игре</span></div>
    </div>
    <div class="section-title">Глобальные события</div>
    <section class="panel stack">
      <div class="field"><label>Удача для всех: <span id="ev-luck-v">×${stats.events.luck_event}</span></label>
        <input type="range" min="0.5" max="5" step="0.25" value="${stats.events.luck_event}" id="ev-luck" style="accent-color:var(--lime)"></div>
      <div class="field"><label>Награды за гонки: <span id="ev-race-v">×${stats.events.race_mult}</span></label>
        <input type="range" min="0.5" max="5" step="0.25" value="${stats.events.race_mult}" id="ev-race" style="accent-color:var(--amber)"></div>
      <button class="btn primary" data-events>Применить события</button>
    </section>
    <div class="section-title">Рассылка всем игрокам</div>
    <section class="panel stack">
      <textarea class="input" id="bc-text" maxlength="3500" placeholder="Новый сезон, промокод FPV-XXXX… (HTML: <b>, <i>, <a>)"></textarea>
      <button class="btn hot" data-broadcast ${broadcast.running ? "disabled" : ""}>${icon("bolt")} Отправить</button>
      ${broadcast.total ? `<p class="muted mono" style="font-size:12px;margin:0">${broadcast.running ? "Идёт" : "Последняя"}: ${broadcast.sent}/${broadcast.total}, ошибок ${broadcast.failed}</p>` : ""}
    </section>`;
}

async function users() {
  const list = await api.get(`/api/admin/users?q=${encodeURIComponent(view.query)}`);
  return `
    <div class="row" style="margin-bottom:10px"><input class="input grow" id="user-q" placeholder="ID, @username или имя" value="${esc(view.query)}">
      <button class="btn primary" data-search>Найти</button></div>
    ${list.length ? list.map((user) => `
      <button class="user-row" data-user="${user.id}">
        <div><b>${esc(user.name)}</b> ${user.banned ? '<span class="badge-red">БАН</span>' : ""}<br>
          <small>id ${user.id}${user.username ? ` · @${esc(user.username)}` : ""}</small></div>
        <div style="text-align:right"><b class="mono" style="color:var(--amber)">${fmt(user.coins)}</b><br><small>ур. ${user.level} · ×${user.luck}</small></div>
      </button>`).join("") : emptyState("🔍", "Никого не нашли")}`;
}

async function promos() {
  const list = await api.get("/api/admin/promos");
  return `
    <section class="panel stack">
      <b>Новый промокод</b>
      <div class="form-grid">
        <div class="field"><label>Код (пусто — случайный)</label><input class="input mono" id="p-code" placeholder="FPV-START" style="text-transform:uppercase"></div>
        <div class="field"><label>Лимит (0 — без)</label><input class="input" type="number" min="0" id="p-uses" value="100"></div>
        <div class="field"><label>Срок, дней (пусто — бессрочно)</label><input class="input" type="number" min="1" max="365" id="p-days"></div>
        <div class="field"><label>Заметка</label><input class="input" id="p-note" maxlength="120" placeholder="для стрима"></div>
      </div>
      ${rewardFields("p")}
      <button class="btn hot" data-create>${icon("ticket")} Создать</button>
    </section>
    <div class="section-title">Промокоды (${list.length})</div>
    ${list.length ? list.map((promo) => `
      <div class="panel" style="margin-bottom:8px">
        <div class="row between"><b class="mono" style="color:${promo.active ? "var(--cyan)" : "var(--dim)"}">${esc(promo.code)}</b>
          <span class="mono muted" style="font-size:12px">${promo.uses}/${promo.max_uses || "∞"}</span></div>
        <div style="font-size:13px;margin:4px 0">${esc(promo.text)}</div>
        <div class="muted" style="font-size:11.5px">${promo.note ? `${esc(promo.note)} · ` : ""}до ${promo.expires_at ? when(promo.expires_at) : "бессрочно"}</div>
        <div class="row" style="margin-top:8px">
          <button class="btn small grow" data-toggle="${esc(promo.code)}" data-active="${promo.active ? 0 : 1}">${promo.active ? "Выключить" : "Включить"}</button>
          <button class="btn small danger" data-delete="${esc(promo.code)}">Удалить</button>
        </div>
      </div>`).join("") : emptyState("🎟", "Промокодов пока нет")}`;
}

async function log() {
  const entries = await api.get("/api/admin/log");
  return entries.length ? `<section class="panel">${entries.map((entry) => `
    <div class="log-row"><code>${when(entry.created_at)}</code> · <b>${esc(ACTIONS[entry.action] || entry.action)}</b>
      ${entry.target_id ? ` → id ${entry.target_id}` : ""}<div class="muted mono" style="font-size:11px;word-break:break-all">${esc(JSON.stringify(entry.details))}</div></div>`).join("")}</section>`
    : emptyState("📜", "Журнал пуст");
}

const RENDERERS = { overview, users, promos, log };

function bind(root, rerender) {
  const run = async (request, message) => {
    try {
      await request();
      haptic("success");
      toast(message, "good");
      rerender();
    } catch (error) {
      errorToast(error);
    }
  };
  const slider = (id, label) => root.querySelector(id)?.addEventListener("input", (event) => {
    root.querySelector(label).textContent = `×${event.target.value}`;
  });
  slider("#ev-luck", "#ev-luck-v");
  slider("#ev-race", "#ev-race-v");
  root.querySelector("[data-events]")?.addEventListener("click", () => run(async () => {
    await api.post("/api/admin/events", { key: "luck_event", value: Number(root.querySelector("#ev-luck").value) });
    await api.post("/api/admin/events", { key: "race_mult", value: Number(root.querySelector("#ev-race").value) });
  }, "События обновлены"));
  root.querySelector("[data-broadcast]")?.addEventListener("click", () => run(
    () => api.post("/api/admin/broadcast", { text: root.querySelector("#bc-text").value }), "Рассылка запущена"));
  const search = () => { view.query = root.querySelector("#user-q").value.trim(); rerender(); };
  root.querySelector("[data-search]")?.addEventListener("click", search);
  root.querySelector("#user-q")?.addEventListener("keydown", (event) => event.key === "Enter" && search());
  root.querySelectorAll("[data-user]").forEach((row) => row.addEventListener("click", () => openUserCard(Number(row.dataset.user), rerender)));
  if (root.querySelector("#p-item")) bindRewardFilter(root, "p");
  root.querySelector("[data-create]")?.addEventListener("click", () => run(() => api.post("/api/admin/promos", {
    code: root.querySelector("#p-code").value.trim() || null,
    max_uses: Number(root.querySelector("#p-uses").value) || 0,
    days: Number(root.querySelector("#p-days").value) || null,
    note: root.querySelector("#p-note").value,
    reward: readReward(root, "p"),
  }), "Промокод создан"));
  root.querySelectorAll("[data-toggle]").forEach((button) => button.addEventListener("click", () => run(
    () => api.patch(`/api/admin/promos/${encodeURIComponent(button.dataset.toggle)}`, { active: button.dataset.active === "1" }), "Готово")));
  root.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", () => run(
    () => api.del(`/api/admin/promos/${encodeURIComponent(button.dataset.delete)}`), "Удалён")));
}

export async function render(root) {
  if (!state.me?.is_admin) {
    root.innerHTML = emptyState("⛔", "Раздел только для администратора");
    return;
  }
  const body = await RENDERERS[view.tab]();
  root.innerHTML = `
    <div class="page-title"><h1><small>// ADMIN</small>Админка</h1>${icon("shield", 'style="width:28px;height:28px;color:var(--pink)"')}</div>
    <div class="segmented" style="margin-bottom:14px">${TABS.map(([id, title]) =>
      `<button data-tab="${id}" class="${view.tab === id ? "active" : ""}">${title}</button>`).join("")}</div>
    ${body}`;
  const rerender = () => render(root);
  root.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
    view.tab = button.dataset.tab;
    rerender();
  }));
  bind(root, rerender);
}
