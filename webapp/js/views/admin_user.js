// Карточка игрока в админке: баланс, уровень/ранг, удача, подарки, бан, ремонт, изъятие деталей.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { item, rarityTitle, state } from "../state.js";
import { confirmSheet, errorToast, esc, fmt, haptic, sheet, toast } from "../ui.js";
import { bindRewardFilter, readReward, rewardFields } from "./admin_forms.js";

function summary(card) {
  const stats = card.stats;
  return `
    <div class="row between" style="margin-bottom:10px">
      <div><h2 style="margin:0">${esc(card.name)}</h2>
        <div class="muted mono" style="font-size:12px">id ${card.id}${card.username ? ` · @${esc(card.username)}` : ""}</div></div>
      ${card.banned ? '<span class="badge-red">БАН</span>' : ""}
    </div>
    <div class="kv-grid" style="margin-bottom:12px">
      <div class="kv"><b>${fmt(card.coins)}</b><span>монет</span></div>
      <div class="kv"><b>${card.level}</b><span>уровень · ${esc(card.progress.rank.title)}</span></div>
      <div class="kv"><b>×${card.luck}</b><span>удача</span></div>
      <div class="kv"><b>${fmt(stats.collection)}</b><span>коллекция · ${stats.items} шт.</span></div>
      <div class="kv"><b>${stats.cases_opened}</b><span>кейсов</span></div>
      <div class="kv"><b>${stats.races} / 🥇${stats.golds}</b><span>гонок</span></div>
    </div>`;
}

function controls(card) {
  const ranks = state.catalog.ranks;
  return `
    <div class="section-title">Баланс и прогресс</div>
    <div class="form-grid">
      <div class="field"><label>Монеты ±</label><input class="input" type="number" id="u-coins" placeholder="+1000 или -500"></div>
      <div class="field"><label>&nbsp;</label><button class="btn" data-do="coins">Применить</button></div>
      <div class="field"><label>Уровень</label><input class="input" type="number" min="1" max="60" id="u-level" value="${card.level}"></div>
      <div class="field"><label>&nbsp;</label><button class="btn" data-do="level">Установить</button></div>
      <div class="field"><label>Ранг</label><select class="input" id="u-rank">${ranks.map((rank, index) =>
        `<option value="${index}" ${card.progress.rank.index === index ? "selected" : ""}>${rank.icon} ${esc(rank.title)} (ур. ${rank.level})</option>`).join("")}</select></div>
      <div class="field"><label>&nbsp;</label><button class="btn" data-do="rank">Повысить</button></div>
      <div class="field full"><label>Удача (шансы в кейсах и апгрейде): <span id="luck-v">×${card.luck}</span></label>
        <input type="range" min="0.25" max="10" step="0.25" value="${card.luck}" id="u-luck" style="accent-color:var(--lime)"></div>
      <div class="field full"><button class="btn" data-do="luck">Сохранить удачу</button></div>
    </div>
    <div class="section-title">Подарок</div>
    ${rewardFields("g")}
    <button class="btn hot block" style="margin-top:10px" data-do="give">${icon("gift")} Выдать</button>
    <div class="section-title">Прочее</div>
    <div class="action-grid">
      <button class="btn" data-do="repair">${icon("wrench")} Починить всё</button>
      <button class="btn ${card.banned ? "primary" : "danger"}" data-do="ban">${card.banned ? "Разбанить" : "Забанить"}</button>
    </div>`;
}

function inventoryList(card) {
  const owned = card.inventory.items;
  if (!owned.length) return '<p class="muted">Инвентарь пуст.</p>';
  return owned.map((entry) => {
    const data = item(entry.id) || entry;
    return `<div class="target-row r-${data.rarity}">${icon(data.slot)}
      <div><div style="font-weight:600;font-size:13px">${esc(data.name)}</div>
      <div class="item-spec">${esc(rarityTitle(data.rarity))} · износ ${entry.wear}%${entry.locked ? " · в сборке" : ""}</div></div>
      <button class="btn small danger" data-take="${entry.uid}">Забрать</button></div>`;
  }).join("");
}

export async function openUserCard(userId, onChanged) {
  let card;
  try {
    card = await api.get(`/api/admin/users/${userId}`);
  } catch (error) {
    errorToast(error);
    return;
  }
  const { el, close } = sheet(`${summary(card)}${controls(card)}
    <div class="section-title">Инвентарь (${card.inventory.items.length})</div><div class="targets" style="max-height:none">${inventoryList(card)}</div>`);
  bindRewardFilter(el, "g");
  el.querySelector("#u-luck").addEventListener("input", (event) => {
    el.querySelector("#luck-v").textContent = `×${event.target.value}`;
  });
  const reopen = () => {
    close();
    if (!location.hash.startsWith("#/admin")) return;  // админ уже ушёл в другой раздел
    onChanged?.();
    openUserCard(userId, onChanged);
  };
  const run = async (request, message) => {
    try {
      await request();
      haptic("success");
      toast(message, "good");
      reopen();
    } catch (error) {
      errorToast(error);
    }
  };
  const value = (id) => el.querySelector(id).value;
  const actions = {
    coins: () => run(() => api.post(`/api/admin/users/${userId}/coins`, { delta: Number(value("#u-coins")) }), "Баланс изменён"),
    level: () => run(() => api.post(`/api/admin/users/${userId}/level`, { level: Number(value("#u-level")) }), "Уровень установлен"),
    rank: () => run(() => api.post(`/api/admin/users/${userId}/rank`, { rank: Number(value("#u-rank")) }), "Ранг выдан"),
    luck: () => run(() => api.post(`/api/admin/users/${userId}/luck`, { luck: Number(value("#u-luck")) }), "Удача обновлена"),
    give: () => run(() => api.post(`/api/admin/users/${userId}/give`, readReward(el, "g")), "Подарок отправлен"),
    repair: () => run(() => api.post(`/api/admin/users/${userId}/repair`), "Детали починены"),
    ban: async () => {
      if (!card.banned && !(await confirmSheet(`Забанить ${card.name}?`, "Забанить", { danger: true }))) return;
      run(() => api.post(`/api/admin/users/${userId}/ban`, { banned: !card.banned }), card.banned ? "Разбанен" : "Забанен");
    },
  };
  el.querySelectorAll("[data-do]").forEach((button) => button.addEventListener("click", () => actions[button.dataset.do]()));
  el.querySelectorAll("[data-take]").forEach((button) => button.addEventListener("click", async () => {
    if (!(await confirmSheet("Забрать деталь у игрока?", "Забрать", { danger: true }))) return;
    run(() => api.del(`/api/admin/users/${userId}/items/${button.dataset.take}`), "Деталь изъята");
  }));
}
