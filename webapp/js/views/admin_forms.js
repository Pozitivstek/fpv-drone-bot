// Конструктор награды для админки: монеты, опыт, деталь, ключи от кейса, готовый комплект («верт»).
import { item, rarityTitle, slotTitle, state } from "../state.js";
import { esc } from "../ui.js";

export function rewardFields(prefix) {
  const items = [...state.catalog.items].sort((a, b) => a.slot.localeCompare(b.slot) || b.value - a.value);
  const cases = Object.entries(state.catalog.cases);
  return `
    <div class="form-grid">
      <div class="field"><label>Монеты</label><input class="input" type="number" min="0" id="${prefix}-coins" placeholder="0"></div>
      <div class="field"><label>Опыт</label><input class="input" type="number" min="0" id="${prefix}-xp" placeholder="0"></div>
      <div class="field full"><label>Деталь</label>
        <input class="input" id="${prefix}-item-filter" placeholder="Поиск: DJI, Tango, RacerX…" style="margin-bottom:6px">
        <select class="input" id="${prefix}-item"><option value="">— без детали —</option>${items.map((data) =>
          `<option value="${esc(data.id)}">[${esc(rarityTitle(data.rarity))}] ${esc(slotTitle(data.slot))}: ${esc(data.name)}</option>`).join("")}</select></div>
      <div class="field"><label>Ключ от кейса</label><select class="input" id="${prefix}-case"><option value="">—</option>${cases.map(([id, data]) =>
        `<option value="${esc(id)}">${esc(data.name)}</option>`).join("")}</select></div>
      <div class="field"><label>Сколько ключей</label><input class="input" type="number" min="1" max="100" value="1" id="${prefix}-case-qty"></div>
      <div class="field full"><label>Готовый дрон (комплект)</label><select class="input" id="${prefix}-kit"><option value="">—</option>${state.catalog.kits.map((kit) =>
        `<option value="${esc(kit.id)}">${esc(kit.name)}</option>`).join("")}</select></div>
    </div>`;
}

export function bindRewardFilter(root, prefix) {
  const filter = root.querySelector(`#${prefix}-item-filter`);
  const select = root.querySelector(`#${prefix}-item`);
  filter.addEventListener("input", () => {
    const query = filter.value.trim().toLowerCase();
    [...select.options].forEach((option) => {
      option.hidden = Boolean(option.value) && !option.textContent.toLowerCase().includes(query);
    });
  });
}

export function readReward(root, prefix) {
  const number = (id) => Math.max(0, Number(root.querySelector(`#${prefix}-${id}`).value) || 0);
  const reward = { coins: number("coins"), xp: number("xp"), items: [], keys: {}, kits: [] };
  const itemId = root.querySelector(`#${prefix}-item`).value;
  const caseId = root.querySelector(`#${prefix}-case`).value;
  const kitId = root.querySelector(`#${prefix}-kit`).value;
  if (itemId && item(itemId)) reward.items.push(itemId);
  if (caseId) reward.keys[caseId] = Math.max(1, number("case-qty"));
  if (kitId) reward.kits.push(kitId);
  return reward;
}
