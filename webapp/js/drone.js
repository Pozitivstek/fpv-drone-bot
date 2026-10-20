// SVG-дрон сверху: геометрия зависит от класса, цвет каждой детали — от её редкости.
const LAYOUTS = {
  whoop: { dx: 62, dy: 52, prop: 34, duct: true, arm: 9 },
  cine: { dx: 72, dy: 58, prop: 40, duct: true, arm: 10 },
  five: { dx: 90, dy: 72, prop: 44, duct: false, arm: 9 },
  seven: { dx: 106, dy: 82, prop: 54, duct: false, arm: 10 },
};
const EMPTY = "#33445f";
const CX = 160;
const CY = 125;

const color = (part) => (part ? `var(--r-${part.rarity})` : EMPTY);
const dash = (part) => (part ? "" : 'stroke-dasharray="6 6"');

function prop(x, y, radius, part, index) {
  const c = color(part);
  const blade = `M0 0 C ${radius * 0.25} ${-radius * 0.35}, ${radius * 0.75} ${-radius * 0.3}, ${radius} 0 C ${radius * 0.7} ${radius * 0.12}, ${radius * 0.3} ${radius * 0.1}, 0 0`;
  const blades = [0, 120, 240].map((angle) => `<path d="${blade}" transform="rotate(${angle})" fill="${c}" opacity="0.55"/>`).join("");
  const direction = index % 2 ? "reverse" : "normal";
  return `
    <circle cx="${x}" cy="${y}" r="${radius}" fill="${c}" opacity="${part ? 0.1 : 0.04}"/>
    <g transform="translate(${x} ${y})"><g class="prop" style="animation-direction:${direction}">${blades}</g></g>`;
}

export function droneSVG(parts = {}, cls = null, { idle = false } = {}) {
  const layout = LAYOUTS[cls] || LAYOUTS.five;
  const motors = [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([sx, sy]) => [CX + sx * layout.dx, CY + sy * layout.dy]);
  const frame = parts.frame;
  const arms = motors.map(([x, y]) =>
    `<line x1="${CX}" y1="${CY}" x2="${x}" y2="${y}" stroke="${color(frame)}" stroke-width="${layout.arm}" stroke-linecap="round" ${dash(frame)} opacity="0.9"/>`).join("");
  const ducts = layout.duct ? motors.map(([x, y]) =>
    `<circle cx="${x}" cy="${y}" r="${layout.prop + 5}" fill="none" stroke="${color(frame)}" stroke-width="5" ${dash(frame)} opacity="0.8"/>`).join("") : "";
  const props = motors.map(([x, y], i) => prop(x, y, layout.prop, parts.props, i)).join("");
  const motorDots = motors.map(([x, y]) =>
    `<circle cx="${x}" cy="${y}" r="11" fill="#0b1224" stroke="${color(parts.motors)}" stroke-width="3.5" ${dash(parts.motors)}/>
     <circle cx="${x}" cy="${y}" r="3.5" fill="${color(parts.motors)}"/>`).join("");
  const video = parts.video;
  const battery = parts.battery;
  const stack = parts.stack;
  return `
  <svg class="drone-svg ${idle ? "idle" : ""}" viewBox="0 0 320 250" role="img" aria-label="Схема дрона">
    <defs>
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>
    <g filter="url(#glow)">${props}${arms}${ducts}${motorDots}</g>
    <rect x="${CX - 30}" y="${CY - 26}" width="60" height="52" rx="10" fill="#0a1224" stroke="${color(frame)}" stroke-width="3" ${dash(frame)}/>
    <rect x="${CX - 16}" y="${CY - 14}" width="32" height="28" rx="4" fill="none" stroke="${color(stack)}" stroke-width="2.5" ${dash(stack)}/>
    <circle cx="${CX}" cy="${CY}" r="4" fill="${color(stack)}"/>
    <rect x="${CX - 40}" y="${CY - 9}" width="80" height="18" rx="5" fill="${color(battery)}" fill-opacity="${battery ? 0.28 : 0.05}" stroke="${color(battery)}" stroke-width="2.5" ${dash(battery)}/>
    <rect x="${CX - 13}" y="${CY - 46}" width="26" height="20" rx="5" fill="#0a1224" stroke="${color(video)}" stroke-width="3" ${dash(video)}/>
    <circle cx="${CX}" cy="${CY - 38}" r="6" fill="${color(video)}" opacity="${video ? 0.9 : 0.3}" filter="url(#glow)"/>
    <circle cx="${CX - 22}" cy="${CY + 22}" r="2.5" fill="var(--pink)" filter="url(#glow)"/>
    <circle cx="${CX + 22}" cy="${CY + 22}" r="2.5" fill="var(--cyan)" filter="url(#glow)"/>
  </svg>`;
}
