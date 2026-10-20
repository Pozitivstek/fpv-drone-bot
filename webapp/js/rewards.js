// Показ наград: тост с перечнем и праздничная шторка при новом уровне или ранге.
import { state } from "./state.js";
import { esc, fmt, haptic, sheet, toast } from "./ui.js";

export const caseName = (caseId) => state.catalog?.cases?.[caseId]?.name || caseId;

export function keysText(keys = {}) {
  return Object.entries(keys).map(([caseId, qty]) => `ключ «${caseName(caseId)}» ×${qty}`);
}

export function rewardText(summary) {
  if (!summary) return "";
  const parts = [];
  if (summary.coins) parts.push(`+${fmt(summary.coins)} монет`);
  if (summary.xp) parts.push(`+${summary.xp} опыта`);
  parts.push(...keysText(summary.keys));
  if (summary.kits?.length) parts.push(...summary.kits.map((kit) => `комплект «${kit}»`));
  else if (summary.items?.length) parts.push(`деталей: ${summary.items.length}`);
  return parts.join(" · ");
}

export function announce(summary, title = "Награда получена") {
  const text = rewardText(summary);
  if (text) toast(`${title}: ${text}`, "good");
  haptic("success");
  if (summary?.level_up) levelUp(summary.level_up);
}

export function levelUp(info) {
  const keys = keysText(info.keys).map(esc);
  haptic("heavy");
  sheet(`
    <div class="center" style="padding:10px 0 4px">
      <div style="font-size:64px;filter:drop-shadow(0 0 20px var(--pink))">${info.rank ? esc(info.rank.icon) : "⚡"}</div>
      <div class="mono" style="color:var(--cyan);letter-spacing:.2em;font-size:12px">LEVEL UP</div>
      <h2 style="font-size:28px;margin:6px 0">Уровень ${info.to}</h2>
      ${info.rank ? `<p style="margin:0 0 8px">Новый ранг: <b style="color:var(--pink)">${esc(info.rank.title)}</b></p>` : ""}
      <p class="muted">Награда: +${fmt(info.coins)} монет${keys.length ? ", " + keys.join(", ") : ""}</p>
    </div>`);
}
