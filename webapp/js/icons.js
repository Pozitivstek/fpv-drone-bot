// Линейные SVG-иконки (цвет — currentColor). Детали рисуются своими силуэтами, без чужих фото.
const wrap = (body, extra = "") =>
  `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ${extra}>${body}</svg>`;

const PATHS = {
  frame: '<path d="M5 5l14 14M19 5L5 19"/><rect x="9" y="9" width="6" height="6" rx="1.2"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>',
  motors: '<circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="3"/><path d="M12 4.5v2.5M12 17v2.5M4.5 12H7M17 12h2.5M6.7 6.7l1.8 1.8M15.5 15.5l1.8 1.8M17.3 6.7l-1.8 1.8M8.5 15.5l-1.8 1.8"/>',
  stack: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 3v3M12 3v3M15 3v3M9 18v3M12 18v3M15 18v3M3 9h3M3 12h3M3 15h3M18 9h3M18 12h3M18 15h3"/>',
  video: '<rect x="3" y="7" width="13" height="10" rx="2.5"/><circle cx="9.5" cy="12" r="3"/><path d="M16 10.5l5-2.5v8l-5-2.5"/><path d="M19 4v3"/>',
  props: '<circle cx="12" cy="12" r="1.8"/><path d="M12 10.2C11 6 12.5 3 14.5 3c1.3 0 1.6 2.4-.8 7.4M13.6 13.1c3.9 1.5 5.6 4.4 4.6 6.1-.7 1.1-2.9.2-6-4.3M10.4 12.6c-3.5 2.4-6.8 2.3-7.7.5-.6-1.2 1.2-2.6 6.7-2.8"/>',
  battery: '<rect x="4" y="6" width="14" height="12" rx="2"/><path d="M18 10h2v4h-2"/><path d="M11.5 8.5l-2.5 4h4l-2.5 3"/>',
  goggles: '<path d="M3 9.5c0-1.4 1.1-2.5 2.5-2.5h13c1.4 0 2.5 1.1 2.5 2.5v4c0 1.4-1.1 2.5-2.5 2.5h-3.2l-1.6-2h-3.4l-1.6 2H5.5C4.1 16 3 14.9 3 13.5z"/><path d="M7 10.5h2.5M14.5 10.5H17"/><path d="M8 7l1-2.5h6L16 7"/>',
  radio: '<rect x="3.5" y="9" width="17" height="11" rx="3"/><circle cx="8.5" cy="14.5" r="2"/><circle cx="15.5" cy="14.5" r="2"/><path d="M8.5 14.5l1-1M15.5 14.5l-1 1M18 9V3.5"/>',
  home: '<path d="M3 11l9-7 9 7"/><path d="M5 9.5V20h14V9.5"/><path d="M10 20v-5h4v5"/>',
  case: '<path d="M3.5 8.5L12 4l8.5 4.5v8L12 21l-8.5-4.5z"/><path d="M3.5 8.5L12 13l8.5-4.5M12 13v8"/>',
  drone: '<rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9.5 9.5L6 6M14.5 9.5L18 6M9.5 14.5L6 18M14.5 14.5L18 18"/><ellipse cx="5.5" cy="5.5" rx="3" ry="1.2"/><ellipse cx="18.5" cy="5.5" rx="3" ry="1.2"/><ellipse cx="5.5" cy="18.5" rx="3" ry="1.2"/><ellipse cx="18.5" cy="18.5" rx="3" ry="1.2"/>',
  gate: '<path d="M4 21V5h16v16"/><path d="M7 21V8h10v13"/><path d="M4 5l3 3M20 5l-3 3"/>',
  flask: '<path d="M9 3h6M10 3v6l-5.5 9.5A1.7 1.7 0 006 21h12a1.7 1.7 0 001.5-2.5L14 9V3"/><path d="M7.5 15h9"/>',
  coin: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5.5"/><path d="M12 9v6M10 10.5h3a1.5 1.5 0 010 3h-2"/>',
  key: '<circle cx="7.5" cy="14.5" r="4"/><path d="M10.5 11.5L20 2M16 6l3 3M14 8l2 2"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 01-8 0z"/><path d="M8 6H4.5a3 3 0 003 4M16 6h3.5a3 3 0 01-3 4M12 13v4M8 21h8M9.5 17h5"/>',
  gift: '<rect x="3.5" y="8" width="17" height="4" rx="1"/><path d="M5 12v8h14v-8M12 8v12"/><path d="M12 8C9 8 7 6.5 8 5s3 0 4 3c1-3 3-4.5 4-3s-1 3-4 3"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.5 3.2-5.5 6.5-5.5s5.9 2 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 010 6.8M18 14.8c2 .7 3.2 2.5 3.5 5.2"/>',
  ticket: '<path d="M3 8.5V6h18v2.5a2.5 2.5 0 000 5V16H3v-2.5a2.5 2.5 0 000-5z"/><path d="M14 6v10" stroke-dasharray="1.5 2"/>',
  wrench: '<path d="M14.5 6.5a4 4 0 00-5.4 5L3.5 17l3.5 3.5 5.6-5.6a4 4 0 005-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bag: '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6a3 3 0 016 0v2"/>',
  shop: '<path d="M4 9l1.5-5h13L20 9"/><path d="M4 9h16v2a3 3 0 01-5.3 1.9A3 3 0 0112 14a3 3 0 01-2.7-1.1A3 3 0 014 11z"/><path d="M5.5 13.5V20h13v-6.5"/>',
  shield: '<path d="M12 3l8 3v5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>',
  ghost: '<path d="M5 20V10a7 7 0 0114 0v10l-2.3-1.5L14.3 20 12 18.5 9.7 20l-2.4-1.5z"/><circle cx="9.5" cy="10.5" r="1"/><circle cx="14.5" cy="10.5" r="1"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  star: '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/>',
  fire: '<path d="M12 21c4 0 7-2.8 7-6.8 0-3.6-2.5-5.6-3.5-8.7-1 2-2 2.8-3 3C12.8 6 11 4 9 3c.5 3.5-4 5.8-4 11.2C5 18.2 8 21 12 21z"/>',
};

export function icon(name, extra = "") {
  return wrap(PATHS[name] || PATHS.case, extra);
}

export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = icon(node.dataset.icon);
  });
}
