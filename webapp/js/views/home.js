// База: профиль пилота, ежедневный бонус, задания, лента редких дропов и быстрые действия.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { announce, keysText } from "../rewards.js";
import { item, refreshMe, state } from "../state.js";
import { errorToast, esc, fmt, haptic, sheet, tg, toast } from "../ui.js";

const PERIOD = { daily: "ДЕНЬ", weekly: "НЕДЕЛЯ" };

function hero(me) {
  const rank = me.progress.rank;
  const stats = me.stats;
  const events = me.events;
  const eventBits = [];
  if (events.luck_event > 1) eventBits.push(`удача ×${events.luck_event}`);
  if (events.race_mult > 1) eventBits.push(`награды за гонки ×${events.race_mult}`);
  return `
    <section class="panel osd hero glow-cyan">
      <div class="hero-top">
        <div class="hero-rank"><span>${rank.icon}</span></div>
        <div class="grow">
          <div class="hero-name ellipsis">${esc(me.name)}</div>
          <div class="hero-title">${esc(rank.title)}${me.luck > 1 ? ` · <span style="color:var(--lime)">буст удачи ×${me.luck}</span>` : ""}</div>
        </div>
      </div>
      <div class="hero-level">
        <div class="row between"><span>LVL ${me.progress.level}</span><span>${fmt(me.progress.level_xp)} / ${fmt(me.progress.level_span)} XP</span></div>
        <div class="xpbar"><i style="width:${me.progress.pct}%"></i></div>
      </div>
      <div class="hero-stats">
        <div class="mini-stat"><b>${fmt(stats.cases_opened)}</b><span>кейсов</span></div>
        <div class="mini-stat"><b>${fmt(stats.races)}</b><span>гонок</span></div>
        <div class="mini-stat"><b>${fmt(stats.golds)}</b><span>золота</span></div>
        <div class="mini-stat"><b>${fmt(stats.collection / 1000)}k</b><span>коллекция</span></div>
      </div>
      ${eventBits.length ? `<div class="event-banner">${icon("fire")} Событие: ${eventBits.join(" · ")}</div>` : ""}
    </section>`;
}

function dailyCard(daily) {
  const days = daily.week.map((day) => {
    const status = day.day < daily.day ? "done" : day.day === daily.day && daily.claimable ? "today" : "";
    const label = Object.keys(day.keys).length ? "🗝" : fmt(day.coins);
    return `<div class="day ${status}">Д${day.day}<b>${label}</b></div>`;
  }).join("");
  const hours = Math.floor(daily.reset_in / 3600);
  const minutes = Math.floor((daily.reset_in % 3600) / 60);
  const reward = [`${fmt(daily.coins)} монет`, ...keysText(daily.keys)].join(" + ");
  return `
    <section class="panel">
      <div class="row between"><b>Ежедневный бонус</b><span class="muted mono" style="font-size:12px">серия: ${daily.streak} дн.</span></div>
      <div class="daily-days">${days}</div>
      ${daily.claimable
        ? `<button class="btn hot block" data-action="daily">${icon("gift")} Забрать: ${esc(reward)}</button>`
        : `<button class="btn block" disabled>Следующий через ${hours} ч ${minutes} мин</button>`}
    </section>`;
}

function taskRow(task) {
  const pct = Math.min(100, Math.round((task.progress / task.goal) * 100));
  const reward = [`+${fmt(task.coins)}`, ...keysText(task.keys).map(() => "🗝")].join(" ");
  const action = task.ready ? `<button class="btn small primary" data-task="${task.id}">Забрать</button>`
    : task.claimed ? '<span class="muted mono" style="font-size:12px">готово ✓</span>' : `<span>${reward}</span>`;
  return `
    <div class="task ${task.claimed ? "done" : ""}">
      <div class="task-title"><span class="task-kind">${PERIOD[task.period]}</span>${esc(task.title)}</div>
      <div class="task-reward">${action}</div>
      <div class="bar"><i style="width:${pct}%"></i></div>
    </div>`;
}

function feedMarkup(feed) {
  if (!feed.length) return '<div class="muted center" style="font-size:13px">Пока тихо — открой кейс и попади в ленту!</div>';
  const cards = feed.map((drop) => {
    const data = item(drop.item);
    return `<div class="feed-item r-${drop.rarity}">${icon(data?.slot || "case")}
      <div><div class="ellipsis" style="max-width:150px">${esc(drop.name)}</div><b>${esc(data?.name || drop.item)}</b></div></div>`;
  }).join("");
  return `<div class="feed"><div class="feed-track">${cards}${cards}</div></div>`;
}

function quickActions(me) {
  return `
    <div class="quick">
      <button class="quick-btn" data-go="/inventory">${icon("bag")}Инвентарь</button>
      <button class="quick-btn" data-go="/top">${icon("trophy")}Рейтинг</button>
      <button class="quick-btn" data-action="promo">${icon("ticket")}Промокод</button>
      <button class="quick-btn" data-action="invite">${icon("users")}Друзья</button>
      ${me.is_admin ? `<button class="quick-btn" data-go="/admin" style="grid-column:span 4;grid-auto-flow:column;justify-content:center;gap:8px">${icon("shield")}Админ-панель</button>` : ""}
    </div>`;
}

function promoSheet(rerender) {
  const { el, close } = sheet(`
    <h2>Промокод</h2>
    <p class="muted" style="margin-top:0">Коды раздаются в канале и на стримах.</p>
    <div class="row"><input class="input grow mono" id="promo-code" placeholder="FPV-XXXXXX" autocomplete="off" style="text-transform:uppercase">
    <button class="btn primary" id="promo-go">OK</button></div>`);
  const input = el.querySelector("#promo-code");
  input.focus();
  const submit = async () => {
    if (!input.value.trim()) return;
    try {
      const result = await api.post("/api/promo", { code: input.value });
      close();
      announce(result, `Промокод ${result.code}`);
      rerender();
    } catch (error) {
      errorToast(error);
    }
  };
  el.querySelector("#promo-go").onclick = submit;
  input.onkeydown = (event) => event.key === "Enter" && submit();
}

function inviteSheet(me) {
  const link = me.ref_link;
  const text = "Залетай в FPV-Drons: собираем дроны и гоняем через ворота! 🚁";
  const { el } = sheet(`
    <h2>Позови друзей</h2>
    <p class="muted" style="margin-top:0">Другу — <b style="color:var(--amber)">+${me.ref_bonus.friend}</b> монет на старте, тебе —
    ${me.ref_bonus.stages.map((stage) => `<b style="color:var(--amber)">+${stage.coins}</b> на ${stage.level} уровне друга`).join(" и ")}.</p>
    <div class="panel mono" style="font-size:12px;word-break:break-all;margin-bottom:12px">${esc(link || "ссылка появится после запуска бота")}</div>
    <div class="row"><button class="btn grow" id="copy">Копировать</button><button class="btn hot grow" id="share">Отправить</button></div>
    <p class="muted center" style="font-size:12px">Приглашено: ${me.stats.referrals}</p>`);
  el.querySelector("#copy").onclick = async () => {
    try {
      await navigator.clipboard.writeText(link);
      toast("Ссылка скопирована", "good");
    } catch {
      toast("Не удалось скопировать — выделите вручную", "error");
    }
  };
  el.querySelector("#share").onclick = () => {
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(url);
    else window.open(url, "_blank");
  };
}

export async function render(root) {
  const [me, tasks, feed] = await Promise.all([refreshMe(), api.get("/api/tasks"), api.get("/api/feed")]);
  state.tasksReady = tasks.some((task) => task.ready);
  root.innerHTML = `
    <div class="page-title"><h1><small>// PILOT HQ</small>База</h1></div>
    <div class="stack">
      ${hero(me)}
      ${dailyCard(me.daily)}
      ${quickActions(me)}
    </div>
    <div class="section-title">Задания <span>${tasks.filter((t) => t.ready).length ? "🔔" : ""}</span></div>
    <section class="panel">${tasks.map(taskRow).join("")}</section>
    <div class="section-title">Лента дропов</div>
    ${feedMarkup(feed)}`;

  const rerender = () => render(root);
  root.querySelector('[data-action="daily"]')?.addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    try {
      announce(await api.post("/api/daily"), "Ежедневный бонус");
      rerender();
    } catch (error) {
      errorToast(error);
    }
  });
  root.querySelectorAll("[data-task]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      announce(await api.post(`/api/tasks/${button.dataset.task}/claim`), "Задание выполнено");
      haptic("success");
      rerender();
    } catch (error) {
      errorToast(error);
    }
  }));
  root.querySelector('[data-action="promo"]').onclick = () => promoSheet(rerender);
  root.querySelector('[data-action="invite"]').onclick = () => inviteSheet(me);
}
