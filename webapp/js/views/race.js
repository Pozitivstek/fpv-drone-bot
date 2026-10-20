// Гонки: трассы с рекордами, таблица лидеров, настройки стиков, запуск мини-игры и итоги заезда.
import { api } from "../api.js";
import { loadRates, runGame, saveRates } from "../game/engine.js";
import { icon } from "../icons.js";
import { levelUp } from "../rewards.js";
import { classTitle, patchMe, refreshMe, slotTitle, state } from "../state.js";
import { errorToast, esc, fmt, fullscreen, haptic, msToTime, sheet } from "../ui.js";

const MEDALS = { gold: ["🥇", "Золото"], silver: ["🥈", "Серебро"], bronze: ["🥉", "Бронза"] };

function trackCard(def, info) {
  const locked = info?.locked;
  return `
    <button class="track-card theme-${def.theme} ${locked ? "locked" : ""}" data-track="${def.id}">
      <div class="track-art"><div class="gate-ic">${locked ? "🔒" : icon("gate")}</div></div>
      <div class="track-info">
        <h3>${esc(def.name)}</h3>
        <p>${esc(def.desc)}</p>
        <div class="meta">
          <span>${def.gates} ворот</span><span>${Math.round(def.length)} м</span>
          <span class="gold">+${fmt(def.reward)}</span>
          ${def.fee ? `<span>взнос ${fmt(def.fee)}</span>` : '<span class="cyan">бесплатно</span>'}
          ${locked ? `<span>с ${def.min_level} ур.</span>` : ""}
          ${info?.my_best ? `<span class="cyan">мой ${msToTime(info.my_best)}</span>` : ""}
          ${info?.record ? `<span>🏆 ${msToTime(info.record.time_ms)}</span>` : ""}
        </div>
      </div>
    </button>`;
}

function buildSummary(hangar) {
  const build = hangar.builds.find((candidate) => candidate.active);
  if (!build) return `<section class="panel"><b>Нет активной сборки</b><p class="muted">Соберите дрон в ангаре.</p></section>`;
  return `
    <section class="panel osd row" style="gap:12px">
      <div class="grow">
        <div class="cls-label">${esc(classTitle(build.cls))}</div>
        <div style="font:400 17px var(--display)">${esc(build.name)}</div>
        <div class="${build.ready ? "status-ok" : "status-bad"} mono" style="font-size:11px;margin-top:4px">
          ${build.ready ? `● ГОТОВ · ${build.stats.speed_kmh} км/ч · ${build.stats.flight_time} с` : `● ${esc(build.issues[0] || "не готов")}`}</div>
      </div>
      <div class="pwr"><b>${build.rating}</b><span>PWR</span></div>
      <button class="icon-btn" data-rates aria-label="Настройки стиков">${icon("sliders")}</button>
    </section>`;
}

function ratesSheet() {
  const rates = loadRates();
  const { el } = sheet(`
    <h2>Рейты и экспо</h2>
    <p class="muted" style="margin-top:0">Как в Betaflight: чувствительность стика и мягкость около центра.</p>
    <div class="rates">
      <div class="field"><label>Чувствительность <span id="rate-v">${rates.rate.toFixed(2)}</span></label>
        <input type="range" min="0.6" max="1.6" step="0.05" value="${rates.rate}" id="rate"></div>
      <div class="field"><label>Экспо <span id="expo-v">${rates.expo.toFixed(2)}</span></label>
        <input type="range" min="0" max="0.8" step="0.05" value="${rates.expo}" id="expo"></div>
      <label class="row"><input type="checkbox" id="invert" ${rates.invert ? "checked" : ""}> Инвертировать вверх/вниз</label>
    </div>`);
  const update = () => {
    const next = { rate: Number(el.querySelector("#rate").value), expo: Number(el.querySelector("#expo").value), invert: el.querySelector("#invert").checked };
    el.querySelector("#rate-v").textContent = next.rate.toFixed(2);
    el.querySelector("#expo-v").textContent = next.expo.toFixed(2);
    saveRates(next);
  };
  el.querySelectorAll("input").forEach((input) => input.addEventListener("input", update));
}

async function trackSheet(def, info, rerender) {
  if (info?.locked) {
    sheet(`<h2>${esc(def.name)}</h2><p class="muted">Трасса откроется на ${def.min_level} уровне. Летайте и открывайте кейсы, чтобы расти.</p>`);
    return;
  }
  let board = [];
  try {
    board = await api.get(`/api/tracks/${def.id}/leaderboard`);
  } catch (error) {
    errorToast(error);
  }
  const rows = board.length ? board.slice(0, 10).map((row) => `
    <div class="lb-row ${row.user_id === state.me.id ? "me" : ""}"><span class="pl">${row.place}</span>
      <div class="ellipsis">${esc(row.name)} <span class="muted" style="font-size:11px">· ${esc(classTitle(row.cls))}</span></div>
      <span class="tm">${msToTime(row.time_ms)}</span></div>`).join("") : '<p class="muted center">Рекордов пока нет — будь первым!</p>';
  const { el, close } = sheet(`
    <div class="track-art theme-${def.theme}" style="height:90px;margin-bottom:12px"><div class="gate-ic">${icon("gate")}</div></div>
    <h2>${esc(def.name)}</h2>
    <p class="muted" style="margin-top:0">${esc(def.desc)}</p>
    <div class="meta" style="margin-bottom:12px">
      <span>${def.gates} ворот</span><span>${Math.round(def.length)} м</span><span>+${def.xp} XP</span>
      <span class="gold">до +${fmt(def.reward)}</span>${info?.my_best ? `<span class="cyan">мой рекорд ${msToTime(info.my_best)}</span>` : ""}
    </div>
    <div class="section-title" style="margin-top:6px">Лидеры трассы</div>
    ${rows}
    <div class="row" style="margin-top:16px">
      <button class="btn grow" data-train>Тренировка</button>
      <button class="btn hot grow" data-race>${icon("play")} Гонка${def.fee ? ` · ${fmt(def.fee)}` : ""}</button>
    </div>
    <p class="muted center" style="font-size:11.5px">Тренировка бесплатна: без наград и без износа. Пропущенные ворота — +3 с.</p>`);
  el.querySelector("[data-train]").onclick = () => { close(); startRace(def, true, rerender); };
  el.querySelector("[data-race]").onclick = () => { close(); startRace(def, false, rerender); };
}

function resultMarkup(result, race) {
  const [emoji, title] = result.finished ? MEDALS[result.medal] || ["🏁", "Финиш"] : ["💥", "Сход"];
  const wear = Object.entries(result.wear).map(([slot, value]) => `${slotTitle(slot)} +${value}%`).join(" · ");
  return `
    <div class="medal">${emoji}</div>
    <h2>${title}</h2>
    ${result.new_record ? '<div class="event-banner">🏆 Новый личный рекорд!</div>' : ""}
    <div class="result-grid">
      <div class="mini-stat"><b>${msToTime(result.total_ms)}</b><span>итог${result.penalty_ms ? ` (+${result.penalty_ms / 1000} с штраф)` : ""}</span></div>
      <div class="mini-stat"><b>${result.place ? `#${result.place}` : "—"}</b><span>место на трассе</span></div>
      <div class="mini-stat"><b style="color:var(--amber)">+${fmt(result.coins)}</b><span>монет</span></div>
      <div class="mini-stat"><b style="color:var(--cyan)">+${result.xp}</b><span>опыта</span></div>
      <div class="mini-stat"><b>${result.gates}/${result.gates + result.missed}</b><span>ворот</span></div>
      <div class="mini-stat"><b>${result.crashes}</b><span>крашей</span></div>
    </div>
    ${race.training ? '<p class="muted">Тренировка — без наград и износа.</p>' : ""}
    ${result.capped ? '<p class="muted center">Дневной лимит наград за гонки исчерпан — рекорды считаются, монеты завтра.</p>' : ""}
    ${wear ? `<p class="muted center" style="font-size:12px;max-width:340px">Износ: ${esc(wear)}</p>` : ""}
    ${result.broken.length ? `<p class="badge-red center">Сломано: ${esc(result.broken.join(", "))} — почините в ангаре</p>` : ""}
    <div class="row" style="width:min(380px,100%)">
      <button class="btn grow" data-exit>К трассам</button>
      <button class="btn hot grow" data-again>Ещё раз</button>
    </div>`;
}

async function startRace(def, training, rerender) {
  let race;
  try {
    race = await api.post("/api/race/start", { track_id: def.id, training });
  } catch (error) {
    errorToast(error);
    return;
  }
  if (race.fee) patchMe({ coins: state.me.coins - race.fee });
  let stop = null;
  const layer = fullscreen("game", { onClose: () => stop?.() });
  layer.el.innerHTML = `
    <canvas></canvas>
    <button class="icon-btn hud-exit" data-quit aria-label="Выйти">${icon("close")}</button>
    <button class="boost-btn">BOOST</button>
    <div class="stick-hint">Веди пальцем по экрану — это стик.<br>Ворота — по центру, BOOST — быстрее, но жрёт батарею.</div>`;
  const exit = () => {
    layer.close();
    rerender();
  };
  const onEnd = async (claim) => {
    stop?.();
    const overlay = document.createElement("div");
    overlay.className = "result";
    overlay.innerHTML = '<div class="splash-line mono">ОТПРАВКА ТЕЛЕМЕТРИИ<span class="dots"></span></div>';
    layer.el.appendChild(overlay);
    try {
      const result = await api.post(`/api/race/${race.race_id}/finish`, claim);
      haptic(result.medal ? "success" : result.finished ? "light" : "error");
      overlay.innerHTML = resultMarkup(result, race);
      patchMe({ coins: result.balance });
      if (result.level_up) levelUp(result.level_up);
    } catch (error) {
      overlay.innerHTML = `<div class="medal">⚠️</div><h2>Не засчитано</h2><p class="muted center">${esc(error.message)}</p>
        <div class="row"><button class="btn grow" data-exit>К трассам</button><button class="btn hot grow" data-again>Ещё раз</button></div>`;
    }
    overlay.querySelector("[data-exit]").onclick = exit;
    overlay.querySelector("[data-again]").onclick = () => {
      layer.close();
      startRace(def, training, rerender);
    };
    refreshMe().catch(() => {});
  };
  layer.el.querySelector("[data-quit]").onclick = exit;
  stop = runGame({
    canvas: layer.el.querySelector("canvas"), boostButton: layer.el.querySelector(".boost-btn"),
    hint: layer.el.querySelector(".stick-hint"), race, trackDef: def, haptic, onEnd,
  });
}

export async function render(root) {
  const [tracks, hangar] = await Promise.all([api.get("/api/tracks"), api.get("/api/hangar")]);
  const info = Object.fromEntries(tracks.map((entry) => [entry.id, entry]));
  const rerender = () => render(root);
  root.innerHTML = `
    <div class="page-title"><h1><small>// RACE CONTROL</small>Гонки</h1></div>
    ${buildSummary(hangar)}
    <div class="section-title">Трассы</div>
    ${state.catalog.tracks.map((def) => trackCard(def, info[def.id])).join("")}`;
  root.querySelector("[data-rates]")?.addEventListener("click", ratesSheet);
  root.querySelectorAll("[data-track]").forEach((card) => card.addEventListener("click", () => {
    const def = state.tracks.get(card.dataset.track);
    trackSheet(def, info[def.id], rerender);
  }));
}
