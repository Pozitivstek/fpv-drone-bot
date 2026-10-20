// Общее состояние: каталог (статичный) и профиль игрока; подписчики перерисовывают шапку.
import { api } from "./api.js";

export const state = {
  me: null,
  catalog: null,
  items: new Map(),
  tracks: new Map(),
};

const listeners = new Set();

export function onMe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function loadCatalog() {
  const catalog = await api.get("/api/catalog");
  state.catalog = catalog;
  state.items = new Map(catalog.items.map((item) => [item.id, item]));
  state.tracks = new Map(catalog.tracks.map((track) => [track.id, track]));
  return catalog;
}

export async function refreshMe() {
  const previous = state.me;
  state.me = await api.get("/api/me");
  listeners.forEach((listener) => listener(state.me, previous));
  return state.me;
}

/** Быстрое обновление баланса без лишнего запроса (после покупки, открытия кейса). */
export function patchMe(changes) {
  if (!state.me) return;
  const previous = state.me;
  state.me = { ...state.me, ...changes };
  listeners.forEach((listener) => listener(state.me, previous));
}

export const item = (id) => state.items.get(id);
export const slotTitle = (slot) => state.catalog?.slots[slot] || slot;
export const classTitle = (cls) => state.catalog?.classes[cls] || cls || "—";
export const systemTitle = (system) => state.catalog?.systems[system] || system;
export const rarityTitle = (rarity) => state.catalog?.rarities.find((r) => r.id === rarity)?.title || rarity;
