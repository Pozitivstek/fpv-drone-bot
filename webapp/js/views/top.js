// Рейтинг пилотов: по уровню, золотым медалям и стоимости коллекции.
import { api } from "../api.js";
import { state } from "../state.js";
import { emptyState, esc, fmt } from "../ui.js";

const KINDS = [
  { id: "level", title: "Уровень", value: (row) => `ур. ${row.level}` },
  { id: "golds", title: "Золото", value: (row) => `🥇 ${fmt(row.value)}` },
  { id: "collection", title: "Коллекция", value: (row) => `${fmt(row.value)} 💰` },
];
let current = "level";

export async function render(root) {
  const kind = KINDS.find((entry) => entry.id === current);
  const rows = await api.get(`/api/leaderboard?kind=${kind.id}`);
  const medals = { 1: "🥇", 2: "🥈", 3: "🥉" };
  root.innerHTML = `
    <div class="page-title"><h1><small>// LEADERBOARD</small>Рейтинг</h1></div>
    <div class="segmented" style="margin-bottom:12px">${KINDS.map((entry) =>
      `<button data-kind="${entry.id}" class="${entry.id === current ? "active" : ""}">${entry.title}</button>`).join("")}</div>
    <section class="panel">${rows.length ? rows.map((row) => `
      <div class="lb-row ${row.user_id === state.me.id ? "me" : ""}">
        <span class="pl">${medals[row.place] || row.place}</span>
        <div class="ellipsis">${esc(row.rank)} ${esc(row.name)}</div>
        <span class="tm">${kind.value(row)}</span>
      </div>`).join("") : emptyState("🏆", "Рейтинг пока пуст")}</section>`;
  root.querySelectorAll("[data-kind]").forEach((button) => button.addEventListener("click", () => {
    current = button.dataset.kind;
    render(root);
  }));
}
